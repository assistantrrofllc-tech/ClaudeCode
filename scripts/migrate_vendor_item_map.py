#!/usr/bin/env python3
"""
Migration: Vendor-Item Mapping, Project Aliases & Dual Unit Display

Creates:
  - vendor_item_map   — cross-ref linking stock items to vendor SKUs + unit conversion
  - project_aliases   — alternate project names for auto-matching

Alters:
  - stock_items       — ADD unit_label, pack_label

All operations idempotent (IF NOT EXISTS / try-except on ALTER).
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DATABASE_PATH


def migrate(db_path: str | None = None):
    db_path = db_path or DATABASE_PATH
    print(f"[migrate] Using database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # ── vendor_item_map ──────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vendor_item_map (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id       INTEGER NOT NULL REFERENCES vendors(id),
            item_id         INTEGER NOT NULL REFERENCES stock_items(id),
            vendor_sku      TEXT,
            vendor_item_name TEXT,
            vendor_unit     TEXT NOT NULL DEFAULT 'EA',
            vendor_unit_quantity REAL NOT NULL DEFAULT 1,
            notes           TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(vendor_id, item_id)
        )
    """)
    print("  [OK] vendor_item_map table")

    # Index for fast SKU lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_vendor_item_map_sku
        ON vendor_item_map(vendor_id, vendor_sku)
    """)
    print("  [OK] vendor_item_map SKU index")

    # ── project_aliases ──────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_aliases (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER NOT NULL REFERENCES projects(id),
            alias           TEXT NOT NULL,
            source          TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(alias)
        )
    """)
    print("  [OK] project_aliases table")

    # ── stock_items: add unit_label, pack_label ──────────────────
    existing = {r[1] for r in conn.execute("PRAGMA table_info(stock_items)").fetchall()}

    for col, default in [
        ("unit_label", "'EA'"),
        ("pack_label", "'BOX'"),
    ]:
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE stock_items ADD COLUMN {col} TEXT DEFAULT {default}")
                print(f"  [OK] stock_items.{col} added")
            except Exception as e:
                print(f"  [SKIP] stock_items.{col}: {e}")
        else:
            print(f"  [SKIP] stock_items.{col} already exists")

    conn.commit()
    conn.close()
    print("[migrate] Done.")


if __name__ == "__main__":
    migrate()
