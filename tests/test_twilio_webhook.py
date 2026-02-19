"""
Tests for the Twilio webhook and SMS handler.

Simulates Twilio POST payloads hitting the /webhook/sms endpoint
and verifies the full flow: parsing, routing, DB writes, responses.
"""

import os
import sys
import json
from pathlib import Path
from unittest.mock import patch

# Project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use a test database and disable Twilio signature validation for tests
TEST_DB = "/tmp/test_crewledger_webhook.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""

# Must override the cached settings values BEFORE importing app modules
import config.settings as _settings
_settings.TWILIO_AUTH_TOKEN = ""
_settings.OPENAI_API_KEY = ""

from src.app import create_app
from src.database.connection import get_db

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_test_db():
    """Create a fresh test database."""
    os.environ["DATABASE_PATH"] = TEST_DB
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())
    db.close()


def get_test_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def twilio_post(client, from_number="+14075551234", body="", num_media=0, media_url=None):
    """Simulate a Twilio webhook POST."""
    data = {
        "From": from_number,
        "Body": body,
        "NumMedia": str(num_media),
        "MessageSid": "SM_test_123",
        "To": "+18005551234",
    }
    if num_media > 0 and media_url:
        data["MediaUrl0"] = media_url
        data["MediaContentType0"] = "image/jpeg"
    return client.post("/webhook/sms", data=data)


def test_health_endpoint():
    """Health check works."""
    client = get_test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json["status"] == "ok"
    print("  PASS: health endpoint")


def test_new_employee_no_name():
    """First text from unknown number, no name → ask for name."""
    setup_test_db()
    client = get_test_client()
    resp = twilio_post(client, body="hello")
    assert resp.status_code == 200
    assert b"first time" in resp.data
    assert b"your name" in resp.data.lower() or b"What" in resp.data
    print("  PASS: new employee, no name → asks for name")


def test_new_employee_with_name():
    """First text with intro → auto-registers."""
    setup_test_db()
    client = get_test_client()
    resp = twilio_post(client, body="This is Omar, driver for Mario's crew")
    assert resp.status_code == 200
    assert b"Omar" in resp.data
    assert b"Welcome" in resp.data

    # Verify DB
    db = get_db(TEST_DB)
    emp = db.execute("SELECT * FROM employees WHERE phone_number = '+14075551234'").fetchone()
    assert emp is not None
    assert emp["first_name"] == "Omar"
    db.close()
    print("  PASS: new employee with intro → registered as Omar")


def test_new_employee_just_name():
    """First text is just a name → registers."""
    setup_test_db()
    client = get_test_client()
    resp = twilio_post(client, body="Omar")
    assert resp.status_code == 200
    assert b"Omar" in resp.data

    db = get_db(TEST_DB)
    emp = db.execute("SELECT * FROM employees WHERE phone_number = '+14075551234'").fetchone()
    assert emp["first_name"] == "Omar"
    db.close()
    print("  PASS: new employee, just a name → registered")


