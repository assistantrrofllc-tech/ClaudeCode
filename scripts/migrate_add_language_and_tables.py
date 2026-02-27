"""
Migration: Add language_preference column and new document tables.

Adds:
- employees.language_preference (TEXT DEFAULT NULL)
- invoices table + invoice_line_items
- packing_slips table + packing_slip_items
- purchase_orders table
- New conversation states: awaiting_language, awaiting_doc_confirm

Idempotent — safe to run multiple times.
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DATABASE_PATH


def migrate(db_path=None):
    """Run migration on the specified database."""
    path = db_path or DATABASE_PATH
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")

    try:
        # 1. Add language_preference to employees
        cols = [row[1] for row in db.execute("PRAGMA table_info(employees)").fetchall()]
        if "language_preference" not in cols:
            db.execute("ALTER TABLE employees ADD COLUMN language_preference TEXT DEFAULT NULL")
            print("Added employees.language_preference")
        else:
            print("employees.language_preference already exists")

        # 2. Create invoices table
        db.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id     INTEGER NOT NULL,
                vendor_name     TEXT,
                vendor_address  TEXT,
                invoice_number  TEXT,
                date            TEXT,
                project_id      INTEGER,
                subtotal        REAL,
                tax             REAL,
                total           REAL,
                payment_method  TEXT,
                status          TEXT    DEFAULT 'pending'
                                       CHECK(status IN ('pending', 'confirmed', 'flagged', 'rejected', 'deleted', 'duplicate')),
                flag_reason     TEXT,
                image_path      TEXT,
                ocr_confidence  REAL,
                language        TEXT,
                created_at      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (project_id)  REFERENCES projects(id)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_invoices_employee ON invoices(employee_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_invoices_project ON invoices(project_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_invoices_created ON invoices(created_at)")
        print("Created invoices table")

        # 3. Create invoice_line_items table
        db.execute("""
            CREATE TABLE IF NOT EXISTS invoice_line_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id      INTEGER NOT NULL,
                item_name       TEXT,
                quantity        REAL    DEFAULT 1,
                unit_price      REAL,
                total_price     REAL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_inv_li_invoice ON invoice_line_items(invoice_id)")
        print("Created invoice_line_items table")

        # 4. Create packing_slips table
        db.execute("""
            CREATE TABLE IF NOT EXISTS packing_slips (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id     INTEGER NOT NULL,
                vendor_name     TEXT,
                vendor_address  TEXT,
                po_number       TEXT,
                date            TEXT,
                project_id      INTEGER,
                ship_to_site    TEXT,
                item_count      INTEGER DEFAULT 0,
                status          TEXT    DEFAULT 'pending'
                                       CHECK(status IN ('pending', 'confirmed', 'flagged', 'rejected', 'deleted', 'duplicate')),
                flag_reason     TEXT,
                image_path      TEXT,
                ocr_confidence  REAL,
                language        TEXT,
                created_at      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (project_id)  REFERENCES projects(id)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_packing_slips_employee ON packing_slips(employee_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_packing_slips_project ON packing_slips(project_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_packing_slips_status ON packing_slips(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_packing_slips_created ON packing_slips(created_at)")
        print("Created packing_slips table")

        # 5. Create packing_slip_items table
        db.execute("""
            CREATE TABLE IF NOT EXISTS packing_slip_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                packing_slip_id INTEGER NOT NULL,
                item_name       TEXT,
                quantity        REAL    DEFAULT 1,
                unit            TEXT,
                notes           TEXT,
                FOREIGN KEY (packing_slip_id) REFERENCES packing_slips(id) ON DELETE CASCADE
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_ps_items_slip ON packing_slip_items(packing_slip_id)")
        print("Created packing_slip_items table")

        # 6. Create purchase_orders table
        db.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id     INTEGER NOT NULL,
                vendor_name     TEXT,
                vendor_address  TEXT,
                po_number       TEXT,
                date            TEXT,
                project_id      INTEGER,
                subtotal        REAL,
                tax             REAL,
                total           REAL,
                status          TEXT    DEFAULT 'pending'
                                       CHECK(status IN ('pending', 'confirmed', 'flagged', 'rejected', 'deleted', 'duplicate')),
                flag_reason     TEXT,
                image_path      TEXT,
                ocr_confidence  REAL,
                language        TEXT,
                created_at      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (project_id)  REFERENCES projects(id)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_employee ON purchase_orders(employee_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_project ON purchase_orders(project_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_status ON purchase_orders(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_created ON purchase_orders(created_at)")
        print("Created purchase_orders table")

        # Note: conversation_state CHECK constraint can't be altered in SQLite.
        # New states are handled in the schema.sql for fresh databases.
        # For existing databases, we recreate the table if needed.
        row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='conversation_state'"
        ).fetchone()
        if row and "awaiting_language" not in row[0]:
            # Recreate with new states
            db.execute("ALTER TABLE conversation_state RENAME TO _conversation_state_old")
            db.execute("""
                CREATE TABLE conversation_state (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id     INTEGER NOT NULL,
                    receipt_id      INTEGER,
                    state           TEXT    NOT NULL
                                           CHECK(state IN (
                                               'idle',
                                               'awaiting_confirmation',
                                               'awaiting_manual_entry',
                                               'awaiting_missed_details',
                                               'awaiting_language',
                                               'awaiting_doc_confirm'
                                           )),
                    context_json    TEXT,
                    created_at      TEXT    DEFAULT (datetime('now')),
                    updated_at      TEXT    DEFAULT (datetime('now')),
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    FOREIGN KEY (receipt_id)  REFERENCES receipts(id)
                )
            """)
            db.execute("""
                INSERT INTO conversation_state (id, employee_id, receipt_id, state, context_json, created_at, updated_at)
                SELECT id, employee_id, receipt_id, state, context_json, created_at, updated_at
                FROM _conversation_state_old
            """)
            db.execute("DROP TABLE _conversation_state_old")
            db.execute("CREATE INDEX IF NOT EXISTS idx_convo_employee ON conversation_state(employee_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_convo_state ON conversation_state(state)")
            print("Recreated conversation_state with new states")
        else:
            print("conversation_state already has new states")

        db.commit()
        print("Migration complete.")

    finally:
        db.close()


if __name__ == "__main__":
    migrate()
