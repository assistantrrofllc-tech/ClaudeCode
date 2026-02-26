"""
Tests for route-level role access control.

Covers:
- super_admin can access all routes
- company_admin can access operational routes but not settings/user management
- manager gets 403 on write routes
- employee gets 403 on write routes and can't view other profiles
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_role_access.db"
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
    # Re-set env var in case another test module changed it
    os.environ["DATABASE_PATH"] = TEST_DB
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())
    db.execute("INSERT INTO employees (id, phone_number, first_name, email) VALUES (1, '+14075551111', 'Omar', 'omar@test.com')")
    db.execute("INSERT INTO employees (id, phone_number, first_name, email) VALUES (2, '+14075552222', 'Jane', 'jane@test.com')")
    db.execute("INSERT INTO projects (id, name) VALUES (1, 'Test Project')")
    db.execute("""INSERT INTO receipts (id, employee_id, vendor_name, total, status)
                  VALUES (1, 1, 'Home Depot', 45.99, 'confirmed')""")
    db.execute("""INSERT INTO receipts (id, employee_id, vendor_name, total, status)
                  VALUES (2, 2, 'Lowes', 89.50, 'confirmed')""")
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


# ── super_admin access ──────────────────────────────────


def test_super_admin_can_access_settings():
    """super_admin can access settings page."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.get("/settings")
    assert resp.status_code == 200


def test_super_admin_can_access_user_management():
    """super_admin can access user management page."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.get("/admin/users")
    assert resp.status_code == 200


def test_super_admin_can_create_receipt():
    """super_admin can create receipts."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.post("/api/receipts", json={
        "employee_id": 1, "vendor_name": "Test Vendor", "total": 50.00,
    })
    assert resp.status_code == 201


def test_super_admin_can_export():
    """super_admin can export receipts."""
    setup_test_db()
    client = make_client("super_admin")
    resp = client.get("/api/receipts/export?format=csv")
    assert resp.status_code == 200


# ── company_admin access ────────────────────────────────


def test_company_admin_can_view_ledger():
    """company_admin can view ledger."""
    setup_test_db()
    client = make_client("company_admin")
    resp = client.get("/ledger")
    assert resp.status_code == 200


def test_company_admin_can_create_receipt():
    """company_admin can create receipts."""
    setup_test_db()
    client = make_client("company_admin")
    resp = client.post("/api/receipts", json={
        "employee_id": 1, "vendor_name": "Test Vendor", "total": 50.00,
    })
    assert resp.status_code == 201


def test_company_admin_can_export():
    """company_admin can export."""
    setup_test_db()
    client = make_client("company_admin")
    resp = client.get("/api/receipts/export?format=csv")
    assert resp.status_code == 200


def test_company_admin_cannot_access_settings():
    """company_admin gets 403 on settings."""
    setup_test_db()
    client = make_client("company_admin")
    resp = client.get("/settings")
    assert resp.status_code == 403


def test_company_admin_cannot_access_user_management():
    """company_admin gets 403 on user management."""
    setup_test_db()
    client = make_client("company_admin")
    resp = client.get("/admin/users")
    assert resp.status_code == 403


# ── manager access ──────────────────────────────────────


def test_manager_can_view_home():
    """manager can view home."""
    setup_test_db()
    client = make_client("manager")
    resp = client.get("/")
    assert resp.status_code == 200


def test_manager_can_view_ledger():
    """manager can view ledger."""
    setup_test_db()
    client = make_client("manager")
    resp = client.get("/ledger")
    assert resp.status_code == 200


def test_manager_can_view_receipts():
    """manager can view receipts API."""
    setup_test_db()
    client = make_client("manager")
    resp = client.get("/api/receipts")
    assert resp.status_code == 200


def test_manager_can_view_crew():
    """manager can view crew page."""
    setup_test_db()
    client = make_client("manager")
    resp = client.get("/crew")
    assert resp.status_code == 200


