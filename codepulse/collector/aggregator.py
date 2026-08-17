"""Heartbeat Aggregator for CodePulse.

Receives window observations, classifications, and idle state updates,
and aggregates continuous active periods into ActivityHeartbeat records.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Union

from codepulse.collector.classifier import Category, ClassificationResult, classify
from codepulse.collector.window_sensor import WindowObservation
from codepulse.storage.models import ActivityHeartbeat


def _normalize_datetime(dt: Union[datetime, str, float, int]) -> datetime:
    """Ensure timestamps are timezone-aware UTC datetime objects."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    if isinstance(dt, (int, float)):
        return datetime.fromtimestamp(dt, tz=timezone.utc)
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def _normalize_category(
    category: Optional[Union[Category, ClassificationResult, str]],
    process_name: str = "",
    window_title: str = "",
    is_idle: bool = False,
) -> str:
    """Normalize category input into a standard string category name."""
    if is_idle:
        return Category.IDLE.value

    if category is None:
        return classify(process_name, window_title, is_idle).category.value
    if isinstance(category, ClassificationResult):
        return category.category.value
    if isinstance(category, Category):
        return category.value
    if isinstance(category, str):
        try:
            return Category[category.upper()].value
        except (KeyError, AttributeError):
            return category
    return str(category)


@dataclass
class _ActiveBlock:
    """In-memory representation of an ongoing activity session."""

    start_time: datetime
    end_time: datetime
    process_name: str
    window_title: str
    category: str
    project_name: Optional[str]
    is_idle: bool

    def matches(
        self,
        process_name: str,
        window_title: str,
        category: str,
        project_name: Optional[str],
        is_idle: bool,
    ) -> bool:
        """Check if incoming observation attributes match the current active block."""
        return (
            self.process_name == process_name
            and self.window_title == window_title
            and self.category == category
            and self.project_name == project_name
            and self.is_idle == is_idle
        )

    def update_timestamp(self, dt: datetime) -> None:
        """Update time range safely, expanding bounds even if out-of-order."""
        if dt < self.start_time:
            self.start_time = dt
        if dt > self.end_time:
            self.end_time = dt

    def to_heartbeat(self) -> ActivityHeartbeat:
        """Convert the block to an ActivityHeartbeat record."""
        duration = max(0.0, (self.end_time - self.start_time).total_seconds())
        return ActivityHeartbeat(
            timestamp_start=self.start_time.isoformat(),
            timestamp_end=self.end_time.isoformat(),
            duration_seconds=duration,
            process_name=self.process_name,
            window_title=self.window_title,
            category=self.category,
            project_name=self.project_name,
            is_idle=self.is_idle,
        )


class HeartbeatAggregator:
    """Aggregates continuous window observations into completed activity heartbeats."""

    def __init__(self) -> None:
        self._current_block: Optional[_ActiveBlock] = None

    @property
    def has_active_block(self) -> bool:
        """Check whether an active observation block is currently open."""
        return self._current_block is not None

    def add_observation(
        self,
        observation: Optional[Union[WindowObservation, datetime, str]] = None,
        process_name: Optional[str] = None,
        window_title: Optional[str] = None,
        category: Optional[Union[Category, ClassificationResult, str]] = None,
        project_name: Optional[str] = None,
        is_idle: bool = False,
        timestamp: Optional[Union[datetime, str, float, int]] = None,
    ) -> Optional[ActivityHeartbeat]:
        """
        Ingest an observation.

        If the observation matches the ongoing block, the block's end timestamp is updated
        and None is returned.

        If the observation differs in identity (process, window, category, project, idle),
        the previous block is finalized and returned, and a new block is started.
        """
        # 1. Extract observation fields
        if isinstance(observation, WindowObservation):
            obs_time = timestamp if timestamp is not None else observation.timestamp
            proc = process_name if process_name is not None else observation.process_name
            title = window_title if window_title is not None else observation.window_title
        else:
            obs_time = timestamp if timestamp is not None else (observation or datetime.now(timezone.utc))
            proc = process_name if process_name is not None else "Unknown"
            title = window_title if window_title is not None else ""

        dt = _normalize_datetime(obs_time)
        norm_category = _normalize_category(
            category=category,
            process_name=proc,
            window_title=title,
            is_idle=is_idle,
        )

        # 2. If no active block, initialize one
        if self._current_block is None:
            self._current_block = _ActiveBlock(
                start_time=dt,
                end_time=dt,
                process_name=proc,
                window_title=title,
                category=norm_category,
                project_name=project_name,
                is_idle=is_idle,
            )
            return None

        # 3. If matching existing block, expand timestamp range
        if self._current_block.matches(
            process_name=proc,
            window_title=title,
            category=norm_category,
            project_name=project_name,
            is_idle=is_idle,
        ):
            self._current_block.update_timestamp(dt)
            return None

        # 4. Identity changed — finalize previous block and start new one
        completed_heartbeat = self._current_block.to_heartbeat()

        self._current_block = _ActiveBlock(
            start_time=dt,
            end_time=dt,
            process_name=proc,
            window_title=title,
            category=norm_category,
            project_name=project_name,
            is_idle=is_idle,
        )

        return completed_heartbeat

    def update_observation(
        self,
        observation: Optional[Union[WindowObservation, datetime, str]] = None,
        process_name: Optional[str] = None,
        window_title: Optional[str] = None,
        category: Optional[Union[Category, ClassificationResult, str]] = None,
        project_name: Optional[str] = None,
        is_idle: bool = False,
        timestamp: Optional[Union[datetime, str, float, int]] = None,
    ) -> Optional[ActivityHeartbeat]:
        """Alias for add_observation."""
        return self.add_observation(
            observation=observation,
            process_name=process_name,
            window_title=window_title,
            category=category,
            project_name=project_name,
            is_idle=is_idle,
            timestamp=timestamp,
        )

    def start_observation(
        self,
        observation: Optional[Union[WindowObservation, datetime, str]] = None,
        process_name: Optional[str] = None,
        window_title: Optional[str] = None,
        category: Optional[Union[Category, ClassificationResult, str]] = None,
        project_name: Optional[str] = None,
        is_idle: bool = False,
        timestamp: Optional[Union[datetime, str, float, int]] = None,
    ) -> Optional[ActivityHeartbeat]:
        """
        Explicitly start a new observation block.
        Finalizes and returns any existing active block before starting the new one.
        """
        previous = self.finalize_current_block()
        self.add_observation(
            observation=observation,
            process_name=process_name,
            window_title=window_title,
            category=category,
            project_name=project_name,
            is_idle=is_idle,
            timestamp=timestamp,
        )
        return previous

    def finalize_current_block(self) -> Optional[ActivityHeartbeat]:
        """
        Finalize and return the current active block, resetting active block to None.
        Returns None if there is no active block.
        """
        if self._current_block is None:
            return None

        heartbeat = self._current_block.to_heartbeat()
        self._current_block = None
        return heartbeat

    def flush(self) -> Optional[ActivityHeartbeat]:
        """Flush the current active block. Alias for finalize_current_block."""
        return self.finalize_current_block()

    def reset(self) -> None:
        """Reset the aggregator, discarding any active in-memory block."""
        self._current_block = None
