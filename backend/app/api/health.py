import shutil
import subprocess
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, SecretStr, Field
from app.agents.model_adapter import ModelAdapterError
from app.api.credential_route import CredentialSafeRoute
from app.services.mission_credentials import check_model_connection
from app.schemas.common import HealthResponse
from app.settings import get_settings
from app.storage.database import get_database

router = APIRouter(tags=["Health"], route_class=CredentialSafeRoute)


class CheckModelCredentials(BaseModel):
    api_key: SecretStr = Field(repr=False, exclude=True)
    base_url: str | None = Field(default=None, max_length=2048, repr=False, exclude=True)


@router.post("/api/model-config/validate")
async def validate_model_config(request: CheckModelCredentials):
    """Make one small model request to verify key, endpoint and provider protocol."""
    try:
        settings = await check_model_connection(request.api_key.get_secret_value(), request.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ModelAdapterError:
        raise HTTPException(status_code=400, detail="Provider did not accept the API key, model or base URL; check its configuration.") from None
    return {"valid": True, "provider": settings.model_provider, "model": settings.configured_model_name}


def check_docker_available() -> bool:
    """Safely checks if Docker CLI exists and Linux Engine daemon responds."""
    if not shutil.which("docker"):
        return False
    try:
        # Run docker info with short timeout
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        )
        return result.returncode == 0
    except Exception:
        return False


@router.get("/api/model-config")
async def get_model_config():
    settings = get_settings()
    return {"provider": settings.model_provider, "model": settings.configured_model_name,
            "endpoint_configured": bool(settings.model_base_url and settings.configured_model_name)}


@router.get("/api/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Readiness probe for KAGE AI frontend without disclosing sensitive credentials.
    Conforms to frontend classifyHealth schema expectations.
    """
    settings = get_settings()
    docker_ready = check_docker_available()
    model_ready = settings.model_configured

    # Check active missions count
    db = get_database()
    active_count = 0
    try:
        missions = await db.list_missions(limit=10)
        active_count = sum(1 for m in missions if m.status not in ["APPLIED", "REJECTED", "CANCELLED", "BLOCKED"])
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        service="kage-backend",
        version="0.1.0",
        docker_available=docker_ready,
        model_configured=model_ready,
        storage_ready=True,
        active_missions_count=active_count,
    )

