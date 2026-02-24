#!/usr/bin/env python3
"""
Generate public_token for all employees that don't have one.

Also creates the qr_scan_log table if it doesn't exist.

Usage:
    python scripts/generate_public_tokens.py          # dry-run (default)
    python scripts/generate_public_tokens.py --apply  # actually write to DB
"""

import argparse
import secrets
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.connection import get_db


def main():
    parser = argparse.ArgumentParser(description="Generate public tokens for employees")
    parser.add_argument("--apply", action="store_true", help="Actually write to DB (default is dry-run)")
    args = parser.parse_args()

    db = get_db()
    try:
        # Ensure public_token column exists
        cols = [row[1] for row in db.execute("PRAGMA table_info(employees)").fetchall()]
        if "public_token" not in cols:
            if args.apply:
                db.execute("ALTER TABLE employees ADD COLUMN public_token TEXT UNIQUE")
                print("Added public_token column to employees table.")
            else:
                print("WOULD add public_token column to employees table.")

        # Ensure qr_scan_log table exists
        db.execute("""
            CREATE TABLE IF NOT EXISTS qr_scan_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id     INTEGER NOT NULL,
                ip_address      TEXT,
                user_agent      TEXT,
                scanned_at      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_qr_scans_employee ON qr_scan_log(employee_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_qr_scans_time ON qr_scan_log(scanned_at)")
        if args.apply:
            db.commit()
            print("Ensured qr_scan_log table exists.")

        # Generate tokens for employees without one
        employees = db.execute(
            "SELECT id, first_name, full_name, public_token FROM employees"
        ).fetchall()

        generated = 0
        skipped = 0
        for emp in employees:
            name = emp["full_name"] or emp["first_name"]
            if emp["public_token"]:
                print(f"  SKIP: {name} (already has token)")
                skipped += 1
                continue

            token = secrets.token_urlsafe(12)
            if args.apply:
                db.execute(
                    "UPDATE employees SET public_token = ? WHERE id = ?",
                    (token, emp["id"]),
                )
            print(f"  {'SET' if args.apply else 'WOULD SET'}: {name} → {token}")
            generated += 1

        if args.apply:
            db.commit()

        print(f"\n{'='*50}")
        print(f"SUMMARY {'(DRY RUN)' if not args.apply else '(APPLIED)'}")
        print(f"  Generated: {generated}")
        print(f"  Skipped:   {skipped}")
        if not args.apply and generated > 0:
            print(f"\nRun with --apply to write changes to the database.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
