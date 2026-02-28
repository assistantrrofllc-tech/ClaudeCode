"""Tests for CrewCert training sessions and Get Certified intake."""

import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_training.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""

# Stub twilio import for test environments without dependency installed.
if "twilio" not in sys.modules:
    twilio_mod = types.ModuleType("twilio")
    twilio_req_mod = types.ModuleType("twilio.request_validator")
    twilio_twiml_mod = types.ModuleType("twilio.twiml")
    twilio_msg_mod = types.ModuleType("twilio.twiml.messaging_response")

    class _DummyRequestValidator:
        def __init__(self, *args, **kwargs):
            pass

        def validate(self, *args, **kwargs):
            return True

    twilio_req_mod.RequestValidator = _DummyRequestValidator
    twilio_msg_mod.MessagingResponse = lambda *args, **kwargs: ""
    twilio_mod.request_validator = twilio_req_mod
    twilio_twiml_mod.messaging_response = twilio_msg_mod
    sys.modules["twilio"] = twilio_mod
    sys.modules["twilio.request_validator"] = twilio_req_mod
    sys.modules["twilio.twiml"] = twilio_twiml_mod
    sys.modules["twilio.twiml.messaging_response"] = twilio_msg_mod

if "openai" not in sys.modules:
    openai_mod = types.ModuleType("openai")

    class _DummyOpenAI:
        def __init__(self, *args, **kwargs):
            pass

    openai_mod.OpenAI = _DummyOpenAI
    sys.modules["openai"] = openai_mod

if "thefuzz" not in sys.modules:
    thefuzz_mod = types.ModuleType("thefuzz")
    fuzz_mod = types.ModuleType("thefuzz.fuzz")

    def _ratio(a, b):
        return 100 if a == b else 0

    fuzz_mod.ratio = _ratio
    thefuzz_mod.fuzz = fuzz_mod
    sys.modules["thefuzz"] = thefuzz_mod
    sys.modules["thefuzz.fuzz"] = fuzz_mod

