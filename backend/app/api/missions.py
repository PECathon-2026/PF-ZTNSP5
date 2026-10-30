from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.schemas.mission import (
    AcceptanceCriterion,
    CreateMissionRequest,
    CriterionStatus,
    Mission,
    MissionBudgets,
    MissionStatus,
)
from app.schemas.task import MissionTask
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.agent_message import AgentMessage
from app.schemas.guild import Clarification
from app.schemas.approval import Approval
from app.storage.guild import GuildStore, GuildConflict
from app.storage.database import get_database
from app.services.mission_credentials import set_mission_key, has_mission_key, forget_mission_key
from app.api.credential_route import CredentialSafeRoute

router = APIRouter(prefix="/api/missions", tags=["Missions"], route_class=CredentialSafeRoute)


class MissionDetailResponse(BaseModel):
    mission: Mission
    criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    tasks: list[MissionTask] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)
    clarifications: list[Clarification] = Field(default_factory=list)
    plan_revision: int = 0
    approvals: list[Approval] = Field(default_factory=list)
    repository_files: list[str] = Field(default_factory=list)
    acceptance_test_proposal: dict | None = None
    own_api_key: bool = False
    api_key_ready: bool = False


@router.post("", response_model=MissionDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(request: CreateMissionRequest) -> MissionDetailResponse:
    """Create a new mission and initialize its acceptance criteria."""
    db = get_database()

    mission = Mission(
        repository_id=request.repository_id,
        request_text=request.request_text,
        status=MissionStatus.PLANNING,
        budgets=MissionBudgets(**request.limits.model_dump()),
    )

    criteria_objects = [
        AcceptanceCriterion(
            mission_id=mission.id,
            description=crit_text,
            status=CriterionStatus.PENDING,
        )
        for crit_text in request.criteria
    ]

    if request.api_key is not None:
        try:
            set_mission_key(mission.id, request.api_key.get_secret_value(), request.base_url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    elif request.base_url is not None:
        raise HTTPException(status_code=422, detail="A custom base URL requires a mission API key.")

    try:
        await db.create_mission(mission, criteria_objects)
        if request.api_key is not None:
            async with GuildStore(db).transaction() as connection:
                await connection.execute("INSERT INTO guild_context VALUES (?,?)", (mission.id, '{"own_api_key":true}'))
    except Exception:
        forget_mission_key(mission.id)
        raise

    # Emit creation event
    await db.emit_event(
        mission_id=mission.id,
        event_type="MISSION_CREATED",
        source="SYSTEM",
        display_payload={
            "title": "Mission initialized",
            "request": mission.request_text,
            "criteria_count": len(criteria_objects),
            "limits": request.limits.model_dump(),
        },
    )

    return MissionDetailResponse(
        mission=mission,
        criteria=criteria_objects,
        tasks=[],
        own_api_key=request.api_key is not None,
        api_key_ready=has_mission_key(mission.id),
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
    store = GuildStore(db)
    context = await store.context(mission_id) or {}

    return MissionDetailResponse(
        mission=mission,
        criteria=criteria,
        tasks=tasks,
        candidates=await store.records(Candidate, mission_id),
        evidence=await store.records(Evidence, mission_id),
        findings=await store.records(Finding, mission_id),
        messages=await store.records(AgentMessage, mission_id),
        clarifications=await store.records(Clarification, mission_id),
        plan_revision=context.get("plan_revision", 0),
        approvals=await store.records(Approval, mission_id),
        repository_files=context.get("repository", {}).get("included_files", []),
        acceptance_test_proposal=context.get("acceptance_tests"),
        own_api_key=context.get("own_api_key", False),
        api_key_ready=has_mission_key(mission_id),
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

    from app.services.guild_service import get_guild_controller
    try:
        await get_guild_controller().cancel(mission_id)
    except GuildConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    updated = await db.get_mission(mission_id)
    criteria = await db.get_criteria(mission_id)
    tasks = await db.get_tasks(mission_id)

    return MissionDetailResponse(
        mission=updated or mission,
        criteria=criteria,
        tasks=tasks,
    )

