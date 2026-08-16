"""Application configuration for CodePulse."""

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass
class Settings:
    """Core settings and default configuration values."""

    app_name: str = "CodePulse"
    version: str = "0.1.0"

    # Base Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    db_path: Path = field(default_factory=lambda: Path("codepulse.db"))

    # Tracking & Idle Defaults
    polling_interval_seconds: int = 5
    idle_threshold_seconds: int = 180  # 3 minutes

    # Server Defaults
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # AI Defaults
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings with optional environment variable overrides."""
        return cls(
            db_path=Path(os.getenv("CODEPULSE_DB_PATH", "codepulse.db")),
            polling_interval_seconds=int(os.getenv("CODEPULSE_POLL_INTERVAL", "5")),
            idle_threshold_seconds=int(os.getenv("CODEPULSE_IDLE_THRESHOLD", "180")),
            api_host=os.getenv("CODEPULSE_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("CODEPULSE_API_PORT", "8000")),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        )


settings = Settings.from_env()
