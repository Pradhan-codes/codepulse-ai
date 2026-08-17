"""Data models for CodePulse storage."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ActivityHeartbeat:
    """Represents an aggregated activity heartbeat record."""

    timestamp_start: str
    timestamp_end: str
    duration_seconds: float
    process_name: str
    category: str
    window_title: Optional[str] = ""
    project_name: Optional[str] = None
    is_idle: bool = False
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the heartbeat to a dictionary."""
        return {
            "id": self.id,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "duration_seconds": self.duration_seconds,
            "process_name": self.process_name,
            "window_title": self.window_title,
            "category": self.category,
            "project_name": self.project_name,
            "is_idle": self.is_idle,
        }

    @classmethod
    def from_row(cls, row: Any) -> "ActivityHeartbeat":
        """Construct an ActivityHeartbeat from a sqlite3.Row or dictionary/tuple."""
        if hasattr(row, "keys"):
            return cls(
                id=row["id"],
                timestamp_start=row["timestamp_start"],
                timestamp_end=row["timestamp_end"],
                duration_seconds=float(row["duration_seconds"]),
                process_name=row["process_name"],
                window_title=row["window_title"] or "",
                category=row["category"],
                project_name=row["project_name"],
                is_idle=bool(row["is_idle"]),
            )
        return cls(
            id=row[0],
            timestamp_start=row[1],
            timestamp_end=row[2],
            duration_seconds=float(row[3]),
            process_name=row[4],
            window_title=row[5] or "",
            category=row[6],
            project_name=row[7],
            is_idle=bool(row[8]),
        )
