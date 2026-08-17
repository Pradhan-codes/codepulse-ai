"""Repository for storing and querying activity heartbeat records."""

from pathlib import Path
from typing import List, Optional, Union

from codepulse.storage.db import get_connection, init_db
from codepulse.storage.models import ActivityHeartbeat


class ActivityRepository:
    """Repository handling database operations for activity heartbeats."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        """Initialize the database schema."""
        init_db(self.db_path)

    def insert(self, record: ActivityHeartbeat) -> int:
        """
        Insert an activity heartbeat record.
        Returns the inserted record's database ID.
        """
        query = """
        INSERT INTO activity_heartbeat (
            timestamp_start,
            timestamp_end,
            duration_seconds,
            process_name,
            window_title,
            category,
            project_name,
            is_idle
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    record.timestamp_start,
                    record.timestamp_end,
                    record.duration_seconds,
                    record.process_name,
                    record.window_title,
                    record.category,
                    record.project_name,
                    1 if record.is_idle else 0,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            if record_id is not None:
                record.id = record_id
            return record_id or 0

    def get_records(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[ActivityHeartbeat]:
        """
        Retrieve records, optionally filtered by time range.
        - If start_time is provided: filters for timestamp_start >= start_time
        - If end_time is provided: filters for timestamp_end <= end_time
        """
        conditions = []
        params = []

        if start_time is not None:
            conditions.append("timestamp_start >= ?")
            params.append(start_time)
        if end_time is not None:
            conditions.append("timestamp_end <= ?")
            params.append(end_time)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM activity_heartbeat {where_clause} ORDER BY timestamp_start ASC;"

        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [ActivityHeartbeat.from_row(row) for row in rows]

    def count(self) -> int:
        """Count total activity records in the database."""
        query = "SELECT COUNT(*) FROM activity_heartbeat;"
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            return row[0] if row else 0


# Convenience functional API
def initialize_database(db_path: Optional[Union[str, Path]] = None) -> None:
    """Initialize database tables and indexes."""
    ActivityRepository(db_path).initialize()


def insert_record(record: ActivityHeartbeat, db_path: Optional[Union[str, Path]] = None) -> int:
    """Insert an activity record."""
    return ActivityRepository(db_path).insert(record)


def get_records_by_time_range(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> List[ActivityHeartbeat]:
    """Retrieve activity records within an optional time range."""
    return ActivityRepository(db_path).get_records(start_time=start_time, end_time=end_time)


def count_records(db_path: Optional[Union[str, Path]] = None) -> int:
    """Count total activity records."""
    return ActivityRepository(db_path).count()
