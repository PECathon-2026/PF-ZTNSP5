import json

import httpx
import pytest
import pytest_asyncio

from app.schemas.guild import AcceptanceTestDecision
from app.schemas.mission import MissionStatus
from app.schemas.candidate import Candidate
from app.services.approval_service import ApprovalService
from app.services.execution_service import ContainerExecutor
from app.storage.guild import GuildConflict
from tests.report_fixtures import passing_report
from tests.unit.test_m4_guild import guild, tool


@pytest_asyncio.fixture
async def reviewed(guild):
    controller, mission, model, _, repo = guild
    original = model.respond
    captured = []

    class Checks(ContainerExecutor):
        async def run(self, directory, profile, selector=None):
            generated = (directory / "test_kage_value.py").exists()
            value = (directory / "app.py").read_text()
            captured.append((profile, selector, generated, value))
            if profile == "python_bandit":
                return {"status": "SUCCEEDED", "exit_code": 0, "stdout": "", "stderr": "", "duration_ms": 1,
                        "command": ["docker", "bandit"], "report": {"results": [], "errors": [], "truncated": False}}
            node = selector or ("test_kage_value.py::test_value_two" if generated else "test_app.py::test_get")
            report = passing_report(node)
            code = 0
            if generated and "value = 1" in value:
                code = 1
                report["exitcode"] = 1
                report["summary"] = {"failed": 1, "passed": 0, "total": 1, "collected": 1}
                report["tests"][0].update(outcome="failed", call="failed")
            return {"status": "FAILED" if code else "SUCCEEDED", "exit_code": code, "stdout": "fixture result",
                    "stderr": "", "duration_ms": 1, "execution_source": "docker",
                    "command": ["docker", "pytest", "--", selector] if selector else ["docker", "pytest"], "report": report}

    def with_designer(request):
        body = json.loads(request.content)
        if not any(t["name"] == "submit_acceptance_tests" for t in body["tools"]):
            return original(request)
        if len(body["messages"]) == 1:
            calls = [tool("read_file", {"relative_path": "app.py"}, "design-read")]
        else:
            calls = [tool("submit_acceptance_tests", {"summary": "Verify value two",
                "files": [{"path": "test_kage_value.py", "content": "def test_value_two():\n    from app import value\n    assert value == 2\n"}],
                "mappings": [{"criterion_description": "Return value 2", "test_selectors": ["test_kage_value.py::test_value_two"]}]}, "design-submit")]
        return httpx.Response(200, json={"content": calls, "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1}})

    model.respond = with_designer
    controller.executor = Checks()
    await (await controller.start(mission.id, "plan"))
    state = await controller.db.get_mission(mission.id)
    assert state.status == MissionStatus.READY_FOR_AUTHORIZATION, state.failure_reason
    yield controller, mission, repo, captured


@pytest.mark.asyncio
async def test_reviewed_tests_allow_all_agents_to_finish_without_modifying_original_tests(reviewed):
    controller, mission, repo, calls = reviewed
    context = await controller.store.context(mission.id)
    digest = context["acceptance_tests"]["hash"]
    assert context["acceptance_tests"]["accepted"] is False
    assert not any(item[2] for item in calls)  # proposed code has NOT run
    with pytest.raises(GuildConflict, match="human review"):
        await controller.start(mission.id, "execute", 1)
    await controller.review_tests(mission.id, AcceptanceTestDecision(proposal_hash=digest, accept=True))
    assert not any(item[2] for item in calls)  # accepting tests alone does NOT execute them
    await (await controller.start(mission.id, "execute", 1))
    state = await controller.db.get_mission(mission.id)
    assert state.status == MissionStatus.VERIFYING, state.failure_reason
    assert any(generated and "value = 1" in source for _, _, generated, source in calls)
    assert any(generated and "value = 2" in source for _, _, generated, source in calls)
    candidate = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == state.active_candidate_id)
    assert candidate.changed_files == ["app.py"]
    assert not (controller.workspaces.get_candidate_dir(mission.id, candidate.id) / "test_kage_value.py").exists()
    assert not (repo / "test_kage_value.py").exists()
    assert (repo / "app.py").read_text() == "value = 1\n"
    assert (await ApprovalService(controller).verify(mission.id)).status == MissionStatus.VERIFIED_AWAITING_APPROVAL


@pytest.mark.asyncio
async def test_stale_or_rejected_test_proposal_does_not_start_developer(reviewed):
    controller, mission, _, _ = reviewed
    with pytest.raises(GuildConflict, match="stale"):
        await controller.review_tests(mission.id, AcceptanceTestDecision(proposal_hash="0" * 64, accept=True))
    context = await controller.store.context(mission.id)
    await controller.review_tests(mission.id, AcceptanceTestDecision(proposal_hash=context["acceptance_tests"]["hash"], accept=False))
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.BLOCKED
    with pytest.raises(GuildConflict):
        await controller.start(mission.id, "execute", 1)


@pytest.mark.asyncio
async def test_changed_test_proposal_cannot_be_accepted_with_old_hash(reviewed):
    controller, mission, _, _ = reviewed
    context = await controller.store.context(mission.id)
    digest = context["acceptance_tests"]["hash"]
    context["acceptance_tests"]["proposal"]["files"][0]["content"] = "def test_weakened():\n    assert True\n"
    async with controller.store.transaction() as db:
        await db.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission.id))
    with pytest.raises(GuildConflict, match="changed"):
        await controller.review_tests(mission.id, AcceptanceTestDecision(proposal_hash=digest, accept=True))


