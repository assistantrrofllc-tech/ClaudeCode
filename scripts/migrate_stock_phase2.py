#!/usr/bin/env python3
"""
CrewStock Phase 2 schema migration.

Adds:
  - vendors: contact_email, notes, updated_at columns
  - stock_items: vendor_id, image_path, asset_id columns
  - project_inventory: quantity_ordered column
  - inventory_documents table (PO/invoice uploads)
  - inventory_document_items table (parsed line items)
  - reorder_requests table (email reorder drafts/history)
  - assets table (lightweight tool/equipment tracking)
  - storage directories for images and documents

All operations are idempotent (IF NOT EXISTS / try-except on ALTER).

Run:
    python scripts/migrate_stock_phase2.py
"""

import os
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.connection import get_db


def _safe_alter(db, table, column, col_def):
    """Add a column to a table, ignoring if it already exists."""
    try:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        print(f"  Added {table}.{column}")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print(f"  {table}.{column} already exists — skipped")
        else:
            print(f"  WARNING: {table}.{column} — {e}")


def run_migration():
    db = get_db()
    try:
        # ── ALTER existing tables ─────────────────────────────────

        print("Altering existing tables...")

        # vendors: add contact_email, notes, updated_at
        _safe_alter(db, "vendors", "contact_email", "TEXT")
        _safe_alter(db, "vendors", "notes", "TEXT")
        _safe_alter(db, "vendors", "updated_at", "TEXT DEFAULT (datetime('now'))")

        # stock_items: add vendor_id, image_path, asset_id
        _safe_alter(db, "stock_items", "vendor_id", "INTEGER REFERENCES vendors(id)")
        _safe_alter(db, "stock_items", "image_path", "TEXT")
        _safe_alter(db, "stock_items", "asset_id", "INTEGER")

        # project_inventory: add quantity_ordered
        _safe_alter(db, "project_inventory", "quantity_ordered", "REAL DEFAULT 0")

        db.commit()

        # ── CREATE new tables ─────────────────────────────────────

        print("Creating new tables...")

        db.executescript("""
        -- PO/invoice document uploads for project inventory
        CREATE TABLE IF NOT EXISTS inventory_documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER NOT NULL,
            vendor_id       INTEGER REFERENCES vendors(id),
            doc_type        TEXT    DEFAULT 'unknown',  -- 'po', 'invoice', 'packing_slip', 'unknown'
            filename        TEXT    NOT NULL,
            file_path       TEXT    NOT NULL,
            status          TEXT    DEFAULT 'pending',  -- 'pending', 'parsed', 'confirmed', 'error'
            notes           TEXT,
            uploaded_by     TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        );

        -- Parsed line items from uploaded documents
        CREATE TABLE IF NOT EXISTS inventory_document_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id     INTEGER NOT NULL REFERENCES inventory_documents(id) ON DELETE CASCADE,
            line_number     INTEGER DEFAULT 0,
            description     TEXT    NOT NULL,
            quantity        REAL    DEFAULT 0,
            unit_price      REAL,
            total_price     REAL,
            stock_item_id   INTEGER REFERENCES stock_items(id),  -- NULL until matched
            match_status    TEXT    DEFAULT 'unmatched',  -- 'unmatched', 'matched', 'skipped'
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        -- Reorder email drafts and history
        CREATE TABLE IF NOT EXISTS reorder_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id       INTEGER REFERENCES vendors(id),
            status          TEXT    DEFAULT 'draft',  -- 'draft', 'sent', 'cancelled'
            items_json      TEXT    NOT NULL,  -- JSON array of {item_id, name, quantity, unit, notes}
            notes           TEXT,
            email_to        TEXT,
            email_subject   TEXT,
            email_body      TEXT,
            sent_at         TEXT,
            created_by      TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        );

        -- Lightweight tool/equipment tracking (CrewAsset cross-wire)
        CREATE TABLE IF NOT EXISTS assets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            category        TEXT    DEFAULT 'tool',
            serial_number   TEXT,
            stock_item_id   INTEGER REFERENCES stock_items(id),
            vendor_id       INTEGER REFERENCES vendors(id),
            assigned_to     TEXT,
            status          TEXT    DEFAULT 'available',  -- 'available', 'in_use', 'maintenance', 'retired'
            notes           TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        );
        """)

        print("New tables created successfully.")
        db.commit()

        # ── Create storage directories ────────────────────────────

        print("Creating storage directories...")
        project_root = Path(__file__).resolve().parent.parent
        dirs = [
            project_root / "storage" / "stock_images",
            project_root / "storage" / "inventory_documents",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            print(f"  {d}")

        # ── Summary ───────────────────────────────────────────────

        for table in ("inventory_documents", "inventory_document_items",
                      "reorder_requests", "assets"):
            count = db.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
            print(f"  {table}: {count} rows")

    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
    print("Phase 2 migration complete.")
