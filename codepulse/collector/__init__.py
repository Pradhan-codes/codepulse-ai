"""Activity collection and Windows sensor modules."""

from codepulse.collector.window_sensor import (
    WindowObservation,
    WindowSensor,
    get_active_window,
)
from codepulse.collector.idle_sensor import (
    IdleSensor,
    get_idle_seconds,
    is_idle,
)
from codepulse.collector.classifier import (
    ActivityClassifier,
    Category,
    ClassificationResult,
    classify,
)

__all__ = [
    "WindowObservation",
    "WindowSensor",
    "get_active_window",
    "IdleSensor",
    "get_idle_seconds",
    "is_idle",
    "ActivityClassifier",
    "Category",
    "ClassificationResult",
    "classify",
]