def test_receipt_submission_with_photo():
    """Known employee sends a photo → OCR runs, receipt created with data, confirmation sent."""
    setup_test_db()
    db = get_db(TEST_DB)
    db.execute("INSERT INTO employees (phone_number, first_name) VALUES ('+14075551234', 'Omar')")
    db.commit()
    db.close()

    client = get_test_client()

    mock_ocr_data = {
        "vendor_name": "Ace Home & Supply",
        "vendor_city": "Kissimmee",
        "vendor_state": "FL",
        "purchase_date": "2026-02-18",
        "subtotal": 94.57,
        "tax": 6.07,
        "total": 100.64,
        "payment_method": "VISA 1234",
        "line_items": [
            {"item_name": "Utility Lighter", "quantity": 1, "unit_price": 7.59, "extended_price": 7.59},
            {"item_name": "Propane Exchange", "quantity": 1, "unit_price": 27.99, "extended_price": 27.99},
            {"item_name": "20lb Propane Cylinder", "quantity": 1, "unit_price": 59.99, "extended_price": 59.99},
        ],
    }

    # Mock both image download and OCR so we don't hit real APIs
    with patch("src.messaging.sms_handler.download_and_save_image") as mock_dl, \
         patch("src.messaging.sms_handler.extract_receipt_data") as mock_ocr:
        mock_dl.return_value = "storage/receipts/omar_20260218_143052.jpg"
        mock_ocr.return_value = mock_ocr_data
        resp = twilio_post(
            client,
            body="Project Sparrow",
            num_media=1,
            media_url="https://api.twilio.com/fake/media/img123",
        )

    assert resp.status_code == 200
    body = resp.data.decode()
    # TwiML XML-encodes & to &amp; so check both forms
    assert "Ace Home" in body
    assert "Kissimmee FL" in body
    assert "$100.64" in body
    assert "3 items" in body
    assert "Utility Lighter" in body
    assert "Project: Project Sparrow" in body
    assert "Omar" in body
    assert "YES" in body

    # Verify receipt was created with OCR data
    db = get_db(TEST_DB)
    receipt = db.execute("SELECT * FROM receipts WHERE employee_id = 1").fetchone()
    assert receipt is not None
    assert receipt["status"] == "pending"
    assert receipt["vendor_name"] == "Ace Home & Supply"
    assert receipt["vendor_city"] == "Kissimmee"
    assert receipt["total"] == 100.64
    assert receipt["matched_project_name"] == "Project Sparrow"
    assert receipt["raw_ocr_json"] is not None

    # Verify line items were saved
    items = db.execute("SELECT * FROM line_items WHERE receipt_id = ?", (receipt["id"],)).fetchall()
    assert len(items) == 3
    assert items[0]["item_name"] == "Utility Lighter"
    assert items[1]["unit_price"] == 27.99

    # Verify conversation state
    convo = db.execute("SELECT * FROM conversation_state WHERE employee_id = 1").fetchone()
    assert convo["state"] == "awaiting_confirmation"
    assert convo["receipt_id"] == receipt["id"]
    db.close()
    print("  PASS: photo receipt → OCR data saved, confirmation message sent")


def test_receipt_submission_ocr_failure():
    """OCR fails → receipt flagged, user asked to retake photo."""
    setup_test_db()
    db = get_db(TEST_DB)
    db.execute("INSERT INTO employees (phone_number, first_name) VALUES ('+14075551234', 'Omar')")
    db.commit()
    db.close()

    client = get_test_client()

    with patch("src.messaging.sms_handler.download_and_save_image") as mock_dl, \
         patch("src.messaging.sms_handler.extract_receipt_data") as mock_ocr:
        mock_dl.return_value = "storage/receipts/omar_20260218_143052.jpg"
        mock_ocr.return_value = None  # OCR failed
        resp = twilio_post(
            client,
            body="Project Sparrow",
            num_media=1,
            media_url="https://api.twilio.com/fake/media/img123",
        )

    assert resp.status_code == 200
    body = resp.data.decode()
    assert "couldn't read" in body.lower() or "another photo" in body.lower()

    # Receipt still saved as flagged
    db = get_db(TEST_DB)
    receipt = db.execute("SELECT * FROM receipts WHERE employee_id = 1").fetchone()
    assert receipt is not None
    assert receipt["status"] == "flagged"
    assert "OCR" in receipt["flag_reason"]
    db.close()
    print("  PASS: OCR failure → receipt flagged, user asked to retake")


def test_confirmation_yes():
    """Employee replies YES → receipt confirmed."""
    setup_test_db()
    db = get_db(TEST_DB)
    db.execute("INSERT INTO employees (phone_number, first_name) VALUES ('+14075551234', 'Omar')")
    db.execute("INSERT INTO receipts (employee_id, status) VALUES (1, 'pending')")
    db.execute("INSERT INTO conversation_state (employee_id, receipt_id, state) VALUES (1, 1, 'awaiting_confirmation')")
    db.commit()
    db.close()

    client = get_test_client()
    resp = twilio_post(client, body="Yes")
    assert resp.status_code == 200
    assert b"Saved" in resp.data

    db = get_db(TEST_DB)
    receipt = db.execute("SELECT * FROM receipts WHERE id = 1").fetchone()
    assert receipt["status"] == "confirmed"
    assert receipt["confirmed_at"] is not None
    convo = db.execute("SELECT * FROM conversation_state WHERE employee_id = 1").fetchone()
    assert convo["state"] == "idle"
    db.close()
    print("  PASS: YES reply → receipt confirmed")


