"""
Tests for the role-based permission system.

Covers:
- Role hierarchy
- Permission checking (check_permission)
- require_role decorator
- Data masking helpers
- is_own_data_only logic
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_permissions.db"
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
from src.services.permissions import (
    ROLE_HIERARCHY,
    ACCESS_LEVELS,
    DEFAULT_ACCESS,
    get_role_level,
    has_minimum_role,
    mask_phone,
    mask_email,
    check_permission,
    is_own_data_only,
    get_current_role,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_test_db():
    os.environ["DATABASE_PATH"] = TEST_DB
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Omar')")
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


# ── Role Hierarchy ────────────────────────────────────


def test_role_hierarchy_order():
    """super_admin > company_admin > manager > employee."""
    assert ROLE_HIERARCHY["super_admin"] > ROLE_HIERARCHY["company_admin"]
    assert ROLE_HIERARCHY["company_admin"] > ROLE_HIERARCHY["manager"]
    assert ROLE_HIERARCHY["manager"] > ROLE_HIERARCHY["employee"]


def test_role_hierarchy_values():
    """Each role has the expected numeric level."""
    assert ROLE_HIERARCHY["super_admin"] == 4
    assert ROLE_HIERARCHY["company_admin"] == 3
    assert ROLE_HIERARCHY["manager"] == 2
    assert ROLE_HIERARCHY["employee"] == 1


def test_get_role_level():
    """get_role_level returns correct values for all roles."""
    assert get_role_level("super_admin") == 4
    assert get_role_level("company_admin") == 3
    assert get_role_level("manager") == 2
    assert get_role_level("employee") == 1
    assert get_role_level("unknown_role") == 0


# ── Access Levels ─────────────────────────────────────


def test_access_levels_order():
    """Access levels are ordered none < view < edit < admin."""
    assert ACCESS_LEVELS.index("none") < ACCESS_LEVELS.index("view")
    assert ACCESS_LEVELS.index("view") < ACCESS_LEVELS.index("edit")
    assert ACCESS_LEVELS.index("edit") < ACCESS_LEVELS.index("admin")


# ── Default Access ────────────────────────────────────


def test_super_admin_has_admin_access_to_all():
    """super_admin has admin access to all modules."""
    for module, level in DEFAULT_ACCESS["super_admin"].items():
        assert level == "admin", f"super_admin should have admin access to {module}"


def test_company_admin_has_edit_access():
    """company_admin has edit access to operational modules."""
    for module in ("crewledger", "crewcert"):
        assert DEFAULT_ACCESS["company_admin"][module] == "edit"


def test_company_admin_no_settings():
    """company_admin cannot access settings or user management."""
    assert DEFAULT_ACCESS["company_admin"]["settings"] == "none"
    assert DEFAULT_ACCESS["company_admin"]["user_management"] == "none"


def test_manager_has_view_only():
    """manager has view access to operational modules."""
    for module in ("crewledger", "crewcert"):
        assert DEFAULT_ACCESS["manager"][module] == "view"


def test_manager_no_settings():
    """manager cannot access settings."""
    assert DEFAULT_ACCESS["manager"]["settings"] == "none"


def test_employee_limited_access():
    """employee has view access to crewledger/crewcert only."""
    assert DEFAULT_ACCESS["employee"]["crewledger"] == "view"
    assert DEFAULT_ACCESS["employee"]["crewcert"] == "view"
    assert DEFAULT_ACCESS["employee"]["settings"] == "none"
    assert DEFAULT_ACCESS["employee"]["user_management"] == "none"


# ── Permission Checking (in app context) ─────────────


def test_check_permission_super_admin():
    """super_admin passes all permission checks."""
    setup_test_db()
    app = get_app()
    with app.test_request_context():
        from flask import session
        session["user"] = {"email": "test@example.com", "system_role": "super_admin"}
        session["employee_id"] = 1
        assert check_permission(None, "crewledger", "admin") is True
        assert check_permission(None, "settings", "admin") is True


def test_check_permission_manager_view_only():
    """manager can view but not edit."""
    setup_test_db()
    app = get_app()
    with app.test_request_context():
        from flask import session
        session["user"] = {"email": "test@example.com", "system_role": "manager"}
        session["employee_id"] = 1
        assert check_permission(None, "crewledger", "view") is True
        assert check_permission(None, "crewledger", "edit") is False


def test_check_permission_employee_no_settings():
    """employee cannot access settings."""
    setup_test_db()
    app = get_app()
    with app.test_request_context():
        from flask import session
        session["user"] = {"email": "test@example.com", "system_role": "employee"}
        session["employee_id"] = 1
        assert check_permission(None, "settings", "view") is False


# ── is_own_data_only ──────────────────────────────────


def test_is_own_data_employee():
    """Employee role returns True for is_own_data_only."""
    setup_test_db()
    app = get_app()
    with app.test_request_context():
        from flask import session
        session["user"] = {"email": "test@example.com", "system_role": "employee"}
        assert is_own_data_only() is True


def test_is_not_own_data_admin():
    """Admin roles return False for is_own_data_only."""
    setup_test_db()
    app = get_app()
    with app.test_request_context():
        from flask import session
        session["user"] = {"email": "test@example.com", "system_role": "super_admin"}
        assert is_own_data_only() is False

        session["user"] = {"email": "test@example.com", "system_role": "company_admin"}
        assert is_own_data_only() is False

        session["user"] = {"email": "test@example.com", "system_role": "manager"}
        assert is_own_data_only() is False


# ── get_current_role ──────────────────────────────────


def test_get_current_role_from_session():
    """get_current_role reads from session correctly."""
    setup_test_db()
    app = get_app()
    with app.test_request_context():
        from flask import session
        session["user"] = {"email": "test@example.com", "system_role": "manager"}
        assert get_current_role() == "manager"


def test_get_current_role_defaults_to_employee():
    """get_current_role defaults to employee when no session."""
    setup_test_db()
    app = get_app()
    with app.test_request_context():
        assert get_current_role() == "employee"


# ── has_minimum_role ──────────────────────────────────


def test_has_minimum_role():
    """has_minimum_role checks role level correctly."""
    setup_test_db()
    app = get_app()
    with app.test_request_context():
        from flask import session
        session["user"] = {"email": "test@example.com", "system_role": "company_admin"}
        assert has_minimum_role("employee") is True
        assert has_minimum_role("manager") is True
        assert has_minimum_role("company_admin") is True
        assert has_minimum_role("super_admin") is False


# ── Data Masking ──────────────────────────────────────


def test_mask_phone():
    """mask_phone shows only last 4 digits."""
    assert mask_phone("+14075551234") == "***-***-1234"
    assert mask_phone("5551234") == "***-***-1234"
    assert mask_phone("") == ""
    assert mask_phone(None) == ""


def test_mask_email():
    """mask_email shows first char + domain."""
    assert mask_email("john@example.com") == "j***@example.com"
    assert mask_email("a@b.co") == "a***@b.co"
    assert mask_email("") == ""
    assert mask_email(None) == ""
