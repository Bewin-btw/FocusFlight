import os
import sqlite3
from pathlib import Path
from typing import Iterator
from contextlib import contextmanager

# app/db/db.py -> project root is 2 levels up
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "focusflight.db"

def _db_path() -> Path:
    return Path(os.getenv("FOCUSFLIGHT_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()