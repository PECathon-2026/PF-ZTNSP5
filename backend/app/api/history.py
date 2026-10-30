"""Read-only, bounded historical activity and frozen-baseline inspection."""

import json

from fastapi import APIRouter, HTTPException, Query

from app.schemas.candidate import Candidate
from app.security.paths import PathSecurityError
from app.security.redaction import redact_secrets
from app.services.guild_service import get_guild_controller
from app.storage.database import get_database
from app.storage.guild import GuildStore
from app.tools.files import read_file

router = APIRouter(prefix="/api/missions", tags=["Mission history"])


@router.get("/{mission_id}/history")
async def mission_history(mission_id: str, after: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
    db = get_database()
    if not await db.get_mission(mission_id):
        raise HTTPException(status_code=404, detail="Mission not found")
    events = await db.get_events(mission_id, after_sequence=after, limit=limit)
    cursor = events[-1].sequence if events else after
    more = bool(await db.get_events(mission_id, after_sequence=cursor, limit=1))
    context = await GuildStore(db).context(mission_id) or {}
    # Use the same bounded, redacted envelope policy as SSE.
    from app.api.events import frame
    return {
        "events": [json.loads(frame(event).split("data: ", 1)[1].strip()) for event in events],
        "next_cursor": cursor,
        "has_more": more,
        "repository_name": redact_secrets(context.get("repository", {}).get("name", "")) or None,
    }


@router.get("/{mission_id}/baseline/file")
async def baseline_file(mission_id: str, path: str = Query(min_length=1, max_length=500)):
    controller = get_guild_controller()
    if not await controller.db.get_mission(mission_id):
        raise HTTPException(status_code=404, detail="Mission not found")
    context = await controller.store.context(mission_id) or {}
    baseline = next((c for c in await controller.store.records(Candidate, mission_id)
                     if c.id == context.get("baseline_candidate_id")), None)
    if not baseline:
        raise HTTPException(status_code=404, detail="Frozen baseline is not available")
    directory = controller.workspaces.get_candidate_dir(mission_id, baseline.id)
    try:
        controller.workspaces.validate_candidate(baseline)
    except (OSError, ValueError, PathSecurityError):
        raise HTTPException(status_code=409, detail="Frozen baseline is missing or changed") from None
    try:
        return read_file(directory, path)
    except PathSecurityError:
        raise HTTPException(status_code=403, detail="Path is outside the approved baseline") from None
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="File is missing or exceeds the read limit") from None
