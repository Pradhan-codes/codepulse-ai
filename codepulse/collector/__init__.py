"""Activity collection and Windows sensor modules."""

from codepulse.collector.window_sensor import (
    WindowObservation,
    WindowSensor,
    get_active_window,
)

__all__ = [
    "WindowObservation",
    "WindowSensor",
    "get_active_window",
]
