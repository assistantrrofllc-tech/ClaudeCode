"""
Tests for the dashboard routes and receipt image serving.

Covers:
- Dashboard home page rendering
- Receipt image serving (valid file, missing file, path traversal)
- API endpoints (receipts list, receipt detail, stats)
- Receipt image modal data
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_dashboard.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["RECEIPT_STORAGE_PATH"] = "/tmp/test_receipt_images"

import config.settings as _settings
_settings.TWILIO_AUTH_TOKEN = ""
_settings.OPENAI_API_KEY = ""
_settings.RECEIPT_STORAGE_PATH = "/tmp/test_receipt_images"

from src.app import create_app
from src.database.connection import get_db

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"
IMAGE_DIR = Path("/tmp/test_receipt_images")


def setup_test_db():
    """Create a fresh DB with test data."""
    os.environ["DATABASE_PATH"] = TEST_DB
    os.environ["RECEIPT_STORAGE_PATH"] = str(IMAGE_DIR)
    _settings.RECEIPT_STORAGE_PATH = str(IMAGE_DIR)

    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())

    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Omar')")
    db.execute("INSERT INTO projects (id, name) VALUES (1, 'Sparrow')")

    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, vendor_city, vendor_state, purchase_date,
         subtotal, tax, total, payment_method, status, project_id, image_path,
         created_at)
        VALUES (1, 1, 'Ace Home & Supply', 'Kissimmee', 'FL', '2026-02-18',
                94.57, 6.07, 100.64, 'VISA 1234', 'confirmed', 1,
                '/tmp/test_receipt_images/omar_20260218_143052.jpg',
                '2026-02-18 14:30:52')""")

    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, total, status,
         flag_reason, created_at)
        VALUES (2, 1, 'QuikTrip', '2026-02-18', 35.00, 'flagged',
                'Employee rejected OCR read', '2026-02-18 16:00:00')""")

    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (1, 'Utility Lighter', 1, 7.59, 7.59)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (1, 'Propane Exchange', 1, 27.99, 27.99)")

    db.commit()
    db.close()


def get_test_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


# ── Dashboard Home Page ──────────────────────────────────


def test_dashboard_home():
    """Dashboard home page renders with stats and receipts."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"CrewLedger" in resp.data
    assert b"Ace Home" in resp.data or b"Recent" in resp.data


def test_dashboard_stats_api():
    """Stats API returns correct counts."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_receipts"] == 2
    assert data["flagged_count"] == 1
    assert data["confirmed_count"] == 1


# ── Receipt Image Serving ────────────────────────────────


def test_serve_valid_image():
    """Serving a valid receipt image returns 200."""
    setup_test_db()
    # Create a fake image file
    img_path = IMAGE_DIR / "omar_20260218_143052.jpg"
    img_path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)  # Fake JPEG

    client = get_test_client()
    resp = client.get("/receipts/image/omar_20260218_143052.jpg")
    assert resp.status_code == 200


def test_serve_missing_image():
    """Requesting a non-existent image returns 404."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/receipts/image/nonexistent.jpg")
    assert resp.status_code == 404


def test_path_traversal_blocked():
    """Path traversal attempts are blocked."""
    setup_test_db()
    client = get_test_client()

    resp = client.get("/receipts/image/../../../etc/passwd")
    assert resp.status_code == 404

    resp = client.get("/receipts/image/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code == 404


def test_path_with_slashes_blocked():
    """Filenames with slashes are rejected."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/receipts/image/sub/dir/file.jpg")
    assert resp.status_code == 404


# ── Receipt API ──────────────────────────────────────────


def test_api_receipts_list():
    """API returns list of receipts."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2


def test_api_receipts_filter_status():
    """API filters by status."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts?status=flagged")
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["status"] == "flagged"


def test_api_receipt_detail():
    """API returns single receipt with line items."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["vendor_name"] == "Ace Home & Supply"
    assert data["total"] == 100.64
    assert len(data["line_items"]) == 2
    assert data["line_items"][0]["item_name"] == "Utility Lighter"
    assert data["image_url"] == "/receipts/image/omar_20260218_143052.jpg"


def test_api_receipt_detail_not_found():
    """API returns 404 for non-existent receipt."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts/999")
    assert resp.status_code == 404


def test_api_receipts_sort():
    """API sorts by amount."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts?sort=amount&order=asc")
    data = resp.get_json()
    assert data[0]["total"] <= data[1]["total"]


