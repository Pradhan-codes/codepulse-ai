"""Unit tests for HeartbeatAggregator."""

from datetime import datetime, timedelta, timezone
import pytest

from codepulse.collector.aggregator import HeartbeatAggregator
from codepulse.collector.classifier import Category, ClassificationResult
from codepulse.collector.window_sensor import WindowObservation


def test_empty_aggregator():
    """Test that an empty aggregator has no active block and flushes None."""
    agg = HeartbeatAggregator()
    assert not agg.has_active_block
    assert agg.finalize_current_block() is None
    assert agg.flush() is None


def test_first_observation():
    """Test that the first observation initializes an active block without finalizing."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)

    obs = WindowObservation(
        timestamp=t0,
        process_name="Code.exe",
        window_title="codepulse - VS Code",
    )

    result = agg.add_observation(obs, category=Category.CODING, project_name="codepulse")

    assert result is None
    assert agg.has_active_block

    # Flush should return the single observation with 0s duration
    flushed = agg.flush()
    assert flushed is not None
    assert flushed.process_name == "Code.exe"
    assert flushed.window_title == "codepulse - VS Code"
    assert flushed.category == "Coding"
    assert flushed.project_name == "codepulse"
    assert flushed.duration_seconds == 0.0
    assert flushed.timestamp_start == t0.isoformat()
    assert flushed.timestamp_end == t0.isoformat()
    assert not agg.has_active_block


def test_consecutive_same_observations():
    """Test that consecutive identical observations accumulate duration."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=5)
    t2 = t0 + timedelta(seconds=15)

    # 1. First observation
    res0 = agg.add_observation(
        process_name="Code.exe",
        window_title="app.py",
        category=Category.CODING,
        timestamp=t0,
    )
    assert res0 is None

    # 2. Second observation at +5s
    res1 = agg.add_observation(
        process_name="Code.exe",
        window_title="app.py",
        category=Category.CODING,
        timestamp=t1,
    )
    assert res1 is None

    # 3. Third observation at +15s
    res2 = agg.update_observation(
        process_name="Code.exe",
        window_title="app.py",
        category=Category.CODING,
        timestamp=t2,
    )
    assert res2 is None

    # Flush
    flushed = agg.flush()
    assert flushed is not None
    assert flushed.duration_seconds == 15.0
    assert flushed.timestamp_start == t0.isoformat()
    assert flushed.timestamp_end == t2.isoformat()


def test_window_title_change():
    """Test that changing window title finalizes previous block and begins a new one."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=30)
    t2 = t0 + timedelta(seconds=45)

    # Coding on app.py for 30 seconds
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t0)
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t1)

    # Switched to tests.py
    finished_block = agg.add_observation(
        process_name="Code.exe",
        window_title="tests.py",
        category=Category.CODING,
        timestamp=t2,
    )

    assert finished_block is not None
    assert finished_block.window_title == "app.py"
    assert finished_block.duration_seconds == 30.0
    assert finished_block.timestamp_start == t0.isoformat()
    assert finished_block.timestamp_end == t1.isoformat()

    # Flush the active new block (tests.py)
    flushed = agg.flush()
    assert flushed is not None
    assert flushed.window_title == "tests.py"
    assert flushed.duration_seconds == 0.0
    assert flushed.timestamp_start == t2.isoformat()


def test_category_change():
    """Test that changing category on same app finalizes previous block."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=20)
    t2 = t0 + timedelta(seconds=25)

    agg.add_observation(process_name="chrome.exe", window_title="Tab", category=Category.DOCUMENTATION, timestamp=t0)
    agg.add_observation(process_name="chrome.exe", window_title="Tab", category=Category.DOCUMENTATION, timestamp=t1)

    finished = agg.add_observation(
        process_name="chrome.exe",
        window_title="Tab",
        category=Category.DISTRACTION,
        timestamp=t2,
    )

    assert finished is not None
    assert finished.category == "Documentation"
    assert finished.duration_seconds == 20.0

    current = agg.flush()
    assert current is not None
    assert current.category == "Distraction"


