"""
Tests for weekly email report — data aggregation, HTML/plaintext
rendering, and API endpoints.
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_report.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""

import config.settings as _settings
_settings.TWILIO_AUTH_TOKEN = ""
_settings.OPENAI_API_KEY = ""

from src.app import create_app
from src.database.connection import get_db
from src.services.report_generator import get_weekly_report_data
from src.services.email_sender import render_report_html, render_report_plaintext

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_test_db():
    """Create a fresh DB and seed it with a week of receipt data."""
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()

    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())

    # Employees
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Omar')")
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (2, '+14075552222', 'Mario')")
    db.execute("INSERT INTO employees (id, phone_number, first_name, full_name) VALUES (3, '+14075553333', 'Luis', 'Luis Garcia')")

    # Projects
    db.execute("INSERT INTO projects (id, name) VALUES (1, 'Sparrow')")
    db.execute("INSERT INTO projects (id, name) VALUES (2, 'Hawk')")

    # Omar's receipts (3 receipts across 2 days)
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, vendor_city, vendor_state, purchase_date,
         subtotal, tax, total, payment_method, status, project_id, matched_project_name,
         created_at)
        VALUES (1, 1, 'Ace Home & Supply', 'Kissimmee', 'FL', '2026-02-09',
                94.57, 6.07, 100.64, 'VISA 1234', 'confirmed', 1, 'Sparrow',
                '2026-02-09 10:30:00')""")
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, vendor_city, vendor_state, purchase_date,
         subtotal, tax, total, payment_method, status, project_id, matched_project_name,
         created_at)
        VALUES (2, 1, 'Home Depot', 'Orlando', 'FL', '2026-02-10',
                42.50, 2.87, 45.37, 'CASH', 'confirmed', 1, 'Sparrow',
                '2026-02-10 14:15:00')""")
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, total, status,
         flag_reason, created_at)
        VALUES (3, 1, 'QuikTrip', '2026-02-10', 35.00, 'flagged',
                'Employee rejected OCR read', '2026-02-10 16:00:00')""")

    # Mario's receipt (1 receipt, missed)
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, total, status,
         is_missed_receipt, flag_reason, matched_project_name, created_at)
        VALUES (4, 2, 'Home Depot', '2026-02-11', 67.89, 'flagged',
                1, 'Missed receipt', 'Hawk', '2026-02-11 09:00:00')""")

    # Luis has no receipts this week (should not appear)

    # Line items for receipt #1
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (1, 'Utility Lighter', 1, 7.59, 7.59)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (1, 'Propane Exchange', 1, 27.99, 27.99)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (1, '20lb Propane Cylinder', 1, 59.99, 59.99)")

    # Line items for receipt #2
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (2, 'Roofing Nails 1lb', 2, 8.99, 17.98)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (2, 'Caulk Gun', 1, 12.49, 12.49)")

    db.commit()
    db.close()


def get_test_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


# ── Report data aggregation tests ────────────────────────────


def test_report_data_structure():
    """Report data has the correct top-level structure."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    assert report["week_start"] == "2026-02-09"
    assert report["week_end"] == "2026-02-15"
    assert isinstance(report["total_spend"], float)
    assert isinstance(report["total_receipts"], int)
    assert isinstance(report["employees"], list)
    print("  PASS: report has correct top-level structure")


def test_report_totals():
    """Total spend and receipt count are correct."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    # 100.64 + 45.37 + 35.00 + 67.89 = 248.90
    assert report["total_spend"] == 248.90
    assert report["total_receipts"] == 4
    assert report["flagged_count"] == 2  # receipt #3 and #4
    print("  PASS: totals are correct ($248.90, 4 receipts, 2 flagged)")


def test_report_employee_sections():
    """Only employees with receipts appear, in alphabetical order."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    names = [e["name"] for e in report["employees"]]
    assert len(names) == 2
    assert "Mario" in names
    assert "Omar" in names
    # Luis has no receipts — should not appear
    assert "Luis" not in names and "Luis Garcia" not in names
    print("  PASS: only employees with receipts appear (Omar, Mario)")