# ── Employee Management API ──────────────────────────────


def test_employees_page():
    """Employee management page renders."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/employees")
    assert resp.status_code == 200
    assert b"Omar" in resp.data
    assert b"Employees" in resp.data


def test_api_employees_list():
    """API returns list of employees."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/employees")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["first_name"] == "Omar"


def test_api_add_employee():
    """API adds a new employee."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/employees", json={
        "first_name": "Carlos",
        "phone_number": "+14075552222",
        "crew": "Mario's Crew",
        "role": "Driver",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "created"

    # Verify in DB
    db = get_db(TEST_DB)
    emp = db.execute("SELECT * FROM employees WHERE phone_number = '+14075552222'").fetchone()
    assert emp is not None
    assert emp["first_name"] == "Carlos"
    assert emp["crew"] == "Mario's Crew"
    db.close()


def test_api_add_employee_duplicate_phone():
    """API rejects duplicate phone number."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/employees", json={
        "first_name": "Duplicate",
        "phone_number": "+14075551111",  # Omar's number
    })
    assert resp.status_code == 409


def test_api_add_employee_missing_fields():
    """API rejects employee with missing required fields."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/employees", json={"first_name": "NoPhone"})
    assert resp.status_code == 400


def test_api_add_employee_phone_normalization():
    """API normalizes phone numbers to E.164 format."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/employees", json={
        "first_name": "Mario",
        "phone_number": "4075553333",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["phone_number"] == "+14075553333"


def test_api_deactivate_employee():
    """API deactivates an employee."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/employees/1/deactivate")
    assert resp.status_code == 200

    db = get_db(TEST_DB)
    emp = db.execute("SELECT * FROM employees WHERE id = 1").fetchone()
    assert emp["is_active"] == 0
    db.close()


def test_api_activate_employee():
    """API reactivates an employee."""
    setup_test_db()
    # First deactivate
    db = get_db(TEST_DB)
    db.execute("UPDATE employees SET is_active = 0 WHERE id = 1")
    db.commit()
    db.close()

    client = get_test_client()
    resp = client.post("/api/employees/1/activate")
    assert resp.status_code == 200

    db = get_db(TEST_DB)
    emp = db.execute("SELECT * FROM employees WHERE id = 1").fetchone()
    assert emp["is_active"] == 1
    db.close()


def test_api_update_employee():
    """API updates employee fields."""
    setup_test_db()
    client = get_test_client()
    resp = client.put("/api/employees/1", json={
        "first_name": "Omar Jr",
        "crew": "Night Shift",
    })
    assert resp.status_code == 200

    db = get_db(TEST_DB)
    emp = db.execute("SELECT * FROM employees WHERE id = 1").fetchone()
    assert emp["first_name"] == "Omar Jr"
    assert emp["crew"] == "Night Shift"
    db.close()


def test_api_employee_detail():
    """API returns single employee (CrewCert QR landing page)."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/employees/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["first_name"] == "Omar"
    assert data["phone_number"] == "+14075551111"
    assert "employee_uuid" in data


def test_api_employee_not_found():
    """API returns 404 for non-existent employee."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/employees/999")
    assert resp.status_code == 404


# ── Ledger Page ──────────────────────────────────────────


def test_ledger_page():
    """Ledger page renders."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/ledger")
    assert resp.status_code == 200
    assert b"Ledger" in resp.data


# ── Export Endpoints ──────────────────────────────────────


def test_export_csv():
    """Export as Google Sheets CSV."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts/export?format=csv")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/csv")
    text = resp.data.decode()
    assert "Date,Employee,Vendor" in text
    assert "Ace Home & Supply" in text
    assert "100.64" in text


def test_export_quickbooks():
    """Export as QuickBooks CSV."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts/export?format=quickbooks")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/csv")
    text = resp.data.decode()
    assert "Vendor" in text
    assert "Materials & Supplies" in text


