"""Activity collection and Windows sensor modules."""

from codepulse.collector.aggregator import HeartbeatAggregator
from codepulse.collector.classifier import (
    ActivityClassifier,
    Category,
    ClassificationResult,
    classify,
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
    "HeartbeatAggregator",
    "IdleSensor",
    "WindowObservation",
    "WindowSensor",
    "classify",
    "get_active_window",
    "get_idle_seconds",
    "is_idle",
]