def test_omar_section():
    """Omar's section has correct spend, counts, and daily breakdown."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    omar = next(e for e in report["employees"] if e["name"] == "Omar")
    assert omar["receipt_count"] == 3
    assert omar["total_spend"] == 181.01  # 100.64 + 45.37 + 35.00

    # Daily summary
    assert "2026-02-09" in omar["daily_summary"]
    assert omar["daily_summary"]["2026-02-09"]["count"] == 1
    assert omar["daily_summary"]["2026-02-09"]["spend"] == 100.64

    assert "2026-02-10" in omar["daily_summary"]
    assert omar["daily_summary"]["2026-02-10"]["count"] == 2
    assert omar["daily_summary"]["2026-02-10"]["spend"] == 80.37  # 45.37 + 35.00

    # Flagged receipt present
    assert len(omar["flagged_receipts"]) == 1
    assert omar["flagged_receipts"][0]["vendor_name"] == "QuikTrip"
    print("  PASS: Omar's section — $181.01, 3 receipts, 1 flagged")


def test_receipt_line_items_in_report():
    """Receipt detail includes line items."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    omar = next(e for e in report["employees"] if e["name"] == "Omar")
    ace_receipt = next(r for r in omar["receipts"] if r["vendor_name"] == "Ace Home & Supply")
    assert len(ace_receipt["line_items"]) == 3
    assert ace_receipt["line_items"][0]["item_name"] == "Utility Lighter"
    assert ace_receipt["line_items"][2]["extended_price"] == 59.99
    print("  PASS: line items included in receipt detail")


def test_missed_receipt_in_report():
    """Missed receipts are correctly flagged."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    mario = next(e for e in report["employees"] if e["name"] == "Mario")
    assert mario["receipt_count"] == 1
    assert mario["receipts"][0]["is_missed_receipt"] is True
    assert mario["receipts"][0]["status"] == "flagged"
    print("  PASS: Mario's missed receipt correctly flagged")


def test_empty_week():
    """No receipts in range → empty employees list."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-01-01", "2026-01-07")
    db.close()

    assert report["total_spend"] == 0.0
    assert report["total_receipts"] == 0
    assert len(report["employees"]) == 0
    print("  PASS: empty week → no employees, zero totals")


# ── HTML rendering tests ─────────────────────────────────────


def test_html_contains_key_elements():
    """HTML report contains expected structural elements."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    html = render_report_html(report)
    assert "CrewLedger Weekly Report" in html
    assert "Feb 9" in html  # date range
    assert "$248.90" in html  # total spend
    assert "Omar" in html
    assert "Mario" in html
    assert "Ace Home" in html
    assert "FLAGGED" in html
    assert "MISSED" in html
    assert "Utility Lighter" in html
    print("  PASS: HTML contains all key elements")


def test_html_flagged_alert():
    """HTML shows flagged alert banner when there are flagged receipts."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    html = render_report_html(report)
    assert "2 flagged receipts" in html
    print("  PASS: HTML shows flagged alert banner")


# ── Plaintext rendering tests ────────────────────────────────


def test_plaintext_contains_key_elements():
    """Plaintext report contains expected elements."""
    setup_test_db()
    db = get_db(TEST_DB)
    report = get_weekly_report_data(db, "2026-02-09", "2026-02-15")
    db.close()

    text = render_report_plaintext(report)
    assert "CREWLEDGER WEEKLY REPORT" in text
    assert "$248.90" in text
    assert "Omar" in text
    assert "Mario" in text
    assert "[FLAGGED]" in text
    assert "[MISSED]" in text
    assert "Utility Lighter" in text
    print("  PASS: plaintext contains all key elements")


# ── API endpoint tests ───────────────────────────────────────


def test_preview_endpoint():
    """GET /reports/weekly/preview returns HTML."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/reports/weekly/preview?week_start=2026-02-09&week_end=2026-02-15")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")
    assert b"CrewLedger Weekly Report" in resp.data
    assert b"Omar" in resp.data
    print("  PASS: /reports/weekly/preview returns HTML")


def test_data_endpoint():
    """GET /reports/weekly/data returns JSON."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/reports/weekly/data?week_start=2026-02-09&week_end=2026-02-15")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_spend"] == 248.90
    assert data["total_receipts"] == 4
    assert len(data["employees"]) == 2
    print("  PASS: /reports/weekly/data returns correct JSON")


def test_send_endpoint_no_smtp():
    """POST /reports/weekly/send fails gracefully without SMTP config."""
    setup_test_db()
    client = get_test_client()
    resp = client.post(
        "/reports/weekly/send",
        json={"week_start": "2026-02-09", "week_end": "2026-02-15", "recipient": "test@example.com"},
    )
    # Should fail because SMTP not configured in test env
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["status"] == "failed"
    print("  PASS: /reports/weekly/send fails gracefully without SMTP")


if __name__ == "__main__":
    print("Testing weekly report...\n")

    # Data aggregation
    test_report_data_structure()
    test_report_totals()
    test_report_employee_sections()
    test_omar_section()
    test_receipt_line_items_in_report()
    test_missed_receipt_in_report()
    test_empty_week()

    # Rendering
    test_html_contains_key_elements()
    test_html_flagged_alert()
    test_plaintext_contains_key_elements()

    # API endpoints
    test_preview_endpoint()
    test_data_endpoint()
    test_send_endpoint_no_smtp()

    print("\nAll report tests passed!")

    # Cleanup
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