def test_idle_transition():
    """Test transitioning from active to idle state and back."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=60)
    t2 = t0 + timedelta(seconds=180)
    t3 = t0 + timedelta(seconds=300)
    t4 = t0 + timedelta(seconds=360)

    # 1. Active coding for 60s
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, is_idle=False, timestamp=t0)
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, is_idle=False, timestamp=t1)

    # 2. User goes idle at t2
    idle_start = agg.add_observation(
        process_name="Code.exe",
        window_title="app.py",
        category=Category.CODING,
        is_idle=True,
        timestamp=t2,
    )
    assert idle_start is not None
    assert idle_start.is_idle is False
    assert idle_start.duration_seconds == 60.0

    # User remains idle at t3
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, is_idle=True, timestamp=t3)

    # 3. User comes back active at t4
    active_back = agg.add_observation(
        process_name="Code.exe",
        window_title="app.py",
        category=Category.CODING,
        is_idle=False,
        timestamp=t4,
    )
    assert active_back is not None
    assert active_back.is_idle is True
    assert active_back.category == "Idle"
    assert active_back.duration_seconds == 120.0  # from t2 (180s) to t3 (300s)

    # Flush active block
    final_active = agg.flush()
    assert final_active is not None
    assert final_active.is_idle is False


def test_project_name_change():
    """Test that project_name change triggers block finalization."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=40)

    agg.add_observation(process_name="Code.exe", window_title="main.py", category=Category.CODING, project_name="project-a", timestamp=t0)
    finished = agg.add_observation(
        process_name="Code.exe",
        window_title="main.py",
        category=Category.CODING,
        project_name="project-b",
        timestamp=t1,
    )

    assert finished is not None
    assert finished.project_name == "project-a"
    assert finished.duration_seconds == 0.0

    current = agg.flush()
    assert current is not None
    assert current.project_name == "project-b"


def test_timestamp_gaps():
    """Test duration calculation over large time gaps."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)  # 900 seconds gap

    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t0)
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t1)

    flushed = agg.flush()
    assert flushed is not None
    assert flushed.duration_seconds == 900.0


def test_out_of_order_timestamps():
    """Test that out-of-order timestamps expand the bounds and never produce negative durations."""
    agg = HeartbeatAggregator()
    t_mid = datetime(2026, 8, 17, 10, 5, 0, tzinfo=timezone.utc)
    t_early = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 8, 17, 10, 10, 0, tzinfo=timezone.utc)

    # First observe at 10:05
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t_mid)
    # Then observe at 10:00 (earlier)
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t_early)
    # Then observe at 10:10 (later)
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t_late)

    flushed = agg.flush()
    assert flushed is not None
    assert flushed.timestamp_start == t_early.isoformat()
    assert flushed.timestamp_end == t_late.isoformat()
    assert flushed.duration_seconds == 600.0
    assert flushed.duration_seconds >= 0.0


def test_start_observation_explicit():
    """Test start_observation explicitly finalizes previous and starts fresh."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=10)

    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t0)
    prev = agg.start_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING, timestamp=t1)

    assert prev is not None
    assert prev.timestamp_start == t0.isoformat()
    assert agg.has_active_block


def test_reset():
    """Test reset clears in-memory state."""
    agg = HeartbeatAggregator()
    agg.add_observation(process_name="Code.exe", window_title="app.py", category=Category.CODING)
    assert agg.has_active_block

    agg.reset()
    assert not agg.has_active_block
    assert agg.flush() is None


def test_window_observation_input_and_classification_result():
    """Test passing WindowObservation and ClassificationResult directly."""
    agg = HeartbeatAggregator()
    t0 = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
    obs = WindowObservation(timestamp=t0, process_name="cursor.exe", window_title="main.py")
    clf = ClassificationResult(category=Category.CODING, matched_rule="Cursor editor")

    agg.add_observation(observation=obs, category=clf)
    flushed = agg.flush()

    assert flushed is not None
    assert flushed.process_name == "cursor.exe"
    assert flushed.category == "Coding"
