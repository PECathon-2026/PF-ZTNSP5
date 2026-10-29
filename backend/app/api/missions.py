import asyncio
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.schemas.mission import (
    AcceptanceCriterion,
    CreateMissionRequest,
    CriterionStatus,
    Mission,
    MissionStatus,
)
from app.schemas.task import MissionTask
from app.schemas.events import MissionEvent
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.approval import Approval
from app.storage.database import get_database

router = APIRouter(prefix="/api/missions", tags=["Missions"])


class MissionDetailResponse(BaseModel):
    mission: Mission
    criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    tasks: list[MissionTask] = Field(default_factory=list)


class MissionReportResponse(BaseModel):
    mission: Mission
    criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    tasks: list[MissionTask] = Field(default_factory=list)
    events: list[MissionEvent] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)


@router.post("", response_model=MissionDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(request: CreateMissionRequest) -> MissionDetailResponse:
    """Create a new mission and initialize its acceptance criteria."""
    db = get_database()

    mission = Mission(
        repository_id=request.repository_id,
        request_text=request.request_text,
        status=MissionStatus.PLANNING,
    )

    criteria_objects = [
        AcceptanceCriterion(
            mission_id=mission.id,
            description=crit_text,
            status=CriterionStatus.PENDING,
        )
        for crit_text in request.criteria
    ]

    await db.create_mission(mission, criteria_objects)

    # Emit creation event
    await db.emit_event(
        mission_id=mission.id,
        event_type="MISSION_CREATED",
        source="SYSTEM",
        display_payload={
            "title": "Mission initialized",
            "request": mission.request_text,
            "criteria_count": len(criteria_objects),
        },
    )

    return MissionDetailResponse(
        mission=mission,
        criteria=criteria_objects,
        tasks=[],
    )


@router.get("", response_model=list[Mission])
async def list_missions(limit: int = 50) -> list[Mission]:
    """List recent missions."""
    db = get_database()
    return await db.list_missions(limit=limit)


@router.get("/{mission_id}", response_model=MissionDetailResponse)
async def get_mission(mission_id: str) -> MissionDetailResponse:
    """Retrieve full mission state, criteria, and tasks."""
    db = get_database()
    mission = await db.get_mission(mission_id)
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission '{mission_id}' not found.",
        )

    criteria = await db.get_criteria(mission_id)
    tasks = await db.get_tasks(mission_id)

    return MissionDetailResponse(
        mission=mission,
        criteria=criteria,
        tasks=tasks,
    )


@router.post("/{mission_id}/cancel", response_model=MissionDetailResponse)
async def cancel_mission(mission_id: str) -> MissionDetailResponse:
    """Request mission cancellation and terminate active execution."""
    db = get_database()
    mission = await db.get_mission(mission_id)
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission '{mission_id}' not found.",
        )

    if mission.status in [MissionStatus.APPLIED, MissionStatus.REJECTED, MissionStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mission is already in terminal state '{mission.status.value}'.",
        )

    await db.update_mission_status(mission_id, MissionStatus.CANCELLED, failure_reason="Cancelled by user")

    await db.emit_event(
        mission_id=mission_id,
        event_type="MISSION_CANCELLED",
        source="SYSTEM",
        display_payload={"reason": "User requested cancellation"},
    )

    updated = await db.get_mission(mission_id)
    criteria = await db.get_criteria(mission_id)
    tasks = await db.get_tasks(mission_id)

    return MissionDetailResponse(
        mission=updated or mission,
        criteria=criteria,
        tasks=tasks,
    )


@router.get("/{mission_id}/report", response_model=MissionReportResponse)
async def get_mission_report(mission_id: str) -> MissionReportResponse:
    """
    Authoritative snapshot for the command center and evidence screens:
    mission, criteria, tasks, events, candidates, findings, evidence and approvals.
    """
    db = get_database()
    mission = await db.get_mission(mission_id)
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission '{mission_id}' not found.",
        )

    return MissionReportResponse(
        mission=mission,
        criteria=await db.get_criteria(mission_id),
        tasks=await db.get_tasks(mission_id),
        events=await db.get_events(mission_id, after_sequence=0),
        candidates=await db.get_candidates(mission_id),
        findings=await db.get_findings(mission_id),
        evidence=await db.get_evidence(mission_id),
        approvals=await db.get_approvals(mission_id),
    )


@router.get("/{mission_id}/events")
async def get_mission_events(
    mission_id: str,
    request: Request,
    after: int = Query(0, ge=0, description="Return events with sequence greater than this cursor"),
):
    """
    Mission event stream (spec §6.4).

    - Default: JSON list of persisted events after the given sequence.
    - `Accept: text/event-stream`: SSE stream with `id` set to the monotonic
      sequence, replayable via `Last-Event-ID`, plus comment heartbeats.
    """
    db = get_database()
    mission = await db.get_mission(mission_id)
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission '{mission_id}' not found.",
        )

    accept_header = (request.headers.get("accept") or "").lower()
    last_event_id = request.headers.get("last-event-id")
    start_cursor = after
    if last_event_id and last_event_id.isdigit():
        start_cursor = max(start_cursor, int(last_event_id))

    if "text/event-stream" in accept_header:
        async def event_stream():
            cursor = start_cursor
            heartbeat_ticks = 0
            yield "retry: 2000\n\n"
            try:
                while True:
                    events = await db.get_events(mission_id, after_sequence=cursor)
                    for event in events:
                        cursor = event.sequence
                        yield (
                            f"id: {event.sequence}\n"
                            f"event: mission\n"
                            f"data: {event.model_dump_json()}\n\n"
                        )
                    heartbeat_ticks += 1
                    if heartbeat_ticks % 15 == 0:
                        yield f": heartbeat {cursor}\n\n"
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                raise

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return await db.get_events(mission_id, after_sequence=start_cursor)

