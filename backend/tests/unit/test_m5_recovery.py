import asyncio
import json

import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.agents.model_adapter import ModelAdapter, ModelAdapterConfig
from app.schemas.agent_message import AgentMessage, MessageType
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding, FindingStatus
from app.schemas.guild import Clarification
from app.schemas.mission import AcceptanceCriterion, ClarificationAnswerRequest, Mission, MissionBudgets, MissionStatus
from app.schemas.task import MissionTask, TaskStatus
from app.services.guild_service import GuildController
from app.services.repository_service import RepositoryService
from app.services.workspace_service import WorkspaceService
from app.settings import Settings
from app.storage.artifacts import ArtifactStorage
from app.storage.database import Database
from app.storage.guild import GuildConflict


def tool(name, arguments, id):
    return {"type": "tool_use", "name": name, "input": arguments, "id": id}


class RecoveryModel:
    def __init__(self):
        self.turns = {}
        self.developer_runs = 0
        self.review_runs = 0
        self.clarify_initial = False
        self.clarify_repair = False
        self.keep_clarifying = False
        self.weaken_criteria = False
        self.unknown_finding = False
        self.initial_review_fails = False
        self.ignore_prior_review = False
        self.fail_role = None
        self.no_progress = False
        self.repair_contexts = []

    def factory(self):
        return ModelAdapter(settings=Settings(model_provider="anthropic", anthropic_api_key="test-key", anthropic_base_url="https://example.test/v1"),
                            config=ModelAdapterConfig(max_retries=0), transport=httpx.MockTransport(self.respond))

    def respond(self, request):
        body = json.loads(request.content)
        names = {t["name"] for t in body["tools"]}
        role = "repair" if "submit_repair_plan" in names else "plan" if "submit_plan" in names else "review" if "submit_review" in names else "developer"
        self.turns[role] = self.turns.get(role, 0) + 1
        if self.fail_role == role:
            return httpx.Response(401, json={"error": "test failure"})
        turn = sum(m["role"] == "assistant" for m in body["messages"]) + 1
        context = json.loads(body["messages"][0]["content"])
        if role in {"plan", "repair"}:
            if role == "repair" and turn == 1:
                self.repair_contexts.append(context)
            ask = self.clarify_initial if role == "plan" else self.clarify_repair
            if ask and (self.keep_clarifying or not context["clarification_answers"]):
                calls = [tool("request_clarification", {"question": "Should the result be exactly 3?", "reason": "Clarify the target value"}, "question")]
            elif turn == 1:
                calls = [tool("read_file", {"relative_path": "app.py"}, "planner-read")]
            else:
                proposal = {
                    "summary": "Repair the failing value" if role == "repair" else "Implement the requested value",
                    "criteria": [{"description": "Return value 3", "check_profile": "python_pytest"}],
                    "tasks": [{"key": "value", "title": "Update value", "description": "Use findings and preserve tests", "dependencies": []}],
                }
                if role == "repair":
                    proposal["finding_ids"] = [f["id"] for f in context["findings"]]
                    if self.unknown_finding:
                        proposal["finding_ids"] = ["find-invented"]
                    if self.weaken_criteria:
                        proposal["criteria"][0]["check_profile"] = "python_syntax"
                calls = [tool("submit_repair_plan" if role == "repair" else "submit_plan", proposal, f"plan-{turn}")]
        elif role == "developer":
            if turn == 1:
                self.developer_runs += 1
                calls = [tool("read_file", {"relative_path": "app.py"}, "read")]
            elif turn == 2:
                output = json.loads(body["messages"][-1]["content"][0]["content"])
                replacement = output["content"].strip() if self.no_progress and self.developer_runs > 1 else f"value = {self.developer_runs + 1}"
                calls = [tool("apply_patch", {"relative_path": "app.py", "target": output["content"].strip(),
                                              "replacement": replacement, "expected_fingerprint": output["fingerprint"]}, "patch")]
            elif turn == 3:
                calls = [tool("read_file", {"relative_path": "app.py"}, "read-back"), tool("read_diff", {"relative_path": "app.py"}, "diff")]
            else:
                calls = [tool("submit_candidate", {"summary": "Source ready"}, "submit")]
        else:
            if turn == 1:
                self.review_runs += 1
                calls = [tool("read_file", {"relative_path": "app.py"}, "review-read"), tool("read_diff", {"relative_path": "app.py"}, "review-diff")]
            else:
                findings = [{"severity": "HIGH", "title": "Seeded review issue", "description": "Review the value contract",
                             "observed_behavior": "Wrong value", "expected_behavior": "Expected value", "file_path": "app.py",
                             "evidence_ids": [context["evidence"][0]["id"]]}] if self.initial_review_fails and self.review_runs == 1 else []
                resolved = [] if self.ignore_prior_review else [f["id"] for f in context["prior_findings"]]
                calls = [tool("submit_review", {"summary": "Reviewed", "findings": findings, "resolved_finding_ids": resolved}, "review-submit")]
        return httpx.Response(200, json={"content": calls, "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 5}})


class RecoveryExecutor:
    def __init__(self):
        self.calls = []
        self.always_fail = False
        self.never_fail = False
        self.environment_failure = False
        self.baseline_defect = False

    async def run(self, directory, profile):
        self.calls.append((directory, profile))
        number = len(self.calls)
        if number == 1:
            code = 1 if self.baseline_defect else 0
        else:
            code = 0 if self.never_fail else 1 if number == 2 or self.always_fail else 0
        status = "SUCCEEDED" if code == 0 else "FAILED"
        if number > 1 and self.environment_failure:
            code, status = 126, "BLOCKED"
        # Read generated bytes only; no repository imports or host execution.
        if number == 3 and code == 0:
            assert (directory / "app.py").read_text() == "value = 3\n"
        await asyncio.sleep(0)
        return {"status": status, "exit_code": code, "duration_ms": 10, "command": ["python", "-m", "pytest", "-q"],
                "stdout": "1 passed" if code == 0 else "FAILED seeded check: expected value 3", "stderr": ""}


@pytest_asyncio.fixture
async def recovery(tmp_path, monkeypatch):
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
    model, executor = RecoveryModel(), RecoveryExecutor()
    controller = GuildController(database=db, workspaces=WorkspaceService(tmp_path / "workspaces"), artifacts=ArtifactStorage(tmp_path / "artifacts"),
                                 executor=executor, adapter_factory=model.factory)
    mission = Mission(repository_id=record["repository_id"], request_text="Return value 3", status=MissionStatus.PLANNING)
    await db.create_mission(mission, [AcceptanceCriterion(mission_id=mission.id, description="Return value 3")])
    yield controller, mission, model, executor, repo
    await controller.close()


async def run(recovery):
    controller, mission, *_ = recovery
    await (await controller.start(mission.id, "plan"))
    planned = await controller.db.get_mission(mission.id)
    if planned.status == MissionStatus.READY_FOR_AUTHORIZATION:
        await (await controller.start(mission.id, "execute", planned.scope_version))
    return await controller.db.get_mission(mission.id)


async def set_budgets(controller, mission, **changes):
    current = await controller.db.get_mission(mission.id)
    budget = MissionBudgets(**{**current.budgets.model_dump(), **changes})
    async with controller.store.transaction() as connection:
        await connection.execute("UPDATE missions SET budgets_json=? WHERE id=?", (budget.model_dump_json(), mission.id))


@pytest.mark.asyncio
async def test_m5_seeded_failure_replans_repairs_and_retests(recovery):
    controller, mission, model, executor, repo = recovery
    result = await run(recovery)
    assert result.status == MissionStatus.VERIFYING, result.failure_reason
    assert result.budgets.repair_rounds_used == 1
    assert result.budgets.model_turns_used == sum(model.turns.values()) == 16
    assert result.budgets.input_tokens_used == 160 and result.budgets.output_tokens_used == 80
    assert len(executor.calls) == 3
    context = await controller.store.context(mission.id)
    assert context["plan_revision"] == 2 and len(context["plan_history"]) == 2
    assert model.repair_contexts[0]["findings"]
    assert any(e["exit_code"] == 1 and "expected value 3" in e["stdout"] for e in model.repair_contexts[0]["evidence"])
    candidates = await controller.store.records(Candidate, mission.id)
    assert len(candidates) == 3 and candidates[1].state.value == "SUPERSEDED"
    assert candidates[2].parent_candidate_id == candidates[1].id
    evidence = {e.id: e for e in await controller.store.records(Evidence, mission.id)}
    findings = await controller.store.records(Finding, mission.id)
    assert findings and all(f.status == FindingStatus.RESOLVED for f in findings)
    assert all(evidence[e].candidate_id == result.active_candidate_id and evidence[e].exit_code == 0 for f in findings for e in f.resolution_evidence_ids)
    assert (repo / "app.py").read_text() == "value = 1\n"
    assert all(c.status.value == "PENDING" for c in await controller.db.get_criteria(mission.id))
    tasks = await controller.db.get_tasks(mission.id)
    assert all(t.status == TaskStatus.DONE for t in tasks if t.id in context["task_ids"])
    assert all(t.status == TaskStatus.CANCELLED for t in tasks if t.id not in context["task_ids"])
    assert any(m.sender == "SHOGUN" and m.recipient == "SAMURAI" and m.type == MessageType.TASK_PROPOSAL for m in await controller.store.records(AgentMessage, mission.id))


@pytest.mark.asyncio
@pytest.mark.parametrize("cap", [0, 1, 3])
async def test_repair_cap_prevents_extra_model_or_write_rounds(recovery, cap):
    controller, mission, model, executor, _ = recovery
    executor.always_fail = True
    await set_budgets(controller, mission, max_repair_rounds=cap, max_model_turns=100, max_tool_calls=200)
    result = await run(recovery)
    assert result.status == MissionStatus.BUDGET_EXHAUSTED, result.failure_reason
    assert result.budgets.repair_rounds_used == cap
    assert model.developer_runs == cap + 1
    assert len(executor.calls) == cap + 2
    assert len(await controller.store.records(Candidate, mission.id)) == cap + 2
    assert not controller.workspaces._leases
    assert "Repair round limit" in result.failure_reason


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("max_model_turns", 1), ("max_tool_calls", 1), ("max_tokens", 1)])
async def test_global_budget_exhaustion_is_persisted(recovery, field, value):
    controller, mission, model, executor, _ = recovery
    await set_budgets(controller, mission, **{field: value})
    result = await run(recovery)
    assert result.status == MissionStatus.BUDGET_EXHAUSTED
    assert result.budgets.model_turns_used == sum(model.turns.values())
    assert model.developer_runs == 0
    if field == "max_tokens":
        assert result.budgets.input_tokens_used + result.budgets.output_tokens_used == 15


