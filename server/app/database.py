import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import DATABASE_PATH, ensure_data_directories


CREATE_IMAGES_TABLE = """
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    device_id TEXT NOT NULL,
    label TEXT DEFAULT 'unknown',
    captured_at TEXT,
    uploaded_at TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    status TEXT DEFAULT 'unlabeled',
    reserved_for_test INTEGER DEFAULT 0
);
"""

CREATE_LABELS_TABLE = """
CREATE TABLE IF NOT EXISTS labels (
    name TEXT PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db() -> None:
    ensure_data_directories()
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(CREATE_IMAGES_TABLE)
        conn.execute(CREATE_LABELS_TABLE)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(images)").fetchall()}
        if "reserved_for_test" not in columns:
            conn.execute("ALTER TABLE images ADD COLUMN reserved_for_test INTEGER DEFAULT 0")
        conn.commit()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    init_db()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
