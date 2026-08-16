"""Tests for CodePulse foundation and configuration."""

import pytest
import codepulse
from codepulse.config import Settings, settings
from codepulse.main import main, print_banner


def test_package_metadata():
    """Verify package name and version are defined."""
    assert codepulse.__version__ == "0.1.0"
    assert codepulse.__app_name__ == "CodePulse"


def test_default_settings():
    """Verify default configuration values."""
    s = Settings()
    assert s.app_name == "CodePulse"
    assert s.polling_interval_seconds == 5
    assert s.idle_threshold_seconds == 180
    assert s.api_host == "127.0.0.1"
    assert s.api_port == 8000
    assert s.gemini_model == "gemini-2.5-flash"


def test_settings_from_env(monkeypatch):
    """Verify settings can be loaded from environment variables."""
    monkeypatch.setenv("CODEPULSE_POLL_INTERVAL", "10")
    monkeypatch.setenv("CODEPULSE_IDLE_THRESHOLD", "300")
    monkeypatch.setenv("CODEPULSE_API_PORT", "9000")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")

    s = Settings.from_env()
    assert s.polling_interval_seconds == 10
    assert s.idle_threshold_seconds == 300
    assert s.api_port == 9000
    assert s.gemini_api_key == "test-key-123"


def test_main_cli_execution(capsys):
    """Verify that running main() exits cleanly and prints startup banner."""
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "CodePulse v0.1.0" in captured.out
    assert "Foundation initialized" in captured.out
