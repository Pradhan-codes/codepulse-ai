"""Windows Idle Sensor for CodePulse.

Detects how long the user has been idle (no keyboard or mouse input)
using the Windows GetLastInputInfo API via ctypes.

Privacy note: This module only measures elapsed idle TIME.
It does NOT log keystrokes, mouse positions, or input contents.
"""

import ctypes
import ctypes.wintypes
import sys


def get_idle_seconds() -> float:
    """Return the number of seconds since the user's last keyboard or mouse input.

    Uses the Windows GetLastInputInfo API to read the system tick count
    of the most recent physical input event, then compares it to the
    current tick count.

    Returns:
        Seconds of idle time as a float, or 0.0 if the API is unavailable.
    """
    if sys.platform != "win32":
        return 0.0

    try:
        # LASTINPUTINFO struct: cbSize (UINT) + dwTime (DWORD)
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("dwTime", ctypes.wintypes.DWORD),
            ]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)

        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0

        current_tick = ctypes.windll.kernel32.GetTickCount()

        # GetTickCount returns milliseconds; convert to seconds
        elapsed_ms = current_tick - lii.dwTime
        # Handle the rare 49.7-day tick count rollover
        if elapsed_ms < 0:
            elapsed_ms = 0

        return elapsed_ms / 1000.0
    except Exception:
        return 0.0


def is_idle(threshold_seconds: int = 180) -> bool:
    """Check whether the user has been idle longer than the given threshold.

    Args:
        threshold_seconds: Number of seconds of inactivity before the user
            is considered idle. Defaults to 180 (3 minutes), matching the
            value in codepulse.config.Settings.

    Returns:
        True if idle time >= threshold, False otherwise.
    """
    return get_idle_seconds() >= threshold_seconds


class IdleSensor:
    """Sensor interface for checking user idle state."""

    def __init__(self, threshold_seconds: int = 180):
        self.threshold_seconds = threshold_seconds

    def get_idle_seconds(self) -> float:
        """Return seconds since last user input."""
        return get_idle_seconds()

    def is_idle(self) -> bool:
        """Return True if the user has been idle past the configured threshold."""
        return is_idle(self.threshold_seconds)
