#!/usr/bin/env python3
"""
Initialize the CrewLedger SQLite database.

Usage:
    python scripts/setup_db.py                    # default: data/crewledger.db
    python scripts/setup_db.py --db path/to.db    # custom path
    python scripts/setup_db.py --seed              # include sample projects
"""

import argparse
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.connection import get_db

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"

SAMPLE_PROJECTS = [
    ("Sparrow", "123 Main St", "Kissimmee", "FL"),
    ("Falcon", "456 Oak Ave", "Orlando", "FL"),
    ("Hawk", "789 Pine Rd", "Sanford", "FL"),
    ("Eagle", "321 Elm Blvd", "Winter Park", "FL"),
    ("Osprey", "654 Cedar Ln", "St Cloud", "FL"),
]


def init_database(db_path: str, seed: bool = False) -> None:
    """Create all tables from schema.sql and optionally seed sample data."""
    schema_sql = SCHEMA_PATH.read_text()

    conn = get_db(db_path)
    try:
        conn.executescript(schema_sql)
        print(f"Database initialized: {db_path}")

        if seed:
            conn.executemany(
                "INSERT OR IGNORE INTO projects (name, address, city, state) VALUES (?, ?, ?, ?)",
                SAMPLE_PROJECTS,
            )
            conn.commit()
            print(f"Seeded {len(SAMPLE_PROJECTS)} sample projects")

        # Print summary
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        print(f"Tables created: {', '.join(row['name'] for row in tables)}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the CrewLedger database")
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_PATH", "data/crewledger.db"),
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the database with sample projects",
    )
    args = parser.parse_args()

    init_database(args.db, seed=args.seed)


if __name__ == "__main__":
    main()
