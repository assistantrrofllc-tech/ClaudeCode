"""
Tests for the dashboard API endpoints.

Covers: summary stats, flagged receipt queue (approve/edit/dismiss),
search & filter, and the dashboard page route.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_dashboard.db"
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
    """Create a fresh DB and seed with data for dashboard tests."""
    os.environ["DATABASE_PATH"] = TEST_DB
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()

    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())

    # Employees
    db.execute("INSERT INTO employees (id, phone_number, first_name, crew) VALUES (1, '+14075551111', 'Omar', 'Alpha')")
    db.execute("INSERT INTO employees (id, phone_number, first_name, full_name) VALUES (2, '+14075552222', 'Mario', 'Mario Gonzalez')")

    # Projects
    db.execute("INSERT INTO projects (id, name) VALUES (1, 'Sparrow')")
    db.execute("INSERT INTO projects (id, name) VALUES (2, 'Hawk')")

    # Receipt 1: Omar, confirmed
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, subtotal, tax, total,
         payment_method, status, project_id, matched_project_name, created_at)
        VALUES (1, 1, 'Ace Home', '2026-02-09', 94.57, 6.07, 100.64,
                'VISA 1234', 'confirmed', 1, 'Sparrow', '2026-02-09 10:30:00')""")

    # Receipt 2: Omar, confirmed
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, subtotal, tax, total,
         payment_method, status, project_id, matched_project_name, created_at)
        VALUES (2, 1, 'Home Depot', '2026-02-10', 42.50, 2.87, 45.37,
                'CASH', 'confirmed', 1, 'Sparrow', '2026-02-10 14:15:00')""")

    # Receipt 3: Omar, flagged
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, total, status,
         flag_reason, created_at)
        VALUES (3, 1, 'QuikTrip', '2026-02-10', 35.00, 'flagged',
                'Employee rejected OCR read', '2026-02-10 16:00:00')""")

    # Receipt 4: Mario, flagged + missed
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, total, status,
         is_missed_receipt, flag_reason, matched_project_name, created_at)
        VALUES (4, 2, 'Home Depot', '2026-02-11', 67.89, 'flagged',
                1, 'Missed receipt', 'Hawk', '2026-02-11 09:00:00')""")

    # Previous week receipt (for comparison stats)
    db.execute("""INSERT INTO receipts
        (id, employee_id, vendor_name, purchase_date, total, status, created_at)
        VALUES (5, 1, 'Walmart', '2026-02-02', 50.00, 'confirmed', '2026-02-02 12:00:00')""")

    # Line items for receipt #1
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (1, 'Utility Lighter', 1, 7.59, 7.59)")
    db.execute("INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (1, 'Propane Exchange', 1, 27.99, 27.99)")

    db.commit()
    db.close()


def get_test_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


# ── Dashboard page route ─────────────────────────────────────


def test_dashboard_page_loads():
    """GET / returns the dashboard HTML."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"CrewLedger" in resp.data
    assert b"bottom-nav" in resp.data


def test_dashboard_route_loads():
    """GET /dashboard also works."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"CrewLedger" in resp.data


# ── Summary API ──────────────────────────────────────────────


def test_summary_returns_json():
    """GET /api/dashboard/summary returns valid JSON."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/summary?week_start=2026-02-09&week_end=2026-02-15")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "current_week" in data
    assert "previous_week" in data
    assert "flagged_count" in data


def test_summary_current_week_totals():
    """Current week totals are correct (confirmed + pending only)."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/summary?week_start=2026-02-09&week_end=2026-02-15")
    data = resp.get_json()
    # Receipts 1 and 2 are confirmed in range: 100.64 + 45.37 = 146.01
    assert data["current_week"]["total_spend"] == 146.01
    assert data["current_week"]["receipt_count"] == 2


def test_summary_previous_week():
    """Previous week totals are computed."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/summary?week_start=2026-02-09&week_end=2026-02-15")
    data = resp.get_json()
    # Receipt 5 is in the previous week: $50.00
    assert data["previous_week"]["total_spend"] == 50.0
    assert data["previous_week"]["receipt_count"] == 1


def test_summary_flagged_count():
    """Flagged count includes all flagged receipts."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/summary?week_start=2026-02-09&week_end=2026-02-15")
    data = resp.get_json()
    assert data["flagged_count"] == 2  # receipts 3 and 4


def test_summary_by_crew():
    """By crew breakdown has employee spend data."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/summary?week_start=2026-02-09&week_end=2026-02-15")
    data = resp.get_json()
    assert len(data["by_crew"]) >= 1
    omar = next(c for c in data["by_crew"] if c["name"] == "Omar")
    assert omar["spend"] == 146.01


def test_summary_by_project():
    """By project breakdown is present."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/summary?week_start=2026-02-09&week_end=2026-02-15")
    data = resp.get_json()
    assert len(data["by_project"]) >= 1
    sparrow = next(p for p in data["by_project"] if p["name"] == "Sparrow")
    assert sparrow["spend"] == 146.01


def test_summary_recent_activity():
    """Recent activity returns up to 10 receipts."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/summary?week_start=2026-02-09&week_end=2026-02-15")
    data = resp.get_json()
    assert isinstance(data["recent_activity"], list)
    assert len(data["recent_activity"]) <= 10
    assert len(data["recent_activity"]) == 5  # we seeded 5 total receipts