def test_export_excel():
    """Export as Excel .xlsx."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts/export?format=excel")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.content_type or "xlsx" in (resp.headers.get("Content-Disposition", ""))


def test_export_applies_filters():
    """Export respects status filter."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/receipts/export?format=csv&status=confirmed")
    text = resp.data.decode()
    assert "Ace Home & Supply" in text
    assert "QuikTrip" not in text


# ── Unknown Contacts ─────────────────────────────────────


def test_api_unknown_contacts():
    """API returns unknown contact attempts."""
    setup_test_db()
    db = get_db(TEST_DB)
    db.execute("INSERT INTO unknown_contacts (phone_number, message_body, has_media) VALUES ('+14079999999', 'who is this', 0)")
    db.commit()
    db.close()

    client = get_test_client()
    resp = client.get("/api/unknown-contacts")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["phone_number"] == "+14079999999"


# ── Email Settings ────────────────────────────────────────


def test_settings_page():
    """Settings page renders."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert b"Email Report Settings" in resp.data


def test_api_get_settings():
    """API returns current email settings."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "frequency" in data
    assert data["frequency"] == "weekly"
    assert data["enabled"] == "1"


def test_api_update_settings():
    """API updates email settings."""
    setup_test_db()
    client = get_test_client()
    resp = client.put("/api/settings", json={
        "recipient_email": "kim@roofing.com",
        "frequency": "daily",
        "enabled": "1",
    })
    assert resp.status_code == 200

    # Verify
    resp2 = client.get("/api/settings")
    data = resp2.get_json()
    assert data["recipient_email"] == "kim@roofing.com"
    assert data["frequency"] == "daily"


def test_api_update_settings_rejects_invalid():
    """API ignores unknown setting keys."""
    setup_test_db()
    client = get_test_client()
    resp = client.put("/api/settings", json={
        "recipient_email": "kim@test.com",
        "hacker_field": "evil_value",
    })
    assert resp.status_code == 200

    resp2 = client.get("/api/settings")
    data = resp2.get_json()
    assert data["recipient_email"] == "kim@test.com"
    assert "hacker_field" not in data


def test_api_send_now_no_recipient():
    """Send Now fails if no recipient email."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/settings/send-now")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "recipient" in data["error"].lower() or "email" in data["error"].lower()


if __name__ == "__main__":
    print("Testing dashboard...\n")
    test_dashboard_home()
    print("  PASS: dashboard home")
    test_dashboard_stats_api()
    print("  PASS: stats API")
    test_serve_valid_image()
    print("  PASS: serve valid image")
    test_serve_missing_image()
    print("  PASS: missing image 404")
    test_path_traversal_blocked()
    print("  PASS: path traversal blocked")
    test_path_with_slashes_blocked()
    print("  PASS: slashes blocked")
    test_api_receipts_list()
    print("  PASS: receipts list")
    test_api_receipts_filter_status()
    print("  PASS: receipts filter")
    test_api_receipt_detail()
    print("  PASS: receipt detail")
    test_api_receipt_detail_not_found()
    print("  PASS: receipt not found")
    test_api_receipts_sort()
    print("  PASS: receipts sort")
    test_employees_page()
    print("  PASS: employees page")
    test_api_employees_list()
    print("  PASS: employees list API")
    test_api_add_employee()
    print("  PASS: add employee")
    test_api_add_employee_duplicate_phone()
    print("  PASS: duplicate phone rejected")
    test_api_add_employee_missing_fields()
    print("  PASS: missing fields rejected")
    test_api_add_employee_phone_normalization()
    print("  PASS: phone normalization")
    test_api_deactivate_employee()
    print("  PASS: deactivate employee")
    test_api_activate_employee()
    print("  PASS: activate employee")
    test_api_update_employee()
    print("  PASS: update employee")
    test_api_employee_detail()
    print("  PASS: employee detail")
    test_api_employee_not_found()
    print("  PASS: employee not found")
    test_ledger_page()
    print("  PASS: ledger page")
    test_api_unknown_contacts()
    print("  PASS: unknown contacts API")
    print("\nAll dashboard tests passed!")

    # Cleanup
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
    import shutil
    if IMAGE_DIR.exists():
        shutil.rmtree(IMAGE_DIR)
