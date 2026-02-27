"""
SMS message router.

Takes a parsed incoming message and decides what to do with it based on:
1. Is this a known employee? (lookup by phone number)
2. Do they have a language preference set?
3. What is their current conversation state?
4. What did they send? (photo, YES/NO, text about a missed receipt, etc.)

Returns a reply string to send back via TwiML.
"""

import json
import logging
import os
import re
import secrets

from src.database.connection import get_db
from src.messaging.i18n import msg
from src.services.image_store import download_and_save_image
from src.services.ocr import extract_receipt_data, format_confirmation_message

log = logging.getLogger(__name__)

# Minimum image file size in bytes — below this we warn about quality
_MIN_IMAGE_SIZE = 10 * 1024  # 10KB


def normalize_phone(phone: str) -> str:
    """Normalize a phone number to E.164 format (+1XXXXXXXXXX).

    Handles: +14075551234, 4075551234, 407-555-1234, (407) 555-1234, 1-407-555-1234, etc.
    """
    if not phone:
        return phone
    digits = re.sub(r"[^\d]", "", phone)
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits[0] == "1":
        return "+" + digits
    # Already has +, return as-is if it was valid
    if phone.startswith("+") and len(digits) == 11:
        return "+" + digits
    # Return original with + prefix if we can't normalize
    return phone


def _get_employee_lang(employee) -> str:
    """Get the employee's language preference, defaulting to 'en'."""
    return (employee["language_preference"] or "en") if employee else "en"


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
        lang = _get_employee_lang(employee)

        # --- Check conversation state ---
        convo = _get_conversation_state(db, employee_id)

        # If awaiting language selection
        if convo and convo["state"] == "awaiting_language":
            return _handle_language_selection(db, employee_id, first_name, body)

        # If language_preference is NULL — first contact, ask language
        if employee["language_preference"] is None:
            _set_conversation_state(db, employee_id, "awaiting_language")
            return msg("language_prompt")

        # If awaiting confirmation and they replied YES or NO
        if convo and convo["state"] == "awaiting_confirmation":
            return _handle_confirmation_reply(db, employee_id, first_name, body, convo, lang)

        # If awaiting manual entry details (after replying NO)
        if convo and convo["state"] == "awaiting_manual_entry":
            return _handle_manual_entry(db, employee_id, first_name, body, convo, lang)

        # If awaiting missed receipt details
        if convo and convo["state"] == "awaiting_missed_details":
            return _handle_missed_details(db, employee_id, first_name, body, convo, lang)

        # --- New inbound message (idle state) ---

        # Photo attached → document submission (receipt, invoice, packing slip)
        if media:
            return _handle_document_submission(db, employee_id, first_name, body, media, lang)

        # No photo — check if it's about a missed receipt
        if _is_missed_receipt_message(body):
            return _handle_missed_receipt(db, employee_id, first_name, body, lang)

        # Unrecognized message
        return msg("unrecognized", lang, name=first_name)
    finally:
        db.close()


# ── Language preference ────────────────────────────────────


_ENGLISH_VARIANTS = {"english", "eng", "en", "ingles", "inglés"}
_SPANISH_VARIANTS = {"espanol", "español", "spanish", "esp", "es", "spanish", "spa"}


def _handle_language_selection(db, employee_id: int, first_name: str, body: str) -> str:
    """Process language selection reply. Accept various EN/ES inputs."""
    reply = body.strip().lower()

    if reply in _ENGLISH_VARIANTS:
        db.execute(
            "UPDATE employees SET language_preference = 'en', updated_at = datetime('now') WHERE id = ?",
            (employee_id,),
        )
        db.commit()
        _clear_conversation_state(db, employee_id)
        log.info("Employee %d (%s) selected language: en", employee_id, first_name)
        return msg("welcome", "en", name=first_name)

    if reply in _SPANISH_VARIANTS:
        db.execute(
            "UPDATE employees SET language_preference = 'es', updated_at = datetime('now') WHERE id = ?",
            (employee_id,),
        )
        db.commit()
        _clear_conversation_state(db, employee_id)
        log.info("Employee %d (%s) selected language: es", employee_id, first_name)
        return msg("welcome", "es", name=first_name)

    # Didn't understand — re-prompt
    return msg("language_invalid")


