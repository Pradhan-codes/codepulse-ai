"""Deterministic analytics metrics calculation for CodePulse.

Computes total active time, category breakdowns, deep work blocks,
context-switching metrics, and focus score from ActivityHeartbeat records.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

from codepulse.storage.models import ActivityHeartbeat


@dataclass(frozen=True)
class ActivityMetrics:
    """Structured metrics calculated from activity heartbeats."""

    total_active_seconds: float
    coding_seconds: float
    documentation_seconds: float
    communication_seconds: float
    distraction_seconds: float
    other_seconds: float
    deep_work_seconds: float
    deep_work_blocks: int
    context_switches: int
    context_switch_index: float
    focus_score: float
    top_project: Optional[str] = None


def is_coding_category(category: str) -> bool:
    """Return True if category represents active coding/development."""
    cat = (category or "").strip().lower()
    return cat in ("coding", "development", "dev")


def is_documentation_category(category: str) -> bool:
    """Return True if category represents documentation or technical research."""
    cat = (category or "").strip().lower()
    return cat in ("documentation", "research", "docs")


def is_work_category(category: str) -> bool:
    """Return True if category is productive work (Coding or Documentation)."""
    return is_coding_category(category) or is_documentation_category(category)


def is_communication_category(category: str) -> bool:
    """Return True if category represents team or email communication."""
    cat = (category or "").strip().lower()
    return cat in ("communication", "comms")


def is_distraction_category(category: str) -> bool:
    """Return True if category represents distraction or non-work sites."""
    cat = (category or "").strip().lower()
    return cat in ("distraction", "distractions")


def _parse_iso_timestamp(ts: str) -> datetime:
    """Parse ISO timestamp string into a timezone-aware UTC datetime."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def _sort_records(records: Iterable[ActivityHeartbeat]) -> List[ActivityHeartbeat]:
    """Sort heartbeats by start timestamp ascending."""
    return sorted(
        records,
        key=lambda r: _parse_iso_timestamp(r.timestamp_start),
    )


def calculate_category_durations(
    records: Iterable[ActivityHeartbeat],
) -> Tuple[float, float, float, float, float, float, Optional[str]]:
    """Calculate cumulative durations for each category and identify top project.

    Returns:
        Tuple of (total_active, coding, documentation, communication, distraction, other, top_project)
    """
    coding_sec = 0.0
    doc_sec = 0.0
    comm_sec = 0.0
    dist_sec = 0.0
    other_sec = 0.0
    project_durations: defaultdict[str, float] = defaultdict(float)

    for r in records:
        if r.is_idle or (r.category or "").strip().lower() == "idle":
            continue

        duration = max(0.0, float(r.duration_seconds))
        if duration <= 0:
            continue

        cat = r.category or "Other"
        if is_coding_category(cat):
            coding_sec += duration
        elif is_documentation_category(cat):
            doc_sec += duration
        elif is_communication_category(cat):
            comm_sec += duration
        elif is_distraction_category(cat):
            dist_sec += duration
        else:
            other_sec += duration

        if r.project_name:
            project_durations[r.project_name] += duration

    total_active_sec = coding_sec + doc_sec + comm_sec + dist_sec + other_sec

    top_project = None
    if project_durations:
        top_project = max(project_durations.items(), key=lambda item: item[1])[0]

    return (
        total_active_sec,
        coding_sec,
        doc_sec,
        comm_sec,
        dist_sec,
        other_sec,
        top_project,
    )


