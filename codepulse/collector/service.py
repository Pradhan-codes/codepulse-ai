"""Activity Collector Service for CodePulse.

Orchestrates window sensor, idle sensor, classifier, heartbeat aggregator,
and SQLite persistence in a clean, background polling lifecycle.
"""

import logging
from pathlib import Path
import threading
import time
from typing import Callable, Optional, Union

from codepulse.collector.aggregator import HeartbeatAggregator
from codepulse.collector.classifier import classify
from codepulse.collector.idle_sensor import is_idle as check_is_idle
from codepulse.collector.window_sensor import WindowObservation, get_active_window
from codepulse.config import Settings, settings as default_settings
from codepulse.storage.models import ActivityHeartbeat
from codepulse.storage.repository import ActivityRepository

logger = logging.getLogger(__name__)


class ActivityCollectorService:
    """Orchestrates continuous collection of desktop activity."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        repository: Optional[ActivityRepository] = None,
        aggregator: Optional[HeartbeatAggregator] = None,
        window_sensor_fn: Optional[Callable[[], WindowObservation]] = None,
        idle_sensor_fn: Optional[Callable[[int], bool]] = None,
        polling_interval_seconds: Optional[int] = None,
        idle_threshold_seconds: Optional[int] = None,
        flush_interval_seconds: int = 60,
        db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.settings = settings or default_settings
        resolved_db_path = db_path if db_path is not None else self.settings.db_path
        self.repository = repository or ActivityRepository(db_path=resolved_db_path)
        self.aggregator = aggregator or HeartbeatAggregator()
        self.window_sensor_fn = window_sensor_fn or get_active_window
        self.idle_sensor_fn = idle_sensor_fn or check_is_idle

        self.polling_interval_seconds = (
            polling_interval_seconds
            if polling_interval_seconds is not None
            else self.settings.polling_interval_seconds
        )
        self.idle_threshold_seconds = (
            idle_threshold_seconds
            if idle_threshold_seconds is not None
            else self.settings.idle_threshold_seconds
        )
        self.flush_interval_seconds = flush_interval_seconds

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_flush_time: float = time.time()
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """Return True if background collection thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def run_once(self) -> Optional[ActivityHeartbeat]:
        """
        Execute a single observation cycle.

        1. Query window sensor
        2. Query idle sensor
        3. Classify activity
        4. Ingest into aggregator
        5. Persist finalized heartbeat (if state changed or periodic flush triggered)

        Returns:
            The finalized ActivityHeartbeat if one was produced and stored, else None.
        """
        with self._lock:
            finalized_record: Optional[ActivityHeartbeat] = None
            try:
                # 1. Active window observation
                obs = self.window_sensor_fn()

                # 2. Idle state
                idle = self.idle_sensor_fn(self.idle_threshold_seconds)

                # 3. Classify
                classification = classify(
                    process_name=obs.process_name,
                    window_title=obs.window_title,
                    is_idle=idle,
                )

                # 4. Aggregator ingest
                finalized_record = self.aggregator.add_observation(
                    observation=obs,
                    category=classification.category,
                    is_idle=idle,
                )

                # 5. Persist if state changed and finalized
                if finalized_record is not None:
                    self.repository.insert(finalized_record)
                    self._last_flush_time = time.time()

                # 6. Check periodic flush interval
                now = time.time()
                if (now - self._last_flush_time) >= self.flush_interval_seconds:
                    flushed = self.aggregator.flush()
                    if flushed is not None:
                        self.repository.insert(flushed)
                        finalized_record = flushed
                    self._last_flush_time = now

            except Exception as e:
                logger.error("Error during collection cycle: %s", e, exc_info=True)

            return finalized_record

    def flush(self) -> Optional[ActivityHeartbeat]:
        """
        Force-flush the active observation block and persist to repository.

        Returns:
            The flushed ActivityHeartbeat if an active block existed, else None.
        """
        with self._lock:
            record = self.aggregator.flush()
            if record is not None:
                self.repository.insert(record)
                self._last_flush_time = time.time()
            return record

    def start(self) -> None:
        """Start background activity collection thread."""
        with self._lock:
            if self.is_running:
                logger.warning("ActivityCollectorService is already running.")
                return

            # Ensure repository database schema is initialized
            self.repository.initialize()

            self._stop_event.clear()
            self._last_flush_time = time.time()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="CodePulse-CollectorThread",
                daemon=True,
            )
            self._thread.start()
            logger.info(
                "ActivityCollectorService started (poll=%ds, idle_threshold=%ds, flush=%ds).",
                self.polling_interval_seconds,
                self.idle_threshold_seconds,
                self.flush_interval_seconds,
            )

    def stop(self, timeout: float = 2.0) -> None:
        """
        Stop the background collection thread cleanly and flush any active block.
        """
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        # Flush any remaining observation on exit
        self.flush()
        logger.info("ActivityCollectorService stopped.")

    def _run_loop(self) -> None:
        """Internal background polling loop."""
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.error("Unhandled error in collector loop: %s", e, exc_info=True)

            # Wait for next poll interval or until stop_event is triggered
            if self._stop_event.wait(timeout=self.polling_interval_seconds):
                break