# ── Employee lookup / registration ──────────────────────────


def _lookup_employee(db, phone: str):
    """Find an employee by phone number. Returns Row or None.

    Tries exact match first, then normalized E.164 match.
    """
    normalized = normalize_phone(phone)

    # Exact match (fast path)
    row = db.execute(
        "SELECT * FROM employees WHERE phone_number = ?", (normalized,)
    ).fetchone()
    if row:
        return row

    # Fallback: strip all non-digits from both sides and compare last 10 digits
    phone_digits = re.sub(r"[^\d]", "", phone)[-10:]
    if len(phone_digits) == 10:
        rows = db.execute("SELECT * FROM employees WHERE is_active = 1").fetchall()
        for emp in rows:
            emp_digits = re.sub(r"[^\d]", "", emp["phone_number"] or "")[-10:]
            if emp_digits == phone_digits:
                # Fix the stored number to E.164 for future lookups
                db.execute(
                    "UPDATE employees SET phone_number = ? WHERE id = ?",
                    (normalized, emp["id"]),
                )
                db.commit()
                log.info("Auto-normalized phone for employee %s: %s → %s",
                         emp["first_name"], emp["phone_number"], normalized)
                return emp

    return None


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

    token = secrets.token_urlsafe(12)
    db.execute(
        "INSERT INTO employees (phone_number, first_name, public_token) VALUES (?, ?, ?)",
        (phone, name, token),
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


def _resolve_category_id(db, category_name: str):
    """Resolve a category name (from OCR) to a category_id. Falls back to 'Other'."""
    if not category_name:
        return None
    row = db.execute(
        "SELECT id FROM categories WHERE LOWER(name) = LOWER(?) AND is_active = 1",
        (category_name.strip(),),
    ).fetchone()
    if row:
        return row["id"]
    # Fuzzy fallback — check if the name is close to any category
    from thefuzz import fuzz
    cats = db.execute("SELECT id, name FROM categories WHERE is_active = 1").fetchall()
    best_id, best_score = None, 0
    for c in cats:
        score = fuzz.ratio(category_name.strip().lower(), c["name"].lower())
        if score > best_score:
            best_score = score
            best_id = c["id"]
    if best_score >= 60:
        return best_id
    # Default to "Other"
    other = db.execute("SELECT id FROM categories WHERE name = 'Other'").fetchone()
    return other["id"] if other else None


def _categorize_by_vendor(db, vendor_name: str):
    """Fallback: guess category from vendor name when OCR doesn't suggest one."""
    if not vendor_name:
        return None
    lower = vendor_name.lower()
    # Vendor-to-category mapping per spec
    fuel_vendors = ["gas", "fuel", "shell", "chevron", "bp", "exxon", "mobil", "circle k",
                    "wawa", "racetrac", "speedway", "sunoco", "murphy", "qt", "quiktrip",
                    "lake wales", "citgo", "valero", "marathon"]
    material_vendors = ["home depot", "lowe", "menard", "ace hardware", "84 lumber",
                        "abc supply", "beacon", "srs", "build"]
    food_vendors = ["mcdonald", "burger", "subway", "wendy", "chick-fil", "taco bell",
                    "pizza", "restaurant", "diner", "cafe", "publix", "walmart",
                    "dollar general", "dollar tree", "convenience", "smoke shop"]
    safety_vendors = ["safety", "grainger", "fastenal"]
    lodging_vendors = ["hotel", "motel", "inn", "suites", "lodge", "airbnb", "extended stay"]

    for kw in fuel_vendors:
        if kw in lower:
            return db.execute("SELECT id FROM categories WHERE name = 'Fuel'").fetchone()["id"]
    for kw in material_vendors:
        if kw in lower:
            return db.execute("SELECT id FROM categories WHERE name = 'Materials'").fetchone()["id"]
    for kw in food_vendors:
        if kw in lower:
            return db.execute("SELECT id FROM categories WHERE name = 'Food & Drinks'").fetchone()["id"]
    for kw in safety_vendors:
        if kw in lower:
            return db.execute("SELECT id FROM categories WHERE name = 'Safety Gear'").fetchone()["id"]
    for kw in lodging_vendors:
        if kw in lower:
            return db.execute("SELECT id FROM categories WHERE name = 'Lodging'").fetchone()["id"]
    return None


# ── Document submission (photo received) ─────────────────────


def _handle_document_submission(db, employee_id: int, first_name: str, body: str, media: list, lang: str) -> str:
    """Process a new document submission — classify and route.

    Flow:
    1. Download and save the image
    2. Check image quality
    3. Classify document type (receipt, invoice, packing slip)
    4. Route to appropriate handler
    """
    image_url = media[0]["url"]
    image_path = download_and_save_image(image_url, employee_id, db)

    if not image_path:
        db.execute(
            "INSERT INTO receipts (employee_id, image_path, matched_project_name, status, flag_reason) "
            "VALUES (?, ?, ?, 'flagged', 'Image download failed — Twilio URL saved for retry')",
            (employee_id, image_url, body if body else None),
        )
        db.commit()
        log.error("Image download failed for employee %d, saved Twilio URL: %s", employee_id, image_url)
        return msg("image_download_failed", lang, name=first_name)

    # Image quality check
    quality_warning = ""
    try:
        file_size = os.path.getsize(image_path)
        if file_size < _MIN_IMAGE_SIZE:
            quality_warning = msg("image_quality_warning", lang) + "\n\n"
            log.info("Small image (%d bytes) from employee %d", file_size, employee_id)
    except OSError:
        pass

    # Classify document type
    doc_type = "receipt"  # default
    try:
        from src.services.doc_classifier import classify_document
        result = classify_document(image_path)
        doc_type = result.get("doc_type", "receipt")
        log.info("Document classified as '%s' (confidence: %.2f) for employee %d",
                 doc_type, result.get("confidence", 0), employee_id)
    except ImportError:
        log.debug("doc_classifier not available, defaulting to receipt")
    except Exception as e:
        log.warning("Document classification failed, defaulting to receipt: %s", e)

    # Route by document type
    if doc_type == "invoice" or doc_type == "purchase_order":
        return quality_warning + _handle_invoice_submission(db, employee_id, first_name, body, image_path, lang)
    elif doc_type == "packing_slip":
        return quality_warning + _handle_packing_slip_submission(db, employee_id, first_name, body, image_path, lang)
    else:
        # receipt or unknown — default receipt flow
        return quality_warning + _handle_receipt_submission(db, employee_id, first_name, body, image_path, lang)


def _check_duplicate(db, employee_id: int, vendor_name: str, total: float, purchase_date: str) -> bool:
    """Check if a similar receipt already exists (same vendor + total + date + employee)."""
    if not vendor_name or total is None:
        return False
    row = db.execute(
        """SELECT id FROM receipts
           WHERE employee_id = ? AND vendor_name = ? AND total = ? AND purchase_date = ?
           AND status NOT IN ('deleted', 'duplicate')""",
        (employee_id, vendor_name, total, purchase_date),
    ).fetchone()
    return row is not None


def _handle_receipt_submission(db, employee_id: int, first_name: str, body: str, image_path: str, lang: str) -> str:
    """Process a receipt submission with an already-downloaded image."""
    # Run OCR on the downloaded image
    ocr_data = extract_receipt_data(image_path)

    if not ocr_data:
        cursor = db.execute(
            "INSERT INTO receipts (employee_id, image_path, matched_project_name, status, flag_reason) "
            "VALUES (?, ?, ?, 'flagged', 'OCR processing failed')",
            (employee_id, image_path, body if body else None),
        )
        db.commit()
        log.warning("OCR failed for employee %d, image: %s", employee_id, image_path)
        return msg("ocr_failed", lang, name=first_name)

    # Resolve project
    project_name = body if body else None
    project_id = None
    if project_name:
        project_id = _resolve_project_id(db, project_name)

    # Resolve category
    category_id = _resolve_category_id(db, ocr_data.get("category"))
    if not category_id:
        category_id = _categorize_by_vendor(db, ocr_data.get("vendor_name"))

    # Duplicate detection
    is_dup = _check_duplicate(
        db, employee_id,
        ocr_data.get("vendor_name"),
        ocr_data.get("total"),
        ocr_data.get("purchase_date"),
    )

    status = "pending"
    flag_reason = None
    if is_dup:
        status = "flagged"
        flag_reason = "Possible duplicate — similar receipt already exists"

    cursor = db.execute(
        """INSERT INTO receipts
           (employee_id, image_path, vendor_name, vendor_city, vendor_state,
            purchase_date, subtotal, tax, total, payment_method,
            project_id, matched_project_name, category_id, raw_ocr_json, status, flag_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            category_id,
            json.dumps(ocr_data),
            status,
            flag_reason,
        ),
    )
    receipt_id = cursor.lastrowid

    # Save line items
    for item in ocr_data.get("line_items", []):
        db.execute(
            """INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price)
               VALUES (?, ?, ?, ?, ?)""",
            (
                receipt_id,
                item.get("item_name", "Unknown item"),
                item.get("quantity", 1),
                item.get("unit_price"),
                item.get("extended_price"),
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

    _set_conversation_state(db, employee_id, "idle", receipt_id)

    vendor = ocr_data.get("vendor_name", "unknown vendor")
    total = ocr_data.get("total")
    total_str = f" for ${total:.2f}" if total else ""
    reply = msg("receipt_saved", lang, name=first_name, total_str=total_str, vendor=vendor)

    if is_dup:
        reply += "\n" + msg("duplicate_warning", lang)

    return reply


def _handle_invoice_submission(db, employee_id: int, first_name: str, body: str, image_path: str, lang: str) -> str:
    """Process an invoice submission — extract data and save to invoices table."""
    try:
        from src.services.ocr import extract_invoice_data
        ocr_data = extract_invoice_data(image_path)
    except (ImportError, AttributeError):
        ocr_data = extract_receipt_data(image_path)

    if not ocr_data:
        db.execute(
            "INSERT INTO invoices (employee_id, image_path, status, flag_reason) "
            "VALUES (?, ?, 'flagged', 'OCR processing failed')",
            (employee_id, image_path),
        )
        db.commit()
        return msg("ocr_failed", lang, name=first_name)

    # Move image to invoices storage
    _move_to_doc_storage(image_path, "invoices", body)

    project_id = None
    if body:
        project_id = _resolve_project_id(db, body)

    cursor = db.execute(
        """INSERT INTO invoices
           (employee_id, image_path, vendor_name, vendor_address, invoice_number,
            date, project_id, subtotal, tax, total, payment_method, status, language)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (
            employee_id,
            image_path,
            ocr_data.get("vendor_name"),
            ocr_data.get("vendor_address"),
            ocr_data.get("invoice_number"),
            ocr_data.get("purchase_date") or ocr_data.get("date"),
            project_id,
            ocr_data.get("subtotal"),
            ocr_data.get("tax"),
            ocr_data.get("total"),
            ocr_data.get("payment_method"),
            lang,
        ),
    )
    invoice_id = cursor.lastrowid

    # Save line items
    for item in ocr_data.get("line_items", []):
        db.execute(
            "INSERT INTO invoice_line_items (invoice_id, item_name, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)",
            (invoice_id, item.get("item_name"), item.get("quantity", 1), item.get("unit_price"), item.get("extended_price")),
        )

    db.commit()
    vendor = ocr_data.get("vendor_name", "unknown vendor")
    log.info("Invoice #%d created for employee %d — %s", invoice_id, employee_id, vendor)

    _set_conversation_state(db, employee_id, "idle")
    return msg("invoice_saved", lang, name=first_name, vendor=vendor)