def calculate_deep_work(
    records: Iterable[ActivityHeartbeat],
    min_block_seconds: float = 1500.0,  # 25 minutes
    max_interruption_seconds: float = 60.0,  # 1 minute
) -> Tuple[float, int]:
    """Identify uninterrupted deep work blocks and total deep work duration.

    A deep work block is continuous Coding/Documentation work >= 25 minutes,
    permitting brief interruptions of <= 60 seconds.

    Returns:
        Tuple of (deep_work_seconds, deep_work_blocks_count)
    """
    sorted_records = _sort_records(records)
    if not sorted_records:
        return 0.0, 0

    total_deep_work_seconds = 0.0
    deep_work_blocks_count = 0

    block_start_dt: Optional[datetime] = None
    block_end_dt: Optional[datetime] = None
    block_work_duration: float = 0.0

    def finalize_current_block() -> None:
        nonlocal total_deep_work_seconds, deep_work_blocks_count, block_start_dt, block_end_dt, block_work_duration
        if block_start_dt is not None and block_end_dt is not None:
            span_seconds = max(0.0, (block_end_dt - block_start_dt).total_seconds())
            if span_seconds >= min_block_seconds or block_work_duration >= min_block_seconds:
                deep_work_blocks_count += 1
                total_deep_work_seconds += span_seconds

        block_start_dt = None
        block_end_dt = None
        block_work_duration = 0.0

    for r in sorted_records:
        if r.is_idle or (r.category or "").strip().lower() == "idle":
            continue

        r_start = _parse_iso_timestamp(r.timestamp_start)
        r_end = _parse_iso_timestamp(r.timestamp_end)
        r_duration = max(0.0, float(r.duration_seconds))

        if is_work_category(r.category):
            if block_start_dt is None:
                # Start new candidate deep work block
                block_start_dt = r_start
                block_end_dt = r_end
                block_work_duration = r_duration
            else:
                # Calculate interruption between last work end and current work start
                assert block_end_dt is not None
                interruption = max(0.0, (r_start - block_end_dt).total_seconds())
                if interruption <= max_interruption_seconds:
                    # Continue ongoing deep work block
                    if r_end > block_end_dt:
                        block_end_dt = r_end
                    block_work_duration += r_duration
                else:
                    # Interruption exceeded threshold — close previous and start new
                    finalize_current_block()
                    block_start_dt = r_start
                    block_end_dt = r_end
                    block_work_duration = r_duration
        else:
            # Non-work active record (e.g. Communication or Distraction)
            if block_start_dt is not None and block_end_dt is not None:
                # If non-work record extends past the interruption threshold, finalize block
                interruption = max(0.0, (r_end - block_end_dt).total_seconds())
                if interruption > max_interruption_seconds:
                    finalize_current_block()

    finalize_current_block()
    return total_deep_work_seconds, deep_work_blocks_count


def calculate_context_switches(
    records: Iterable[ActivityHeartbeat],
    max_switch_window_seconds: float = 600.0,  # 10 minutes
) -> int:
    """Calculate work-to-distraction/communication context switches.

    A context switch is counted when activity transitions from Work -> Non-Work -> Work
    within a 10-minute window.
    """
    sorted_records = _sort_records(records)
    active_records = [
        r for r in sorted_records
        if not r.is_idle and (r.category or "").strip().lower() != "idle"
    ]

    if len(active_records) < 3:
        return 0

    context_switches = 0
    in_work_state = False
    last_work_end_dt: Optional[datetime] = None
    saw_non_work_interruption = False

    for r in active_records:
        r_start = _parse_iso_timestamp(r.timestamp_start)
        r_end = _parse_iso_timestamp(r.timestamp_end)

        if is_work_category(r.category):
            if in_work_state and saw_non_work_interruption and last_work_end_dt is not None:
                gap = (r_start - last_work_end_dt).total_seconds()
                if 0 <= gap <= max_switch_window_seconds:
                    context_switches += 1

            in_work_state = True
            saw_non_work_interruption = False
            last_work_end_dt = r_end
        else:
            # Non-work active category
            if in_work_state:
                saw_non_work_interruption = True

    return context_switches


def calculate_focus_score(
    coding_seconds: float,
    documentation_seconds: float,
    total_active_seconds: float,
    context_switch_index: float,
) -> float:
    """Compute the 0-100 Focus Score.

    Formula:
        Score = ((Coding + 0.8 * Docs) / TotalActive) * 100 - (CSI * 2.5)
        Clamped to [0.0, 100.0].
    """
    if total_active_seconds <= 0:
        return 0.0

    work_ratio = (coding_seconds + 0.8 * documentation_seconds) / total_active_seconds
    raw_score = (work_ratio * 100.0) - (context_switch_index * 2.5)
    return round(max(0.0, min(100.0, raw_score)), 2)


def calculate_metrics(records: Iterable[ActivityHeartbeat]) -> ActivityMetrics:
    """Calculate all productivity metrics from a collection of activity heartbeats."""
    (
        total_active,
        coding,
        doc,
        comm,
        dist,
        other,
        top_project,
    ) = calculate_category_durations(records)

    deep_work_sec, deep_work_blocks = calculate_deep_work(records)
    context_switches = calculate_context_switches(records)

    active_hours = total_active / 3600.0
    csi = round(context_switches / active_hours, 2) if active_hours > 0 else 0.0

    focus_score = calculate_focus_score(
        coding_seconds=coding,
        documentation_seconds=doc,
        total_active_seconds=total_active,
        context_switch_index=csi,
    )

    return ActivityMetrics(
        total_active_seconds=total_active,
        coding_seconds=coding,
        documentation_seconds=doc,
        communication_seconds=comm,
        distraction_seconds=dist,
        other_seconds=other,
        deep_work_seconds=deep_work_sec,
        deep_work_blocks=deep_work_blocks,
        context_switches=context_switches,
        context_switch_index=csi,
        focus_score=focus_score,
        top_project=top_project,
    )
