"""Recovery uses real SQLite/files and scripted agents; no paid model calls."""

import asyncio
import json

import httpx
import pytest
import pytest_asyncio

from app.agents.model_adapter import ModelAdapter
from app.schemas.approval import Approval, ApprovalDecision, ApprovalRequest
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.mission import AcceptanceCriterion, Mission, MissionBudgets, MissionLimits, MissionStatus
from app.schemas.recovery import BudgetExtensionRequest, ContinueMissionRequest
from app.schemas.task import MissionTask, TaskStatus
from app.services.approval_service import ApprovalService
from app.services.guild_service import GuildController
from app.services.recovery_service import RecoveryService
from app.services.repository_service import RepositoryService
from app.services.workspace_service import WorkspaceService
from app.settings import Settings
from app.storage.artifacts import ArtifactStorage
from app.storage.database import Database
from app.storage.guild import GuildConflict
from tests.report_fixtures import passing_report


class RecoveryAgent:
    def __init__(self):
        self.calls = []

    def factory(self):
        return ModelAdapter(settings=Settings(model_provider="anthropic", anthropic_api_key="synthetic-key",
                            anthropic_base_url="https://test.invalid/v1"), transport=httpx.MockTransport(self.respond))

    def respond(self, request):
        body = json.loads(request.content)
        names = {t["name"] for t in body["tools"]}
        role = "review" if "submit_review" in names else "plan" if "submit_plan" in names else "developer"
        turn = sum(m["role"] == "assistant" for m in body["messages"]) + 1
        def call(name, args):
            return {"type": "tool_use", "id": f"{role}-{turn}-{name}", "name": name, "input": args}
        if role == "developer":
            # First submission must fail: inherited changes have not been inspected.
            if turn in {1, 3}:
                calls = [call("submit_candidate", {"summary": "Recovered source inspected"})]
            else:
                calls = [call("read_file", {"relative_path": "app.py"}), call("read_diff", {"relative_path": "app.py"})]
        elif role == "review":
            if turn == 1:
                calls = [call("read_file", {"relative_path": "app.py"}), call("read_diff", {"relative_path": "app.py"})]
            else:
                calls = [call("submit_review", {"summary": "Reviewed", "findings": [], "resolved_finding_ids": []})]
        else:
            calls = [call("read_file", {"relative_path": "app.py"})] if turn == 1 else [call("submit_plan", {
                "summary": "Use existing expectations", "criteria": [{"description": "Return three", "check_profile": "python_pytest", "test_selectors": ["test_app.py::test_value"]}],
                "tasks": [{"key": "value", "title": "Return three", "description": "Set value to three", "dependencies": []}]} )]
        self.calls.append((role, turn))
        return httpx.Response(200, json={"content": calls, "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 5}})


class ControlledChecks:
    def __init__(self):
        self.calls = []

    async def run(self, directory, profile, selector=None):
        self.calls.append((directory, selector))
        return {"status": "SUCCEEDED", "exit_code": 0, "duration_ms": 0, "stdout": "Controlled fixture", "stderr": "",
                "command": ["controlled-check"], "report": passing_report(selector or "test_app.py::test_value"),
                "controlled_evaluation": True, "output_truncated": False}


@pytest_asyncio.fixture
async def recovery_case(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n")
    (repo / "test_app.py").write_text("from app import value\n\ndef test_value():\n    assert value == 3\n")
    repositories = RepositoryService()
    monkeypatch.setattr(repositories, "_check_docker", lambda: True)
    record = repositories.connect_repository(str(repo))
    monkeypatch.setattr("app.services.repository_service._repo_service_instance", repositories)
    db = Database(tmp_path / "recovery.db")
    await db.init_db()
    agents, checks = RecoveryAgent(), ControlledChecks()
    ws = WorkspaceService(tmp_path / "workspaces")
    controller = GuildController(db, ws, ArtifactStorage(tmp_path / "artifacts"), checks, agents.factory)
    mission = Mission(repository_id=record["repository_id"], request_text="Return three", status=MissionStatus.BUDGET_EXHAUSTED,
                      budgets=MissionBudgets(model_turns_used=25, tool_calls_used=12, input_tokens_used=1000, output_tokens_used=100, time_used_seconds=20))
    criterion = AcceptanceCriterion(mission_id=mission.id, description="Return three", verification_method='test_profile:python_pytest|["test_app.py::test_value"]')
    await db.create_mission(mission, [criterion])
    workspace = ws.create_disposable_workspace(mission.id, mission.repository_id)
    baseline = ws.freeze_candidate(mission.id, mission.repository_id)
    (workspace / "app.py").write_text("value = 3\n")  # an interrupted developer edit
    tasks = [MissionTask(mission_id=mission.id, title="Return three", description="Set value to three", owner_agent="SAMURAI", status=TaskStatus.BLOCKED)]
    tasks += [MissionTask(mission_id=mission.id, title=role, description="Check", owner_agent=role, dependencies=[tasks[0].id]) for role in ("SENTINEL", "SHADOW_COUNCIL")]
    context = {"repository": {k: record[k] for k in ("repository_id", "name", "path", "included_files", "fingerprint")},
               "baseline_candidate_id": baseline.id, "execution_authorized": True, "auto_repair": True,
               "task_ids": [t.id for t in tasks], "plan_revision": 1,
               "plan": {"summary": "Return three", "criteria": [{"description": "Return three", "check_profile": "python_pytest", "test_selectors": ["test_app.py::test_value"]}]}}
    context["approved_criteria"] = context["plan"]["criteria"]
    async with controller.store.transaction() as connection:
        for entity in [baseline, *tasks]:
            await controller.store._save(connection, entity)
        await connection.execute("INSERT INTO guild_context VALUES (?,?)", (mission.id, json.dumps(context)))
    yield controller, mission, repo, agents, checks, baseline
    await controller.close()


async def extend(service, mission_id):
    state = await service.inspect(mission_id)
    return await service.extend_budget(mission_id, BudgetExtensionRequest(checkpoint_token=state["checkpoint_token"],
        limits=MissionLimits(max_model_turns=60, max_tool_calls=100, max_tokens=320000, max_time_seconds=900)))


@pytest.mark.asyncio
async def test_partial_checkpoint_requires_budget_and_explicit_review(recovery_case):
    controller, mission, repo, model, checks, _ = recovery_case
    service = RecoveryService(controller)
    first = await service.inspect(mission.id)
    assert first["stage"] == "development" and first["partial_edits"]
    assert not first["can_continue"] and "value = 3" in first["diff"]
    assert (await service.read_partial_file(mission.id, first["checkpoint_token"], "app.py"))["content"] == "value = 3\n"
    with pytest.raises(GuildConflict):
        await service.read_partial_file(mission.id, first["checkpoint_token"], "../outside.py")
    assert first["budgets"]["model_turns_used"] == 25
    second = await extend(service, mission.id)
    assert second["can_continue"] and second["budgets"]["model_turns_used"] == 25
    assert not model.calls and not checks.calls
    with pytest.raises(GuildConflict, match="partial edits"):
        await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=second["checkpoint_token"]))
    job = await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=second["checkpoint_token"], accept_partial_edits=True))
    await job
    final = await controller.db.get_mission(mission.id)
    assert final.status == MissionStatus.VERIFYING, final.failure_reason
    assert final.budgets.model_turns_used > 25 and final.budgets.repair_rounds_used == 0
    assert model.calls.count(("developer", 1)) == 1
    events = await controller.db.get_events(mission.id)
    assert any(e.display_payload.get("stage") == "failed" for e in events)  # handoff before inspection denied
    candidate = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == final.active_candidate_id)
    assert (controller.workspaces.get_candidate_dir(mission.id, candidate.id) / "app.py").read_text() == "value = 3\n"
    assert (repo / "app.py").read_text() == "value = 1\n"
    assert not controller.workspaces._leases
    # Controlled evidence never becomes a successful real verification.
    result = await ApprovalService(controller).verify(mission.id)
    assert result.status == MissionStatus.FAILED_VERIFICATION


