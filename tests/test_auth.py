"""
Tests for Google OAuth authentication.

Covers:
- Login page rendering
- Login redirect for protected routes
- Post-login redirect to original URL
- Logout clears session
- Unauthenticated requests redirect to login
- Unprotected routes work without login (webhooks, QR verify, health)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_auth.db"
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


def setup_test_db():
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


def get_unauthenticated_client():
    return get_app().test_client()


def get_authenticated_client():
    client = get_app().test_client()
    with client.session_transaction() as sess:
        sess["user"] = {
            "email": "test@example.com",
            "name": "Test User",
            "picture": "",
            "role": "admin",
        }
    return client


# ── Login Page ──────────────────────────────────────────


def test_login_page_renders():
    """Login page shows sign-in button."""
    setup_test_db()
    client = get_unauthenticated_client()
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert b"Sign in with Google" in resp.data


def test_login_page_redirects_when_authenticated():
    """Authenticated users are redirected from login page."""
    setup_test_db()
    client = get_authenticated_client()
    resp = client.get("/auth/login")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


# ── Protected Routes Redirect ──────────────────────────────


def test_protected_route_redirects_to_login():
    """Unauthenticated access to protected route redirects to login."""
    setup_test_db()
    client = get_unauthenticated_client()
    resp = client.get("/ledger")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_protected_route_preserves_next_url():
    """Login redirect includes next= parameter with original URL."""
    setup_test_db()
    client = get_unauthenticated_client()
    resp = client.get("/projects")
    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert "/auth/login" in location
    assert "next=" in location


def test_protected_api_redirects_to_login():
    """API endpoints also redirect when unauthenticated."""
    setup_test_db()
    client = get_unauthenticated_client()
    resp = client.get("/api/receipts")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_authenticated_access_works():
    """Authenticated users can access protected routes."""
    setup_test_db()
    client = get_authenticated_client()
    resp = client.get("/")
    assert resp.status_code == 200


# ── Unprotected Routes ──────────────────────────────────


def test_health_check_no_login():
    """Health check works without login."""
    setup_test_db()
    client = get_unauthenticated_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_auth_routes_no_login():
    """Auth routes work without login."""
    setup_test_db()
    client = get_unauthenticated_client()
    resp = client.get("/auth/login")
    assert resp.status_code == 200


# ── Logout ──────────────────────────────────────────────


def test_logout_clears_session():
    """Logout clears session and redirects to login."""
    setup_test_db()
    client = get_authenticated_client()

    # Verify we're logged in
    resp = client.get("/")
    assert resp.status_code == 200

    # Logout
    resp = client.get("/auth/logout")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]

    # Now we should be redirected
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# ── Home Screen ──────────────────────────────────────────


def test_home_screen_shows_module_cards():
    """Home screen shows CrewLedger and CrewCert cards."""
    setup_test_db()
    client = get_authenticated_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"CrewLedger" in resp.data
    assert b"CrewCert" in resp.data
    assert b"CrewSchedule" in resp.data  # Coming soon card
    assert b"receipts this week" in resp.data


def test_home_screen_requires_login():
    """Home screen redirects to login when not authenticated."""
    setup_test_db()
    client = get_unauthenticated_client()
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
