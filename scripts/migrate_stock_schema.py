#!/usr/bin/env python3
"""
CrewStock schema migration — creates stock tables and migrates existing inventory data.

Tables created:
  - stock_shops        Shop locations (Orlando, Tampa, etc.)
  - stock_items        Master item catalog
  - shop_inventory     Per-shop quantity tracking
  - project_inventory  Items checked out to projects
  - stock_transactions Audit log of all movements

Run:
    python scripts/migrate_stock_schema.py
"""

import os
import re
import sys
import uuid
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.connection import get_db


def parse_quantity(qty_text):
    """Parse TEXT quantity like '20 PIECES' into numeric value and unit.

    Returns (numeric_qty, unit_str).
    Examples:
        '20 PIECES'  -> (20, 'PIECES')
        '5 ROLLS'    -> (5, 'ROLLS')
        '100'        -> (100, 'EACH')
        ''           -> (0, 'EACH')
        None         -> (0, 'EACH')
    """
    if not qty_text or not str(qty_text).strip():
        return 0, "EACH"

    text = str(qty_text).strip().upper()

    # Try to extract leading number
    match = re.match(r"(\d+(?:\.\d+)?)\s*(.*)", text)
    if match:
        num = float(match.group(1))
        unit = match.group(2).strip() or "EACH"
        return int(num) if num == int(num) else num, unit

    # No number found — treat whole string as description, qty=0
    return 0, "EACH"


def run_migration():
    db = get_db()
    try:
        # ── Create tables ────────────────────────────────────────

        db.executescript("""
        -- Shop locations
        CREATE TABLE IF NOT EXISTS stock_shops (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            address     TEXT,
            qr_code_id  TEXT   UNIQUE DEFAULT (lower(hex(randomblob(8)))),
            created_at  TEXT   DEFAULT (datetime('now'))
        );

        -- Master item catalog
        CREATE TABLE IF NOT EXISTS stock_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            sku             TEXT,
            manufacturer    TEXT,
            category        TEXT    DEFAULT 'General',
            unit            TEXT    DEFAULT 'EACH',
            pieces_per_unit INTEGER DEFAULT 1,
            reorder_point   INTEGER DEFAULT 0,
            qr_code_id      TEXT   UNIQUE DEFAULT (lower(hex(randomblob(8)))),
            created_at      TEXT   DEFAULT (datetime('now')),
            updated_at      TEXT   DEFAULT (datetime('now'))
        );

        -- Per-shop quantity tracking
        CREATE TABLE IF NOT EXISTS shop_inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER NOT NULL REFERENCES stock_items(id),
            shop_id     INTEGER NOT NULL REFERENCES stock_shops(id),
            quantity    REAL    DEFAULT 0,
            section     TEXT,
            updated_at  TEXT   DEFAULT (datetime('now')),
            UNIQUE(item_id, shop_id)
        );

        -- Items checked out to projects
        CREATE TABLE IF NOT EXISTS project_inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER NOT NULL REFERENCES stock_items(id),
            project_id  INTEGER NOT NULL,
            quantity    REAL    DEFAULT 0,
            updated_at  TEXT   DEFAULT (datetime('now')),
            UNIQUE(item_id, project_id)
        );

        -- Audit log of all inventory movements
        CREATE TABLE IF NOT EXISTS stock_transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            type            TEXT    NOT NULL,  -- 'checkout', 'return', 'restock', 'adjustment'
            item_id         INTEGER NOT NULL REFERENCES stock_items(id),
            shop_id         INTEGER REFERENCES stock_shops(id),
            project_id      INTEGER,
            employee_id     INTEGER,
            quantity        REAL    NOT NULL,
            notes           TEXT,
            created_at      TEXT   DEFAULT (datetime('now')),
            created_by      TEXT
        );
        """)

        print("Tables created successfully.")

        # ── Seed shops ────────────────────────────────────────────

        for shop_name in ("Orlando Shop", "Tampa Shop"):
            db.execute(
                "INSERT OR IGNORE INTO stock_shops (name) VALUES (?)",
                (shop_name,),
            )
        db.commit()

        shops = {
            row["name"]: row["id"]
            for row in db.execute("SELECT id, name FROM stock_shops").fetchall()
        }
        print(f"Shops seeded: {list(shops.keys())}")

        # ── Migrate existing inventory rows ───────────────────────

        # Check if old inventory table exists
        table_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'"
        ).fetchone()

        if not table_check:
            print("No existing 'inventory' table found — skipping data migration.")
            db.commit()
            return

        old_rows = db.execute(
            "SELECT id, item_name, quantity, manufacturer, location, section FROM inventory"
        ).fetchall()

        if not old_rows:
            print("Existing 'inventory' table is empty — nothing to migrate.")
            db.commit()
            return

        migrated = 0
        skipped = 0

        for row in old_rows:
            item_name = row["item_name"]
            manufacturer = row["manufacturer"] or ""
            location = row["location"] or ""
            section = row["section"] or ""
            qty_numeric, unit = parse_quantity(row["quantity"])

            # Map location to shop
            shop_id = None
            loc_lower = location.lower()
            for shop_name, sid in shops.items():
                if shop_name.lower().split()[0] in loc_lower:
                    shop_id = sid
                    break
            if shop_id is None:
                # Default to first shop if location doesn't match
                shop_id = list(shops.values())[0] if shops else None

            if shop_id is None:
                skipped += 1
                continue

            # Check if this item already exists in stock_items
            existing = db.execute(
                "SELECT id FROM stock_items WHERE name = ? AND manufacturer = ?",
                (item_name, manufacturer),
            ).fetchone()

            if existing:
                item_id = existing["id"]
            else:
                qr_code_id = uuid.uuid4().hex[:16]
                cursor = db.execute(
                    """INSERT INTO stock_items (name, manufacturer, unit, qr_code_id)
                       VALUES (?, ?, ?, ?)""",
                    (item_name, manufacturer, unit, qr_code_id),
                )
                item_id = cursor.lastrowid

            # Upsert shop_inventory
            db.execute(
                """INSERT INTO shop_inventory (item_id, shop_id, quantity, section)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(item_id, shop_id)
                   DO UPDATE SET quantity = quantity + excluded.quantity,
                                 section = COALESCE(excluded.section, section),
                                 updated_at = datetime('now')""",
                (item_id, shop_id, qty_numeric, section),
            )
            migrated += 1

        db.commit()
        print(f"Migrated {migrated} inventory rows, skipped {skipped}.")

        # Summary
        item_count = db.execute("SELECT COUNT(*) AS c FROM stock_items").fetchone()["c"]
        inv_count = db.execute("SELECT COUNT(*) AS c FROM shop_inventory").fetchone()["c"]
        print(f"Total stock_items: {item_count}, shop_inventory rows: {inv_count}")

    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
    print("Migration complete.")
