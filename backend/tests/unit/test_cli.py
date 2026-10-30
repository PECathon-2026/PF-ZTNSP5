import asyncio
import json

import pytest

from app.cli import Console, parser, execute, create_cli_mission, get_cli_model_credentials
from app.schemas.approval import Approval
from app.schemas.candidate import Candidate
from app.schemas.mission import ClarificationAnswerRequest, Mission, MissionStatus
from app.schemas.guild import Clarification
from app.storage.guild import GuildConflict
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
async def test_cli_auto_criteria_and_manual_commands_are_not_silent_requirements():
    messages = []
    assert await Console(ask=lambda _: "", say=messages.append).collect_criteria() == []
    answers = iter(["/help", "/manual", "nothing", "/clear", "Pagination preserves sorting", "/done", "KEEP"])
    manual = await Console(ask=lambda _: next(answers), say=messages.append).collect_criteria()
    assert manual == ["Pagination preserves sorting"]
    answers = iter(["/manual", "wht do you mean by that", "/done", ""])
    assert await Console(ask=lambda _: next(answers), say=messages.append).collect_criteria() == []


@pytest.mark.asyncio
async def test_shogun_can_propose_criteria_when_user_supplied_none(guild):
    controller, mission, _, _, _ = guild
    created = Mission(repository_id=mission.repository_id, request_text="Set the value to two", status=MissionStatus.PLANNING)
    await controller.db.create_mission(created)
    await (await controller.start(created.id, "plan"))
    assert (await controller.db.get_mission(created.id)).status == MissionStatus.READY_FOR_AUTHORIZATION
    assert [c.description for c in await controller.db.get_criteria(created.id)] == ["Return value 2"]


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
async def test_interactive_verified_mission_offers_save_to_existing_repository(recovery):
    controller, mission, repo, service, candidate_id = await prepared(recovery)
    await service.verify(mission.id)
    candidate = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == candidate_id)
    output = []
    answers = iter(["SAVE", candidate.content_fingerprint, "APPLY " + candidate.content_fingerprint])
    assert await Console(ask=lambda _: next(answers), say=output.append, offer_save=True).workflow(controller, mission.id) == 0
    assert (repo / "app.py").read_text() == "value = 2\n"
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.APPLIED
    assert any("Original repository:" in line and str(repo) in line for line in output)
    assert any("Candidate SHA-256:" in line and candidate.content_fingerprint in line for line in output)


@pytest.mark.asyncio
async def test_declining_interactive_save_keeps_existing_repository_unchanged(recovery):
    controller, mission, repo, service, _ = await prepared(recovery)
    await service.verify(mission.id)
    output = []
    assert await Console(ask=lambda _: "", say=output.append, offer_save=True).workflow(controller, mission.id) == 0
    assert (repo / "app.py").read_text() == "value = 1\n"
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.VERIFIED_AWAITING_APPROVAL
    assert not await controller.store.records(Approval, mission.id)


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


@pytest.mark.asyncio
async def test_interrupted_follow_up_is_reviewed_before_new_mission_and_never_replays_writes(guild):
    controller, source, model, executor, repo = guild
    await (await controller.start(source.id, "plan"))
    async with controller.store.transaction() as db:
        await db.execute("UPDATE missions SET status='INTERRUPTED' WHERE id=?", (source.id,))
    old = await controller.db.get_mission(source.id)
    before = {m.id for m in await controller.db.list_missions()}
    output = []
    answers = iter(["Add a small example", ""])
    assert await Console(ask=lambda _: next(answers), say=output.append).follow_up(controller, source.id) == 0, output[-10:]
    assert {m.id for m in await controller.db.list_missions()} == before
    assert any("Unfinished workspace edits" in line for line in output)
    assert (await controller.db.get_mission(source.id)).status == old.status

    model.turns.clear()  # The scripted model starts a fresh conversation for the new mission.
    executor.calls.clear()
    answers = iter(["Add a small example", "CREATE FOLLOW-UP", ""])
    result = await Console(ask=lambda _: next(answers), say=output.append).follow_up(controller, source.id)
    assert result == 0, [(m.status, m.failure_reason) for m in await controller.db.list_missions()]
    successors = [m for m in await controller.db.list_missions() if m.id not in before]
    assert len(successors) == 1
    new = successors[0]
    assert new.id != source.id and source.id in new.request_text
    assert "Add a small example" in new.request_text
    assert new.status == MissionStatus.READY_FOR_AUTHORIZATION
    assert [c.description for c in await controller.db.get_criteria(new.id)] == [
        c.description for c in await controller.db.get_criteria(source.id)]
    assert (await controller.db.get_mission(source.id)).status == MissionStatus.INTERRUPTED
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_active_mission_uses_resume_instead_of_creating_follow_up(guild):
    controller, source, _, _, _ = guild
    await (await controller.start(source.id, "plan"))
    with pytest.raises(GuildConflict, match="resume"):
        await Console(ask=lambda _: "", say=lambda _: None).follow_up(controller, source.id)
    assert len(await controller.db.list_missions()) == 1


