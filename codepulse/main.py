"""Entry point for the CodePulse application."""

import sys
from codepulse import __app_name__, __version__
from codepulse.config import settings


def print_banner() -> None:
    """Print startup banner and status."""
    banner = f"""
============================================================
  {__app_name__} v{__version__} - AI-Powered Developer Workflow Analytics
============================================================
  Status: Foundation initialized
  Database: {settings.db_path}
  Polling Interval: {settings.polling_interval_seconds}s
  Idle Threshold: {settings.idle_threshold_seconds}s
============================================================
"""
    print(banner.strip())


def main() -> int:
    """Main CLI entry point."""
    print_banner()
    print("\nCodePulse foundation is ready. Start building collectors and analytics!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
