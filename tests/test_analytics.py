"""Unit tests for CodePulse Analytics V1."""

from datetime import datetime, timedelta, timezone
import pytest

from codepulse.analytics.metrics import (
    calculate_category_durations,
    calculate_context_switches,
    calculate_deep_work,
    calculate_focus_score,
    calculate_metrics,
)
from codepulse.analytics.summarizer import (
    DailySummary,
    generate_daily_summary,
    summarize_git_commits,
)
from codepulse.collector.git_sensor import GitCommit
from codepulse.storage.models import ActivityHeartbeat


def test_empty_and_zero_active_data():
    """Test metrics calculation on empty records and idle-only records."""
    metrics_empty = calculate_metrics([])
    assert metrics_empty.total_active_seconds == 0.0
    assert metrics_empty.coding_seconds == 0.0
    assert metrics_empty.deep_work_seconds == 0.0
    assert metrics_empty.deep_work_blocks == 0
    assert metrics_empty.context_switches == 0
    assert metrics_empty.context_switch_index == 0.0
    assert metrics_empty.focus_score == 0.0
    assert metrics_empty.top_project is None

    # Idle-only record
    idle_rec = ActivityHeartbeat(
        timestamp_start="2026-08-17T10:00:00Z",
        timestamp_end="2026-08-17T10:30:00Z",
        duration_seconds=1800.0,
        process_name="None",
        window_title="",
        category="Idle",
        is_idle=True,
    )
    metrics_idle = calculate_metrics([idle_rec])
    assert metrics_idle.total_active_seconds == 0.0
    assert metrics_idle.focus_score == 0.0


def test_category_durations_and_idle_exclusion():
    """Test summing category durations and ignoring idle records."""
    records = [
        ActivityHeartbeat("2026-08-17T10:00:00Z", "2026-08-17T10:30:00Z", 1800.0, "Code.exe", "Coding", project_name="proj-a"),
        ActivityHeartbeat("2026-08-17T10:30:00Z", "2026-08-17T10:45:00Z", 900.0, "chrome.exe", "Documentation", project_name="proj-a"),
        ActivityHeartbeat("2026-08-17T10:45:00Z", "2026-08-17T11:00:00Z", 900.0, "slack.exe", "Communication"),
        ActivityHeartbeat("2026-08-17T11:00:00Z", "2026-08-17T11:15:00Z", 900.0, "chrome.exe", "Distraction"),
        ActivityHeartbeat("2026-08-17T11:15:00Z", "2026-08-17T11:20:00Z", 300.0, "explorer.exe", "Other"),
        ActivityHeartbeat("2026-08-17T11:20:00Z", "2026-08-17T12:00:00Z", 2400.0, "None", "Idle", is_idle=True),
    ]

    total, coding, doc, comm, dist, other, top_proj = calculate_category_durations(records)

    assert coding == 1800.0
    assert doc == 900.0
    assert comm == 900.0
    assert dist == 900.0
    assert other == 300.0
    assert total == 4800.0  # 1800+900+900+900+300 (idle excluded)
    assert top_proj == "proj-a"


def test_deep_work_qualifying_session():
    """Test deep work >= 25 minutes (1500 seconds)."""
    t0 = datetime(2026, 8, 17, 9, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=30)  # 1800 seconds

    records = [
        ActivityHeartbeat(
            timestamp_start=t0.isoformat(),
            timestamp_end=t1.isoformat(),
            duration_seconds=1800.0,
            process_name="Code.exe",
            category="Coding",
        )
    ]

    deep_sec, blocks = calculate_deep_work(records)
    assert blocks == 1
    assert deep_sec == 1800.0


def test_deep_work_below_threshold():
    """Test sessions under 25 minutes do not count as deep work blocks."""
    t0 = datetime(2026, 8, 17, 9, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=20)  # 1200 seconds (< 1500s)

    records = [
        ActivityHeartbeat(
            timestamp_start=t0.isoformat(),
            timestamp_end=t1.isoformat(),
            duration_seconds=1200.0,
            process_name="Code.exe",
            category="Coding",
        )
    ]

    deep_sec, blocks = calculate_deep_work(records)
    assert blocks == 0
    assert deep_sec == 0.0


def test_deep_work_with_short_interruption():
    """Test deep work with an interruption <= 60 seconds merges into 1 block."""
    t0 = datetime(2026, 8, 17, 9, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)  # 900s
    t2 = t1 + timedelta(seconds=30)  # 30s interruption (Slack)
    t3 = t2 + timedelta(minutes=15)  # 900s (MDN docs)

    records = [
        ActivityHeartbeat(t0.isoformat(), t1.isoformat(), 900.0, "Code.exe", "Coding"),
        ActivityHeartbeat(t1.isoformat(), t2.isoformat(), 30.0, "Slack.exe", "Communication"),
        ActivityHeartbeat(t2.isoformat(), t3.isoformat(), 900.0, "chrome.exe", "Documentation"),
    ]

    deep_sec, blocks = calculate_deep_work(records)
    assert blocks == 1
    assert deep_sec >= 1800.0


