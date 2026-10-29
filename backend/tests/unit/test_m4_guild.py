import asyncio
import json

import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.agents.model_adapter import ModelAdapter, ModelAdapterConfig
from app.agents.guild import SentinelRunner
from app.schemas.agent_message import AgentMessage, MessageType
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence, EvidenceKind
from app.schemas.finding import Finding
from app.schemas.guild import GuildPlan
from app.schemas.mission import AcceptanceCriterion, Mission, MissionStatus
from app.schemas.task import MissionTask, TaskStatus
from app.services.execution_service import ContainerExecutor
from app.services.guild_service import GuildController
from app.services.repository_service import RepositoryService
from app.services.workspace_service import WorkspaceService
from app.settings import Settings
from app.storage.artifacts import ArtifactStorage
from app.storage.database import Database
from app.storage.guild import GuildConflict, GuildStore


def tool(name, arguments, call_id):
    return {"type": "tool_use", "name": name, "input": arguments, "id": call_id}


def plan_payload():
    return {
        "summary": "Update value while preserving the interface",
        "criteria": [{"description": "Return value 2", "check_profile": "python_pytest"}],
        "tasks": [{"key": "change", "title": "Update value", "description": "Change value from 1 to 2", "dependencies": []}],
    }


class ScriptedGuildModel:
    """Actual adapter protocol with deterministic proposals; never calls a real LLM."""
    def __init__(self):
        self.turns = {}
        self.review_finding = False
        self.plan = plan_payload()

    def factory(self):
        return ModelAdapter(
            settings=Settings(model_provider="anthropic", anthropic_api_key="test-key", anthropic_base_url="https://example.test/v1"),
            config=ModelAdapterConfig(retry_base_delay=0.0), transport=httpx.MockTransport(self.respond),
        )

    def respond(self, request):
        body = json.loads(request.content)
        prompt = body["system"]
        role = "SHOGUN" if "You are SHOGUN" in prompt else "SHADOW_COUNCIL" if "You are SHADOW_COUNCIL" in prompt else "SAMURAI"
        turn = self.turns.get(role, 0) + 1
        self.turns[role] = turn
        if role == "SHOGUN":
            calls = [tool("read_file", {"relative_path": "app.py"}, "plan-read")] if turn == 1 else [tool("submit_plan", self.plan, "plan-submit")]
        elif role == "SAMURAI":
            iteration = (turn - 1) // 4
            turn = (turn - 1) % 4 + 1
            if turn == 1:
                calls = [tool("read_file", {"relative_path": "app.py"}, "dev-read")]
            elif turn == 2:
                output = json.loads(body["messages"][-1]["content"][0]["content"])
                calls = [tool("apply_patch", {"relative_path": "app.py", "target": f"value = {iteration + 1}", "replacement": f"value = {iteration + 2}", "expected_fingerprint": output["fingerprint"]}, "dev-patch")]
            elif turn == 3:
                calls = [tool("read_file", {"relative_path": "app.py"}, "dev-read-back"), tool("read_diff", {"relative_path": "app.py"}, "dev-diff")]
            else:
                calls = [tool("submit_candidate", {"summary": "Source ready"}, "dev-submit")]
        else:
            if turn == 1:
                calls = [tool("read_file", {"relative_path": "app.py"}, "review-read"), tool("read_diff", {"relative_path": "app.py"}, "review-diff")]
            else:
                context = json.loads(body["messages"][0]["content"])
                findings = [{
                    "severity": "HIGH", "title": "Review defect", "description": "Contract mismatch",
                    "observed_behavior": "Value changed", "expected_behavior": "Preserve public behavior",
                    "file_path": "app.py", "evidence_ids": [context["evidence"][0]["id"]],
                }] if self.review_finding else []
                calls = [tool("submit_review", {"summary": "Diff inspected", "findings": findings}, "review-submit")]
        return httpx.Response(200, json={"content": calls, "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 10}})


class FakeExecutor:
    def __init__(self):
        self.calls = []
        self.final_code = 1
        self.status = "FAILED"
        self.block_baseline = False

    async def run(self, directory, profile, test_selector=None):
        self.calls.append((directory, profile))
        baseline = len(self.calls) == 1
        if baseline and self.block_baseline:
            code, status = 126, "BLOCKED"
        else:
            code = 0 if baseline else self.final_code
            status = "SUCCEEDED" if code == 0 else self.status
        await asyncio.sleep(0)
        return {
            "status": status, "exit_code": code, "duration_ms": 12,
            "stdout": "1 passed" if code == 0 else "FAILED test_value: assertion mismatch",
            "stderr": "", "command": ["python", "-m", "pytest", "-q"],
        }


@pytest_asyncio.fixture
async def guild(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "test_app.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    repositories = RepositoryService()
    monkeypatch.setattr(repositories, "_check_docker", lambda: True)
    record = repositories.connect_repository(str(repo))
    monkeypatch.setattr("app.services.repository_service._repo_service_instance", repositories)
    db = Database(tmp_path / "guild.db")
    await db.init_db()
    model, executor = ScriptedGuildModel(), FakeExecutor()
    controller = GuildController(
        database=db, workspaces=WorkspaceService(tmp_path / "workspaces"),
        artifacts=ArtifactStorage(tmp_path / "artifacts"), executor=executor, adapter_factory=model.factory,
        auto_repair=False,
    )
    mission = Mission(repository_id=record["repository_id"], request_text="Return value 2", status=MissionStatus.PLANNING)
    await db.create_mission(mission, [AcceptanceCriterion(mission_id=mission.id, description="Return value 2")])
    yield controller, mission, model, executor, repo
    await controller.close()


async def plan_and_execute(guild):
    controller, mission, _, _, _ = guild
    await (await controller.start(mission.id, "plan"))
    planned = await controller.db.get_mission(mission.id)
    assert planned.status == MissionStatus.READY_FOR_AUTHORIZATION, planned.failure_reason
    await (await controller.start(mission.id, "execute", planned.scope_version))
    return await controller.db.get_mission(mission.id)


@pytest.mark.asyncio
async def test_m4_exit_failure_reopens_task_and_routes_evidence(guild):
    controller, mission, _, executor, repo = guild
    result = await plan_and_execute(guild)
    assert result.status == MissionStatus.REPAIRING, result.failure_reason
    tasks = await controller.db.get_tasks(mission.id)
    developer = next(t for t in tasks if t.owner_agent == "SAMURAI")
    assert developer.status == TaskStatus.READY and developer.attempt == 2
    assert all(t.status == TaskStatus.BLOCKED for t in tasks if t.owner_agent != "SAMURAI")
    findings = await controller.store.records(Finding, mission.id)
    failure = next(f for f in findings if f.source_agent == "SENTINEL")
    evidence = await controller.store.records(Evidence, mission.id)
    failed_check = next(e for e in evidence if e.id in failure.evidence_ids)
    assert failed_check.exit_code == 1 and failed_check.metadata["classification"] == "CODE_FAILURE"
    assert failed_check.duration_ms == 12
    messages = await controller.store.records(AgentMessage, mission.id)
    routed = [m for m in messages if m.type == MessageType.FINDING]
    assert {m.recipient for m in routed} == {"SHOGUN", "SAMURAI"}
    assert all(m.candidate_id == result.active_candidate_id and m.evidence_ids == failure.evidence_ids for m in routed)
    assert all(m.payload["reopened_task_ids"] == [developer.id] for m in routed)
    assert (repo / "app.py").read_text() == "value = 1\n"
    assert all("candidates" in directory.parts for directory, _ in executor.calls)
    assert not controller.workspaces._leases
    # Durable evidence is usable after reconstructing the store, not just from memory.
    restored = GuildStore(Database(controller.db.db_path))
    assert len(await restored.records(Candidate, mission.id)) == 2
    assert (await restored.records(MissionTask, mission.id))[0].attempt == 2
    assert controller.artifacts.read_artifact(mission.id, failed_check.stdout_artifact_id).startswith("FAILED")
    assert all(c.status.value == "PENDING" for c in await controller.db.get_criteria(mission.id))
    baseline = (await restored.records(Candidate, mission.id))[0]
    with pytest.raises(GuildConflict, match="active candidate"):
        await controller.route_findings(mission.id, "obsolete-operation", baseline)


@pytest.mark.asyncio
async def test_success_stops_at_verifier_boundary(guild):
    controller, mission, _, executor, _ = guild
    executor.final_code = 0
    result = await plan_and_execute(guild)
    assert result.status == MissionStatus.VERIFYING, result.failure_reason
    assert all(t.status == TaskStatus.DONE for t in await controller.db.get_tasks(mission.id))
    assert result.budgets.model_turns_used == 8
    assert not await controller.store.records(Finding, mission.id)


@pytest.mark.asyncio
async def test_reviewer_finding_also_routes_to_developer(guild):
    controller, mission, model, executor, _ = guild
    executor.final_code = 0
    model.review_finding = True
    result = await plan_and_execute(guild)
    assert result.status == MissionStatus.REPAIRING, result.failure_reason
    findings = await controller.store.records(Finding, mission.id)
    assert findings[0].source_agent == "SHADOW_COUNCIL"
    assert any(m.recipient == "SAMURAI" and m.sender == "SHADOW_COUNCIL" for m in await controller.store.records(AgentMessage, mission.id))


@pytest.mark.asyncio
async def test_environment_failure_blocks_without_repairing_code(guild):
    controller, mission, _, executor, _ = guild
    executor.final_code, executor.status = 126, "BLOCKED"
    result = await plan_and_execute(guild)
    assert result.status == MissionStatus.BLOCKED
    developer = (await controller.db.get_tasks(mission.id))[0]
    assert developer.attempt == 1 and developer.status == TaskStatus.DONE
    assert any(m.type == MessageType.BLOCKER for m in await controller.store.records(AgentMessage, mission.id))


@pytest.mark.asyncio
async def test_missing_docker_blocks_before_models_or_edits(guild):
    controller, mission, model, executor, repo = guild
    executor.block_baseline = True
    await (await controller.start(mission.id, "plan"))
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.BLOCKED
    assert not model.turns
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_stale_authorization_and_duplicate_start_are_rejected(guild):
    controller, mission, _, _, _ = guild
    with pytest.raises(GuildConflict):
        await controller.start(mission.id, "execute", 1)
    first = await controller.start(mission.id, "plan")
    with pytest.raises(GuildConflict):
        await controller.start(mission.id, "plan")
    await first
    with pytest.raises(GuildConflict):
        await controller.start(mission.id, "execute", 999)
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.READY_FOR_AUTHORIZATION


@pytest.mark.asyncio
async def test_cancel_running_operation_preserves_cancelled_status(guild):
    controller, mission, _, executor, _ = guild
    entered, cleaned = asyncio.Event(), asyncio.Event()

    async def slow(*args):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    executor.run = slow
    await controller.start(mission.id, "plan")
    await entered.wait()
    await controller.cancel(mission.id)
    assert cleaned.is_set()
    result = await controller.db.get_mission(mission.id)
    assert result.status == MissionStatus.CANCELLED and result.cancel_requested
    assert not controller.jobs


@pytest.mark.asyncio
async def test_restart_marks_interrupted_without_replaying(guild):
    controller, mission, model, _, _ = guild
    await controller.store.claim(mission.id, "plan")
    restored = GuildStore(Database(controller.db.db_path))
    await restored.recover()
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.INTERRUPTED
    assert not model.turns


@pytest.mark.parametrize("tasks", [
    [{"key": "a", "dependencies": ["a"]}],
    [{"key": "a", "dependencies": ["b"]}, {"key": "b", "dependencies": ["a"]}],
    [{"key": "a", "dependencies": ["missing"]}],
    [{"key": "a", "dependencies": []}, {"key": "a", "dependencies": []}],
])
def test_planner_rejects_invalid_dag(tasks):
    payload = plan_payload()
    payload["tasks"] = [{**item, "title": "Task", "description": "Implement"} for item in tasks]
    with pytest.raises(ValidationError):
        GuildPlan.model_validate(payload)


@pytest.mark.asyncio
async def test_evidence_fingerprint_binding_is_transactional(guild):
    controller, mission, _, _, _ = guild
    token = await controller.store.claim(mission.id, "plan")
    candidate = Candidate(mission_id=mission.id, workspace_snapshot_id="snapshot", content_fingerprint="abc")
    evidence = Evidence(mission_id=mission.id, candidate_id=candidate.id, kind=EvidenceKind.TEST, source="SENTINEL", fingerprint="wrong")
    with pytest.raises(GuildConflict):
        await controller.store.commit(mission.id, token, entities=[candidate, evidence])
    assert not await controller.store.records(Candidate, mission.id)
    assert not await controller.store.records(Evidence, mission.id)


@pytest.mark.asyncio
async def test_sentinel_rejects_changed_snapshot(guild):
    controller, mission, _, executor, _ = guild
    controller.workspaces.create_disposable_workspace(mission.id, mission.repository_id)
    candidate = controller.workspaces.freeze_candidate(mission.id, mission.repository_id)
    directory = controller.workspaces.get_candidate_dir(mission.id, candidate.id)
    (directory / "app.py").write_text("tampered = True\n")
    with pytest.raises(ValueError, match="fingerprint"):
        await SentinelRunner(executor, controller.workspaces, controller.artifacts).run(candidate, ["python_pytest"])
    assert not executor.calls


@pytest.mark.asyncio
async def test_parallel_events_have_unique_monotonic_sequences(guild):
    controller, mission, _, _, _ = guild
    await asyncio.gather(*(controller.db.emit_event(mission.id, "TEST", "SYSTEM", {}) for _ in range(10)))
    assert [event.sequence for event in await controller.db.get_events(mission.id)] == list(range(1, 11))


def test_container_policy_and_selector_rejection(tmp_path):
    executor = ContainerExecutor()
    command = executor.command(tmp_path, "python_pytest", "devpilot-test", "tests/test_app.py::test_one")
    assert command[command.index("--user") + 1] == "1001:1001"
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--pull") + 1] == "never"
    assert "--read-only" in command and "ALL" in command
    assert command[-2:] == ["--", "tests/test_app.py::test_one"]
    for selector in ["--help", "../escape", "/etc/passwd", "tests/x;whoami", "C:/secrets"]:
        with pytest.raises(ValueError):
            executor.command(tmp_path, "python_pytest", "devpilot-test", selector)
    with pytest.raises(ValueError):
        executor.command(tmp_path, "arbitrary_shell", "devpilot-test")


@pytest.mark.asyncio
async def test_execution_blocks_without_any_subprocess_fallback(tmp_path, monkeypatch):
    executor = ContainerExecutor()

    async def unavailable():
        return False

    async def forbidden(*args, **kwargs):
        pytest.fail("Repository process was launched without Docker")

    monkeypatch.setattr(executor, "available", unavailable)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    result = await executor.run(tmp_path)
    assert result["status"] == "BLOCKED" and result["exit_code"] == 126


@pytest.mark.asyncio
async def test_dependency_order_and_reopening_preserve_candidate_chain(guild):
    controller, mission, model, _, _ = guild
    model.plan["tasks"].append({"key": "followup", "title": "Follow up", "description": "Change value 2 to 3", "dependencies": ["change"]})
    result = await plan_and_execute(guild)
    assert result.status == MissionStatus.REPAIRING, result.failure_reason
    developers = [t for t in await controller.db.get_tasks(mission.id) if t.owner_agent == "SAMURAI"]
    assert [t.status for t in developers] == [TaskStatus.READY, TaskStatus.PENDING]
    assert developers[1].dependencies == [developers[0].id]
    candidates = await controller.store.records(Candidate, mission.id)
    assert len(candidates) == 3
    assert candidates[1].parent_candidate_id == candidates[0].id
    assert candidates[2].parent_candidate_id == candidates[1].id
    assert candidates[1].state.value == "SUPERSEDED"
    first_snapshot = controller.workspaces.get_candidate_dir(mission.id, candidates[1].id)
    assert (first_snapshot / "app.py").read_text() == "value = 2\n"


@pytest.mark.asyncio
async def test_api_authorization_and_durable_candidate_reads(guild, monkeypatch):
    from app.main import app
    controller, mission, _, _, _ = guild
    monkeypatch.setattr("app.storage.database._db_instance", controller.db)
    monkeypatch.setattr("app.services.guild_service._controller", controller)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/missions/{mission.id}/plan")
        assert response.status_code == 202
        await asyncio.gather(*list(controller.jobs.values()))
        assert (await client.post(f"/api/missions/{mission.id}/authorize", json={"scope_version": 999})).status_code == 409
        assert (await client.post(f"/api/missions/{mission.id}/authorize", json={"scope_version": 1})).status_code == 202
        await asyncio.gather(*list(controller.jobs.values()))
        detail = (await client.get(f"/api/missions/{mission.id}")).json()
        assert detail["mission"]["status"] == "REPAIRING"
        candidate_id = detail["mission"]["active_candidate_id"]
        assert detail["messages"] and detail["findings"] and detail["evidence"]
        # Read after dropping all in-memory candidate/repository metadata.
        controller.workspaces._candidates.clear()
        from app.services.repository_service import get_repository_service
        get_repository_service()._repositories.clear()
        prefix = f"/api/missions/{mission.id}/candidates/{candidate_id}"
        diff = await client.get(prefix + "/diff")
        assert diff.status_code == 200 and "+value = 2" in diff.json()["unified_diff"]
        source = await client.get(prefix + "/file", params={"path": "app.py"})
        assert source.status_code == 200 and "value = 2" in source.json()["content"]
        assert (await client.get(prefix + "/file", params={"path": "../secret"})).status_code == 403
        evidence = detail["evidence"][-1]
        assert (await client.get(f"/api/missions/{mission.id}/evidence/{evidence['id']}")).status_code == 200
        assert (await client.get(f"/api/missions/other/evidence/{evidence['id']}")).status_code == 404
        assert (await client.get(f"/api/missions/other/candidates/{candidate_id}/diff")).status_code == 404


@pytest.mark.asyncio
async def test_output_draining_is_bounded_and_keeps_consuming():
    reader = asyncio.StreamReader()
    reader.feed_data(b"x" * 100000)
    reader.feed_eof()
    text, truncated = await ContainerExecutor()._drain(reader, 100)
    assert text == "x" * 100 and truncated and reader.at_eof()


@pytest.mark.asyncio
async def test_reviewer_cannot_cite_invented_evidence(guild):
    controller, mission, model, executor, _ = guild
    original = model.respond

    def response(request):
        result = original(request)
        payload = result.json()
        for block in payload["content"]:
            if block["name"] == "submit_review":
                block["input"]["findings"][0]["evidence_ids"] = ["ev-invented"]
        return httpx.Response(200, json=payload)

    model.respond = response
    model.review_finding = True
    executor.final_code = 0
    result = await plan_and_execute(guild)
    assert result.status == MissionStatus.BLOCKED
    assert not await controller.store.records(Finding, mission.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_container_timeout_or_cancellation_kills_and_removes(tmp_path, monkeypatch, cancel):
    from app.settings import get_settings
    executor = ContainerExecutor()
    launched = asyncio.Event()
    removed = []

    class Process:
        returncode = None

        def __init__(self):
            self.done = asyncio.Event()
            self.stdout, self.stderr = asyncio.StreamReader(), asyncio.StreamReader()
            self.stdout.feed_data(b"partial test output")
            self.stdout.feed_eof()
            self.stderr.feed_eof()

        async def wait(self):
            await self.done.wait()
            return self.returncode

        def kill(self):
            self.returncode = -9
            self.done.set()

    process = Process()

    async def available():
        return True

    async def create(*args, **kwargs):
        assert args[:2] == ("docker", "run")
        launched.set()
        return process

    async def remove(name):
        removed.append(name)

    monkeypatch.setattr(executor, "available", available)
    monkeypatch.setattr(executor, "_remove", remove)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(get_settings(), "check_timeout_seconds", 0.02)
    job = asyncio.create_task(executor.run(tmp_path))
    await launched.wait()
    if cancel:
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
    else:
        result = await job
        assert result["status"] == "TIMED_OUT" and result["exit_code"] == 124
        assert result["stdout"] == "partial test output"
    assert process.returncode == -9
    assert len(removed) == 1 and removed[0].startswith("devpilot-")


@pytest.mark.asyncio
async def test_shogun_cannot_edit_source(guild):
    controller, mission, model, _, repo = guild

    def forbidden(request):
        count = model.turns.get("SHOGUN", 0) + 1
        model.turns["SHOGUN"] = count
        return httpx.Response(200, json={
            "content": [tool("apply_patch", {"relative_path": "app.py", "content": "unsafe"}, f"forbidden-{count}")],
            "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    model.respond = forbidden
    await (await controller.start(mission.id, "plan"))
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.BLOCKED
    assert (repo / "app.py").read_text() == "value = 1\n"
    assert (controller.workspaces.get_mission_workspace_dir(mission.id) / "app.py").read_text() == "value = 1\n"


def test_artifact_redacts_configured_backend_credentials(tmp_path, monkeypatch):
    from app.settings import get_settings
    monkeypatch.setattr(get_settings(), "azure_openai_api_key", "synthetic-backend-key")
    artifacts = ArtifactStorage(tmp_path)
    artifact_id, _ = artifacts.save_artifact("miss-test", "stdout.txt", "key=synthetic-backend-key")
    assert artifacts.read_artifact("miss-test", artifact_id) == "key=[REDACTED]"
