"""
Load sample data into CrewLedger — two real receipts for demo purposes.

Creates:
- "Rob" employee (Robert Cordero)
- "Sparrow" project (if not exists)
- Bays Smoke Shop receipt ($67.08) with placeholder image
- Home Depot receipt ($94.81) with placeholder image
- Line items for both receipts

Run with: python scripts/load_sample_data.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.connection import get_db
from config.settings import RECEIPT_STORAGE_PATH


def create_placeholder_jpeg(filepath: str, label: str) -> None:
    """Create a minimal valid JPEG file as placeholder.

    This is a tiny 1x1 pixel JPEG — replace with the actual receipt photo
    by copying the real image to this path.
    """
    # Minimal valid JPEG (1x1 white pixel)
    jpeg_bytes = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0x7B, 0x94, 0x11, 0x00, 0x00, 0x00, 0x00, 0x00,
        0xFF, 0xD9,
    ])
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    Path(filepath).write_bytes(jpeg_bytes)
    print(f"  Created placeholder: {filepath}")
    print(f"  -> Replace with actual {label} receipt photo")


def load_sample_data():
    """Insert sample data into the database."""
    schema_path = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"

    db = get_db()
    try:
        # Ensure schema is up to date
        db.executescript(schema_path.read_text())

        # ── Employee: Rob ─────────────────────────────────────
        existing = db.execute("SELECT id FROM employees WHERE first_name = 'Rob'").fetchone()
        if existing:
            rob_id = existing["id"]
            print(f"  Rob already exists (id={rob_id})")
        else:
            db.execute(
                "INSERT INTO employees (phone_number, first_name, full_name, role, crew) VALUES (?, ?, ?, ?, ?)",
                ("+14075550001", "Rob", "Robert Cordero", "PM", "Alpha"),
            )
            rob_id = db.execute("SELECT id FROM employees WHERE first_name = 'Rob'").fetchone()["id"]
            print(f"  Created employee: Rob (id={rob_id})")

        # ── Project: Sparrow ──────────────────────────────────
        existing = db.execute("SELECT id FROM projects WHERE name = 'Sparrow'").fetchone()
        if existing:
            sparrow_id = existing["id"]
            print(f"  Sparrow project already exists (id={sparrow_id})")
        else:
            db.execute(
                "INSERT INTO projects (name, city, state, status) VALUES (?, ?, ?, ?)",
                ("Sparrow", "Kissimmee", "FL", "active"),
            )
            sparrow_id = db.execute("SELECT id FROM projects WHERE name = 'Sparrow'").fetchone()["id"]
            print(f"  Created project: Sparrow (id={sparrow_id})")

        # ── Receipt 1: Bays Smoke Shop — $67.08 ──────────────
        img1_name = "rob_20260220_161500.jpg"
        img1_path = str(Path(RECEIPT_STORAGE_PATH) / img1_name)
        create_placeholder_jpeg(img1_path, "Bays Smoke Shop")

        ocr1 = {
            "vendor_name": "Bays Smoke Shop",
            "vendor_city": "Kissimmee",
            "vendor_state": "FL",
            "purchase_date": "2026-02-20",
            "subtotal": 62.13,
            "tax": 4.95,
            "total": 67.08,
            "payment_method": "VISA 4821",
            "line_items": [
                {"item_name": "Black & Mild Wine", "quantity": 2, "unit_price": 3.49, "extended_price": 6.98},
                {"item_name": "Swisher Sweets", "quantity": 1, "unit_price": 5.99, "extended_price": 5.99},
                {"item_name": "Gatorade 12pk", "quantity": 2, "unit_price": 12.99, "extended_price": 25.98},
                {"item_name": "Red Bull 4pk", "quantity": 1, "unit_price": 9.99, "extended_price": 9.99},
                {"item_name": "Water 24pk", "quantity": 1, "unit_price": 6.99, "extended_price": 6.99},
                {"item_name": "Ice 10lb bag", "quantity": 1, "unit_price": 3.99, "extended_price": 3.99},
                {"item_name": "Snickers bar", "quantity": 2, "unit_price": 1.10, "extended_price": 2.20},
            ],
        }

        existing = db.execute("SELECT id FROM receipts WHERE vendor_name = 'Bays Smoke Shop' AND total = 67.08").fetchone()
        if existing:
            print(f"  Bays Smoke Shop receipt already exists (id={existing['id']})")
        else:
            db.execute(
                """INSERT INTO receipts
                    (employee_id, project_id, vendor_name, vendor_city, vendor_state,
                     purchase_date, subtotal, tax, total, payment_method,
                     image_path, status, matched_project_name, raw_ocr_json,
                     notes, created_at, confirmed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rob_id, sparrow_id,
                    "Bays Smoke Shop", "Kissimmee", "FL",
                    "2026-02-20", 62.13, 4.95, 67.08, "VISA 4821",
                    img1_path, "confirmed", "Sparrow",
                    json.dumps(ocr1),
                    "Crew drinks and snacks for Thursday",
                    "2026-02-20 16:15:00", "2026-02-20 16:16:00",
                ),
            )
            r1_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            for item in ocr1["line_items"]:
                db.execute(
                    "INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (?, ?, ?, ?, ?)",
                    (r1_id, item["item_name"], item["quantity"], item["unit_price"], item["extended_price"]),
                )
            print(f"  Created receipt: Bays Smoke Shop $67.08 (id={r1_id})")

        # ── Receipt 2: Home Depot — $94.81 ────────────────────
        img2_name = "rob_20260220_172300.jpg"
        img2_path = str(Path(RECEIPT_STORAGE_PATH) / img2_name)
        create_placeholder_jpeg(img2_path, "Home Depot")

        ocr2 = {
            "vendor_name": "Home Depot",
            "vendor_city": "Kissimmee",
            "vendor_state": "FL",
            "purchase_date": "2026-02-20",
            "subtotal": 87.94,
            "tax": 6.87,
            "total": 94.81,
            "payment_method": "VISA 4821",
            "line_items": [
                {"item_name": "OSB Sheathing 7/16\" 4x8", "quantity": 2, "unit_price": 14.98, "extended_price": 29.96},
                {"item_name": "Roofing Nails 1-1/4\" 5lb", "quantity": 1, "unit_price": 12.97, "extended_price": 12.97},
                {"item_name": "Flashing Roll 14\"x50'", "quantity": 1, "unit_price": 18.47, "extended_price": 18.47},
                {"item_name": "Caulk Gun", "quantity": 1, "unit_price": 8.97, "extended_price": 8.97},
                {"item_name": "Roof Sealant Tube", "quantity": 2, "unit_price": 5.98, "extended_price": 11.96},
                {"item_name": "Utility Knife Blades 10pk", "quantity": 1, "unit_price": 5.61, "extended_price": 5.61},
            ],
        }

        existing = db.execute("SELECT id FROM receipts WHERE vendor_name = 'Home Depot' AND total = 94.81").fetchone()
        if existing:
            print(f"  Home Depot receipt already exists (id={existing['id']})")
        else:
            db.execute(
                """INSERT INTO receipts
                    (employee_id, project_id, vendor_name, vendor_city, vendor_state,
                     purchase_date, subtotal, tax, total, payment_method,
                     image_path, status, matched_project_name, raw_ocr_json,
                     notes, created_at, confirmed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rob_id, sparrow_id,
                    "Home Depot", "Kissimmee", "FL",
                    "2026-02-20", 87.94, 6.87, 94.81, "VISA 4821",
                    img2_path, "confirmed", "Sparrow",
                    json.dumps(ocr2),
                    "Roofing materials for Sparrow job",
                    "2026-02-20 17:23:00", "2026-02-20 17:24:00",
                ),
            )
            r2_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            for item in ocr2["line_items"]:
                db.execute(
                    "INSERT INTO line_items (receipt_id, item_name, quantity, unit_price, extended_price) VALUES (?, ?, ?, ?, ?)",
                    (r2_id, item["item_name"], item["quantity"], item["unit_price"], item["extended_price"]),
                )
            print(f"  Created receipt: Home Depot $94.81 (id={r2_id})")

        db.commit()
        print("\nSample data loaded successfully!")
        print(f"  Images saved to: {RECEIPT_STORAGE_PATH}/")
        print("  Replace placeholder images with actual receipt photos.")

    finally:
        db.close()


if __name__ == "__main__":
    print("Loading CrewLedger sample data...\n")
    load_sample_data()
