import shutil
import subprocess
from fastapi import APIRouter
from app.schemas.common import HealthResponse
from app.settings import get_settings
from app.storage.database import get_database

router = APIRouter(tags=["Health"])


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


@router.get("/api/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Readiness probe for KAGE AI frontend without disclosing sensitive credentials.
    Conforms to frontend classifyHealth schema expectations.
    """
    settings = get_settings()
    docker_ready = check_docker_available()
    model_ready = bool(settings.anthropic_base_url and settings.anthropic_api_key)

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

