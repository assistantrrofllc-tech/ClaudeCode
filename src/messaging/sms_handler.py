"""
SMS message router.

Takes a parsed incoming message and decides what to do with it based on:
1. Is this a known employee? (lookup by phone number)
2. What is their current conversation state?
3. What did they send? (photo, YES/NO, text about a missed receipt, etc.)

Returns a reply string to send back via TwiML.

Steps 3-10 will plug into the hooks left here (OCR, confirmation,
project matching, categorization, etc.)
"""

import json
import logging
import re

from src.database.connection import get_db
from src.services.image_store import download_and_save_image

log = logging.getLogger(__name__)


def handle_incoming_message(parsed: dict) -> str:
    """Route an incoming SMS/MMS and return the reply text."""
    phone = parsed["from_number"]
    body = parsed["body"]
    media = parsed["media"]

    db = get_db()
    try:
        employee = _lookup_employee(db, phone)

        # --- New employee: auto-register ---
        if employee is None:
            return _handle_new_employee(db, phone, body, media)

        first_name = employee["first_name"]
        employee_id = employee["id"]

        # --- Check conversation state ---
        convo = _get_conversation_state(db, employee_id)

        # If awaiting confirmation and they replied YES or NO
        if convo and convo["state"] == "awaiting_confirmation":
            return _handle_confirmation_reply(db, employee_id, first_name, body, convo)

        # If awaiting manual entry details (after replying NO)
        if convo and convo["state"] == "awaiting_manual_entry":
            return _handle_manual_entry(db, employee_id, first_name, body, convo)

        # If awaiting missed receipt details
        if convo and convo["state"] == "awaiting_missed_details":
            return _handle_missed_details(db, employee_id, first_name, body, convo)

        # --- New inbound message (idle state) ---

        # Photo attached → receipt submission
        if media:
            return _handle_receipt_submission(db, employee_id, first_name, body, media)

        # No photo — check if it's about a missed receipt
        if _is_missed_receipt_message(body):
            return _handle_missed_receipt(db, employee_id, first_name, body)

        # Unrecognized message
        return (
            f"Hey {first_name}, I didn't quite get that. "
            "To submit a receipt, text me a photo with the project name. "
            "Example: [photo] Project Sparrow"
        )
    finally:
        db.close()


# ── Employee lookup / registration ──────────────────────────


def _lookup_employee(db, phone: str):
    """Find an employee by phone number. Returns Row or None."""
    return db.execute(
        "SELECT * FROM employees WHERE phone_number = ?", (phone,)
    ).fetchone()


def _handle_new_employee(db, phone: str, body: str, media: list) -> str:
    """Auto-register a new employee from their first message.

    Tries to extract a name from the message body. If no name is found,
    asks them to introduce themselves.

    Full implementation in Step 7 — for now, does basic name extraction.
    """
    name = _extract_name_from_intro(body)
    if not name:
        return (
            "Hey! Looks like this is your first time texting CrewLedger. "
            "What's your name? Just reply with your first name and "
            "I'll get you set up."
        )

    db.execute(
        "INSERT INTO employees (phone_number, first_name) VALUES (?, ?)",
        (phone, name),
    )
    db.commit()
    log.info("New employee registered: %s (%s)", name, phone)

    employee = _lookup_employee(db, phone)

    # If they also sent a photo with their intro, process the receipt
    if media:
        return (
            f"Welcome to CrewLedger, {name}! You're all set. "
            "Let me process that receipt now..."
        )
        # Step 3 will add OCR processing here

    return (
        f"Welcome to CrewLedger, {name}! You're all set. "
        "Send me a photo of a receipt with the project name to get started. "
        "Example: [photo] Project Sparrow"
    )