def test_deep_work_with_long_interruption():
    """Test deep work with an interruption > 60 seconds splits the blocks."""
    t0 = datetime(2026, 8, 17, 9, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)  # 15 min coding
    t2 = t1 + timedelta(minutes=5)   # 5 min interruption (> 60s)
    t3 = t2 + timedelta(minutes=15)  # 15 min coding

    records = [
        ActivityHeartbeat(t0.isoformat(), t1.isoformat(), 900.0, "Code.exe", "Coding"),
        ActivityHeartbeat(t1.isoformat(), t2.isoformat(), 300.0, "Slack.exe", "Communication"),
        ActivityHeartbeat(t2.isoformat(), t3.isoformat(), 900.0, "Code.exe", "Coding"),
    ]

    deep_sec, blocks = calculate_deep_work(records)
    assert blocks == 0
    assert deep_sec == 0.0


def test_context_switches_calculation():
    """Test detecting Work -> Non-Work -> Work transitions within 10 minutes."""
    t0 = datetime(2026, 8, 17, 9, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=2)   # 2 min YouTube
    t3 = t2 + timedelta(minutes=10)  # Back to coding (switch 1)
    t4 = t3 + timedelta(minutes=1)   # 1 min Slack
    t5 = t4 + timedelta(minutes=10)  # Back to coding (switch 2)

    records = [
        ActivityHeartbeat(t0.isoformat(), t1.isoformat(), 600.0, "Code.exe", "Coding"),
        ActivityHeartbeat(t1.isoformat(), t2.isoformat(), 120.0, "chrome.exe", "Distraction"),
        ActivityHeartbeat(t2.isoformat(), t3.isoformat(), 600.0, "Code.exe", "Coding"),
        ActivityHeartbeat(t3.isoformat(), t4.isoformat(), 60.0, "Slack.exe", "Communication"),
        ActivityHeartbeat(t4.isoformat(), t5.isoformat(), 600.0, "chrome.exe", "Documentation"),
    ]

    switches = calculate_context_switches(records)
    assert switches == 2


def test_focus_score_formula():
    """Test Focus Score calculation and clamping to 0-100."""
    # Perfect coding with 0 CSI
    score_perfect = calculate_focus_score(
        coding_seconds=3600.0,
        documentation_seconds=0.0,
        total_active_seconds=3600.0,
        context_switch_index=0.0,
    )
    assert score_perfect == 100.0

    # Mixed coding & docs with CSI penalty
    # (5400 + 0.8 * 1800) / 7200 = 6840 / 7200 = 0.95 (95.0)
    # CSI = 2.0 -> Penalty = 2.0 * 2.5 = 5.0
    # Final = 95.0 - 5.0 = 90.0
    score_mixed = calculate_focus_score(
        coding_seconds=5400.0,
        documentation_seconds=1800.0,
        total_active_seconds=7200.0,
        context_switch_index=2.0,
    )
    assert score_mixed == 90.0

    # Excessive distraction clamping to 0
    score_zero = calculate_focus_score(
        coding_seconds=0.0,
        documentation_seconds=0.0,
        total_active_seconds=3600.0,
        context_switch_index=10.0,
    )
    assert score_zero == 0.0


def test_unsorted_records_handling():
    """Test that metrics calculation works correctly when records are out of order."""
    t0 = datetime(2026, 8, 17, 9, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)
    t2 = t1 + timedelta(minutes=15)

    rec1 = ActivityHeartbeat(t0.isoformat(), t1.isoformat(), 900.0, "Code.exe", "Coding")
    rec2 = ActivityHeartbeat(t1.isoformat(), t2.isoformat(), 900.0, "Code.exe", "Coding")

    # Pass in reverse order
    metrics = calculate_metrics([rec2, rec1])
    assert metrics.total_active_seconds == 1800.0
    assert metrics.coding_seconds == 1800.0
    assert metrics.deep_work_blocks == 1
    assert metrics.deep_work_seconds == 1800.0


def test_generate_daily_summary_and_git_stats():
    """Test complete daily summary generation including Git commit metrics."""
    records = [
        ActivityHeartbeat("2026-08-17T09:00:00Z", "2026-08-17T10:00:00Z", 3600.0, "Code.exe", "Coding", project_name="codepulse"),
        ActivityHeartbeat("2026-08-17T10:00:00Z", "2026-08-17T10:30:00Z", 1800.0, "chrome.exe", "Documentation", project_name="codepulse"),
    ]

    git_commits = [
        GitCommit("hash1", "2026-08-17T09:30:00Z", "feat: metrics", "codepulse", "main", files_changed=3, insertions=150, deletions=20),
        GitCommit("hash2", "2026-08-17T10:15:00Z", "docs: update", "codepulse", "main", files_changed=1, insertions=10, deletions=2),
    ]

    summary = generate_daily_summary(records, git_commits=git_commits)

    assert summary.date == "2026-08-17"
    assert summary.total_active_seconds == 5400
    assert summary.coding_seconds == 3600
    assert summary.research_seconds == 1800
    assert summary.top_project == "codepulse"
    assert summary.git_commits_count == 2
    assert summary.git_files_changed == 4
    assert summary.git_insertions == 160
    assert summary.git_deletions == 22

    # Test serialization and deserialization
    d = summary.to_dict()
    assert d["git_commits_count"] == 2
    from_db = DailySummary.from_row(d)
    assert from_db.date == "2026-08-17"
    assert from_db.focus_score == summary.focus_score