@pytest.mark.asyncio
async def test_second_natural_language_answer_edits_follow_up_instead_of_closing(guild):
    controller, source, _, _, repo = guild
    await (await controller.start(source.id, "plan"))
    async with controller.store.transaction() as db:
        await db.execute("UPDATE missions SET status='INTERRUPTED' WHERE id=?", (source.id,))
    output = []
    answers = iter(["Keep the existing helper", "Also add an example", "Keep the existing helper", "/cancel"])
    assert await Console(ask=lambda _: next(answers), say=output.append).follow_up(controller, source.id) == 0
    previews = [line for line in output if line.startswith("New request for review:")]
    assert len(previews) >= 3
    assert "Also add an example" in previews[-1]
    assert previews[-1].count("Keep the existing helper") == 1
    assert len(await controller.db.list_missions()) == 1
    assert (await controller.db.get_mission(source.id)).status == MissionStatus.INTERRUPTED
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_second_follow_up_detail_can_be_confirmed_after_repreview(guild):
    controller, source, model, executor, repo = guild
    await (await controller.start(source.id, "plan"))
    async with controller.store.transaction() as db:
        await db.execute("UPDATE missions SET status='INTERRUPTED' WHERE id=?", (source.id,))
    model.turns.clear()
    executor.calls.clear()
    replies = iter(["Fix the helper", "Add a usage example", "CREATE FOLLOW-UP", ""])
    assert await Console(ask=lambda _: next(replies), say=lambda _: None).follow_up(controller, source.id) == 0
    successors = [m for m in await controller.db.list_missions() if m.id != source.id]
    assert len(successors) == 1
    assert "Fix the helper" in successors[0].request_text
    assert "Add a usage example" in successors[0].request_text
    assert successors[0].status == MissionStatus.READY_FOR_AUTHORIZATION
    assert (await controller.db.get_mission(source.id)).status == MissionStatus.INTERRUPTED
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_follow_up_preview_carries_human_answer_but_no_old_evidence(recovery):
    controller, source, model, _, repo = recovery
    model.clarify_initial = True
    await (await controller.start(source.id, "plan"))
    question = (await controller.store.records(Clarification, source.id))[0]
    await (await controller.answer(source.id, ClarificationAnswerRequest(
        question_id=question.id, answer="Only fix app.py")))
    async with controller.store.transaction() as db:
        await db.execute("UPDATE missions SET status='INTERRUPTED' WHERE id=?", (source.id,))
    output = []
    answers = iter(["", ""])
    assert await Console(ask=lambda _: next(answers), say=output.append).follow_up(controller, source.id) == 0
    request = next(line for line in output if line.startswith("New request for review:"))
    assert "Prior user clarifications" in request and "Only fix app.py" in request
    assert source.id in request and "test_profile" not in request
    assert len(await controller.db.list_missions()) == 1
    assert (repo / "app.py").read_text() == "value = 1\n"


def test_continue_command_routes_to_interactive_dashboard():
    from types import SimpleNamespace
    from app.cli import select_console
    from app.cli_tui import GuildDashboard
    args = parser().parse_args(["continue", "miss-abcd"])
    tty = SimpleNamespace(isatty=lambda: True)
    assert args.mission_id == "miss-abcd"
    assert isinstance(select_console(args, stdout=tty, stdin=tty), GuildDashboard)


@pytest.mark.asyncio
async def test_cli_base_url_and_hidden_key_create_isolated_mission(guild, monkeypatch):
    from app.services import mission_credentials as credentials
    controller, source, _, _, _ = guild
    async def checked(key, base_url):
        assert key == "user-secret" and base_url == "https://custom.example/v1"
    monkeypatch.setattr(credentials, "check_model_connection", checked)
    lines = []
    answers = iter(["https://custom.example/v1", "user-secret"])
    key, url = await get_cli_model_credentials(Console(ask=lambda _: next(answers), say=lines.append))
    mission = Mission(repository_id=source.repository_id, request_text="New mission", status=MissionStatus.PLANNING)
    await create_cli_mission(controller, mission, [], key=key, base_url=url)
    assert (await controller.store.context(mission.id)) == {"own_api_key": True}
    assert credentials.mission_settings(mission.id).model_base_url == "https://custom.example/v1"
    assert credentials.mission_settings(mission.id).model_api_key == "user-secret"
    assert "user-secret" not in str(lines)
    assert parser().parse_args(["run", "--own-api-key", "--base-url", url]).base_url == url