def _handle_packing_slip_submission(db, employee_id: int, first_name: str, body: str, image_path: str, lang: str) -> str:
    """Process a packing slip submission — extract data and save to packing_slips table."""
    try:
        from src.services.ocr import extract_packing_slip_data
        ocr_data = extract_packing_slip_data(image_path)
    except (ImportError, AttributeError):
        ocr_data = extract_receipt_data(image_path)

    if not ocr_data:
        db.execute(
            "INSERT INTO packing_slips (employee_id, image_path, status, flag_reason) "
            "VALUES (?, ?, 'flagged', 'OCR processing failed')",
            (employee_id, image_path),
        )
        db.commit()
        return msg("ocr_failed", lang, name=first_name)

    _move_to_doc_storage(image_path, "packing-slips", body)

    project_id = None
    if body:
        project_id = _resolve_project_id(db, body)

    items = ocr_data.get("line_items", [])
    cursor = db.execute(
        """INSERT INTO packing_slips
           (employee_id, image_path, vendor_name, vendor_address, po_number,
            date, project_id, ship_to_site, item_count, status, language)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (
            employee_id,
            image_path,
            ocr_data.get("vendor_name"),
            ocr_data.get("vendor_address"),
            ocr_data.get("po_number"),
            ocr_data.get("purchase_date") or ocr_data.get("date"),
            project_id,
            ocr_data.get("ship_to_site"),
            len(items),
            lang,
        ),
    )
    slip_id = cursor.lastrowid

    for item in items:
        db.execute(
            "INSERT INTO packing_slip_items (packing_slip_id, item_name, quantity, unit, notes) VALUES (?, ?, ?, ?, ?)",
            (slip_id, item.get("item_name"), item.get("quantity", 1), item.get("unit"), item.get("notes")),
        )

    db.commit()
    vendor = ocr_data.get("vendor_name", "unknown vendor")
    log.info("Packing slip #%d created for employee %d — %s", slip_id, employee_id, vendor)

    _set_conversation_state(db, employee_id, "idle")
    return msg("packing_slip_saved", lang, name=first_name, vendor=vendor)


def _move_to_doc_storage(image_path: str, doc_type: str, project_hint: str = None):
    """Move an image from receipts storage to the appropriate doc type storage.

    Best-effort — if the move fails, the original path remains valid.
    """
    try:
        from config.settings import PROJECT_ROOT
        src_path = os.path.abspath(image_path)
        dest_dir = os.path.join(str(PROJECT_ROOT), "storage", doc_type)
        os.makedirs(dest_dir, exist_ok=True)
        # Image stays in place — path is already stored in DB
        # Future: could physically move for organization
    except Exception:
        pass


# ── Confirmation flow (YES/NO replies) ──────────────────────


def _handle_confirmation_reply(db, employee_id: int, first_name: str, body: str, convo, lang: str) -> str:
    """Handle a YES or NO reply to a receipt confirmation."""
    reply = body.upper().strip()
    receipt_id = convo["receipt_id"]

    if reply in ("YES", "Y", "YEP", "YEAH", "CORRECT", "LOOKS GOOD", "GOOD", "SI", "SÍ"):
        db.execute(
            "UPDATE receipts SET status = 'confirmed', confirmed_at = datetime('now') WHERE id = ?",
            (receipt_id,),
        )
        db.commit()
        _clear_conversation_state(db, employee_id)
        log.info("Receipt #%d confirmed by %s", receipt_id, first_name)
        return msg("confirmed", lang, name=first_name)

    if reply in ("NO", "N", "NOPE", "WRONG", "INCORRECT"):
        db.execute(
            "UPDATE receipts SET status = 'flagged', flag_reason = 'Employee rejected OCR read' WHERE id = ?",
            (receipt_id,),
        )
        db.commit()
        _set_conversation_state(db, employee_id, "awaiting_manual_entry", receipt_id)
        return msg("rejected", lang, name=first_name)

    return msg("confirm_prompt", lang, name=first_name)


# ── Manual entry (after NO reply) ───────────────────────────


def _handle_manual_entry(db, employee_id: int, first_name: str, body: str, convo, lang: str) -> str:
    """Handle manual text entry after employee rejected OCR."""
    receipt_id = convo["receipt_id"]

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

    return msg("manual_entry_saved", lang, name=first_name)


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


def _handle_missed_receipt(db, employee_id: int, first_name: str, body: str, lang: str) -> str:
    """Start the missed receipt flow — collect required fields via text."""
    cursor = db.execute(
        "INSERT INTO receipts (employee_id, is_missed_receipt, status, flag_reason, matched_project_name) "
        "VALUES (?, 1, 'flagged', 'Missed receipt', ?)",
        (employee_id, body),
    )
    receipt_id = cursor.lastrowid
    db.commit()

    _set_conversation_state(db, employee_id, "awaiting_missed_details", receipt_id)

    return msg("missed_receipt_prompt", lang, name=first_name)


def _handle_missed_details(db, employee_id: int, first_name: str, body: str, convo, lang: str) -> str:
    """Capture the missed receipt details from the employee's text."""
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

    return msg("missed_receipt_saved", lang, name=first_name)