@pytest.mark.asyncio
async def test_duplicate_continuation_and_stale_budget_decisions_are_rejected(recovery_case):
    controller, mission, *_ = recovery_case
    service = RecoveryService(controller)
    before = await service.inspect(mission.id)
    state = await extend(service, mission.id)
    with pytest.raises(GuildConflict, match="changed"):
        await service.extend_budget(mission.id, BudgetExtensionRequest(checkpoint_token=before["checkpoint_token"], limits=MissionLimits(max_model_turns=80)))
    request = ContinueMissionRequest(checkpoint_token=state["checkpoint_token"], accept_partial_edits=True)
    results = await asyncio.gather(service.continue_mission(mission.id, request), service.continue_mission(mission.id, request), return_exceptions=True)
    jobs = [r for r in results if isinstance(r, asyncio.Task)]
    assert len(jobs) == 1
    assert any(isinstance(r, GuildConflict) for r in results)
    await jobs[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["original", "workspace", "tests", "baseline"])
async def test_changes_after_inspection_do_not_resume(recovery_case, target):
    controller, mission, repo, model, *_ = recovery_case
    service = RecoveryService(controller)
    state = await extend(service, mission.id)
    roots = {"original": repo, "workspace": controller.workspaces.get_mission_workspace_dir(mission.id),
             "tests": controller.workspaces.get_mission_workspace_dir(mission.id), "baseline": controller.workspaces.get_baseline_dir(mission.id)}
    (roots[target] / ("test_app.py" if target == "tests" else "app.py")).write_text("changed = True\n")
    with pytest.raises(GuildConflict):
        await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=state["checkpoint_token"], accept_partial_edits=True))
    assert not model.calls
    assert not controller.workspaces._leases


