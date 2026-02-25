"""
Tests for the QuickBooks CSV export endpoint.

Verifies CSV format, column mapping, filtering, date formatting,
and response headers match QuickBooks import requirements.
"""

import csv
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_export.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""

import config.settings as _settings
_settings.TWILIO_AUTH_TOKEN = ""
_settings.OPENAI_API_KEY = ""

from src.app import create_app
from src.database.connection import get_db

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_test_db():
    """Create a fresh DB and seed with receipt data for export tests."""
    os.environ["DATABASE_PATH"] = TEST_DB
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()

    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())

    # Employees
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Omar')")
    db.execute("INSERT INTO employees (id, phone_number, first_name, full_name) VALUES (2, '+14075552222', 'Mario', 'Mario Gonzalez')")

    # Projects
    db.execute("INSERT INTO projects (id, name) VALUES (1, 'Sparrow')")
    db.execute("INSERT INTO projects (id, name) VALUES (2, 'Hawk')")

    # Categories (seeded by schema, IDs by insertion order):
    # 1=Materials, 2=Fuel, 3=Food & Drinks, 4=Tools & Equipment,
    # 5=Safety Gear, 6=Office & Admin, 7=Lodging, 8=Other

    # Receipt 1: Omar, confirmed, full data, Project Sparrow
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, vendor_city, vendor_state, purchase_date,
         subtotal, tax, total, payment_method, status, project_id, matched_project_name,
         created_at)
        VALUES (1, 1, 'Ace Home & Supply', 'Kissimmee', 'FL', '2026-02-09',
                94.57, 6.07, 100.64, 'Mastercard ending 7718', 'confirmed', 1, 'Sparrow',
                '2026-02-09 10:30:00')""")

    # Receipt 2: Omar, confirmed, Project Sparrow
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, vendor_city, vendor_state, purchase_date,
         subtotal, tax, total, payment_method, status, project_id, matched_project_name,
         created_at)
        VALUES (2, 1, 'Home Depot', 'Orlando', 'FL', '2026-02-10',
                42.50, 2.87, 45.37, 'CASH', 'confirmed', 1, 'Sparrow',
                '2026-02-10 14:15:00')""")

    # Receipt 3: Omar, flagged (should NOT appear in export)
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, total, status,
         flag_reason, created_at)
        VALUES (3, 1, 'QuikTrip', '2026-02-10', 35.00, 'flagged',
                'Employee rejected OCR read', '2026-02-10 16:00:00')""")

    # Receipt 4: Mario, confirmed, Project Hawk
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, vendor_city, vendor_state, purchase_date,
         subtotal, tax, total, payment_method, status, project_id, matched_project_name,
         created_at)
        VALUES (4, 2, 'Lowe''s', 'Kissimmee', 'FL', '2026-02-11',
                67.89, 4.75, 72.64, 'VISA 4321', 'confirmed', 2, 'Hawk',
                '2026-02-11 09:00:00')""")

    # Receipt 5: Omar, pending (should appear — pending is valid for export)
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date,
         subtotal, tax, total, payment_method, status, matched_project_name,
         created_at)
        VALUES (5, 1, 'Harbor Freight', '2026-02-12',
                29.99, 2.10, 32.09, 'Mastercard ending 7718', 'pending', 'Sparrow',
                '2026-02-12 11:00:00')""")

    # Receipt 6: Outside the date range (should NOT appear)
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date,
         subtotal, tax, total, status, created_at)
        VALUES (6, 1, 'Walmart', '2026-02-20',
                15.00, 1.05, 16.05, 'confirmed', '2026-02-20 08:00:00')""")

    # Line items for receipt #1 (Ace) — Fuel (id=2)
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price, category_id) VALUES (1, 'Utility Lighter', 1, 7.59, 7.59, 2)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price, category_id) VALUES (1, 'Propane Exchange', 1, 27.99, 27.99, 2)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price, category_id) VALUES (1, '20lb Propane Cylinder', 1, 59.99, 59.99, 2)")

    # Line items for receipt #2 (Home Depot) — Materials (id=1) and Tools & Equipment (id=4)
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price, category_id) VALUES (2, 'Roofing Nails 1lb', 2, 8.99, 17.98, 1)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price, category_id) VALUES (2, 'Caulk Gun', 1, 12.49, 12.49, 4)")

    # Line items for receipt #4 (Lowe's) — Safety Gear (id=5)
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price, category_id) VALUES (4, 'Safety Harness', 1, 45.99, 45.99, 5)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price, category_id) VALUES (4, 'Hard Hat', 1, 21.90, 21.90, 5)")

    # Receipt #5 has no line items (pending, not yet processed)

    db.commit()
    db.close()


def get_test_client():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = {
            "email": "test@example.com",
            "name": "Test User",
            "picture": "",
            "role": "admin",
        }
    return client


def parse_csv_response(resp) -> list[dict]:
    """Parse a CSV response into a list of dicts."""
    text = resp.data.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


# ── Basic endpoint tests ─────────────────────────────────────


def test_export_returns_csv():
    """GET /export/quickbooks returns a CSV file with correct headers."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    assert resp.status_code == 200
    assert resp.content_type == "text/csv; charset=utf-8"
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    assert "crewledger_export" in resp.headers.get("Content-Disposition", "")
    print("  PASS: returns CSV with correct headers")


def test_export_csv_columns():
    """CSV has the exact QuickBooks column names."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    expected_columns = [
        "Date", "Vendor", "Account", "Amount", "Tax",
        "Total", "Payment Method", "Memo", "Line Items",
    ]
    assert list(rows[0].keys()) == expected_columns
    print("  PASS: CSV has correct QuickBooks column names")


