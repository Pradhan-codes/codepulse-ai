"""Database and persistent storage modules."""

from codepulse.storage.db import get_connection, get_db_path, init_db
from codepulse.storage.models import ActivityHeartbeat
from codepulse.storage.repository import (
    ActivityRepository,
    count_records,
    get_records_by_time_range,
    initialize_database,
    insert_record,
)

__all__ = [
    "ActivityHeartbeat",
    "ActivityRepository",
    "count_records",
    "get_connection",
    "get_db_path",
    "get_records_by_time_range",
    "init_db",
    "initialize_database",
    "insert_record",
]
