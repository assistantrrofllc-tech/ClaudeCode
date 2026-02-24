#!/usr/bin/env python3
"""
Link cert PDF files to certification records in the database.

For each PDF in storage/certifications/cert_files/:
  1. Parse the filename: {employee-slug}_{cert-type-slug}.pdf
  2. Match to an employee and cert type using mappings
  3. Create a certification record if one doesn't exist
  4. Set document_path on the record

Usage:
    python scripts/link_cert_files.py          # dry-run (default)
    python scripts/link_cert_files.py --apply  # actually write to DB
"""

import os
import sys
import argparse
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import CERT_STORAGE_PATH
from src.database.connection import get_db

# ── File employee slug → DB employee ID ──
# Built from VPS employee data. Handles mismatches between file names
# and DB full_name values.
EMPLOYEE_MAP = {
    "alejandro-vasquez": 23,
    "byron-orellana": 14,
    "diego-joel-lux-pu": 16,
    "gerardo-martinez": 5,
    "ignacio-martinez": 7,
    "jaimen-efrain-vasquez": 10,
    "javiron-misael-ci-fuentes": 20,
    "jenry-martinez": 19,
    "juan-martinez-lopez": 18,
    "kayne-juarez": 9,
    "ludin-lopez": 15,
    "mario-jeronimo": 21,
    "mario-martinez": 2,
    "marvin-marteinz": 17,  # typo in filename preserved
    "maynor-pu": 12,
    "milder-lopez": 3,
    "nery-martinez": 13,
    "omar-robles": 22,
    "pedro-martinez-lopez": 6,
    "richard-maldonado": 4,
    "saul-martinez": 11,
    "wuilson-lopez": 8,
    "zachary-robbins": 24,
    "jakob-robbins": 36,
    "justin-robbins": 37,
    "steven-sosa": 38,
    "robert-cordero": 1,
}

# ── File cert-type slug → DB cert_type_id ──
# Maps the naming convention in cert files to the DB certification_types table.
CERT_TYPE_MAP = {
    "extended-reach-forklift": 5,              # ext-reach-forklift
    "fall-protection-comp-person": 4,          # fall-protection
    "ashi-cpr-first-aid-aed": 3,               # first-aid-cpr
    "aerial-work-platform-all-terrain": 10,    # aerial-work-platform
    "aerial-work-platform-oct4-2024": 10,      # aerial-work-platform (dated)
    "cpr-first-aid-aed": 3,                   # first-aid-cpr
    "fall-protection": 4,                      # fall-protection
    "osha-10-hour-construction": 1,            # osha-10
    "osha-30-hour-construction": 2,            # osha-30
    "sss-basic-rigging": 11,                   # basic-rigging
    "rigger-signal-person-basic": 12,          # rigger-signal-person
}

# Files to skip (don't follow naming convention)
SKIP_FILES = {"mario-martinez_certification.pdf"}


def parse_filename(filename):
    """Parse '{employee-slug}_{cert-slug}.pdf' → (employee_slug, cert_slug)."""
    stem = filename.rsplit(".", 1)[0]  # remove .pdf
    parts = stem.split("_", 1)
    if len(parts) != 2:
        return None, None
    return parts[0], parts[1]


def main():
    parser = argparse.ArgumentParser(description="Link cert PDF files to DB records")
    parser.add_argument("--apply", action="store_true", help="Actually write to DB (default is dry-run)")
    args = parser.parse_args()

    cert_files_dir = Path(CERT_STORAGE_PATH) / "cert_files"
    if not cert_files_dir.exists():
        print(f"ERROR: cert_files directory not found at {cert_files_dir}")
        sys.exit(1)

    pdf_files = sorted(f.name for f in cert_files_dir.iterdir() if f.suffix == ".pdf")
    print(f"Found {len(pdf_files)} PDF files in {cert_files_dir}\n")

    linked = 0
    skipped = 0
    errors = []

    db = get_db()
    try:
        for filename in pdf_files:
            if filename in SKIP_FILES:
                print(f"  SKIP: {filename} (in skip list)")
                skipped += 1
                continue

            emp_slug, cert_slug = parse_filename(filename)
            if not emp_slug or not cert_slug:
                print(f"  SKIP: {filename} (cannot parse)")
                skipped += 1
                continue

            employee_id = EMPLOYEE_MAP.get(emp_slug)
            if employee_id is None:
                msg = f"  MISS: {filename} — employee '{emp_slug}' not in mapping"
                print(msg)
                errors.append(msg)
                continue

            cert_type_id = CERT_TYPE_MAP.get(cert_slug)
            if cert_type_id is None:
                msg = f"  MISS: {filename} — cert type '{cert_slug}' not in mapping"
                print(msg)
                errors.append(msg)
                continue

            doc_path = f"cert_files/{filename}"

            # Check if cert record already exists for this employee + type
            existing = db.execute(
                "SELECT id, document_path FROM certifications WHERE employee_id = ? AND cert_type_id = ? AND is_active = 1",
                (employee_id, cert_type_id),
            ).fetchone()

            if existing:
                if existing["document_path"] == doc_path:
                    print(f"  OK:   {filename} — already linked (cert #{existing['id']})")
                    linked += 1
                    continue
                # Update existing record
                if args.apply:
                    db.execute(
                        "UPDATE certifications SET document_path = ?, updated_at = datetime('now') WHERE id = ?",
                        (doc_path, existing["id"]),
                    )
                print(f"  LINK: {filename} → cert #{existing['id']} (updated document_path)")
                linked += 1
            else:
                # Create new cert record
                if args.apply:
                    cursor = db.execute(
                        """INSERT INTO certifications (employee_id, cert_type_id, document_path)
                           VALUES (?, ?, ?)""",
                        (employee_id, cert_type_id, doc_path),
                    )
                    print(f"  NEW:  {filename} → cert #{cursor.lastrowid} (employee={employee_id}, type={cert_type_id})")
                else:
                    print(f"  NEW:  {filename} → (would create: employee={employee_id}, type={cert_type_id})")
                linked += 1

        if args.apply:
            db.commit()

        print(f"\n{'='*50}")
        print(f"SUMMARY {'(DRY RUN)' if not args.apply else '(APPLIED)'}")
        print(f"  Linked:  {linked}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors:  {len(errors)}")
        if errors:
            print(f"\nUnresolved:")
            for e in errors:
                print(f"  {e}")
        if not args.apply and linked > 0:
            print(f"\nRun with --apply to write changes to the database.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
