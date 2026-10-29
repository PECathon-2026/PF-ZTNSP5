from enum import Enum
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """System readiness without revealing credentials."""
    status: str = "ok"
    service: str = "kage-backend"
    version: str = "0.1.0"
    docker_available: bool = False
    model_configured: bool = False
    storage_ready: bool = True
    active_missions_count: int = 0


class PreflightStatus(str, Enum):
    READY = "READY"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    CHECKING = "CHECKING"


class PreflightResult(BaseModel):
    status: PreflightStatus
    detected_profile: str = "python_pytest"
    file_count: int = 0
    excluded_count: int = 0
    existing_modifications: bool = False
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None