@pytest.mark.asyncio
async def test_failed_model_call_still_consumes_budget(recovery):
    controller, mission, model, _, _ = recovery
    model.fail_role = "plan"
    result = await run(recovery)
    assert result.status == MissionStatus.BLOCKED
    assert result.budgets.model_turns_used == 1


@pytest.mark.asyncio
async def test_initial_clarification_resumes_without_replaying_baseline(recovery):
    controller, mission, model, executor, _ = recovery
    model.clarify_initial = True
    result = await run(recovery)
    assert result.status == MissionStatus.AWAITING_CLARIFICATION
    assert len(executor.calls) == 1 and model.developer_runs == 0
    question = (await controller.store.records(Clarification, mission.id))[0]
    before = result.budgets.model_turns_used
    await (await controller.answer(mission.id, ClarificationAnswerRequest(question_id=question.id, answer="Exactly 3")))
    result = await controller.db.get_mission(mission.id)
    assert result.status == MissionStatus.READY_FOR_AUTHORIZATION, result.failure_reason
    assert len(executor.calls) == 1
    assert result.budgets.model_turns_used > before
    assert (await controller.store.records(Clarification, mission.id))[0].status == "ANSWERED"
    with pytest.raises(GuildConflict):
        await controller.answer(mission.id, ClarificationAnswerRequest(question_id=question.id, answer="Again"))


