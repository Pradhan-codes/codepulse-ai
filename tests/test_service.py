"""Unit tests for ActivityCollectorService."""

from datetime import datetime, timezone
from pathlib import Path
import time
import pytest

from codepulse.collector.service import ActivityCollectorService
from codepulse.collector.window_sensor import WindowObservation
from codepulse.config import Settings
from codepulse.storage.repository import ActivityRepository


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Fixture providing a temporary database file."""
    return tmp_path / "test_service.db"


@pytest.fixture
def temp_repo(temp_db_path: Path) -> ActivityRepository:
    """Fixture providing an initialized ActivityRepository on temp DB."""
    repo = ActivityRepository(db_path=temp_db_path)
    repo.initialize()
    return repo


def test_one_collection_cycle(temp_repo: ActivityRepository):
    """Test executing a single collection cycle without switching activity."""
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    obs = WindowObservation(timestamp=t0, process_name="Code.exe", window_title="main.py")

    service = ActivityCollectorService(
        repository=temp_repo,
        window_sensor_fn=lambda: obs,
        idle_sensor_fn=lambda threshold: False,
        flush_interval_seconds=300,
    )

    # First cycle starts an active block; nothing finalized yet
    result = service.run_once()
    assert result is None
    assert temp_repo.count() == 0


def test_activity_changes_and_repository_persistence(temp_repo: ActivityRepository):
    """Test that switching foreground activity finalizes and persists the previous record."""
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 17, 10, 0, 30, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 17, 10, 0, 45, tzinfo=timezone.utc)

    current_obs = WindowObservation(timestamp=t0, process_name="Code.exe", window_title="app.py")

    service = ActivityCollectorService(
        repository=temp_repo,
        window_sensor_fn=lambda: current_obs,
        idle_sensor_fn=lambda threshold: False,
        flush_interval_seconds=300,
    )

    # 1. Cycle 1: VS Code at t0
    service.run_once()
    assert temp_repo.count() == 0

    # 2. Cycle 2: VS Code at t1 (same activity, accumulated duration)
    current_obs = WindowObservation(timestamp=t1, process_name="Code.exe", window_title="app.py")
    service.run_once()
    assert temp_repo.count() == 0

    # 3. Cycle 3: Switch to Chrome at t2 (triggers persistence of VS Code record)
    current_obs = WindowObservation(timestamp=t2, process_name="chrome.exe", window_title="Documentation - MDN Web Docs")
    finalized = service.run_once()

    assert finalized is not None
    assert finalized.process_name == "Code.exe"
    assert finalized.window_title == "app.py"
    assert finalized.category == "Coding"
    assert finalized.duration_seconds == 30.0
    assert temp_repo.count() == 1

    records = temp_repo.get_records()
    assert len(records) == 1
    assert records[0].process_name == "Code.exe"
    assert records[0].duration_seconds == 30.0


def test_idle_observation(temp_repo: ActivityRepository):
    """Test that entering idle state finalizes active work and records idle session."""
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 17, 10, 1, 0, tzinfo=timezone.utc)

    current_obs = WindowObservation(timestamp=t0, process_name="Code.exe", window_title="app.py")
    idle_state = False

    service = ActivityCollectorService(
        repository=temp_repo,
        window_sensor_fn=lambda: current_obs,
        idle_sensor_fn=lambda threshold: idle_state,
        flush_interval_seconds=300,
    )

    # Active work
    service.run_once()

    # Transition to idle
    idle_state = True
    current_obs = WindowObservation(timestamp=t1, process_name="Code.exe", window_title="app.py")
    persisted = service.run_once()

    assert persisted is not None
    assert persisted.is_idle is False
    assert temp_repo.count() == 1

    # Flush should store the idle block
    flushed_idle = service.flush()
    assert flushed_idle is not None
    assert flushed_idle.is_idle is True
    assert flushed_idle.category == "Idle"
    assert temp_repo.count() == 2


def test_manual_and_periodic_flush(temp_repo: ActivityRepository):
    """Test manual flush and periodic automatic flush after timeout."""
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    obs = WindowObservation(timestamp=t0, process_name="Code.exe", window_title="app.py")

    service = ActivityCollectorService(
        repository=temp_repo,
        window_sensor_fn=lambda: obs,
        idle_sensor_fn=lambda threshold: False,
        flush_interval_seconds=60,
    )

    service.run_once()
    assert temp_repo.count() == 0

    # Manual flush
    flushed = service.flush()
    assert flushed is not None
    assert flushed.process_name == "Code.exe"
    assert temp_repo.count() == 1

    # Second flush immediately is a no-op
    assert service.flush() is None
    assert temp_repo.count() == 1

    # Simulate periodic flush by manipulating _last_flush_time
    service.run_once()
    assert temp_repo.count() == 1
    service._last_flush_time = time.time() - 100  # Older than 60s
    service.run_once()
    assert temp_repo.count() == 2


def test_start_and_stop_lifecycle(temp_repo: ActivityRepository):
    """Test starting and stopping the background collection thread."""
    obs = WindowObservation(process_name="Code.exe", window_title="index.py")

    service = ActivityCollectorService(
        repository=temp_repo,
        window_sensor_fn=lambda: obs,
        idle_sensor_fn=lambda threshold: False,
        polling_interval_seconds=1,
    )

    assert not service.is_running
    service.start()
    assert service.is_running

    # Calling start again while running is a safe no-op
    service.start()
    assert service.is_running

    time.sleep(0.05)
    service.stop()

    assert not service.is_running
    # On stop, flush should have persisted the active block
    assert temp_repo.count() >= 1


def test_configurable_polling_interval_and_threshold(temp_db_path: Path):
    """Test configuring polling interval and idle threshold."""
    custom_settings = Settings(
        db_path=temp_db_path,
        polling_interval_seconds=10,
        idle_threshold_seconds=240,
    )

    service = ActivityCollectorService(settings=custom_settings)
    assert service.polling_interval_seconds == 10
    assert service.idle_threshold_seconds == 240

    # Direct override in constructor takes precedence
    custom_service = ActivityCollectorService(
        settings=custom_settings,
        polling_interval_seconds=2,
        idle_threshold_seconds=60,
    )
    assert custom_service.polling_interval_seconds == 2
    assert custom_service.idle_threshold_seconds == 60


def test_error_in_polling_cycle_does_not_kill_service(temp_repo: ActivityRepository):
    """Test that exceptions during a poll cycle are handled safely without crashing."""
    call_count = 0

    def flaky_sensor():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Temporary Windows API error")
        return WindowObservation(process_name="Code.exe", window_title="fixed.py")

    service = ActivityCollectorService(
        repository=temp_repo,
        window_sensor_fn=flaky_sensor,
        idle_sensor_fn=lambda threshold: False,
    )

    # 1st call raises, should be caught and return None
    res1 = service.run_once()
    assert res1 is None

    # 2nd call succeeds normally
    res2 = service.run_once()
    assert res2 is None
    flushed = service.flush()
    assert flushed is not None
    assert flushed.process_name == "Code.exe"
    assert temp_repo.count() == 1
