import sqlite3
from app.core.config import settings

def connect() -> sqlite3.Connection:
    con = sqlite3.connect(settings.db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def init_db() -> None:
    con = connect()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        planned_minutes INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        actual_seconds INTEGER DEFAULT 0,

        distractions_count INTEGER DEFAULT 0,
        altitude_end INTEGER DEFAULT 100,
        turbulence_end INTEGER DEFAULT 0,
        grade TEXT DEFAULT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS distractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        noted_at TEXT NOT NULL,
        note TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        idx INTEGER NOT NULL,
        due_seconds INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        note TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    );
    """)

    con.commit()
    con.close()