# ── Flagged API ──────────────────────────────────────────────


def test_flagged_returns_list():
    """GET /api/dashboard/flagged returns flagged receipts."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/flagged")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 2
    assert len(data["flagged"]) == 2


def test_flagged_has_required_fields():
    """Each flagged receipt has required fields."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/flagged")
    data = resp.get_json()
    receipt = data["flagged"][0]
    assert "id" in receipt
    assert "vendor" in receipt
    assert "employee" in receipt
    assert "flag_reason" in receipt
    assert "total" in receipt
    assert "date" in receipt


def test_approve_receipt():
    """POST approve changes status to confirmed."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/dashboard/flagged/3/approve")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "approved"

    # Verify DB
    db = get_db(TEST_DB)
    receipt = db.execute("SELECT * FROM receipts WHERE id = 3").fetchone()
    assert receipt["status"] == "confirmed"
    assert receipt["confirmed_at"] is not None
    db.close()


def test_dismiss_receipt():
    """POST dismiss changes status to rejected."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/dashboard/flagged/3/dismiss")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "dismissed"

    db = get_db(TEST_DB)
    receipt = db.execute("SELECT * FROM receipts WHERE id = 3").fetchone()
    assert receipt["status"] == "rejected"
    db.close()


def test_edit_receipt():
    """POST edit updates fields and approves."""
    setup_test_db()
    client = get_test_client()
    resp = client.post(
        "/api/dashboard/flagged/3/edit",
        json={"vendor": "QuikTrip #45", "total": 38.50, "project": "Sparrow"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "updated"

    db = get_db(TEST_DB)
    receipt = db.execute("SELECT * FROM receipts WHERE id = 3").fetchone()
    assert receipt["status"] == "confirmed"
    assert receipt["vendor_name"] == "QuikTrip #45"
    assert receipt["total"] == 38.50
    assert receipt["matched_project_name"] == "Sparrow"
    db.close()


def test_approve_nonexistent_receipt():
    """Approve returns 404 for nonexistent receipt."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/dashboard/flagged/999/approve")
    assert resp.status_code == 404


def test_approve_non_flagged_receipt():
    """Approve returns 400 for non-flagged receipt."""
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/dashboard/flagged/1/approve")  # receipt 1 is confirmed
    assert resp.status_code == 400


# ── Search API ───────────────────────────────────────────────


def test_search_returns_results():
    """GET /api/dashboard/search returns results."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data
    assert "total" in data
    assert "filters" in data
    assert data["total"] == 5  # all 5 receipts


def test_search_filter_by_status():
    """Status filter works."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search?status=flagged")
    data = resp.get_json()
    assert data["total"] == 2
    for r in data["results"]:
        assert r["status"] == "flagged"


def test_search_filter_by_vendor():
    """Vendor search is partial match."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search?vendor=Home+Depot")
    data = resp.get_json()
    assert data["total"] == 2  # Home Depot (receipt 2) and Home Depot (receipt 4)


def test_search_filter_by_date_range():
    """Date range filter works."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search?date_start=2026-02-09&date_end=2026-02-10")
    data = resp.get_json()
    assert data["total"] == 3  # receipts 1, 2, 3


def test_search_filter_by_amount():
    """Amount range filter works."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search?amount_min=50&amount_max=110")
    data = resp.get_json()
    assert data["total"] == 3  # 100.64, 67.89, 50.00


def test_search_sort_by_amount():
    """Sorting by amount works."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search?sort=amount&order=desc")
    data = resp.get_json()
    totals = [r["total"] for r in data["results"] if r["total"] is not None]
    assert totals == sorted(totals, reverse=True)


def test_search_pagination():
    """Pagination returns correct page info."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search?per_page=2&page=1")
    data = resp.get_json()
    assert len(data["results"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["total_pages"] == 3


def test_search_has_filter_options():
    """Search response includes filter dropdown options."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search")
    data = resp.get_json()
    assert len(data["filters"]["employees"]) == 2
    assert len(data["filters"]["projects"]) == 2
    assert len(data["filters"]["categories"]) == 7  # 7 seeded categories


def test_search_results_have_line_items():
    """Search results include line items."""
    setup_test_db()
    client = get_test_client()
    resp = client.get("/api/dashboard/search?vendor=Ace")
    data = resp.get_json()
    assert data["total"] == 1
    assert len(data["results"][0]["line_items"]) == 2  # 2 items for receipt 1


if __name__ == "__main__":
    print("Testing dashboard API...\n")
    test_dashboard_page_loads()
    test_dashboard_route_loads()
    test_summary_returns_json()
    test_summary_current_week_totals()
    test_summary_previous_week()
    test_summary_flagged_count()
    test_summary_by_crew()
    test_summary_by_project()
    test_summary_recent_activity()
    test_flagged_returns_list()
    test_flagged_has_required_fields()
    test_approve_receipt()
    test_dismiss_receipt()
    test_edit_receipt()
    test_approve_nonexistent_receipt()
    test_approve_non_flagged_receipt()
    test_search_returns_results()
    test_search_filter_by_status()
    test_search_filter_by_vendor()
    test_search_filter_by_date_range()
    test_search_filter_by_amount()
    test_search_sort_by_amount()
    test_search_pagination()
    test_search_has_filter_options()
    test_search_results_have_line_items()
    print("\nAll dashboard tests passed!")

    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
