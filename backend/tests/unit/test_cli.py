import asyncio
import json

import pytest

from app.cli import Console, parser, execute
from app.schemas.approval import Approval
from app.schemas.mission import MissionStatus
from tests.unit.test_m4_guild import guild
from tests.unit.test_m5_recovery import recovery
from tests.unit.test_m6_approval import prepared


@pytest.mark.asyncio
async def test_cli_shows_live_agent_work_and_never_authorizes_itself(guild):
    controller, mission, _, _, repo = guild
    lines = []
    console = Console(ask=lambda _: "", say=lines.append)
    assert await console.workflow(controller, mission.id, start_plan=True) == 0
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.READY_FOR_AUTHORIZATION
    assert any("SHOGUN" in line.upper() and "read" in line.lower() for line in lines)
    assert any("test_profile:python_pytest" in line for line in lines)
    assert any("Plan awaiting authorization" in line for line in lines)
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_cli_real_flow_requires_authorize_then_shows_failures(guild):
    controller, mission, _, _, repo = guild
    lines = []
    answers = iter(["AUTHORIZE"])
    result = await Console(ask=lambda _: next(answers), say=lines.append).workflow(controller, mission.id, start_plan=True)
    assert result == 1
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.REPAIRING
    assert any("Samurai" in line and "app.py" in line for line in lines)
    assert any("Sentinel" in line and "did not pass" in line for line in lines)
    assert any("Controller" in line and "routed" in line for line in lines)
    assert not await controller.store.records(Approval, mission.id)
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_cli_approval_requires_exact_fingerprint_then_separate_apply(recovery):
    controller, mission, repo, service, candidate_id = await prepared(recovery)
    assert (await service.verify(mission.id)).status == MissionStatus.VERIFIED_AWAITING_APPROVAL
    candidate = next(c for c in await controller.store.records(
        __import__("app.schemas.candidate", fromlist=["Candidate"]).Candidate, mission.id) if c.id == candidate_id)
    lines = []
    console = Console(ask=lambda _: "wrong", say=lines.append)
    assert await console.approve(controller, mission.id) == 0
    assert not await controller.store.records(Approval, mission.id)
    assert (repo / "app.py").read_text() == "value = 1\n"
    answers = iter([candidate.content_fingerprint, ""])
    assert await Console(ask=lambda _: next(answers), say=lines.append).approve(controller, mission.id) == 0
    assert len(await controller.store.records(Approval, mission.id)) == 1
    assert (repo / "app.py").read_text() == "value = 1\n"
    assert await Console(ask=lambda _: "APPLY " + candidate.content_fingerprint, say=lines.append).approve(controller, mission.id) == 0
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.APPLIED
    assert (repo / "app.py").read_text() == "value = 2\n"


@pytest.mark.asyncio
async def test_cli_replays_persisted_events_without_duplicating(guild):
    controller, mission, _, _, _ = guild
    first = await controller.db.emit_event(mission.id, "AGENT_ACTIVITY", "SHOGUN",
                                           {"summary": "Shogun read route.py", "stage": "outcome"})
    second = await controller.db.emit_event(mission.id, "AGENT_ACTIVITY", "SAMURAI",
                                            {"summary": "Samurai prepared edit", "stage": "intent"})
    lines = []
    console = Console(say=lines.append)
    cursor = await console.stream(controller.db, mission.id, after=first.sequence)
    assert cursor == second.sequence
    assert len(lines) == 1 and "prepared edit" in lines[0]
    assert await console.stream(controller.db, mission.id, after=cursor) == cursor
    assert len(lines) == 1


@pytest.mark.asyncio
async def test_follow_exits_if_an_inactive_mission_has_no_running_guild_job(guild):
    controller, mission, _, _, _ = guild
    lines = []
    cursor = await asyncio.wait_for(Console(say=lines.append).stream(controller.db, mission.id, follow=True, timeout=2), 1)
    assert cursor == 0
    assert any("No active guild operation" in line for line in lines)


@pytest.mark.asyncio
async def test_cli_readonly_proof_command_does_not_create_or_approve(guild, monkeypatch):
    controller, mission, _, _, _ = guild
    import app.storage.database as database_module
    monkeypatch.setattr(database_module, "_db_instance", controller.db)
    lines = []
    args = parser().parse_args(["proof", mission.id, "--format", "json"])
    assert await execute(args, Console(say=lines.append)) == 0
    card = json.loads(lines[0])
    assert card["mission_id"] == mission.id and not card["approvals"]
    assert not await controller.store.records(Approval, mission.id)
