"""
Tests for SMS flow enhancements.

Covers:
- Image quality warning for small files
- Duplicate detection
- Document classification routing
- Pending receipt handling
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_smsflow.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["RECEIPT_STORAGE_PATH"] = "/tmp/test_receipt_images"

import config.settings as _settings
_settings.TWILIO_AUTH_TOKEN = ""
_settings.OPENAI_API_KEY = "test-key"
_settings.RECEIPT_STORAGE_PATH = "/tmp/test_receipt_images"

from src.database.connection import get_db
from src.messaging.sms_handler import (
    _check_duplicate, _handle_receipt_submission, _MIN_IMAGE_SIZE,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"
IMAGE_DIR = Path("/tmp/test_receipt_images")


def setup_function():
    """Create a fresh DB with test data."""
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())
    db.execute(
        "INSERT INTO employees (id, phone_number, first_name, is_active, language_preference) "
        "VALUES (1, '+14075551111', 'Omar', 1, 'en')"
    )
    db.execute("INSERT INTO projects (id, name) VALUES (1, 'Sparrow')")
    db.commit()
    db.close()


def teardown_function():
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()


# ── Duplicate Detection ──────────────────────────────

def test_duplicate_detection_finds_exact_match():
    """Duplicate detection should find matching vendor + total + date + employee."""
    db = get_db(TEST_DB)
    db.execute(
        "INSERT INTO receipts (employee_id, vendor_name, total, purchase_date, status) "
        "VALUES (1, 'Home Depot', 45.37, '2026-02-10', 'confirmed')"
    )
    db.commit()

    result = _check_duplicate(db, 1, "Home Depot", 45.37, "2026-02-10")
    assert result is True
    db.close()


def test_duplicate_detection_no_false_positive_different_vendor():
    """Different vendor should not be flagged as duplicate."""
    db = get_db(TEST_DB)
    db.execute(
        "INSERT INTO receipts (employee_id, vendor_name, total, purchase_date, status) "
        "VALUES (1, 'Home Depot', 45.37, '2026-02-10', 'confirmed')"
    )
    db.commit()

    result = _check_duplicate(db, 1, "Lowes", 45.37, "2026-02-10")
    assert result is False
    db.close()


def test_duplicate_detection_no_false_positive_different_total():
    """Different total should not be flagged as duplicate."""
    db = get_db(TEST_DB)
    db.execute(
        "INSERT INTO receipts (employee_id, vendor_name, total, purchase_date, status) "
        "VALUES (1, 'Home Depot', 45.37, '2026-02-10', 'confirmed')"
    )
    db.commit()

    result = _check_duplicate(db, 1, "Home Depot", 99.99, "2026-02-10")
    assert result is False
    db.close()


def test_duplicate_detection_no_false_positive_different_date():
    """Different date should not be flagged as duplicate."""
    db = get_db(TEST_DB)
    db.execute(
        "INSERT INTO receipts (employee_id, vendor_name, total, purchase_date, status) "
        "VALUES (1, 'Home Depot', 45.37, '2026-02-10', 'confirmed')"
    )
    db.commit()

    result = _check_duplicate(db, 1, "Home Depot", 45.37, "2026-02-11")
    assert result is False
    db.close()


def test_duplicate_detection_ignores_deleted():
    """Deleted receipts should not trigger duplicate detection."""
    db = get_db(TEST_DB)
    db.execute(
        "INSERT INTO receipts (employee_id, vendor_name, total, purchase_date, status) "
        "VALUES (1, 'Home Depot', 45.37, '2026-02-10', 'deleted')"
    )
    db.commit()

    result = _check_duplicate(db, 1, "Home Depot", 45.37, "2026-02-10")
    assert result is False
    db.close()


def test_duplicate_detection_handles_none_values():
    """Duplicate detection should handle None vendor/total gracefully."""
    db = get_db(TEST_DB)
    result = _check_duplicate(db, 1, None, None, "2026-02-10")
    assert result is False
    db.close()


# ── Image Quality ────────────────────────────────────

def test_min_image_size_threshold():
    """Verify the minimum image size threshold is 10KB."""
    assert _MIN_IMAGE_SIZE == 10 * 1024


# ── Receipt Submission with Duplicate ────────────────

@patch("src.messaging.sms_handler.extract_receipt_data")
def test_receipt_submission_flags_duplicate(mock_ocr):
    """When a duplicate is found, receipt should be saved but flagged."""
    mock_ocr.return_value = {
        "vendor_name": "Home Depot",
        "total": 45.37,
        "purchase_date": "2026-02-10",
        "line_items": [],
    }

    db = get_db(TEST_DB)
    # Create existing receipt
    db.execute(
        "INSERT INTO receipts (employee_id, vendor_name, total, purchase_date, status) "
        "VALUES (1, 'Home Depot', 45.37, '2026-02-10', 'confirmed')"
    )
    db.commit()

    # Create test image
    test_img = str(IMAGE_DIR / "test_dup.jpg")
    Path(test_img).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 500)

    result = _handle_receipt_submission(db, 1, "Omar", "Sparrow", test_img, "en")

    # Should contain duplicate warning
    assert "similar" in result.lower() or "duplicate" in result.lower()

    # Receipt should be saved with flagged status
    row = db.execute(
        "SELECT status, flag_reason FROM receipts WHERE vendor_name = 'Home Depot' AND status = 'flagged'"
    ).fetchone()
    assert row is not None
    assert "duplicate" in row["flag_reason"].lower()

    db.close()
    Path(test_img).unlink(missing_ok=True)
