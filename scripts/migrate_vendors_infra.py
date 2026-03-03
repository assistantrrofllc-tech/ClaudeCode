#!/usr/bin/env python3
"""
Vendors Infrastructure Migration — Promote vendors to shared CrewOS platform.

Idempotent: safe to run multiple times.

Changes:
  ALTER vendors: +vendor_type, +city, +state, +zip, +website, +account_number,
                 +payment_terms, +image_path, +status, +contact_phone
  CREATE vendor_contacts — multiple contacts per vendor
  CREATE vendor_aliases — OCR name variations for auto-matching receipts
  ALTER receipts: +vendor_id (FK → vendors.id)

Usage:
    python scripts/migrate_vendors_infra.py
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DATABASE_PATH


def migrate():
    db_path = os.environ.get("DATABASE_PATH", DATABASE_PATH)
    print(f"Database: {db_path}")

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    # ── ALTER vendors ─────────────────────────────────────────────
    print("\nAltering vendors table...")
    vendor_alters = [
        ("vendor_type", "TEXT NOT NULL DEFAULT 'supplier'"),
        ("city", "TEXT"),
        ("state", "TEXT"),
        ("zip", "TEXT"),
        ("website", "TEXT"),
        ("account_number", "TEXT"),
        ("payment_terms", "TEXT"),
        ("image_path", "TEXT"),
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("contact_phone", "TEXT"),
    ]

    for col, col_def in vendor_alters:
        try:
            # SQLite rejects non-constant DEFAULT on ALTER, so strip it
            if "DEFAULT" in col_def and "(" in col_def:
                simple_def = col_def.split("DEFAULT")[0].strip()
                db.execute(f"ALTER TABLE vendors ADD COLUMN {col} {simple_def}")
            else:
                db.execute(f"ALTER TABLE vendors ADD COLUMN {col} {col_def}")
            print(f"  Added vendors.{col}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"  vendors.{col} already exists")
            else:
                print(f"  WARNING: vendors.{col} — {e}")

    # ── ALTER receipts ────────────────────────────────────────────
    print("\nAltering receipts table...")
    try:
        db.execute("ALTER TABLE receipts ADD COLUMN vendor_id INTEGER REFERENCES vendors(id)")
        print("  Added receipts.vendor_id")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("  receipts.vendor_id already exists")
        else:
            print(f"  WARNING: receipts.vendor_id — {e}")

    # ── CREATE vendor_contacts ────────────────────────────────────
    print("\nCreating new tables...")
    db.execute("""
        CREATE TABLE IF NOT EXISTS vendor_contacts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id   INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL,
            role        TEXT,
            email       TEXT,
            phone       TEXT,
            is_primary  INTEGER DEFAULT 0,
            notes       TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── CREATE vendor_aliases ─────────────────────────────────────
    db.execute("""
        CREATE TABLE IF NOT EXISTS vendor_aliases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id   INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
            alias       TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # Create unique index on alias for fast lookups
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_vendor_aliases_alias ON vendor_aliases(alias)")
    except sqlite3.OperationalError:
        pass

    # Index on receipts.vendor_id for spend queries
    try:
        db.execute("CREATE INDEX IF NOT EXISTS idx_receipts_vendor_id ON receipts(vendor_id)")
    except sqlite3.OperationalError:
        pass

    db.commit()
    print("  Tables created successfully.")

    # ── Migrate existing contact_name/contact_email to vendor_contacts ──
    print("\nMigrating existing contacts to vendor_contacts...")
    existing_contacts = db.execute("""
        SELECT v.id, v.contact_name, v.contact_email, v.contact_phone
        FROM vendors v
        WHERE v.contact_name IS NOT NULL AND v.contact_name != ''
    """).fetchall()

    migrated = 0
    for vc in existing_contacts:
        # Check if already migrated
        exists = db.execute(
            "SELECT id FROM vendor_contacts WHERE vendor_id = ? AND name = ?",
            (vc["id"], vc["contact_name"]),
        ).fetchone()
        if not exists:
            db.execute(
                """INSERT INTO vendor_contacts (vendor_id, name, email, phone, is_primary)
                   VALUES (?, ?, ?, ?, 1)""",
                (vc["id"], vc["contact_name"], vc["contact_email"], vc["contact_phone"]),
            )
            migrated += 1

    db.commit()
    print(f"  Migrated {migrated} existing contacts (skipped {len(existing_contacts) - migrated} already migrated)")

    # ── Summary ───────────────────────────────────────────────────
    print("\nVerification:")
    for table in ("vendor_contacts", "vendor_aliases"):
        count = db.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
        print(f"  {table}: {count} rows")

    vendor_count = db.execute("SELECT COUNT(*) AS c FROM vendors").fetchone()["c"]
    print(f"  vendors: {vendor_count} total")

    receipts_with_vendor = db.execute(
        "SELECT COUNT(*) AS c FROM receipts WHERE vendor_id IS NOT NULL"
    ).fetchone()["c"]
    print(f"  receipts with vendor_id: {receipts_with_vendor}")

    db.close()
    print("\nVendors infrastructure migration complete.")


if __name__ == "__main__":
    migrate()
