"""Analytics and productivity metrics modules."""

from codepulse.analytics.metrics import (
    ActivityMetrics,
    calculate_category_durations,
    calculate_context_switches,
    calculate_deep_work,
    calculate_focus_score,
    calculate_metrics,
    is_coding_category,
    is_communication_category,
    is_distraction_category,
    is_documentation_category,
    is_work_category,
)
from codepulse.analytics.summarizer import (
    DailySummary,
    generate_daily_summary,
    summarize_git_commits,
)

__all__ = [
    "ActivityMetrics",
    "DailySummary",
    "calculate_category_durations",
    "calculate_context_switches",
    "calculate_deep_work",
    "calculate_focus_score",
    "calculate_metrics",
    "generate_daily_summary",
    "is_coding_category",
    "is_communication_category",
    "is_distraction_category",
    "is_documentation_category",
    "is_work_category",
    "summarize_git_commits",
]
