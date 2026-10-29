import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load backend-local configuration from either the workspace root or backend/.
# Explicit process environment still takes precedence.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
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
    model_provider: Literal["anthropic", "azure_openai"] = Field(default_factory=lambda: os.getenv("DEVPILOT_MODEL_PROVIDER", "anthropic"))
    anthropic_base_url: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_BASE_URL", "https://api.argmin.run/v1"))
    anthropic_api_key: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""), repr=False, exclude=True)
    model_name: str = Field(default_factory=lambda: os.getenv("DEVPILOT_MODEL", "claude-3-5-sonnet-20241022"))
    azure_openai_base_url: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_BASE_URL", ""))
    azure_openai_api_key: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""), repr=False, exclude=True)
    azure_openai_deployment: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT", ""))
    azure_openai_api: Literal["chat_completions", "responses"] = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_API", "chat_completions"))
    azure_openai_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_REASONING_EFFORT") or None
    )

    @property
    def model_base_url(self) -> str:
        return self.azure_openai_base_url if self.model_provider == "azure_openai" else self.anthropic_base_url

    @property
    def model_api_key(self) -> str:
        return self.azure_openai_api_key if self.model_provider == "azure_openai" else self.anthropic_api_key

    @property
    def configured_model_name(self) -> str:
        return self.azure_openai_deployment if self.model_provider == "azure_openai" else self.model_name

    @property
    def model_configured(self) -> bool:
        return bool(self.model_base_url and self.configured_model_name and self.model_api_key and self.model_api_key != "your_key_here")

    # Execution & Limits
    docker_image: str = Field(default_factory=lambda: os.getenv("DEVPILOT_DOCKER_IMAGE", "devpilot-checks:py312"))
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
