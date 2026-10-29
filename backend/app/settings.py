import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env if present
load_dotenv()


class Settings(BaseModel):
    """DevPilot / KAGE AI Application Settings."""

    # Server configuration
    host: str = Field(default_factory=lambda: os.getenv("DEVPILOT_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("DEVPILOT_PORT", "8000")))
    debug: bool = Field(default_factory=lambda: os.getenv("DEVPILOT_DEBUG", "false").lower() == "true")

    # Storage paths
    data_dir: Path = Field(default_factory=lambda: Path(os.getenv("DEVPILOT_DATA_DIR", "./data")))
    db_path: Path = Field(default_factory=lambda: Path(os.getenv("DEVPILOT_DB_PATH", "./data/devpilot.db")))
    artifacts_dir: Path = Field(default_factory=lambda: Path(os.getenv("DEVPILOT_ARTIFACTS_DIR", "./data/artifacts")))

    # Model configuration (Server-Side Only)
    anthropic_base_url: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_BASE_URL", "https://api.argmin.run/v1"))
    anthropic_api_key: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model_name: str = Field(default_factory=lambda: os.getenv("DEVPILOT_MODEL", "claude-3-5-sonnet-20241022"))

    # Execution & Limits
    docker_image: str = Field(default_factory=lambda: os.getenv("DEVPILOT_DOCKER_IMAGE", "python:3.12-slim"))
    max_repair_rounds: int = Field(default_factory=lambda: int(os.getenv("DEVPILOT_MAX_REPAIR_ROUNDS", "3")))
    check_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("DEVPILOT_CHECK_TIMEOUT_SECONDS", "60")))
    max_file_size_bytes: int = Field(default_factory=lambda: int(os.getenv("DEVPILOT_MAX_FILE_SIZE_BYTES", "524288")))  # 512 KB

    def ensure_directories(self) -> None:
        """Ensure runtime storage directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        if self.db_path.parent:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Retrieve or create singleton application settings."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
        _settings_instance.ensure_directories()
    return _settings_instance
