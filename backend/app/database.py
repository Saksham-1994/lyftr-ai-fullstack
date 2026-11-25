import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import settings

def _db_path() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        if not path.startswith("/"):
            path = os.path.abspath(path)
        return path
    raise RuntimeError("DATABASE_URL must use SQLite, for example sqlite:////data/app.db")

DB_PATH = _db_path()

def initialize_database() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)")
        conn.commit()

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def add_message(session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, json.dumps(metadata) if metadata is not None else None, created_at)
        )
        conn.commit()

def get_messages(session_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content, metadata FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
    return [
        {"role": row["role"], "content": row["content"],
         **({"metadata": json.loads(row["metadata"])} if row["metadata"] else {})}
        for row in rows
    ]

def session_exists(session_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM messages WHERE session_id = ? LIMIT 1", (session_id,)).fetchone()
    return row is not None

def database_is_ready() -> bool:
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False
