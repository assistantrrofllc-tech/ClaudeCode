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
from src.services.ocr import extract_receipt_data, format_confirmation_message

log = logging.getLogger(__name__)


def handle_incoming_message(parsed: dict) -> str | None:
    """Route an incoming SMS/MMS and return the reply text.

    Returns None for unknown numbers — no response sent (whitelist security).
    """
    phone = parsed["from_number"]
    body = parsed["body"]
    media = parsed["media"]

    db = get_db()
    try:
        employee = _lookup_employee(db, phone)

        # --- Unknown number: silence + flag ---
        if employee is None:
            _log_unknown_contact(db, phone, body, bool(media))
            return None

        # --- Inactive employee: silence ---
        if not employee["is_active"]:
            log.info("Inactive employee %s (%s) attempted contact", employee["first_name"], phone)
            return None

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


def _log_unknown_contact(db, phone: str, body: str, has_media: bool):
    """Log an SMS attempt from an unregistered phone number.

    No response is sent — complete silence. The attempt is flagged
    in the dashboard review queue for management to see.
    """
    db.execute(
        "INSERT INTO unknown_contacts (phone_number, message_body, has_media) VALUES (?, ?, ?)",
        (phone, body[:500] if body else None, int(has_media)),
    )
    db.commit()
    log.warning("Unknown number %s attempted contact — silenced and flagged", phone)


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


def _resolve_project_id(db, project_name: str):
    """Resolve a project name to a project_id using exact then fuzzy match."""
    from thefuzz import fuzz

    # Exact match first
    row = db.execute(
        "SELECT id FROM projects WHERE LOWER(name) = LOWER(?) AND status = 'active'",
        (project_name.strip(),),
    ).fetchone()
    if row:
        return row["id"]

    # Fuzzy match against active projects
    projects = db.execute("SELECT id, name FROM projects WHERE status = 'active'").fetchall()
    best_id, best_score = None, 0
    for p in projects:
        score = fuzz.ratio(project_name.strip().lower(), p["name"].lower())
        if score > best_score:
            best_score = score
            best_id = p["id"]

    if best_score >= 70:
        return best_id
    return None


_CATEGORY_KEYWORDS = {
    1: ["shingle", "underlayment", "flashing", "ridge cap", "drip edge", "osb", "roofing",
        "tarp", "plywood", "lumber", "deck", "siding", "drywall", "insulation", "cement",
        "concrete", "mortar", "stucco", "tile", "board"],
    2: ["tool", "drill", "saw", "ladder", "grinder", "compressor", "nailer", "gun",
        "sander", "level", "rental", "blade", "bit", "wrench", "hammer", "plier"],
    3: ["nail", "screw", "bolt", "anchor", "bracket", "fastener", "hinge", "latch",
        "nut", "washer", "rivet", "staple", "clip"],
    4: ["hard hat", "helmet", "glove", "harness", "safety", "vest", "glasses", "ppe",
        "respirator", "ear plug", "first aid", "mask", "goggles"],
    5: ["fuel", "gas", "diesel", "propane", "unleaded", "petroleum", "oil change"],
    6: ["office", "permit", "paper", "print", "pen", "marker", "binder", "folder",
        "stamp", "envelope", "shipping"],
    7: ["rag", "water", "tape", "caulk", "adhesive", "silicone", "sealant", "glue",
        "paint", "primer", "brush", "roller", "thinner", "cleaner", "solvent",
        "gatorade", "drink", "snack", "ice", "food", "cup", "towel", "bag"],
}


def _categorize_item(db, item_name: str):
    """Match an item name to a category using keyword lookup."""
    lower = item_name.lower()
    for cat_id, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return cat_id
    return 6  # Default to Office & Misc


# ── Receipt submission (photo received) ─────────────────────


def _handle_receipt_submission(db, employee_id: int, first_name: str, body: str, media: list) -> str:
    """Process a new receipt submission — photo + optional project name.

    Flow:
    1. Download and save the image
    2. Send image to GPT-4o-mini Vision for OCR
    3. Format confirmation message from OCR data
    4. Send confirmation, await YES/NO reply
    """
    # Download the first image (receipts are one photo per text)
    image_url = media[0]["url"]
    image_path = download_and_save_image(image_url, employee_id, db)

    if not image_path:
        return (
            f"Sorry {first_name}, I had trouble downloading that image. "
            "Could you try sending it again?"
        )

    # Run OCR on the downloaded image
    ocr_data = extract_receipt_data(image_path)

    if not ocr_data:
        # OCR failed — save the receipt as flagged so it's not lost
        cursor = db.execute(
            "INSERT INTO receipts (employee_id, image_path, matched_project_name, status, flag_reason) "
            "VALUES (?, ?, ?, 'flagged', 'OCR processing failed')",
            (employee_id, image_path, body if body else None),
        )
        db.commit()
        log.warning("OCR failed for employee %d, image: %s", employee_id, image_path)
        return (
            f"Sorry {first_name}, I couldn't read that receipt clearly. "
            "Could you try taking another photo with better lighting? "
            "Make sure the whole receipt is visible and flat."
        )

    # Create the receipt record with OCR data
    project_name = body if body else None

    # Resolve project name to project_id via fuzzy match
    project_id = None
    if project_name:
        project_id = _resolve_project_id(db, project_name)

    cursor = db.execute(
        """INSERT INTO receipts
           (employee_id, image_path, vendor_name, vendor_city, vendor_state,
            purchase_date, subtotal, tax, total, payment_method,
            project_id, matched_project_name, raw_ocr_json, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (
            employee_id,
            image_path,
            ocr_data.get("vendor_name"),
            ocr_data.get("vendor_city"),
            ocr_data.get("vendor_state"),
            ocr_data.get("purchase_date"),
            ocr_data.get("subtotal"),
            ocr_data.get("tax"),
            ocr_data.get("total"),
            ocr_data.get("payment_method"),
            project_id,
            project_name,
            json.dumps(ocr_data),
        ),
    )
    receipt_id = cursor.lastrowid

    # Save line items with auto-categorization
    for item in ocr_data.get("line_items", []):
        item_name = item.get("item_name", "Unknown item")
        category_id = _categorize_item(db, item_name)
        db.execute(
            """INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price, category_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                receipt_id,
                item_name,
                item.get("quantity", 1),
                item.get("unit_price"),
                item.get("extended_price"),
                category_id,
            ),
        )

    db.commit()
    log.info(
        "Receipt #%d created for employee %d — %s $%.2f, %d items",
        receipt_id, employee_id,
        ocr_data.get("vendor_name", "?"),
        ocr_data.get("total") or 0,
        len(ocr_data.get("line_items", [])),
    )

    # Set conversation state to awaiting confirmation
    _set_conversation_state(db, employee_id, "awaiting_confirmation", receipt_id)

    # Format the confirmation message from OCR data
    return format_confirmation_message(ocr_data, first_name, project_name)


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