def test_export_row_count():
    """Only confirmed and pending receipts within date range are exported."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    # Receipts 1, 2, 4, 5 should appear (confirmed/pending in range)
    # Receipt 3 is flagged — excluded
    # Receipt 6 is outside date range — excluded
    assert len(rows) == 4
    print("  PASS: correct row count (4 receipts)")


def test_export_date_format():
    """Dates are formatted as MM/DD/YYYY for QuickBooks."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    assert rows[0]["Date"] == "02/09/2026"
    assert rows[1]["Date"] == "02/10/2026"
    print("  PASS: dates formatted as MM/DD/YYYY")


def test_export_vendor_and_amounts():
    """Vendor, subtotal, tax, and total are correctly mapped."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    # Receipt 1: Ace Home & Supply
    ace = rows[0]
    assert ace["Vendor"] == "Ace Home & Supply"
    assert float(ace["Amount"]) == 94.57
    assert float(ace["Tax"]) == 6.07
    assert float(ace["Total"]) == 100.64
    assert ace["Payment Method"] == "Mastercard ending 7718"
    print("  PASS: vendor and amounts correctly mapped")


def test_export_memo_format():
    """Memo is formatted as 'Project — Employee Name'."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    # Receipt 1: Omar (no full_name) on Project Sparrow
    assert "Sparrow" in rows[0]["Memo"]
    assert "Omar" in rows[0]["Memo"]

    # Receipt 4: Mario Gonzalez (has full_name) on Project Hawk
    mario_row = next(r for r in rows if "Mario" in r["Memo"])
    assert "Hawk" in mario_row["Memo"]
    assert "Mario Gonzalez" in mario_row["Memo"]
    print("  PASS: memo formatted correctly")


def test_export_line_items_summary():
    """Line items appear as a pipe-separated summary."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    # Receipt 1 has 3 line items
    items_str = rows[0]["Line Items"]
    assert "Utility Lighter" in items_str
    assert "Propane Exchange" in items_str
    assert "20lb Propane Cylinder" in items_str
    assert "|" in items_str  # pipe-separated
    print("  PASS: line items as pipe-separated summary")


def test_export_category_account():
    """Account column maps to the category of line items."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    # Receipt 1: all items are Fuel (category_id=2)
    assert rows[0]["Account"] == "Fuel"

    # Receipt 2: first item is Materials (category_id=1)
    assert rows[1]["Account"] == "Materials"
    print("  PASS: Account column maps to category")


# ── Filter tests ──────────────────────────────────────────────


def test_export_filter_by_employee():
    """employee_id filter returns only that employee's receipts."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15&employee_id=2")
    rows = parse_csv_response(resp)

    assert len(rows) == 1
    assert "Mario" in rows[0]["Memo"]
    print("  PASS: employee_id filter works")


def test_export_filter_by_project():
    """project filter returns only receipts for that project."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15&project=Hawk")
    rows = parse_csv_response(resp)

    assert len(rows) == 1
    assert "Hawk" in rows[0]["Memo"]
    print("  PASS: project filter works")


def test_export_filter_by_category():
    """category filter returns only receipts with matching line item categories."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15&category=Safety+Gear")
    rows = parse_csv_response(resp)

    assert len(rows) == 1
    assert rows[0]["Vendor"] == "Lowe's"
    print("  PASS: category filter works")


def test_export_empty_range():
    """Date range with no receipts returns CSV with headers only."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-01-01&week_end=2026-01-07")
    assert resp.status_code == 200
    rows = parse_csv_response(resp)
    assert len(rows) == 0
    # Verify header row is still present
    text = resp.data.decode("utf-8")
    assert "Date,Vendor,Account" in text
    print("  PASS: empty range returns headers-only CSV")


def test_export_filename_contains_dates():
    """Filename in Content-Disposition includes the date range."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    disposition = resp.headers.get("Content-Disposition", "")
    assert "2026-02-09" in disposition
    assert "2026-02-15" in disposition
    assert disposition.endswith(".csv")
    print("  PASS: filename contains date range")


def test_export_no_flagged_receipts():
    """Flagged receipts are excluded from the export."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    vendors = [r["Vendor"] for r in rows]
    assert "QuikTrip" not in vendors  # Receipt 3 is flagged
    print("  PASS: flagged receipts excluded")


def test_export_receipt_with_no_line_items():
    """Receipts without line items still export with empty Line Items and Account."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    # Receipt 5 (Harbor Freight) has no line items
    harbor = next(r for r in rows if r["Vendor"] == "Harbor Freight")
    assert harbor["Line Items"] == ""
    assert harbor["Account"] == ""
    assert float(harbor["Total"]) == 32.09
    print("  PASS: receipt without line items exports correctly")


def test_export_multiple_line_items_quantity():
    """Line items with quantity > 1 show the quantity in the summary."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/export/quickbooks?week_start=2026-02-09&week_end=2026-02-15")
    rows = parse_csv_response(resp)

    # Receipt 2: Roofing Nails 1lb has quantity 2
    hd = next(r for r in rows if r["Vendor"] == "Home Depot")
    assert "x2" in hd["Line Items"]
    print("  PASS: quantities > 1 shown in line items")


if __name__ == "__main__":
    print("Testing QuickBooks CSV export...\n")
    test_export_returns_csv()
    test_export_csv_columns()
    test_export_row_count()
    test_export_date_format()
    test_export_vendor_and_amounts()
    test_export_memo_format()
    test_export_line_items_summary()
    test_export_category_account()
    test_export_filter_by_employee()
    test_export_filter_by_project()
    test_export_filter_by_category()
    test_export_empty_range()
    test_export_filename_contains_dates()
    test_export_no_flagged_receipts()
    test_export_receipt_with_no_line_items()
    test_export_multiple_line_items_quantity()
    print("\nAll export tests passed!")

    # Cleanup
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
