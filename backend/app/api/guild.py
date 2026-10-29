from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.api.missions import MissionDetailResponse, get_mission
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.guild import AuthorizeGuildRequest
from app.schemas.mission import ClarificationAnswerRequest
from app.schemas.approval import ApprovalRequest, ApplyPatchRequest
from app.services.approval_service import ApprovalService
from app.security.paths import PathSecurityError
from app.services.guild_service import get_guild_controller
from app.storage.guild import GuildConflict
from app.tools.files import read_file
from app.services.proof_card import proof_card, proof_markdown

router = APIRouter(prefix="/api/missions", tags=["Guild"])


@router.get("/{mission_id}/proof")
async def candidate_proof(mission_id: str, format: str = "json"):
    if format not in {"json", "markdown"}:
        raise HTTPException(status_code=422, detail="Choose json or markdown")
    detail = await get_mission(mission_id)
    controller = get_guild_controller()
    context = await controller.store.context(mission_id) or {}
    events = await controller.db.get_events(mission_id, limit=100)  # bounded first batch
    # Include later events in sequence so a long repair run has its latest decisions.
    timeline = list(events)
    while events:
        events = await controller.db.get_events(mission_id, after_sequence=events[-1].sequence, limit=100)
        timeline.extend(events)
        if len(timeline) > 2000:
            timeline = timeline[-2000:]
    card = proof_card(detail, context, timeline)
    return PlainTextResponse(proof_markdown(card), media_type="text/markdown") if format == "markdown" else card


@router.post("/{mission_id}/verify")
async def verify_mission(mission_id: str):
    try:
        await ApprovalService(get_guild_controller()).verify(mission_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Mission not found") from None
    except (GuildConflict, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return await get_mission(mission_id)


@router.post("/{mission_id}/approve")
async def approve_candidate(mission_id: str, request: ApprovalRequest):
    try:
        await ApprovalService(get_guild_controller()).decide(mission_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail="Mission not found") from None
    except (GuildConflict, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return await get_mission(mission_id)


@router.post("/{mission_id}/apply")
async def apply_candidate(mission_id: str, request: ApplyPatchRequest):
    try:
        await ApprovalService(get_guild_controller()).apply(mission_id, request.candidate_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Mission not found") from None
    except (GuildConflict, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return await get_mission(mission_id)


async def _start(mission_id, phase, scope_version=None, auto_repair=None):
    try:
        await get_guild_controller().start(mission_id, phase, scope_version, auto_repair)
    except KeyError:
        raise HTTPException(status_code=404, detail="Mission not found") from None
    except GuildConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return await get_mission(mission_id)


@router.post("/{mission_id}/plan", response_model=MissionDetailResponse, status_code=202)
async def plan_mission(mission_id: str):
    """Start preflight, frozen baseline checks and read-only Shogun planning."""
    return await _start(mission_id, "plan")


@router.post("/{mission_id}/authorize", response_model=MissionDetailResponse, status_code=202)
async def authorize_mission(mission_id: str, request: AuthorizeGuildRequest):
    """Authorize this scope for bounded execution and optional adaptive repairs."""
    return await _start(mission_id, "execute", request.scope_version, request.auto_repair)


@router.post("/{mission_id}/clarifications", response_model=MissionDetailResponse, status_code=202)
async def answer_clarification(mission_id: str, request: ClarificationAnswerRequest):
    try:
        await get_guild_controller().answer(mission_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail="Mission or clarification not found") from None
    except GuildConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return await get_mission(mission_id)


async def _candidate(mission_id, candidate_id):
    controller = get_guild_controller()
    candidates = await controller.store.records(Candidate, mission_id)
    candidate = next((c for c in candidates if c.id == candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found in this mission")
    directory = controller.workspaces.get_candidate_dir(mission_id, candidate.id)
    try:
        if controller.workspaces._compute_dir_hash(directory)[0] != candidate.content_fingerprint:
            raise ValueError("Snapshot changed")
    except (ValueError, OSError, PathSecurityError):
        raise HTTPException(status_code=409, detail="Candidate snapshot is missing or its fingerprint changed") from None
    return controller, candidate, directory


@router.get("/{mission_id}/candidates/{candidate_id}/diff")
async def candidate_diff(mission_id: str, candidate_id: str):
    controller, candidate, _ = await _candidate(mission_id, candidate_id)
    context = await controller.store.context(mission_id)
    controller._restore(context)
    controller.workspaces._candidates[candidate.id] = candidate
    return controller.workspaces.generate_candidate_diff(mission_id, context["repository"]["repository_id"], candidate_id)


@router.get("/{mission_id}/candidates/{candidate_id}/file")
async def candidate_file(mission_id: str, candidate_id: str, path: str = Query(min_length=1, max_length=500)):
    _, _, directory = await _candidate(mission_id, candidate_id)
    try:
        return read_file(directory, path)
    except PathSecurityError:
        raise HTTPException(status_code=403, detail="Path is outside the approved snapshot") from None
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="File is missing or exceeds the read limit") from None


@router.get("/{mission_id}/evidence/{evidence_id}")
async def evidence_detail(mission_id: str, evidence_id: str):
    controller = get_guild_controller()
    evidence = next((e for e in await controller.store.records(Evidence, mission_id) if e.id == evidence_id), None)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found in this mission")
    return controller._evidence_context(evidence)


@router.get("/{mission_id}/patch", response_class=PlainTextResponse)
async def export_patch(mission_id: str):
    controller = get_guild_controller()
    mission = await controller.db.get_mission(mission_id)
    if not mission or not mission.active_candidate_id:
        raise HTTPException(status_code=404, detail="Active candidate not found")
    diff = await candidate_diff(mission_id, mission.active_candidate_id)
    return PlainTextResponse(diff["unified_diff"], media_type="text/x-diff",
                             headers={"Content-Disposition": f'attachment; filename="{mission_id}.patch"'})


@router.get("/{mission_id}/report")
async def mission_report(mission_id: str):
    detail = await get_mission(mission_id)
    controller = get_guild_controller()
    context = await controller.store.context(mission_id) or {}
    evidence = await controller.store.records(Evidence, mission_id)
    findings = await controller.store.records(Finding, mission_id)
    return {
        "mission": detail.mission.model_dump(mode="json"),
        "candidate": next((c.model_dump(mode="json") for c in detail.candidates if c.id == detail.mission.active_candidate_id), None),
        "criteria": [c.model_dump(mode="json") for c in detail.criteria],
        "plan_history": context.get("plan_history", []),
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "findings": [f.model_dump(mode="json") for f in findings],
        "approvals": [a.model_dump(mode="json") for a in detail.approvals],
    }