@pytest.mark.asyncio
async def test_repair_clarification_survives_restart_without_budget_reset(recovery):
    controller, mission, model, executor, _ = recovery
    model.clarify_repair = True
    paused = await run(recovery)
    assert paused.status == MissionStatus.AWAITING_CLARIFICATION, paused.failure_reason
    assert paused.budgets.repair_rounds_used == 1 and model.developer_runs == 1
    question = (await controller.store.records(Clarification, mission.id))[0]
    restored = GuildController(database=controller.db, workspaces=WorkspaceService(controller.workspaces.base_dir), artifacts=controller.artifacts,
                               executor=executor, adapter_factory=model.factory)
    await restored.store.recover()
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.AWAITING_CLARIFICATION
    try:
        await (await restored.answer(mission.id, ClarificationAnswerRequest(question_id=question.id, answer="Use 3")))
        result = await restored.db.get_mission(mission.id)
        assert result.status == MissionStatus.VERIFYING, result.failure_reason
        assert result.budgets.repair_rounds_used == 1
        assert result.budgets.model_turns_used > paused.budgets.model_turns_used
        assert result.budgets.time_used_seconds >= paused.budgets.time_used_seconds
        assert model.developer_runs == 2 and len(executor.calls) == 3
        assert model.repair_contexts[-1]["clarification_answers"][0]["answer"] == "Use 3"
    finally:
        await restored.close()


