"""Activity collection and sensor modules."""

from codepulse.collector.aggregator import HeartbeatAggregator
from codepulse.collector.classifier import (
    ActivityClassifier,
    Category,
    ClassificationResult,
    classify,
)
from codepulse.collector.git_sensor import (
    GitCommit,
    GitSensor,
    get_current_branch,
    get_recent_commits,
    get_repo_name,
    is_git_repository,
)
from codepulse.collector.idle_sensor import (
    IdleSensor,
    get_idle_seconds,
    is_idle,
)
from codepulse.collector.service import ActivityCollectorService
from codepulse.collector.window_sensor import (
    WindowObservation,
    WindowSensor,
    get_active_window,
)

__all__ = [
    "ActivityClassifier",
    "ActivityCollectorService",
    "Category",
    "ClassificationResult",
    "GitCommit",
    "GitSensor",
    "HeartbeatAggregator",
    "IdleSensor",
    "WindowObservation",
    "WindowSensor",
    "classify",
    "get_active_window",
    "get_current_branch",
    "get_idle_seconds",
    "get_recent_commits",
    "get_repo_name",
    "is_git_repository",
    "is_idle",
]
