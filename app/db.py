import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path("storage/index.db")

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT UNIQUE NOT NULL,
  sha256 TEXT NOT NULL,
  modified_ns INTEGER NOT NULL,
  size_bytes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  page_num INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  embedding BLOB,
  FOREIGN KEY(file_id) REFERENCES files(id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='chunks', content_rowid='id');
"""

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30.0)  # 30 second timeout for locks
    con.row_factory = sqlite3.Row
    # Enable WAL mode and set busy timeout for better concurrency
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")  # 30 seconds in milliseconds
    return con 

def init_db():
    con = connect()
    with con:
        con.executescript(SCHEMA)
    con.close()

@contextmanager
def get_db():
    """Context manager for database connections"""
    con = connect()
    try:
        yield con
    finally:
        con.close()