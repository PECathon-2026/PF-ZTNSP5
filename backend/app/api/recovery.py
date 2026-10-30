"""Read checkpoint, explicitly extend ceilings, and claim a guarded continuation."""

from fastapi import APIRouter, HTTPException, Query
from app.api.missions import get_mission
from app.schemas.recovery import BudgetExtensionRequest, ContinueMissionRequest
from app.services.guild_service import get_guild_controller
from app.services.recovery_service import RecoveryService
from app.services.workspace_service import WriterLeaseError
from app.security.paths import PathSecurityError
from app.storage.guild import GuildConflict

router = APIRouter(prefix="/api/missions", tags=["Recovery"])


async def invoke(method, mission_id, request=None):
    service = RecoveryService(get_guild_controller())
    try:
        function = getattr(service, method)
        return await function(mission_id, request) if request is not None else await function(mission_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Mission or recovery checkpoint not found") from None
    except (GuildConflict, WriterLeaseError, PathSecurityError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc) if isinstance(exc, GuildConflict) else "Recovery files or ownership changed; refresh the checkpoint") from None


@router.get("/{mission_id}/recovery")
async def inspect_recovery(mission_id: str):
    return await invoke("inspect", mission_id)


@router.post("/{mission_id}/budget-extension")
async def extend_budget(mission_id: str, request: BudgetExtensionRequest):
    return await invoke("extend_budget", mission_id, request)


@router.post("/{mission_id}/continue", status_code=202)
async def continue_mission(mission_id: str, request: ContinueMissionRequest):
    await invoke("continue_mission", mission_id, request)
    return await get_mission(mission_id)


@router.get("/{mission_id}/recovery/file")
async def recovery_file(mission_id: str, checkpoint_token: str = Query(pattern=r"^[0-9a-f]{64}$"), path: str = Query(min_length=1, max_length=500)):
    try:
        return await RecoveryService(get_guild_controller()).read_partial_file(mission_id, checkpoint_token, path)
    except KeyError:
        raise HTTPException(status_code=404, detail="Mission not found") from None
    except (GuildConflict, PathSecurityError, OSError, ValueError):
        raise HTTPException(status_code=409, detail="Recovery file or checkpoint changed; refresh inspection") from None
