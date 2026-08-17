"""Database connection and lifecycle management for SQLite."""

from pathlib import Path
import sqlite3
from typing import Optional, Union

from codepulse.config import settings

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS activity_heartbeat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_start TEXT NOT NULL,
    timestamp_end TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    process_name TEXT NOT NULL,
    window_title TEXT,
    category TEXT NOT NULL,
    project_name TEXT,
    is_idle INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_heartbeat(timestamp_start, timestamp_end);
CREATE INDEX IF NOT EXISTS idx_activity_category ON activity_heartbeat(category);
"""


def get_db_path(db_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the database path, falling back to configuration default."""
    if db_path is not None:
        return Path(db_path)
    return Path(settings.db_path)


def get_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """
    Create and configure a SQLite connection with production pragmas:
    - WAL journal mode
    - synchronous = NORMAL
    - foreign_keys = ON
    - busy_timeout = 5000ms
    """
    path = get_db_path(db_path)
    path_str = str(path)

    # Ensure parent directory exists if path is not in-memory or relative-only
    if path_str != ":memory:" and path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path_str)
    conn.row_factory = sqlite3.Row

    # Apply SQLite PRAGMAs
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")

    return conn


def init_db(db_path: Optional[Union[str, Path]] = None) -> None:
    """Initialize database tables and indexes."""
    with get_connection(db_path) as conn:
        conn.executescript(CREATE_TABLES_SQL)
        conn.commit()
