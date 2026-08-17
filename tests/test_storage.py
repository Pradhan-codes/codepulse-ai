"""Tests for SQLite storage layer."""

from pathlib import Path
import sqlite3
import pytest

from codepulse.storage.db import get_connection, init_db
from codepulse.storage.models import ActivityHeartbeat
from codepulse.storage.repository import (
    ActivityRepository,
    count_records,
    get_records_by_time_range,
    initialize_database,
    insert_record,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Fixture providing a unique temporary database path for each test."""
    return tmp_path / "test_codepulse.db"


def test_database_initialization_and_schema_creation(temp_db_path: Path):
    """Test that init_db creates table and indexes."""
    assert not temp_db_path.exists()
    init_db(temp_db_path)
    assert temp_db_path.exists()

    conn = get_connection(temp_db_path)
    cursor = conn.cursor()

    # Check table existence
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_heartbeat';")
    assert cursor.fetchone() is not None

    # Check index existence
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indices = [row["name"] for row in cursor.fetchall()]
    assert "idx_activity_time" in indices
    assert "idx_activity_category" in indices
    conn.close()


def test_sqlite_pragmas_and_wal_mode(temp_db_path: Path):
    """Test that connection pragmas (WAL, synchronous, foreign_keys, busy_timeout) are set."""
    conn = get_connection(temp_db_path)
    cursor = conn.cursor()

    # WAL mode
    cursor.execute("PRAGMA journal_mode;")
    assert cursor.fetchone()[0].lower() == "wal"

    # Synchronous mode (1 = NORMAL)
    cursor.execute("PRAGMA synchronous;")
    assert cursor.fetchone()[0] == 1

    # Foreign keys
    cursor.execute("PRAGMA foreign_keys;")
    assert cursor.fetchone()[0] == 1

    # Busy timeout
    cursor.execute("PRAGMA busy_timeout;")
    assert cursor.fetchone()[0] == 5000

    conn.close()


def test_empty_database(temp_db_path: Path):
    """Test queries on an initialized but empty database."""
    init_db(temp_db_path)
    repo = ActivityRepository(temp_db_path)

    assert repo.count() == 0
    assert count_records(temp_db_path) == 0
    assert repo.get_records() == []
    assert get_records_by_time_range(db_path=temp_db_path) == []


def test_insert_and_retrieve_record(temp_db_path: Path):
    """Test inserting a single activity record and retrieving it."""
    init_db(temp_db_path)
    repo = ActivityRepository(temp_db_path)

    record = ActivityHeartbeat(
        timestamp_start="2026-08-17T10:00:00Z",
        timestamp_end="2026-08-17T10:01:00Z",
        duration_seconds=60.0,
        process_name="Code.exe",
        window_title="codepulse - VS Code",
        category="CODING",
        project_name="codepulse",
        is_idle=False,
    )

    inserted_id = repo.insert(record)
    assert inserted_id > 0
    assert record.id == inserted_id
    assert repo.count() == 1

    records = repo.get_records()
    assert len(records) == 1
    retrieved = records[0]

    assert retrieved.id == inserted_id
    assert retrieved.timestamp_start == "2026-08-17T10:00:00Z"
    assert retrieved.timestamp_end == "2026-08-17T10:01:00Z"
    assert retrieved.duration_seconds == 60.0
    assert retrieved.process_name == "Code.exe"
    assert retrieved.window_title == "codepulse - VS Code"
    assert retrieved.category == "CODING"
    assert retrieved.project_name == "codepulse"
    assert retrieved.is_idle is False

    # Test to_dict conversion
    d = retrieved.to_dict()
    assert d["process_name"] == "Code.exe"
    assert d["is_idle"] is False


def test_insert_multiple_records(temp_db_path: Path):
    """Test inserting multiple records with different attributes."""
    initialize_database(temp_db_path)

    records_to_insert = [
        ActivityHeartbeat(
            timestamp_start="2026-08-17T09:00:00Z",
            timestamp_end="2026-08-17T09:15:00Z",
            duration_seconds=900.0,
            process_name="Code.exe",
            window_title="main.py",
            category="CODING",
            project_name="codepulse",
            is_idle=False,
        ),
        ActivityHeartbeat(
            timestamp_start="2026-08-17T09:15:00Z",
            timestamp_end="2026-08-17T09:20:00Z",
            duration_seconds=300.0,
            process_name="chrome.exe",
            window_title="Python documentation",
            category="DOCUMENTATION",
            project_name=None,
            is_idle=False,
        ),
        ActivityHeartbeat(
            timestamp_start="2026-08-17T09:20:00Z",
            timestamp_end="2026-08-17T09:30:00Z",
            duration_seconds=600.0,
            process_name="None",
            window_title="",
            category="IDLE",
            project_name=None,
            is_idle=True,
        ),
    ]

    for rec in records_to_insert:
        insert_record(rec, db_path=temp_db_path)

    assert count_records(temp_db_path) == 3

    fetched = get_records_by_time_range(db_path=temp_db_path)
    assert len(fetched) == 3
    assert fetched[0].category == "CODING"
    assert fetched[1].category == "DOCUMENTATION"
    assert fetched[2].category == "IDLE"
    assert fetched[2].is_idle is True


def test_time_range_filtering(temp_db_path: Path):
    """Test filtering activity records by start and end timestamps."""
    init_db(temp_db_path)
    repo = ActivityRepository(temp_db_path)

    records = [
        ActivityHeartbeat("2026-08-17T08:00:00Z", "2026-08-17T08:30:00Z", 1800.0, "Code.exe", "CODING"),
        ActivityHeartbeat("2026-08-17T09:00:00Z", "2026-08-17T09:30:00Z", 1800.0, "chrome.exe", "DOCUMENTATION"),
        ActivityHeartbeat("2026-08-17T10:00:00Z", "2026-08-17T10:30:00Z", 1800.0, "slack.exe", "COMMUNICATION"),
        ActivityHeartbeat("2026-08-17T11:00:00Z", "2026-08-17T11:30:00Z", 1800.0, "spotify.exe", "DISTRACTION"),
    ]
    for r in records:
        repo.insert(r)

    # Filter with start_time only (>= 09:00:00)
    res_start = repo.get_records(start_time="2026-08-17T09:00:00Z")
    assert len(res_start) == 3
    assert [r.process_name for r in res_start] == ["chrome.exe", "slack.exe", "spotify.exe"]

    # Filter with end_time only (<= 10:30:00)
    res_end = repo.get_records(end_time="2026-08-17T10:30:00Z")
    assert len(res_end) == 3
    assert [r.process_name for r in res_end] == ["Code.exe", "chrome.exe", "slack.exe"]

    # Filter with both start_time and end_time (09:00:00 to 10:30:00)
    res_range = repo.get_records(start_time="2026-08-17T09:00:00Z", end_time="2026-08-17T10:30:00Z")
    assert len(res_range) == 2
    assert [r.process_name for r in res_range] == ["chrome.exe", "slack.exe"]

    # Filter out of range
    res_none = repo.get_records(start_time="2026-08-17T12:00:00Z")
    assert len(res_none) == 0


def test_activity_heartbeat_from_tuple_fallback():
    """Test ActivityHeartbeat.from_row when provided a raw tuple."""
    raw_tuple = (1, "2026-08-17T08:00:00Z", "2026-08-17T08:30:00Z", 1800.0, "Code.exe", "Title", "CODING", "proj", 0)
    heartbeat = ActivityHeartbeat.from_row(raw_tuple)
    assert heartbeat.id == 1
    assert heartbeat.process_name == "Code.exe"
    assert heartbeat.project_name == "proj"
    assert heartbeat.is_idle is False
