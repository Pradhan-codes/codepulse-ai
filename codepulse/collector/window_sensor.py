"""Windows Active Window Sensor for CodePulse.

Captures foreground window title, process ID, and process executable name
using Windows Win32 APIs with robust error handling for edge cases.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Optional


@dataclass(frozen=True)
class WindowObservation:
    """Represents an immutable snapshot of the active foreground window."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    process_name: str = "Unknown"
    window_title: str = ""
    process_id: Optional[int] = None

    @property
    def is_valid(self) -> bool:
        """Returns True if a valid process or window title was detected."""
        return self.process_name != "Unknown" or bool(self.window_title)


def get_process_name_by_pid(pid: int) -> str:
    """Retrieve executable filename from process ID using Win32 APIs.

    Args:
        pid: The target process ID.

    Returns:
        The executable file name (e.g. 'Code.exe') or 'Unknown' if inaccessible.
    """
    if not pid or pid <= 0:
        return "Unknown"

    # Strategy 1: pywin32 OpenProcess + GetModuleFileNameEx
    try:
        import win32api
        import win32con
        import win32process

        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
            False,
            pid,
        )
        try:
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            if exe_path:
                return Path(exe_path).name
        finally:
            win32api.CloseHandle(handle)
    except Exception:
        pass

    # Strategy 2: ctypes QueryFullProcessImageNameW (supports elevated/UWP apps with limited query)
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            pid,
        )
        if handle:
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(1024)
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                    handle, 0, buf, ctypes.byref(size)
                ):
                    return Path(buf.value).name
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass

    return "Unknown"


def get_active_window() -> WindowObservation:
    """Capture the current foreground window observation on Windows.

    Returns:
        WindowObservation with current timestamp, process name, window title, and PID.
    """
    now = datetime.now(timezone.utc)

    if sys.platform != "win32":
        return WindowObservation(
            timestamp=now,
            process_name="Unknown",
            window_title="",
            process_id=None,
        )

    try:
        import win32gui
        import win32process
    except ImportError:
        return WindowObservation(
            timestamp=now,
            process_name="Unknown",
            window_title="",
            process_id=None,
        )

    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or hwnd <= 0:
            return WindowObservation(
                timestamp=now,
                process_name="Unknown",
                window_title="",
                process_id=None,
            )

        # 1. Retrieve window title
        title = ""
        try:
            raw_title = win32gui.GetWindowText(hwnd)
            if raw_title:
                title = raw_title.strip()
        except Exception:
            title = ""

        # 2. Retrieve process ID
        pid: Optional[int] = None
        try:
            _, raw_pid = win32process.GetWindowThreadProcessId(hwnd)
            if raw_pid and raw_pid > 0:
                pid = raw_pid
        except Exception:
            pid = None

        # 3. Retrieve process executable name
        process_name = "Unknown"
        if pid:
            process_name = get_process_name_by_pid(pid)

        return WindowObservation(
            timestamp=now,
            process_name=process_name,
            window_title=title,
            process_id=pid,
        )
    except Exception:
        # Handle unexpected window destruction or permissions race condition
        return WindowObservation(
            timestamp=now,
            process_name="Unknown",
            window_title="",
            process_id=None,
        )


class WindowSensor:
    """Sensor interface for inspecting the active foreground window."""

    @staticmethod
    def get_current_window() -> WindowObservation:
        """Capture and return the current active window observation."""
        return get_active_window()
