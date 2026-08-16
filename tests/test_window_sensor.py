"""Tests for WindowSensor and WindowObservation."""

from datetime import datetime, timezone
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

from codepulse.collector.window_sensor import (
    WindowObservation,
    WindowSensor,
    get_active_window,
    get_process_name_by_pid,
)


def test_window_observation_defaults():
    """Verify WindowObservation default values and immutability."""
    obs = WindowObservation()
    assert obs.process_name == "Unknown"
    assert obs.window_title == ""
    assert obs.process_id is None
    assert isinstance(obs.timestamp, datetime)
    assert obs.is_valid is False

    # Check immutability (frozen dataclass)
    with pytest.raises(Exception):
        obs.process_name = "Code.exe"  # type: ignore


def test_window_observation_custom_values():
    """Verify WindowObservation with explicit parameters."""
    now = datetime.now(timezone.utc)
    obs = WindowObservation(
        timestamp=now,
        process_name="Code.exe",
        window_title="main.py - codepulse",
        process_id=1234,
    )
    assert obs.timestamp == now
    assert obs.process_name == "Code.exe"
    assert obs.window_title == "main.py - codepulse"
    assert obs.process_id == 1234
    assert obs.is_valid is True


def test_get_process_name_invalid_pid():
    """Verify get_process_name_by_pid returns Unknown for invalid PIDs."""
    assert get_process_name_by_pid(0) == "Unknown"
    assert get_process_name_by_pid(-1) == "Unknown"
    assert get_process_name_by_pid(None) == "Unknown"  # type: ignore


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only live API test")
def test_get_process_name_current_process():
    """Verify get_process_name_by_pid returns python for current running process."""
    current_pid = os.getpid()
    proc_name = get_process_name_by_pid(current_pid)
    assert "python" in proc_name.lower()


def test_get_process_name_exception_fallback():
    """Verify get_process_name_by_pid returns Unknown if Win32 API raises exception."""
    with patch("win32api.OpenProcess", side_effect=Exception("Access Denied")):
        name = get_process_name_by_pid(99999)
        assert name == "Unknown"


def test_get_active_window_non_windows_platform(monkeypatch):
    """Verify get_active_window returns fallback observation on non-Windows platforms."""
    monkeypatch.setattr(sys, "platform", "linux")
    obs = get_active_window()
    assert obs.process_name == "Unknown"
    assert obs.window_title == ""
    assert obs.process_id is None


def test_get_active_window_no_foreground_hwnd():
    """Verify get_active_window handles hwnd == 0 (e.g. lock screen)."""
    with patch("win32gui.GetForegroundWindow", return_value=0):
        obs = get_active_window()
        assert obs.process_name == "Unknown"
        assert obs.window_title == ""
        assert obs.process_id is None


def test_get_active_window_mocked_success():
    """Verify get_active_window successfully constructs observation from Win32 calls."""
    with patch("win32gui.GetForegroundWindow", return_value=12345), \
         patch("win32gui.GetWindowText", return_value="test.py - CodePulse - Visual Studio Code"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(100, 4321)), \
         patch("codepulse.collector.window_sensor.get_process_name_by_pid", return_value="Code.exe"):
        
        obs = get_active_window()
        assert obs.process_name == "Code.exe"
        assert obs.window_title == "test.py - CodePulse - Visual Studio Code"
        assert obs.process_id == 4321
        assert obs.is_valid is True


def test_get_active_window_window_disappeared_race_condition():
    """Verify get_active_window handles window destruction race condition gracefully."""
    with patch("win32gui.GetForegroundWindow", return_value=12345), \
         patch("win32gui.GetWindowText", side_effect=Exception("Invalid Window Handle")):
        
        obs = get_active_window()
        # Should not raise exception
        assert isinstance(obs, WindowObservation)


def test_window_sensor_interface():
    """Verify WindowSensor.get_current_window delegates correctly."""
    with patch("codepulse.collector.window_sensor.get_active_window") as mock_get:
        mock_get.return_value = WindowObservation(process_name="Code.exe", window_title="test")
        obs = WindowSensor.get_current_window()
        assert obs.process_name == "Code.exe"
        assert obs.window_title == "test"
        mock_get.assert_called_once()