@pytest.mark.asyncio
async def test_frozen_checks_resume_with_new_candidate_and_keep_old_evidence(recovery_case):
    controller, mission, repo, model, checks, baseline = recovery_case
    service = RecoveryService(controller)
    await extend(service, mission.id)
    current = controller.workspaces.freeze_candidate(mission.id, mission.repository_id, baseline.id)
    tasks = await controller.db.get_tasks(mission.id)
    tasks[0].status = TaskStatus.DONE
    tasks[0].candidate_id = current.id
    old_evidence = Evidence(mission_id=mission.id, candidate_id=current.id, fingerprint=current.content_fingerprint, kind="TEST", source="SENTINEL", exit_code=126)
    async with controller.store.transaction() as db:
        for entity in [current, tasks[0], old_evidence]:
            await controller.store._save(db, entity)
        await db.execute("UPDATE missions SET active_candidate_id=?,status='BLOCKED',failure_reason='Check environment unavailable' WHERE id=?", (current.id, mission.id))
    state = await service.inspect(mission.id)
    assert state["stage"] == "checks_and_review" and not state["partial_edits"]
    await (await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=state["checkpoint_token"])))
    final = await controller.db.get_mission(mission.id)
    assert final.status == MissionStatus.VERIFYING, final.failure_reason
    assert final.active_candidate_id != current.id
    assert not any(role == "developer" for role, _ in model.calls)
    records = await controller.store.records(Evidence, mission.id)
    assert any(e.id == old_evidence.id for e in records)
    assert all(e.candidate_id == final.active_candidate_id for e in records if e.id != old_evidence.id)
    assert len(checks.calls) == 2
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_approval_cannot_be_bypassed(recovery_case):
    controller, mission, *_ = recovery_case
    service = RecoveryService(controller)
    state = await extend(service, mission.id)
    baseline = recovery_case[-1]
    async with controller.store.transaction() as db:
        await controller.store._save(db, Approval(mission_id=mission.id, candidate_id=baseline.id,
            candidate_fingerprint=baseline.content_fingerprint, decision=ApprovalDecision.APPROVED))
    blocked = await service.inspect(mission.id)
    assert not blocked["can_continue"] and not blocked["can_extend_budget"]
    with pytest.raises(GuildConflict):
        await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=state["checkpoint_token"], accept_partial_edits=True))


@pytest.mark.asyncio
async def test_readonly_planning_checkpoint_recovers_without_replaying_workspace_creation(recovery_case):
    controller, mission, _, model, *_ = recovery_case
    service = RecoveryService(controller)
    await extend(service, mission.id)
    (controller.workspaces.get_mission_workspace_dir(mission.id) / "app.py").write_text("value = 1\n")
    context = await controller.store.context(mission.id)
    context["execution_authorized"] = False
    async with controller.store.transaction() as db:
        await db.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission.id))
    state = await service.inspect(mission.id)
    assert state["stage"] == "planning"
    await (await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=state["checkpoint_token"])))
    final = await controller.db.get_mission(mission.id)
    assert final.status == MissionStatus.READY_FOR_AUTHORIZATION, final.failure_reason
    assert all(role == "plan" for role, _ in model.calls)