@pytest.mark.asyncio
async def test_cli_reviews_proposal_before_authorize_and_stops_before_final_apply(reviewed):
    from app.cli import Console
    controller, mission, repo, calls = reviewed
    context = await controller.store.context(mission.id)
    digest = context["acceptance_tests"]["hash"]
    output = []
    answers = iter(["ACCEPT TESTS " + digest, "AUTHORIZE"])
    code = await Console(ask=lambda _: next(answers), say=output.append).workflow(controller, mission.id)
    assert code == 0
    assert any("assert value == 2" in line for line in output)
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.VERIFIED_AWAITING_APPROVAL
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_changed_accepted_test_bundle_invalidates_verification(reviewed):
    controller, mission, _, _ = reviewed
    context = await controller.store.context(mission.id)
    await controller.review_tests(mission.id, AcceptanceTestDecision(proposal_hash=context["acceptance_tests"]["hash"], accept=True))
    await (await controller.start(mission.id, "execute", 1))
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.VERIFYING
    context = await controller.store.context(mission.id)
    context["acceptance_tests"]["proposal"]["files"][0]["content"] += "\n# changed\n"
    async with controller.store.transaction() as db:
        await db.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission.id))
    with pytest.raises(GuildConflict, match="changed"):
        await ApprovalService(controller).verify(mission.id)


@pytest.mark.asyncio
async def test_test_review_api_is_hash_bound_and_blocks_authorize_until_review(reviewed, monkeypatch):
    from app.main import app
    controller, mission, _, _ = reviewed
    monkeypatch.setattr("app.storage.database._db_instance", controller.db)
    monkeypatch.setattr("app.services.guild_service._controller", controller)
    context = await controller.store.context(mission.id)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        prefix = f"/api/missions/{mission.id}"
        detail = (await client.get(prefix)).json()
        assert detail["acceptance_test_proposal"]["accepted"] is False
        assert (await client.post(prefix + "/authorize", json={"scope_version": 1})).status_code == 409
        assert (await client.post(prefix + "/acceptance-tests/review", json={"proposal_hash": "0" * 64, "accept": True})).status_code == 409
        result = await client.post(prefix + "/acceptance-tests/review", json={"proposal_hash": context["acceptance_tests"]["hash"], "accept": True})
        assert result.status_code == 200
        assert result.json()["acceptance_test_proposal"]["accepted"] is True


def test_proposed_tests_cannot_overwrite_existing_files_or_invent_mappings(tmp_path):
    from app.schemas.guild import AcceptanceTestProposal
    from app.services.acceptance_tests import validate_proposal
    data = {"summary": "test", "files": [{"path": "test_kage_new.py", "content": "def test_new():\n    assert 1 == 1\n"}],
            "mappings": [{"criterion_description": "new behavior", "test_selectors": ["test_kage_new.py::test_new"]}]}
    proposal = AcceptanceTestProposal.model_validate(data)
    validate_proposal(proposal, tmp_path, ["new behavior"])
    with pytest.raises(ValueError, match="mapping"):
        validate_proposal(proposal, tmp_path, ["other behavior"])
    (tmp_path / "test_kage_new.py").write_text("# original")
    with pytest.raises(ValueError, match="replace"):
        validate_proposal(proposal, tmp_path, ["new behavior"])
