"""Tests for the Windows Idle Sensor."""

import sys
from unittest.mock import patch, MagicMock
import ctypes
import pytest

from codepulse.collector.idle_sensor import get_idle_seconds, is_idle, IdleSensor


# ---------------------------------------------------------------------------
# get_idle_seconds() tests
# ---------------------------------------------------------------------------

def test_get_idle_seconds_non_windows(monkeypatch):
    """On non-Windows platforms, get_idle_seconds returns 0.0."""
    monkeypatch.setattr(sys, "platform", "linux")
    assert get_idle_seconds() == 0.0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only live test")
def test_get_idle_seconds_returns_non_negative():
    """Live test: idle seconds should always be >= 0."""
    seconds = get_idle_seconds()
    assert isinstance(seconds, float)
    assert seconds >= 0.0


def test_get_idle_seconds_api_failure(monkeypatch):
    """If GetLastInputInfo fails, return 0.0 instead of raising."""
    monkeypatch.setattr(sys, "platform", "win32")

    mock_user32 = MagicMock()
    mock_user32.GetLastInputInfo.return_value = 0  # Simulates API failure

    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32

    with patch("ctypes.windll", mock_windll):
        result = get_idle_seconds()
        assert result == 0.0


# ---------------------------------------------------------------------------
# is_idle() tests
# ---------------------------------------------------------------------------

def test_is_idle_below_threshold():
    """User active for 10 seconds — should NOT be idle at 180s threshold."""
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=10.0):
        assert is_idle(180) is False


def test_is_idle_at_threshold():
    """Idle time exactly equals threshold — should be considered idle."""
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=180.0):
        assert is_idle(180) is True


def test_is_idle_above_threshold():
    """Idle time exceeds threshold — should be idle."""
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=300.0):
        assert is_idle(180) is True


def test_is_idle_custom_threshold():
    """Custom threshold of 60 seconds works correctly."""
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=59.0):
        assert is_idle(60) is False
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=60.0):
        assert is_idle(60) is True


def test_is_idle_zero_threshold():
    """Zero threshold means any idle time counts as idle."""
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=0.5):
        assert is_idle(0) is True


def test_is_idle_default_threshold():
    """Default threshold should be 180 seconds (3 minutes)."""
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=179.0):
        assert is_idle() is False
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=180.0):
        assert is_idle() is True


# ---------------------------------------------------------------------------
# IdleSensor class tests
# ---------------------------------------------------------------------------

def test_idle_sensor_class_custom_threshold():
    """IdleSensor class uses its configured threshold."""
    sensor = IdleSensor(threshold_seconds=60)
    assert sensor.threshold_seconds == 60

    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=59.0):
        assert sensor.is_idle() is False
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=60.0):
        assert sensor.is_idle() is True


def test_idle_sensor_class_get_idle_seconds():
    """IdleSensor.get_idle_seconds delegates to the module function."""
    sensor = IdleSensor()
    with patch("codepulse.collector.idle_sensor.get_idle_seconds", return_value=42.5):
        assert sensor.get_idle_seconds() == 42.5
