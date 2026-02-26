"""
Tests for fleet routes — CrewAsset Vehicles module.

Covers:
- Fleet overview with JSON response and summary stats
- Vehicle detail page (200 and 404)
- Maintenance JSON endpoint
- Add/edit/delete maintenance with role-based permissions
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_fleet.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["RECEIPT_STORAGE_PATH"] = "/tmp/test_receipt_images"
os.environ["TESTING"] = "1"

import config.settings as _settings
_settings.TWILIO_AUTH_TOKEN = ""
_settings.OPENAI_API_KEY = ""
_settings.RECEIPT_STORAGE_PATH = "/tmp/test_receipt_images"

from src.app import create_app
from src.database.connection import get_db

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_test_db():
    """Create a fresh test database with vehicle and maintenance seed data."""
    os.environ["DATABASE_PATH"] = TEST_DB
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())
    # Seed employees (required for foreign keys / session)
    db.execute(
        "INSERT INTO employees (id, phone_number, first_name, email) "
        "VALUES (1, '+14075551111', 'Omar', 'omar@test.com')"
    )
    # Seed vehicles
    db.execute(
        "INSERT INTO vehicles (id, year, make, model, nickname, plate_number, vin, assigned_to, status) "
        "VALUES (1, 2009, 'Ford', 'F150', '2009 F150', 'CDJK69', 'VIN001', '', 'active')"
    )
    db.execute(
        "INSERT INTO vehicles (id, year, make, model, nickname, plate_number, vin, assigned_to, status) "
        "VALUES (2, 2015, 'Ford', 'Transit', '2015 Van', 'RHJE92', 'VIN002', 'Justino', 'active')"
    )
    db.execute(
        "INSERT INTO vehicles (id, year, make, model, nickname, plate_number, vin, assigned_to, status) "
        "VALUES (3, 2020, 'Ford', 'F250', 'Sold Truck', 'ABC123', 'VIN003', '', 'sold')"
    )
    # Seed maintenance records
    db.execute(
        "INSERT INTO vehicle_maintenance (id, vehicle_id, service_date, description, cost, mileage, vendor) "
        "VALUES (1, 1, '2024-01-15', 'Oil change', 45.99, 150000, 'Take 5')"
    )
    db.execute(
        "INSERT INTO vehicle_maintenance (id, vehicle_id, service_date, description, cost, mileage, vendor) "
        "VALUES (2, 1, '2024-06-01', 'Tire rotation', 89.00, 155000, 'Firestone')"
    )
    db.execute(
        "INSERT INTO vehicle_maintenance (id, vehicle_id, service_date, description, cost, mileage, vendor) "
        "VALUES (3, 2, '2024-03-10', 'Brake pads', 350.00, 80000, 'Mavis Tires')"
    )
    db.commit()
    db.close()


def get_app():
    app = create_app()
    app.config["TESTING"] = True
    return app


def make_client(system_role="super_admin", employee_id=1):
    client = get_app().test_client()
    with client.session_transaction() as sess:
        sess["user"] = {
            "email": "test@example.com",
            "name": "Test User",
            "picture": "",
            "role": "admin",
            "system_role": system_role,
        }
        sess["employee_id"] = employee_id
    return client


# ── Fleet Overview ──────────────────────────────────────


def test_fleet_overview_returns_vehicles():
    """GET /fleet/ with JSON accept returns all 3 vehicles."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.get("/fleet/", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "vehicles" in data
    assert len(data["vehicles"]) == 3


def test_fleet_overview_summary_stats():
    """Summary has correct total_vehicles, total_spend, avg_cost."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.get("/fleet/", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    data = resp.get_json()
    summary = data["summary"]
    assert summary["total_vehicles"] == 3
    # total_spend = 45.99 + 89.00 + 350.00 = 484.99
    assert summary["total_spend"] == 484.99
    # avg_cost = 484.99 / 3 = 161.6633... rounded to 2 decimals
    assert summary["avg_cost_per_vehicle"] == round(484.99 / 3, 2)


# ── Vehicle Detail ──────────────────────────────────────


def test_vehicle_detail_page_loads():
    """GET /fleet/1 returns 200."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.get("/fleet/1")
    assert resp.status_code == 200


def test_vehicle_detail_404_for_missing():
    """GET /fleet/999 returns 404."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.get("/fleet/999")
    assert resp.status_code == 404


# ── Maintenance JSON Endpoint ──────────────────────────


def test_maintenance_json_endpoint():
    """GET /fleet/1/maintenance returns maintenance records."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.get("/fleet/1/maintenance")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "maintenance" in data
    # Vehicle 1 has 2 maintenance records
    assert len(data["maintenance"]) == 2


# ── Add Maintenance ────────────────────────────────────


def test_add_maintenance_super_admin():
    """POST /fleet/1/maintenance succeeds for super_admin."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.post(
        "/fleet/1/maintenance",
        json={
            "service_date": "2024-08-01",
            "description": "Transmission fluid",
            "cost": 120.00,
            "mileage": 160000,
            "vendor": "AAMCO",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "id" in data


def test_add_maintenance_manager_forbidden():
    """POST /fleet/1/maintenance returns 403 for manager.

    Manager has crewasset access_level='view', which is below the
    required 'edit' level for adding maintenance records.
    """
    setup_test_db()
    client = make_client("manager")
    resp = client.post(
        "/fleet/1/maintenance",
        json={
            "service_date": "2024-08-01",
            "description": "Transmission fluid",
            "cost": 120.00,
        },
    )
    assert resp.status_code == 403


def test_add_maintenance_employee_forbidden():
    """POST /fleet/1/maintenance returns 403 for employee."""
    setup_test_db()
    client = make_client("employee")
    resp = client.post(
        "/fleet/1/maintenance",
        json={
            "service_date": "2024-08-01",
            "description": "Transmission fluid",
            "cost": 120.00,
        },
    )
    assert resp.status_code == 403


# ── Edit Maintenance ───────────────────────────────────


def test_edit_maintenance_company_admin():
    """PUT /fleet/maintenance/1 succeeds for company_admin."""
    setup_test_db()
    client = make_client("company_admin")
    resp = client.put(
        "/fleet/maintenance/1",
        json={"cost": 55.00, "description": "Full synthetic oil change"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "Maintenance record updated"


def test_edit_maintenance_manager_forbidden():
    """PUT /fleet/maintenance/1 returns 403 for manager."""
    setup_test_db()
    client = make_client("manager")
    resp = client.put(
        "/fleet/maintenance/1",
        json={"cost": 55.00},
    )
    assert resp.status_code == 403


# ── Delete Maintenance ─────────────────────────────────


def test_delete_maintenance_super_admin():
    """DELETE /fleet/maintenance/1 succeeds for super_admin."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.delete("/fleet/maintenance/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "Maintenance record deleted"


def test_delete_maintenance_employee_forbidden():
    """DELETE /fleet/maintenance/1 returns 403 for employee."""
    setup_test_db()
    client = make_client("employee")
    resp = client.delete("/fleet/maintenance/1")
    assert resp.status_code == 403