@pytest.mark.asyncio
async def test_clarification_loop_is_bounded(recovery):
    controller, mission, model, _, _ = recovery
    model.clarify_initial = model.keep_clarifying = True
    await set_budgets(controller, mission, max_clarifications=1)
    await run(recovery)
    question = (await controller.store.records(Clarification, mission.id))[0]
    await (await controller.answer(mission.id, ClarificationAnswerRequest(question_id=question.id, answer="Use 3")))
    result = await controller.db.get_mission(mission.id)
    assert result.status == MissionStatus.BUDGET_EXHAUSTED
    assert result.budgets.clarifications_used == 1
    assert len(await controller.store.records(Clarification, mission.id)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", ["workspace", "candidate", "scope"])
async def test_stale_clarification_is_rejected_without_consuming_answer(recovery, tamper):
    controller, mission, model, _, _ = recovery
    model.clarify_initial = True
    await run(recovery)
    question = (await controller.store.records(Clarification, mission.id))[0]
    if tamper == "scope":
        async with controller.store.transaction() as connection:
            await connection.execute("UPDATE missions SET scope_version=2 WHERE id=?", (mission.id,))
    else:
        directory = controller.workspaces.get_mission_workspace_dir(mission.id) if tamper == "workspace" else controller.workspaces.get_candidate_dir(mission.id, question.candidate_id)
        (directory / "app.py").write_text("tampered = True\n")
    with pytest.raises(GuildConflict):
        await controller.answer(mission.id, ClarificationAnswerRequest(question_id=question.id, answer="Use 3"))
    assert (await controller.store.records(Clarification, mission.id))[0].status == "OPEN"


@pytest.mark.asyncio
async def test_concurrent_answers_claim_exactly_one_continuation(recovery):
    controller, mission, model, _, _ = recovery
    model.clarify_initial = True
    await run(recovery)
    question = (await controller.store.records(Clarification, mission.id))[0]
    request = ClarificationAnswerRequest(question_id=question.id, answer="Use 3")
    outcomes = await asyncio.gather(controller.answer(mission.id, request), controller.answer(mission.id, request), return_exceptions=True)
    jobs = [value for value in outcomes if isinstance(value, asyncio.Task)]
    assert len(jobs) == 1 and sum(isinstance(value, GuildConflict) for value in outcomes) == 1
    await jobs[0]
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.READY_FOR_AUTHORIZATION


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["weaken_criteria", "unknown_finding"])
async def test_repair_plan_cannot_weaken_scope_or_invent_findings(recovery, mode):
    controller, mission, model, _, _ = recovery
    setattr(model, mode, True)
    result = await run(recovery)
    assert result.status == MissionStatus.BLOCKED
    assert model.developer_runs == 1
    assert (await controller.store.context(mission.id))["plan_revision"] == 1


@pytest.mark.asyncio
async def test_environment_failure_does_not_trigger_code_repairs(recovery):
    _, _, model, executor, _ = recovery
    executor.environment_failure = True
    result = await run(recovery)
    assert result.status == MissionStatus.BLOCKED
    assert result.budgets.repair_rounds_used == 0 and "repair" not in model.turns


@pytest.mark.asyncio
async def test_prior_review_finding_requires_resolution_on_new_candidate(recovery):
    controller, mission, model, executor, _ = recovery
    model.initial_review_fails = True
    executor.never_fail = True
    result = await run(recovery)
    assert result.status == MissionStatus.VERIFYING, result.failure_reason
    finding = next(f for f in await controller.store.records(Finding, mission.id) if f.source_agent == "SHADOW_COUNCIL")
    assert finding.status == FindingStatus.RESOLVED and finding.resolution_evidence_ids


@pytest.mark.asyncio
async def test_omitted_review_resolution_cannot_silently_pass(recovery):
    controller, mission, model, executor, _ = recovery
    model.initial_review_fails = model.ignore_prior_review = True
    executor.never_fail = True
    await set_budgets(controller, mission, max_repair_rounds=1)
    result = await run(recovery)
    assert result.status == MissionStatus.BUDGET_EXHAUSTED
    assert any(f.candidate_id == result.active_candidate_id and f.title == "Unresolved prior review finding" for f in await controller.store.records(Finding, mission.id))


