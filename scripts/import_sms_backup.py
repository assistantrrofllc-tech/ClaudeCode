#!/usr/bin/env python3
"""
Import SMS messages from an SMS Backup & Restore XML file into the
communications table.

Usage:
    python scripts/import_sms_backup.py backup.xml
    python scripts/import_sms_backup.py backup.xml --db data/crewledger.db

The XML format is from the "SMS Backup & Restore" Android app.
Each <sms> element has attributes: address, date, type, body, etc.
type=1 = received (inbound), type=2 = sent (outbound).
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.connection import get_db


def parse_sms_xml(xml_path: str):
    """Parse SMS Backup & Restore XML and yield message dicts."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    for sms in root.iter("sms"):
        address = sms.get("address", "")
        body = sms.get("body", "")
        date_ms = sms.get("date", "0")
        msg_type = sms.get("type", "1")  # 1=received, 2=sent

        # Convert millisecond timestamp to datetime
        try:
            ts = datetime.fromtimestamp(int(date_ms) / 1000)
        except (ValueError, OSError):
            ts = datetime.now()

        # Normalize phone number
        phone = address.strip()
        if phone and not phone.startswith("+"):
            digits = "".join(c for c in phone if c.isdigit())
            if len(digits) == 10:
                phone = "+1" + digits
            elif len(digits) == 11 and digits.startswith("1"):
                phone = "+" + digits

        direction = "inbound" if msg_type == "1" else "outbound"

        # Use date_ms as external_id (unique per message in the backup)
        external_id = f"sms_{date_ms}_{address}"

        yield {
            "direction": direction,
            "channel": "sms",
            "from_number": phone if direction == "inbound" else None,
            "to_number": phone if direction == "outbound" else None,
            "body": body,
            "external_id": external_id,
            "created_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


def import_messages(db_path: str, xml_path: str):
    """Import SMS messages from XML into the communications table."""
    if not os.path.exists(xml_path):
        print(f"Error: File not found: {xml_path}")
        sys.exit(1)

    db = get_db(db_path)
    try:
        imported = 0
        skipped = 0
        earliest = None
        latest = None

        for msg in parse_sms_xml(xml_path):
            # Skip duplicates
            existing = db.execute(
                "SELECT id FROM communications WHERE external_id = ?",
                (msg["external_id"],),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            db.execute(
                """INSERT INTO communications
                   (direction, channel, from_number, to_number, body,
                    external_id, created_at, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg["direction"], msg["channel"],
                    msg["from_number"], msg["to_number"],
                    msg["body"], msg["external_id"],
                    msg["created_at"], msg["imported_at"],
                ),
            )
            imported += 1

            # Track date range
            ts = msg["created_at"]
            if earliest is None or ts < earliest:
                earliest = ts
            if latest is None or ts > latest:
                latest = ts

        db.commit()

        print(f"\nSMS Import Complete")
        print(f"  Imported: {imported}")
        print(f"  Skipped (duplicates): {skipped}")
        if earliest and latest:
            print(f"  Date range: {earliest} to {latest}")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import SMS Backup & Restore XML")
    parser.add_argument("xml_file", help="Path to SMS Backup & Restore XML file")
    parser.add_argument("--db", default=None, help="Path to database (default: from env or data/crewledger.db)")
    args = parser.parse_args()

    import_messages(args.db, args.xml_file)
