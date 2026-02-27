"""
Tests for SMS language preference flow.

Covers:
- First contact triggers language prompt
- English/Spanish selection variants
- Invalid response re-prompts
- Subsequent messages use saved language
- i18n message catalog
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_lang.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["RECEIPT_STORAGE_PATH"] = "/tmp/test_receipt_images"

import config.settings as _settings
_settings.DATABASE_PATH = TEST_DB
_settings.TWILIO_AUTH_TOKEN = ""
_settings.OPENAI_API_KEY = ""

from src.database.connection import get_db
from src.messaging.i18n import msg
from src.messaging.sms_handler import (
    handle_incoming_message, _handle_language_selection,
    _ENGLISH_VARIANTS, _SPANISH_VARIANTS,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_function():
    """Create a fresh DB with test data."""
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()

    os.environ["DATABASE_PATH"] = TEST_DB
    _settings.DATABASE_PATH = TEST_DB

    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())
    # Employee with no language preference (NULL = first contact)
    db.execute(
        "INSERT INTO employees (id, phone_number, first_name, is_active) VALUES (1, '+14075551111', 'Omar', 1)"
    )
    # Employee with English preference
    db.execute(
        "INSERT INTO employees (id, phone_number, first_name, is_active, language_preference) VALUES (2, '+14075552222', 'Mario', 1, 'en')"
    )
    # Employee with Spanish preference
    db.execute(
        "INSERT INTO employees (id, phone_number, first_name, is_active, language_preference) VALUES (3, '+14075553333', 'Carlos', 1, 'es')"
    )
    db.commit()
    db.close()


def teardown_function():
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()


# ── First Contact Language Prompt ─────────────────────

def test_first_contact_triggers_language_prompt():
    """Employee with NULL language_preference should get the bilingual prompt."""
    result = handle_incoming_message({
        "from_number": "+14075551111",
        "body": "Hello",
        "media": [],
    })
    assert "English" in result
    assert "Espanol" in result


def test_first_contact_sets_awaiting_language_state():
    """After language prompt, employee should be in awaiting_language state."""
    handle_incoming_message({
        "from_number": "+14075551111",
        "body": "Hello",
        "media": [],
    })
    db = get_db(TEST_DB)
    convo = db.execute(
        "SELECT state FROM conversation_state WHERE employee_id = 1 ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    db.close()
    assert convo["state"] == "awaiting_language"


# ── Language Selection ────────────────────────────────

def test_english_selection():
    """Selecting 'english' should set language_preference to 'en'."""
    # First trigger the prompt
    handle_incoming_message({"from_number": "+14075551111", "body": "Hello", "media": []})
    # Then reply with English
    result = handle_incoming_message({"from_number": "+14075551111", "body": "English", "media": []})
    assert "Thanks" in result or "set" in result.lower()

    db = get_db(TEST_DB)
    row = db.execute("SELECT language_preference FROM employees WHERE id = 1").fetchone()
    db.close()
    assert row["language_preference"] == "en"


def test_espanol_selection():
    """Selecting 'espanol' should set language_preference to 'es'."""
    handle_incoming_message({"from_number": "+14075551111", "body": "Hello", "media": []})
    result = handle_incoming_message({"from_number": "+14075551111", "body": "espanol", "media": []})
    assert "Gracias" in result

    db = get_db(TEST_DB)
    row = db.execute("SELECT language_preference FROM employees WHERE id = 1").fetchone()
    db.close()
    assert row["language_preference"] == "es"


def test_spanish_variant():
    """'spanish' should also set language to 'es'."""
    handle_incoming_message({"from_number": "+14075551111", "body": "Hello", "media": []})
    result = handle_incoming_message({"from_number": "+14075551111", "body": "spanish", "media": []})
    assert "Gracias" in result

    db = get_db(TEST_DB)
    row = db.execute("SELECT language_preference FROM employees WHERE id = 1").fetchone()
    db.close()
    assert row["language_preference"] == "es"


def test_eng_variant():
    """'eng' should set language to 'en'."""
    handle_incoming_message({"from_number": "+14075551111", "body": "Hello", "media": []})
    result = handle_incoming_message({"from_number": "+14075551111", "body": "eng", "media": []})

    db = get_db(TEST_DB)
    row = db.execute("SELECT language_preference FROM employees WHERE id = 1").fetchone()
    db.close()
    assert row["language_preference"] == "en"


def test_invalid_response_reprompts():
    """Invalid language response should re-prompt."""
    handle_incoming_message({"from_number": "+14075551111", "body": "Hello", "media": []})
    result = handle_incoming_message({"from_number": "+14075551111", "body": "French", "media": []})
    assert "English" in result
    assert "Espanol" in result

    # Language should still be NULL
    db = get_db(TEST_DB)
    row = db.execute("SELECT language_preference FROM employees WHERE id = 1").fetchone()
    db.close()
    assert row["language_preference"] is None


# ── Subsequent Messages Use Saved Language ────────────

def test_english_employee_gets_english_messages():
    """Employee with language_preference='en' gets English responses."""
    result = handle_incoming_message({
        "from_number": "+14075552222",
        "body": "Random text",
        "media": [],
    })
    # Should get the unrecognized message in English
    assert "Hey" in result or "didn't" in result


def test_spanish_employee_gets_spanish_messages():
    """Employee with language_preference='es' gets Spanish responses."""
    result = handle_incoming_message({
        "from_number": "+14075553333",
        "body": "Random text",
        "media": [],
    })
    # Should get the unrecognized message in Spanish
    assert "Hola" in result or "entendi" in result


# ── i18n Catalog ──────────────────────────────────────

def test_msg_returns_english():
    result = msg("receipt_saved", "en", name="Omar", total_str=" for $10.00", vendor="Home Depot")
    assert "Omar" in result
    assert "Home Depot" in result


def test_msg_returns_spanish():
    result = msg("receipt_saved", "es", name="Omar", total_str=" for $10.00", vendor="Home Depot")
    assert "Omar" in result
    assert "Listo" in result


def test_msg_language_prompt_is_bilingual():
    result = msg("language_prompt")
    assert "English" in result
    assert "Espanol" in result


def test_msg_fallback_to_key_without_lang():
    result = msg("language_invalid")
    assert "English" in result


def test_english_variants_complete():
    """All expected English variants should be in the set."""
    assert "english" in _ENGLISH_VARIANTS
    assert "eng" in _ENGLISH_VARIANTS
    assert "en" in _ENGLISH_VARIANTS
    assert "ingles" in _ENGLISH_VARIANTS


def test_spanish_variants_complete():
    """All expected Spanish variants should be in the set."""
    assert "espanol" in _SPANISH_VARIANTS
    assert "spanish" in _SPANISH_VARIANTS
    assert "esp" in _SPANISH_VARIANTS
    assert "es" in _SPANISH_VARIANTS
