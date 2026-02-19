"""
CrewLedger database connection management.

Provides a single get_db() function that returns a connection
with foreign keys enabled and Row factory set for dict-like access.
"""

import os
import sqlite3
from pathlib import Path

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/crewledger.db")


def get_db(db_path: str | None = None) -> sqlite3.Connection:
    """Return a SQLite connection with standard config applied."""
    path = db_path or DATABASE_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
