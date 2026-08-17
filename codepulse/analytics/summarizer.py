"""Daily summary generation for CodePulse.

Aggregates activity records and Git commit events into structured daily summaries.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from codepulse.analytics.metrics import ActivityMetrics, calculate_metrics
from codepulse.collector.git_sensor import GitCommit
from codepulse.storage.models import ActivityHeartbeat


@dataclass(frozen=True)
class DailySummary:
    """Summary of daily developer activity matching SQLite daily_summary schema."""

    date: str  # YYYY-MM-DD
    total_active_seconds: int
    coding_seconds: int
    research_seconds: int  # Documentation & research time
    communication_seconds: int
    distraction_seconds: int
    deep_work_seconds: int
    context_switches: int
    focus_score: float  # 0.0 to 100.0
    top_project: Optional[str] = None

    # Extended metrics
    deep_work_blocks: int = 0
    context_switch_index: float = 0.0
    git_commits_count: int = 0
    git_files_changed: int = 0
    git_insertions: int = 0
    git_deletions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert daily summary to a dictionary."""
        return {
            "date": self.date,
            "total_active_seconds": self.total_active_seconds,
            "coding_seconds": self.coding_seconds,
            "research_seconds": self.research_seconds,
            "communication_seconds": self.communication_seconds,
            "distraction_seconds": self.distraction_seconds,
            "deep_work_seconds": self.deep_work_seconds,
            "context_switches": self.context_switches,
            "focus_score": self.focus_score,
            "top_project": self.top_project,
            "deep_work_blocks": self.deep_work_blocks,
            "context_switch_index": self.context_switch_index,
            "git_commits_count": self.git_commits_count,
            "git_files_changed": self.git_files_changed,
            "git_insertions": self.git_insertions,
            "git_deletions": self.git_deletions,
        }

    @classmethod
    def from_row(cls, row: Any) -> "DailySummary":
        """Construct DailySummary from a database row or dict."""
        if hasattr(row, "keys"):
            return cls(
                date=row["date"],
                total_active_seconds=int(row["total_active_seconds"]),
                coding_seconds=int(row["coding_seconds"]),
                research_seconds=int(row["research_seconds"]),
                communication_seconds=int(row["communication_seconds"]),
                distraction_seconds=int(row["distraction_seconds"]),
                deep_work_seconds=int(row["deep_work_seconds"]),
                context_switches=int(row["context_switches"]),
                focus_score=float(row["focus_score"]),
                top_project=row["top_project"] if "top_project" in row.keys() else None,
            )
        return cls(
            date=row[0],
            total_active_seconds=int(row[1]),
            coding_seconds=int(row[2]),
            research_seconds=int(row[3]),
            communication_seconds=int(row[4]),
            distraction_seconds=int(row[5]),
            deep_work_seconds=int(row[6]),
            context_switches=int(row[7]),
            focus_score=float(row[8]),
            top_project=row[9] if len(row) > 9 else None,
        )


def summarize_git_commits(git_commits: Optional[Iterable[GitCommit]] = None) -> Dict[str, int]:
    """Aggregate statistics from Git commit events."""
    if not git_commits:
        return {
            "count": 0,
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
        }

    count = 0
    files_changed = 0
    insertions = 0
    deletions = 0

    for c in git_commits:
        count += 1
        files_changed += max(0, c.files_changed)
        insertions += max(0, c.insertions)
        deletions += max(0, c.deletions)

    return {
        "count": count,
        "files_changed": files_changed,
        "insertions": insertions,
        "deletions": deletions,
    }


def generate_daily_summary(
    records: Iterable[ActivityHeartbeat],
    git_commits: Optional[Iterable[GitCommit]] = None,
    date: Optional[str] = None,
) -> DailySummary:
    """Generate a DailySummary from activity heartbeats and optional Git commits.

    Args:
        records: Collection of ActivityHeartbeat items for the day.
        git_commits: Optional collection of Git commits made during the day.
        date: Target date string (YYYY-MM-DD). If omitted, inferred from records/commits or UTC today.

    Returns:
        A populated DailySummary instance.
    """
    records_list = list(records)
    metrics: ActivityMetrics = calculate_metrics(records_list)
    git_stats = summarize_git_commits(git_commits)

    # Infer date if not provided
    resolved_date = date
    if not resolved_date:
        if records_list and records_list[0].timestamp_start:
            resolved_date = records_list[0].timestamp_start[:10]
        elif git_commits:
            commits_list = list(git_commits)
            if commits_list and commits_list[0].timestamp:
                resolved_date = commits_list[0].timestamp[:10]
        if not resolved_date:
            resolved_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return DailySummary(
        date=resolved_date,
        total_active_seconds=int(round(metrics.total_active_seconds)),
        coding_seconds=int(round(metrics.coding_seconds)),
        research_seconds=int(round(metrics.documentation_seconds)),
        communication_seconds=int(round(metrics.communication_seconds)),
        distraction_seconds=int(round(metrics.distraction_seconds)),
        deep_work_seconds=int(round(metrics.deep_work_seconds)),
        deep_work_blocks=metrics.deep_work_blocks,
        context_switches=metrics.context_switches,
        context_switch_index=metrics.context_switch_index,
        focus_score=metrics.focus_score,
        top_project=metrics.top_project,
        git_commits_count=git_stats["count"],
        git_files_changed=git_stats["files_changed"],
        git_insertions=git_stats["insertions"],
        git_deletions=git_stats["deletions"],
    )
