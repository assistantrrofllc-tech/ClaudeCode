"""
Tests for database schema — verifies new tables and columns exist after schema execution.

Covers:
- New tables: invoices, invoice_line_items, packing_slips, packing_slip_items, purchase_orders
- New column: employees.language_preference
- Updated conversation_state CHECK constraint
- Foreign key relationships
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_schema.db"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_function():
    """Create a fresh DB from schema for each test."""
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
    db = sqlite3.connect(TEST_DB)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA_PATH.read_text())
    db.close()


def teardown_function():
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()


def _get_db():
    db = sqlite3.connect(TEST_DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def _get_table_names(db):
    rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r["name"] for r in rows}


def _get_column_names(db, table):
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


# ── Table Existence ──────────────────────────────────

def test_invoices_table_exists():
    db = _get_db()
    assert "invoices" in _get_table_names(db)
    db.close()


def test_invoice_line_items_table_exists():
    db = _get_db()
    assert "invoice_line_items" in _get_table_names(db)
    db.close()


def test_packing_slips_table_exists():
    db = _get_db()
    assert "packing_slips" in _get_table_names(db)
    db.close()


def test_packing_slip_items_table_exists():
    db = _get_db()
    assert "packing_slip_items" in _get_table_names(db)
    db.close()


def test_purchase_orders_table_exists():
    db = _get_db()
    assert "purchase_orders" in _get_table_names(db)
    db.close()


# ── Column Checks ────────────────────────────────────

def test_employees_language_preference_column():
    db = _get_db()
    cols = _get_column_names(db, "employees")
    assert "language_preference" in cols
    db.close()


def test_language_preference_accepts_null():
    db = _get_db()
    db.execute("INSERT INTO employees (phone_number, first_name) VALUES ('+14075551111', 'Test')")
    db.commit()
    row = db.execute("SELECT language_preference FROM employees WHERE phone_number = '+14075551111'").fetchone()
    assert row["language_preference"] is None
    db.close()


def test_language_preference_accepts_en():
    db = _get_db()
    db.execute("INSERT INTO employees (phone_number, first_name, language_preference) VALUES ('+14075551111', 'Test', 'en')")
    db.commit()
    row = db.execute("SELECT language_preference FROM employees WHERE phone_number = '+14075551111'").fetchone()
    assert row["language_preference"] == "en"
    db.close()


def test_language_preference_accepts_es():
    db = _get_db()
    db.execute("INSERT INTO employees (phone_number, first_name, language_preference) VALUES ('+14075551111', 'Test', 'es')")
    db.commit()
    row = db.execute("SELECT language_preference FROM employees WHERE phone_number = '+14075551111'").fetchone()
    assert row["language_preference"] == "es"
    db.close()


# ── Conversation State ───────────────────────────────

def test_conversation_state_accepts_awaiting_language():
    db = _get_db()
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Test')")
    db.execute("INSERT INTO conversation_state (employee_id, state) VALUES (1, 'awaiting_language')")
    db.commit()
    row = db.execute("SELECT state FROM conversation_state WHERE employee_id = 1").fetchone()
    assert row["state"] == "awaiting_language"
    db.close()


def test_conversation_state_accepts_awaiting_doc_confirm():
    db = _get_db()
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Test')")
    db.execute("INSERT INTO conversation_state (employee_id, state) VALUES (1, 'awaiting_doc_confirm')")
    db.commit()
    row = db.execute("SELECT state FROM conversation_state WHERE employee_id = 1").fetchone()
    assert row["state"] == "awaiting_doc_confirm"
    db.close()


# ── Invoice Table Structure ──────────────────────────

def test_invoices_has_required_columns():
    db = _get_db()
    cols = _get_column_names(db, "invoices")
    expected = {"id", "employee_id", "vendor_name", "vendor_address", "invoice_number",
                "date", "project_id", "subtotal", "tax", "total", "payment_method",
                "status", "flag_reason", "image_path", "ocr_confidence", "language", "created_at"}
    assert expected.issubset(cols)
    db.close()


def test_packing_slips_has_required_columns():
    db = _get_db()
    cols = _get_column_names(db, "packing_slips")
    expected = {"id", "employee_id", "vendor_name", "vendor_address", "po_number",
                "date", "project_id", "ship_to_site", "item_count", "status",
                "flag_reason", "image_path", "ocr_confidence", "language", "created_at"}
    assert expected.issubset(cols)
    db.close()


# ── Foreign Keys ─────────────────────────────────────

def test_invoices_foreign_key_employee():
    db = _get_db()
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Test')")
    db.execute("INSERT INTO invoices (employee_id, vendor_name) VALUES (1, 'Test Vendor')")
    db.commit()
    row = db.execute("SELECT * FROM invoices WHERE employee_id = 1").fetchone()
    assert row is not None
    db.close()


def test_invoices_foreign_key_project():
    db = _get_db()
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Test')")
    db.execute("INSERT INTO projects (id, name) VALUES (1, 'Sparrow')")
    db.execute("INSERT INTO invoices (employee_id, vendor_name, project_id) VALUES (1, 'Test', 1)")
    db.commit()
    row = db.execute("SELECT * FROM invoices WHERE project_id = 1").fetchone()
    assert row is not None
    db.close()


def test_invoice_line_items_cascade_delete():
    db = _get_db()
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Test')")
    db.execute("INSERT INTO invoices (id, employee_id) VALUES (1, 1)")
    db.execute("INSERT INTO invoice_line_items (invoice_id, item_name) VALUES (1, 'Widget')")
    db.commit()
    db.execute("DELETE FROM invoices WHERE id = 1")
    db.commit()
    row = db.execute("SELECT COUNT(*) as cnt FROM invoice_line_items WHERE invoice_id = 1").fetchone()
    assert row["cnt"] == 0
    db.close()


def test_packing_slip_items_cascade_delete():
    db = _get_db()
    db.execute("INSERT INTO employees (id, phone_number, first_name) VALUES (1, '+14075551111', 'Test')")
    db.execute("INSERT INTO packing_slips (id, employee_id) VALUES (1, 1)")
    db.execute("INSERT INTO packing_slip_items (packing_slip_id, item_name) VALUES (1, 'Box')")
    db.commit()
    db.execute("DELETE FROM packing_slips WHERE id = 1")
    db.commit()
    row = db.execute("SELECT COUNT(*) as cnt FROM packing_slip_items WHERE packing_slip_id = 1").fetchone()
    assert row["cnt"] == 0
    db.close()