from src.app import create_app
from src.database.connection import get_db
import src.api.training as training_api

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_test_db():
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()

    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())
    db.execute(
        "INSERT INTO employees (id, phone_number, first_name, full_name, crew, email) VALUES (1, '+14075551111', 'Mario', 'Mario Gonzalez', 'Mario Crew', 'mario@test.com')"
    )
    db.execute(
        "INSERT INTO employees (id, phone_number, first_name, full_name, crew, email) VALUES (2, '+14075552222', 'Pedro', 'Pedro Ruiz', 'Pedro Crew', 'pedro@test.com')"
    )
    db.execute("INSERT INTO projects (id, name, status) VALUES (1, 'Sparrow', 'active')")

    cert_type_id = db.execute(
        "SELECT id FROM certification_types WHERE name = 'OSHA 30'"
    ).fetchone()["id"]
    db.execute(
        """
        INSERT INTO certifications (employee_id, cert_type_id, issued_at, expires_at, notes, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (1, cert_type_id, "2020-01-01", "2025-01-01", "Seed old cert"),
    )
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
            "system_role": "super_admin",
        }
        sess["employee_id"] = 1
    return client


def _provider_id():
    db = get_db(TEST_DB)
    try:
        row = db.execute(
            "SELECT id FROM training_providers WHERE status = 'active' ORDER BY id LIMIT 1"
        ).fetchone()
        return row["id"]
    finally:
        db.close()


def test_training_pages_render():
    setup_test_db()
    client = get_test_client()
    assert client.get("/crewcert/training").status_code == 200
    assert client.get("/crewcert/training/providers").status_code == 200


def test_training_provider_crud_and_active_filter():
    setup_test_db()
    client = get_test_client()

    resp = client.post(
        "/api/training-providers",
        json={
            "company_name": "Acme Safety",
            "contact_name": "Jane",
            "contact_email": "jane@acme.test",
            "certs_offered": ["OSHA 10", "OSHA 30"],
        },
    )
    assert resp.status_code == 201
    provider_id = resp.get_json()["id"]

    resp = client.delete(f"/api/training-providers/{provider_id}")
    assert resp.status_code == 200

    active = client.get("/api/training-providers").get_json()
    assert all(p["id"] != provider_id for p in active)

    all_rows = client.get("/api/training-providers?include_inactive=1").get_json()
    inactive = [p for p in all_rows if p["id"] == provider_id]
    assert len(inactive) == 1
    assert inactive[0]["status"] == "inactive"


def test_training_request_submission_creates_record_and_sends_email(monkeypatch):
    setup_test_db()
    client = get_test_client()

    monkeypatch.setattr(training_api, "send_custom_email", lambda **kwargs: True)
    resp = client.post(
        "/api/training-requests",
        json={
            "provider_id": _provider_id(),
            "company_name": "R&R Florida",
            "contact_name": "Rob",
            "contact_email": "rob@test.com",
            "contact_phone": "407-555-1212",
            "certs_requested": ["OSHA 30", "Fall Protection Competent Person"],
            "num_employees": 8,
            "timeframe": "2_weeks",
            "location_pref": "onsite",
            "notes": "Need quote and dates.",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "submitted"
    assert data["email_sent_at"] is not None


def test_training_request_email_failure_keeps_draft(monkeypatch):
    setup_test_db()
    client = get_test_client()
    monkeypatch.setattr(training_api, "send_custom_email", lambda **kwargs: False)

    resp = client.post(
        "/api/training-requests",
        json={
            "provider_id": _provider_id(),
            "contact_name": "Rob",
            "contact_email": "rob@test.com",
            "certs_requested": ["OSHA 10"],
        },
    )
    assert resp.status_code == 502
    data = resp.get_json()
    assert data["request"]["status"] == "draft"


def test_training_session_create_assign_attendees():
    setup_test_db()
    client = get_test_client()

    resp = client.post(
        "/api/training-sessions",
        json={
            "title": "OSHA 30 Renewal",
            "trainer_id": _provider_id(),
            "preferred_date_start": "2026-03-01",
            "preferred_date_end": "2026-03-07",
            "status": "requested",
            "certs": ["OSHA 30"],
        },
    )
    assert resp.status_code == 201
    session_id = resp.get_json()["id"]

    resp = client.post(
        f"/api/training-sessions/{session_id}/attendees",
        json={"employee_ids": [1, 2]},
    )
    assert resp.status_code == 200

    attendees = client.get(f"/api/training-sessions/{session_id}/attendees").get_json()
    assert len(attendees) == 2


def test_mark_complete_updates_certs_for_attended_only():
    setup_test_db()
    client = get_test_client()

    resp = client.post(
        "/api/training-sessions",
        json={
            "title": "OSHA 30 Renewal",
            "trainer_id": _provider_id(),
            "session_date": "2026-03-01",
            "status": "scheduled",
            "certs": ["OSHA 30"],
        },
    )
    session_id = resp.get_json()["id"]

    client.post(f"/api/training-sessions/{session_id}/attendees", json={"employee_ids": [1, 2]})
    client.put(f"/api/training-sessions/{session_id}/attendees/1", json={"attended": True})
    client.put(f"/api/training-sessions/{session_id}/attendees/2", json={"attended": False})

    done = client.post(
        f"/api/training-sessions/{session_id}/complete",
        json={"session_date": "2026-03-01"},
    )
    assert done.status_code == 200

    db = get_db(TEST_DB)
    try:
        cert_type_id = db.execute(
            "SELECT id FROM certification_types WHERE name = 'OSHA 30'"
        ).fetchone()["id"]

        emp1 = db.execute(
            """
            SELECT issued_at, expires_at FROM certifications
            WHERE employee_id = ? AND cert_type_id = ? AND is_active = 1
            ORDER BY updated_at DESC, id DESC LIMIT 1
            """,
            (1, cert_type_id),
        ).fetchone()
        assert emp1["issued_at"] == "2026-03-01"
        assert emp1["expires_at"] == "2031-03-01"

        emp2 = db.execute(
            "SELECT COUNT(*) AS cnt FROM certifications WHERE employee_id = ? AND cert_type_id = ? AND is_active = 1",
            (2, cert_type_id),
        ).fetchone()
        assert emp2["cnt"] == 0
    finally:
        db.close()


def test_request_validation_required_fields():
    setup_test_db()
    client = get_test_client()
    resp = client.post("/api/training-requests", json={"provider_id": _provider_id()})
    assert resp.status_code == 400


def test_session_lifecycle_transition_requested_confirmed_completed():
    setup_test_db()
    client = get_test_client()
    resp = client.post(
        "/api/training-sessions",
        json={
            "title": "Lifecycle Test",
            "trainer_id": _provider_id(),
            "status": "requested",
            "certs": ["OSHA 10"],
        },
    )
    session_id = resp.get_json()["id"]

    upd = client.put(f"/api/training-sessions/{session_id}", json={"status": "confirmed"})
    assert upd.status_code == 200
    assert upd.get_json()["status"] == "confirmed"

    client.post(f"/api/training-sessions/{session_id}/attendees", json={"employee_ids": [1]})
    client.put(f"/api/training-sessions/{session_id}/attendees/1", json={"attended": True})
    done = client.post(
        f"/api/training-sessions/{session_id}/complete",
        json={"session_date": "2026-04-10"},
    )
    assert done.status_code == 200

    sessions = client.get("/api/training-sessions").get_json()
    this_session = [s for s in sessions if s["id"] == session_id][0]
    assert this_session["status"] == "completed"


def test_upcoming_training_api_returns_future_assignments():
    setup_test_db()
    client = get_test_client()
    resp = client.post(
        "/api/training-sessions",
        json={
            "title": "Future Session",
            "trainer_id": _provider_id(),
            "session_date": "2099-01-01",
            "status": "scheduled",
            "certs": ["OSHA 10"],
        },
    )
    session_id = resp.get_json()["id"]
    client.post(f"/api/training-sessions/{session_id}/attendees", json={"employee_ids": [1]})

    resp = client.get("/api/crew/employees/1/upcoming-training")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 1
    assert rows[0]["id"] == session_id


def test_send_training_request_email(monkeypatch):
    """Send Request emails the provider with cert/employee details."""
    setup_test_db()
    client = get_test_client()

    sent_emails = []
    def fake_send(**kwargs):
        sent_emails.append(kwargs)
        return True
    monkeypatch.setattr("src.api.training.send_custom_email", lambda **kw: fake_send(**kw))

    # Get seeded provider ID
    resp = client.get("/api/training-providers")
    providers = resp.get_json()
    provider_id = providers[0]["id"]

    resp = client.post("/api/training/send-request", json={
        "provider_id": provider_id,
        "certs": ["OSHA 10", "Fall Protection"],
        "employee_names": ["Mario Rodriguez", "Pedro Gonzalez"],
        "preferred_date": "2026-03-15",
        "location": "Tampa office",
        "notes": "Morning preferred",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "provider_name" in data
    assert len(sent_emails) == 1
    assert "OSHA 10" in sent_emails[0]["plain_body"]
    assert "Mario Rodriguez" in sent_emails[0]["plain_body"]


def test_send_training_request_missing_fields():
    """Send Request validates required fields."""
    setup_test_db()
    client = get_test_client()

    # No provider
    resp = client.post("/api/training/send-request", json={"certs": ["OSHA 10"]})
    assert resp.status_code == 400

    # No certs
    resp = client.post("/api/training/send-request", json={"provider_id": 1, "certs": []})
    assert resp.status_code == 400