def test_confirmation_no():
    """Employee replies NO → receipt flagged, asks for correction."""
    setup_test_db()
    db = get_db(TEST_DB)
    db.execute("INSERT INTO employees (phone_number, first_name) VALUES ('+14075551234', 'Omar')")
    db.execute("INSERT INTO receipts (employee_id, status) VALUES (1, 'pending')")
    db.execute("INSERT INTO conversation_state (employee_id, receipt_id, state) VALUES (1, 1, 'awaiting_confirmation')")
    db.commit()
    db.close()

    client = get_test_client()
    resp = twilio_post(client, body="No")
    assert resp.status_code == 200
    assert b"clearer photo" in resp.data or b"details" in resp.data

    db = get_db(TEST_DB)
    receipt = db.execute("SELECT * FROM receipts WHERE id = 1").fetchone()
    assert receipt["status"] == "flagged"
    convo = db.execute("SELECT * FROM conversation_state WHERE employee_id = 1").fetchone()
    assert convo["state"] == "awaiting_manual_entry"
    db.close()
    print("  PASS: NO reply → receipt flagged, awaiting manual entry")


def test_missed_receipt():
    """Employee texts about a missed receipt → starts missed flow."""
    setup_test_db()
    db = get_db(TEST_DB)
    db.execute("INSERT INTO employees (phone_number, first_name) VALUES ('+14075551234', 'Omar')")
    db.commit()
    db.close()

    client = get_test_client()
    resp = twilio_post(client, body="I didn't get a receipt at Home Depot")
    assert resp.status_code == 200
    assert b"Store name" in resp.data or b"log it" in resp.data

    db = get_db(TEST_DB)
    receipt = db.execute("SELECT * FROM receipts WHERE employee_id = 1").fetchone()
    assert receipt is not None
    assert receipt["is_missed_receipt"] == 1
    assert receipt["status"] == "flagged"
    convo = db.execute("SELECT * FROM conversation_state WHERE employee_id = 1").fetchone()
    assert convo["state"] == "awaiting_missed_details"
    db.close()
    print("  PASS: missed receipt → flagged, awaiting details")


def test_missed_receipt_details():
    """Employee provides missed receipt details → saved and idle."""
    setup_test_db()
    db = get_db(TEST_DB)
    db.execute("INSERT INTO employees (phone_number, first_name) VALUES ('+14075551234', 'Omar')")
    db.execute("INSERT INTO receipts (employee_id, is_missed_receipt, status, flag_reason) VALUES (1, 1, 'flagged', 'Missed receipt')")
    db.execute("INSERT INTO conversation_state (employee_id, receipt_id, state) VALUES (1, 1, 'awaiting_missed_details')")
    db.commit()
    db.close()

    client = get_test_client()
    resp = twilio_post(client, body="Home Depot, about $45, roofing nails and caulk, Project Sparrow")
    assert resp.status_code == 200
    assert b"logged" in resp.data

    db = get_db(TEST_DB)
    convo = db.execute("SELECT * FROM conversation_state WHERE employee_id = 1").fetchone()
    assert convo["state"] == "idle"
    db.close()
    print("  PASS: missed receipt details → saved, back to idle")


def test_unrecognized_message():
    """Known employee sends gibberish → helpful hint."""
    setup_test_db()
    db = get_db(TEST_DB)
    db.execute("INSERT INTO employees (phone_number, first_name) VALUES ('+14075551234', 'Omar')")
    db.commit()
    db.close()

    client = get_test_client()
    resp = twilio_post(client, body="what's up")
    assert resp.status_code == 200
    assert b"photo" in resp.data.lower()
    print("  PASS: unrecognized message → helpful hint")


def test_twiml_response_format():
    """Response is valid TwiML XML."""
    setup_test_db()
    client = get_test_client()
    resp = twilio_post(client, body="Hello")
    assert resp.status_code == 200
    assert resp.content_type == "text/xml"
    assert b"<Response>" in resp.data
    assert b"<Message>" in resp.data
    print("  PASS: response is valid TwiML")


if __name__ == "__main__":
    print("Testing Twilio webhook and SMS handler...\n")
    test_health_endpoint()
    test_new_employee_no_name()
    test_new_employee_with_name()
    test_new_employee_just_name()
    test_receipt_submission_with_photo()
    test_receipt_submission_ocr_failure()
    test_confirmation_yes()
    test_confirmation_no()
    test_missed_receipt()
    test_missed_receipt_details()
    test_unrecognized_message()
    test_twiml_response_format()
    print("\nAll tests passed!")

    # Cleanup
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