@pytest.mark.asyncio
async def test_api_clarification_validation_and_cancelled_answer(recovery, monkeypatch):
    from app.main import app
    controller, mission, model, _, _ = recovery
    monkeypatch.setattr("app.storage.database._db_instance", controller.db)
    monkeypatch.setattr("app.services.guild_service._controller", controller)
    model.clarify_initial = True
    await run(recovery)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        detail = (await client.get(f"/api/missions/{mission.id}")).json()
        question = detail["clarifications"][0]
        path = f"/api/missions/{mission.id}/clarifications"
        assert (await client.post(path, json={"question_id": question["id"], "answer": "  "})).status_code == 422
        assert (await client.post(path, json={"question_id": "missing", "answer": "3"})).status_code == 404
        assert (await client.post(f"/api/missions/{mission.id}/cancel")).status_code == 200
        assert (await client.post(path, json={"question_id": question["id"], "answer": "3"})).status_code == 409


def test_repair_limit_cannot_exceed_three():
    with pytest.raises(ValidationError):
        MissionBudgets(max_repair_rounds=4)


@pytest.mark.asyncio
async def test_no_progress_does_not_replay_candidate_checks(recovery):
    controller, mission, model, executor, _ = recovery
    model.no_progress = True
    result = await run(recovery)
    assert result.status == MissionStatus.BLOCKED
    assert "not replayed" in result.failure_reason
    assert len(executor.calls) == 2
    assert len(await controller.store.records(Candidate, mission.id)) == 2


@pytest.mark.asyncio
async def test_elapsed_budget_is_not_reset_by_clarification_resume(recovery):
    controller, mission, model, _, _ = recovery
    model.clarify_initial = True
    await run(recovery)
    question = (await controller.store.records(Clarification, mission.id))[0]
    before = dict(model.turns)
    await set_budgets(controller, mission, max_time_seconds=1, time_used_seconds=1.0)
    await (await controller.answer(mission.id, ClarificationAnswerRequest(question_id=question.id, answer="Use 3")))
    result = await controller.db.get_mission(mission.id)
    assert result.status == MissionStatus.BUDGET_EXHAUSTED
    assert model.turns == before
    assert result.budgets.time_used_seconds >= 1.0


@pytest.mark.asyncio
async def test_cancel_during_repair_releases_writer_lease(recovery):
    controller, mission, model, _, _ = recovery
    paused = asyncio.Event()

    async def respond(request):
        body = json.loads(request.content)
        if any(t["name"] == "submit_candidate" for t in body["tools"]) and model.developer_runs == 2:
            paused.set()
            await asyncio.Event().wait()
        return model.respond(request)

    def factory():
        return ModelAdapter(settings=Settings(model_provider="anthropic", anthropic_api_key="test", anthropic_base_url="https://example.test/v1"),
                            transport=httpx.MockTransport(respond))

    controller.adapter_factory = factory
    await (await controller.start(mission.id, "plan"))
    await controller.start(mission.id, "execute", 1)
    await asyncio.wait_for(paused.wait(), 10)
    assert controller.workspaces._leases
    await controller.cancel(mission.id)
    assert not controller.workspaces._leases
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.CANCELLED
    assert (controller.workspaces.get_mission_workspace_dir(mission.id) / "app.py").read_text() == "value = 2\n"


@pytest.mark.asyncio
async def test_api_answer_starts_one_read_only_continuation(recovery, monkeypatch):
    from app.main import app
    controller, mission, model, executor, _ = recovery
    model.clarify_initial = True
    monkeypatch.setattr("app.storage.database._db_instance", controller.db)
    monkeypatch.setattr("app.services.guild_service._controller", controller)
    await run(recovery)
    question = (await controller.store.records(Clarification, mission.id))[0]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/missions/{mission.id}/clarifications", json={"question_id": question.id, "answer": "Exactly 3"})
        assert response.status_code == 202
        await asyncio.gather(*list(controller.jobs.values()))
        detail = (await client.get(f"/api/missions/{mission.id}")).json()
        assert detail["mission"]["status"] == "READY_FOR_AUTHORIZATION"
        assert detail["clarifications"][0]["status"] == "ANSWERED"
        assert detail["plan_revision"] == 1
    assert len(executor.calls) == 1 and model.developer_runs == 0
