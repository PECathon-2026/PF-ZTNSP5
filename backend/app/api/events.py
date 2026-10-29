"""SQLite-backed SSE with monotonically sequenced replay and idle heartbeats."""

import asyncio
import json

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.storage.database import get_database
from app.security.redaction import redact_secrets

router = APIRouter(prefix="/api/missions", tags=["Mission events"])


def frame(event):
    # One named event keeps the browser listener stable while event_type remains
    # available in the persisted JSON envelope.
    data = redact_secrets(event.model_dump_json())
    if len(data) > 16000:
        data = json.dumps({"sequence": event.sequence, "mission_id": event.mission_id,
                           "event_type": event.event_type, "display_payload": {"truncated": True}})
    return f"id: {event.sequence}\nevent: mission\ndata: {data}\n\n"


async def event_stream(db, mission_id, request, cursor, interval=1):
    sequence = cursor
    idle = 0
    while not await request.is_disconnected():
        events = await db.get_events(mission_id, after_sequence=sequence)
        if events:
            for event in events:
                yield frame(event)
                sequence = event.sequence
            idle = 0
        else:
            idle += 1
            if idle >= 15:
                yield ": heartbeat\n\n"
                idle = 0
        await asyncio.sleep(interval)


@router.get("/{mission_id}/events")
async def mission_events(
    mission_id: str, request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    after: int | None = Query(default=None, ge=0),
):
    db = get_database()
    if not await db.get_mission(mission_id):
        raise HTTPException(status_code=404, detail="Mission not found")
    raw = last_event_id if last_event_id is not None else after
    try:
        cursor = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid event cursor") from None
    if cursor < 0:
        raise HTTPException(status_code=400, detail="Invalid event cursor")

    return StreamingResponse(event_stream(db, mission_id, request, cursor), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
    })