@pytest.mark.asyncio
async def test_repair_cap_still_blocks_even_after_extending_other_budgets(recovery_case):
    controller, mission, *_, baseline = recovery_case
    service = RecoveryService(controller)
    await extend(service, mission.id)
    parent = controller.workspaces.freeze_candidate(mission.id, mission.repository_id, baseline.id)
    finding = Finding(mission_id=mission.id, candidate_id=parent.id, source_agent="SHADOW_COUNCIL", severity="HIGH",
        title="Still wrong", description="Requires another repair", observed_behavior="Wrong value", expected_behavior="Return three")
    context = await controller.store.context(mission.id)
    context["routed_candidates"] = [parent.id]
    current = await controller.db.get_mission(mission.id)
    current.budgets.repair_rounds_used = 3
    async with controller.store.transaction() as db:
        for entity in (parent, finding):
            await controller.store._save(db, entity)
        await db.execute("UPDATE missions SET active_candidate_id=?,budgets_json=? WHERE id=?", (parent.id, current.budgets.model_dump_json(), mission.id))
        await db.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission.id))
    state = await service.inspect(mission.id)
    assert state["stage"] == "repair" and not state["can_continue"]
    assert any("Three-repair" in text for text in state["blockers"])
    with pytest.raises(GuildConflict, match="Three-repair"):
        await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=state["checkpoint_token"]))


@pytest.mark.asyncio
async def test_checkpoint_survives_new_controller_without_resetting_usage(recovery_case):
    controller, mission, repo, model, checks, _ = recovery_case
    await extend(RecoveryService(controller), mission.id)
    restarted = GuildController(controller.db, WorkspaceService(controller.workspaces.base_dir), controller.artifacts, checks, model.factory)
    service = RecoveryService(restarted)
    state = await service.inspect(mission.id)
    assert state["can_continue"] and state["budgets"]["model_turns_used"] == 25
    await (await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=state["checkpoint_token"], accept_partial_edits=True)))
    assert (await controller.db.get_mission(mission.id)).budgets.model_turns_used > 25
    assert (repo / "app.py").read_text() == "value = 1\n"
    await restarted.close()


@pytest.mark.asyncio
async def test_recovery_api_validation_and_extension_does_not_start_jobs(recovery_case, monkeypatch):
    from app.main import app
    controller, mission, _, model, checks, _ = recovery_case
    monkeypatch.setattr("app.api.recovery.get_guild_controller", lambda: controller)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        root = f"/api/missions/{mission.id}"
        state = (await client.get(root + "/recovery")).json()
        assert (await client.post(root + "/continue", json={"checkpoint_token": "bad"})).status_code == 422
        bad = await client.post(root + "/budget-extension", json={"checkpoint_token": state["checkpoint_token"], "limits": {"max_model_turns": 101}})
        assert bad.status_code == 422
        good = await client.post(root + "/budget-extension", json={"checkpoint_token": state["checkpoint_token"],
            "limits": {"max_model_turns": 60, "max_tool_calls": 100, "max_tokens": 320000, "max_time_seconds": 900}})
        assert good.status_code == 200, good.text
        assert good.json()["budgets"]["model_turns_used"] == 25
        assert not model.calls and not checks.calls and not controller.jobs
        file = await client.get(root + "/recovery/file", params={"checkpoint_token": good.json()["checkpoint_token"], "path": "app.py"})
        assert file.status_code == 200 and "value = 3" in file.json()["content"]
        assert (await client.get("/api/missions/missing/recovery")).status_code == 404


@pytest.mark.asyncio
async def test_missing_own_key_cannot_fall_back_to_server_key_on_continue(recovery_case):
    controller, mission, _, model, *_ = recovery_case
    service = RecoveryService(controller)
    await extend(service, mission.id)
    context = await controller.store.context(mission.id)
    context["own_api_key"] = True
    async with controller.store.transaction() as db:
        await db.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission.id))
    state = await service.inspect(mission.id)
    assert not state["can_continue"]
    assert any("API key" in text for text in state["blockers"])
    with pytest.raises(GuildConflict, match="API key"):
        await service.continue_mission(mission.id, ContinueMissionRequest(checkpoint_token=state["checkpoint_token"], accept_partial_edits=True))
    assert not model.calls