def test_manager_cannot_create_receipt():
    """manager gets 403 on create receipt."""
    setup_test_db()
    client = make_client("manager")
    resp = client.post("/api/receipts", json={
        "employee_id": 1, "vendor_name": "Test", "total": 50,
    })
    assert resp.status_code == 403


def test_manager_cannot_export():
    """manager gets 403 on export."""
    setup_test_db()
    client = make_client("manager")
    resp = client.get("/api/receipts/export?format=csv")
    assert resp.status_code == 403


def test_manager_cannot_add_employee():
    """manager gets 403 on add employee."""
    setup_test_db()
    client = make_client("manager")
    resp = client.post("/api/employees", json={
        "first_name": "New", "phone_number": "+14075553333",
    })
    assert resp.status_code == 403


def test_manager_cannot_access_settings():
    """manager gets 403 on settings."""
    setup_test_db()
    client = make_client("manager")
    resp = client.get("/settings")
    assert resp.status_code == 403


def test_manager_cannot_add_project():
    """manager gets 403 on add project."""
    setup_test_db()
    client = make_client("manager")
    resp = client.post("/api/projects", json={"name": "New Project"})
    assert resp.status_code == 403


# ── employee access ─────────────────────────────────────


def test_employee_can_view_home():
    """employee can view home."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.get("/")
    assert resp.status_code == 200


def test_employee_can_view_own_profile():
    """employee can view their own crew detail page."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.get("/crew/1")
    assert resp.status_code == 200


def test_employee_cannot_view_other_profile():
    """employee gets 403 viewing another employee's profile."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.get("/crew/2")
    assert resp.status_code == 403


def test_employee_cannot_create_receipt():
    """employee gets 403 on create receipt."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.post("/api/receipts", json={
        "employee_id": 1, "vendor_name": "Test", "total": 50,
    })
    assert resp.status_code == 403


def test_employee_cannot_export():
    """employee gets 403 on export."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.get("/api/receipts/export?format=csv")
    assert resp.status_code == 403


def test_employee_cannot_access_settings():
    """employee gets 403 on settings."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.get("/settings")
    assert resp.status_code == 403


def test_employee_cannot_add_employee():
    """employee gets 403 on add employee."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.post("/api/employees", json={
        "first_name": "New", "phone_number": "+14075553333",
    })
    assert resp.status_code == 403


def test_employee_cannot_add_project():
    """employee gets 403 on add project."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.post("/api/projects", json={"name": "New Project"})
    assert resp.status_code == 403


def test_employee_cannot_add_certification():
    """employee gets 403 on add certification."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.post("/api/crew/certifications", json={
        "employee_id": 1, "cert_type_id": 1,
    })
    assert resp.status_code == 403


def test_employee_cannot_access_user_management():
    """employee gets 403 on user management."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.get("/admin/users")
    assert resp.status_code == 403


# ── Data isolation ──────────────────────────────────────


def test_employee_sees_only_own_receipts():
    """employee only sees their own receipts."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.get("/api/receipts")
    assert resp.status_code == 200
    data = resp.get_json()
    # All receipts should belong to employee 1
    for r in data:
        assert r["employee_id"] == 1


def test_employee_sees_only_own_crew_data():
    """employee only sees their own record in crew list."""
    setup_test_db()
    client = make_client("employee", employee_id=1)
    resp = client.get("/api/crew/employees")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["id"] == 1


def test_manager_sees_all_receipts():
    """manager sees all receipts (not filtered)."""
    setup_test_db()
    client = make_client("manager")
    resp = client.get("/api/receipts")
    assert resp.status_code == 200
    data = resp.get_json()
    # Should see receipts from both employees
    employee_ids = {r["employee_id"] for r in data}
    assert len(employee_ids) > 1 or len(data) >= 2


def test_manager_sees_all_crew():
    """manager sees all employees in crew list."""
    setup_test_db()
    client = make_client("manager")
    resp = client.get("/api/crew/employees")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) >= 2