def _extract_name_from_intro(body: str) -> str | None:
    """Try to pull a first name out of an intro message.

    Handles patterns like:
        "This is Omar"
        "Hey this is Omar, driver for Mario's crew"
        "Omar here"
        "My name is Omar"
        Just "Omar" (single word)
    """
    if not body:
        return None

    patterns = [
        r"(?:this is|my name is|i'm|im|i am)\s+([A-Z][a-z]+)",
        r"^([A-Z][a-z]+)\s+here\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(1).capitalize()

    # If it's just a single word that looks like a name (not a common word)
    stripped = body.strip()
    _NOT_NAMES = {
        "hello", "hi", "hey", "yo", "sup", "help", "yes", "no", "yep",
        "nope", "ok", "okay", "thanks", "thank", "please", "stop",
        "start", "test", "receipt", "photo", "what", "who", "where",
        "when", "how", "why", "the", "and", "but",
    }
    if re.match(r"^[A-Za-z]{2,20}$", stripped) and stripped.lower() not in _NOT_NAMES:
        return stripped.capitalize()

    return None


# ── Conversation state management ───────────────────────────


def _get_conversation_state(db, employee_id: int):
    """Get the current conversation state for an employee."""
    return db.execute(
        "SELECT * FROM conversation_state WHERE employee_id = ? ORDER BY updated_at DESC LIMIT 1",
        (employee_id,),
    ).fetchone()


def _set_conversation_state(db, employee_id: int, state: str, receipt_id: int = None, context: dict = None):
    """Upsert the conversation state for an employee."""
    existing = _get_conversation_state(db, employee_id)
    context_json = json.dumps(context) if context else None

    if existing:
        db.execute(
            "UPDATE conversation_state SET state = ?, receipt_id = ?, context_json = ?, updated_at = datetime('now') WHERE id = ?",
            (state, receipt_id, context_json, existing["id"]),
        )
    else:
        db.execute(
            "INSERT INTO conversation_state (employee_id, state, receipt_id, context_json) VALUES (?, ?, ?, ?)",
            (employee_id, state, receipt_id, context_json),
        )
    db.commit()


def _clear_conversation_state(db, employee_id: int):
    """Reset employee back to idle."""
    _set_conversation_state(db, employee_id, "idle")


# ── Receipt submission (photo received) ─────────────────────


def _handle_receipt_submission(db, employee_id: int, first_name: str, body: str, media: list) -> str:
    """Process a new receipt submission — photo + optional project name.

    Flow:
    1. Download and save the image          (this step)
    2. Send image to GPT-4o-mini for OCR    (Step 3)
    3. Format confirmation via Ollama        (Step 4)
    4. Send confirmation, await YES/NO       (Step 5)
    """
    # Download the first image (receipts are one photo per text)
    image_url = media[0]["url"]
    image_path = download_and_save_image(image_url, employee_id, db)

    if not image_path:
        return (
            f"Sorry {first_name}, I had trouble downloading that image. "
            "Could you try sending it again?"
        )

    # Create a pending receipt record
    cursor = db.execute(
        "INSERT INTO receipts (employee_id, image_path, matched_project_name, status) VALUES (?, ?, ?, 'pending')",
        (employee_id, image_path, body if body else None),
    )
    receipt_id = cursor.lastrowid
    db.commit()

    log.info("Receipt #%d created for employee %d, image: %s", receipt_id, employee_id, image_path)

    # Set conversation state to awaiting confirmation
    # Steps 3-4 will process OCR and format the confirmation before this reply
    _set_conversation_state(db, employee_id, "awaiting_confirmation", receipt_id)

    # Placeholder — Steps 3+4 will replace this with actual OCR confirmation
    return (
        f"Got it, {first_name}! I received your receipt photo. "
        "Processing it now — I'll send you the details to confirm shortly."
    )


# ── Confirmation flow (YES/NO replies) ──────────────────────


def _handle_confirmation_reply(db, employee_id: int, first_name: str, body: str, convo) -> str:
    """Handle a YES or NO reply to a receipt confirmation.

    YES → confirm and save (Step 6)
    NO  → ask for correction or retake (Step 5 fallback)
    """
    reply = body.upper().strip()
    receipt_id = convo["receipt_id"]

    if reply in ("YES", "Y", "YEP", "YEAH", "CORRECT", "LOOKS GOOD", "GOOD"):
        # Confirm the receipt
        db.execute(
            "UPDATE receipts SET status = 'confirmed', confirmed_at = datetime('now') WHERE id = ?",
            (receipt_id,),
        )
        db.commit()
        _clear_conversation_state(db, employee_id)
        log.info("Receipt #%d confirmed by %s", receipt_id, first_name)
        return f"Saved! Thanks, {first_name}."

    if reply in ("NO", "N", "NOPE", "WRONG", "INCORRECT"):
        # Flag for review, ask for correction
        db.execute(
            "UPDATE receipts SET status = 'flagged', flag_reason = 'Employee rejected OCR read' WHERE id = ?",
            (receipt_id,),
        )
        db.commit()
        _set_conversation_state(db, employee_id, "awaiting_manual_entry", receipt_id)
        return (
            f"No problem, {first_name}. You can:\n"
            "1. Send a clearer photo of the receipt\n"
            "2. Text me the details: vendor, amount, date, and project name\n\n"
            "What would you like to do?"
        )

    # Didn't understand the reply
    return (
        f"{first_name}, just reply YES to save or NO if something looks wrong."
    )


# ── Manual entry (after NO reply) ───────────────────────────


def _handle_manual_entry(db, employee_id: int, first_name: str, body: str, convo) -> str:
    """Handle manual text entry after employee rejected OCR.

    Step 5 will fully implement parsing the manual details.
    For now, flag and acknowledge.
    """
    receipt_id = convo["receipt_id"]

    # Check if they sent a new photo instead
    # (media check happens upstream — if we're here, it's text only)

    # Store the manual text in the context for later processing
    _set_conversation_state(
        db, employee_id, "idle", receipt_id,
        context={"manual_entry_text": body},
    )

    db.execute(
        "UPDATE receipts SET flag_reason = 'Manual entry — needs review', status = 'flagged' WHERE id = ?",
        (receipt_id,),
    )
    db.commit()
    log.info("Receipt #%d manual entry from %s: %s", receipt_id, first_name, body[:100])

    return (
        f"Got it, {first_name}. I've saved your notes and flagged this receipt "
        "for management review. Thanks!"
    )


# ── Missed receipt flow ─────────────────────────────────────


_MISSED_RECEIPT_PATTERNS = [
    r"didn'?t get a receipt",
    r"no receipt",
    r"lost.{0,10}receipt",
    r"forgot.{0,10}receipt",
    r"never got.{0,10}receipt",
]


def _is_missed_receipt_message(body: str) -> bool:
    """Detect if the message is about not having a receipt."""
    lower = body.lower()
    return any(re.search(p, lower) for p in _MISSED_RECEIPT_PATTERNS)


def _handle_missed_receipt(db, employee_id: int, first_name: str, body: str) -> str:
    """Start the missed receipt flow — collect required fields via text."""
    cursor = db.execute(
        "INSERT INTO receipts (employee_id, is_missed_receipt, status, flag_reason, matched_project_name) "
        "VALUES (?, 1, 'flagged', 'Missed receipt', ?)",
        (employee_id, body),
    )
    receipt_id = cursor.lastrowid
    db.commit()

    _set_conversation_state(db, employee_id, "awaiting_missed_details", receipt_id)

    return (
        f"No worries, {first_name}. Let's log it anyway.\n"
        "Please text me:\n"
        "- Store name\n"
        "- Approximate amount\n"
        "- What you bought\n"
        "- Project name\n\n"
        "Example: Home Depot, about $45, roofing nails and caulk, Project Sparrow"
    )


def _handle_missed_details(db, employee_id: int, first_name: str, body: str, convo) -> str:
    """Capture the missed receipt details from the employee's text.

    Full parsing in later steps — for now, store the raw text and flag.
    """
    receipt_id = convo["receipt_id"]

    _set_conversation_state(
        db, employee_id, "idle", receipt_id,
        context={"missed_details_text": body},
    )

    db.execute(
        "UPDATE receipts SET flag_reason = 'Missed receipt — details provided' WHERE id = ?",
        (receipt_id,),
    )
    db.commit()
    log.info("Missed receipt #%d details from %s: %s", receipt_id, first_name, body[:100])

    return (
        f"Got it, {first_name}. I've logged this as a missed receipt. "
        "It'll be reviewed at end of week. Thanks for letting us know!"
    )
