import asyncio
import json
import httpx
from pathlib import Path

import pytest

from app.schemas.candidate import Candidate, CandidateState
from app.schemas.evidence import Evidence, EvidenceKind
from app.schemas.finding import Finding, FindingSeverity
from app.schemas.mission import MissionStatus
from app.agents.guild import SentinelRunner
from app.services.challenge import challenge_candidate, variants
from app.services.execution_service import ContainerExecutor
from app.services.repo_map import repository_map
from app.services.test_reports import normalize_report, report_passes
from app.services.criterion_checks import criterion_selectors, validate_selector, verification_contract_hash
from app.schemas.mission import AcceptanceCriterion
from app.storage.artifacts import ArtifactStorage
from app.services.workspace_service import WorkspaceService
from tests.report_fixtures import passing_report
from tests.unit.test_m4_guild import guild


def test_structured_reports_reject_skips_wrong_nodes_missing_stages_and_spoofed_summary():
    report = passing_report("test_app.py::test_check")
    assert report_passes(report, 0, ["test_app.py::test_check"])
    assert not report_passes(report, 0, ["test_other.py::test_check"])
    assert not report_passes(report, 1, ["test_app.py::test_check"])
    for field, value in (("call", "skipped"), ("teardown", "failed"), ("setup", None)):
        corrupted = json.loads(json.dumps(report))
        corrupted["tests"][0][field] = value
        assert not report_passes(corrupted, 0, ["test_app.py::test_check"])
    corrupted = json.loads(json.dumps(report))
    corrupted["tests"][0]["nodeid"] = "test_other.py::test_check"
    assert not report_passes(corrupted, 0, ["test_app.py::test_check"])
    corrupted = json.loads(json.dumps(report))
    corrupted["summary"]["total"] = 2
    assert normalize_report(corrupted, 0) is None
    assert not report_passes(None)


def test_parameterized_and_class_test_mappings_are_discovered_without_one_to_one_restriction(tmp_path):
    (tmp_path / "test_calc.py").write_text("class TestMath:\n    def test_boundary(self):\n        assert True\n\ndef test_plain():\n    assert True\n")
    selector = "test_calc.py::TestMath::test_boundary"
    assert validate_selector(tmp_path, selector) == selector
    report = passing_report(selector + "[zero]", selector + "[positive]")
    assert report_passes(report, 0, [selector])
    criterion = AcceptanceCriterion(mission_id="m", description="both", verification_method='test_profile:python_pytest|["' + selector + '", "test_calc.py::test_plain"]')
    assert criterion_selectors(criterion)[1] == [selector, "test_calc.py::test_plain"]
    before = verification_contract_hash(tmp_path, [criterion])
    (tmp_path / "test_calc.py").write_text((tmp_path / "test_calc.py").read_text().replace("assert True", "assert 1 == 1"))
    assert before != verification_contract_hash(tmp_path, [criterion])


def test_bounded_repo_map_discovers_symbols_tests_and_changes_with_source(tmp_path):
    (tmp_path / "service.py").write_text("from math import sqrt\n\ndef transform(value):\n    return sqrt(value)\n")
    (tmp_path / "test_service.py").write_text("def test_transform():\n    assert True\n\nclass TestCases:\n    def test_other(self):\n        assert True\n")
    (tmp_path / ".env").write_text("SECRET=hidden")
    before = repository_map(tmp_path)
    assert {entry["path"] for entry in before["files"]} == {"service.py", "test_service.py"}
    assert "test_service.py::test_transform" in before["files"][1]["tests"]
    assert "test_service.py::TestCases::test_other" in before["files"][1]["tests"]
    assert before["files"][0]["symbols"][0]["name"] == "transform"
    (tmp_path / "service.py").write_text("def transform(value):\n    return value + 1\n")
    assert before["map_fingerprint"] != repository_map(tmp_path)["map_fingerprint"]


@pytest.mark.asyncio
async def test_challenge_runs_isolated_variants_without_touching_candidate(tmp_path, monkeypatch):
    baseline, snapshot = tmp_path / "baseline", tmp_path / "snapshot"
    baseline.mkdir(); snapshot.mkdir()
    (baseline / "module.py").write_text("def threshold(value):\n    return value <= 2\n")
    source = "def threshold(value):\n    return value < 2\n"
    (snapshot / "module.py").write_text(source)
    (snapshot / "test_module.py").write_text("from module import threshold\n\ndef test_boundary():\n    assert not threshold(2)\n")

    class Executor:
        def __init__(self, outcome):
            self.outcome = outcome
            self.calls = 0

        async def run(self, directory, profile):
            self.calls += 1
            assert directory != snapshot
            changed = (directory / "module.py").read_text()
            assert changed != source
            if self.outcome == "DETECTED":
                return {"status": "FAILED", "exit_code": 1,
                        "report": {"tests": [{"outcome": "failed", "call": "failed"}]}}
            return {"status": "SUCCEEDED", "exit_code": 0, "report": passing_report("test_module.py::test_boundary")}

    candidate = Candidate(mission_id="mission-test", workspace_snapshot_id="frozen", content_fingerprint="fingerprint", changed_files=["module.py"])
    from app.settings import get_settings
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path / "runtime")
    for outcome in ("DETECTED", "SURVIVED"):
        executor = Executor(outcome)
        evidence, findings = await challenge_candidate(candidate, baseline, snapshot, executor, ArtifactStorage(tmp_path / "artifacts"))
        assert all(item["outcome"] == outcome for item in evidence.metadata["attempts"])
        assert executor.calls == len(evidence.metadata["attempts"])
        assert bool(findings) == (outcome == "SURVIVED")
        assert (snapshot / "module.py").read_text() == source
        assert not (tmp_path / "runtime" / "challenges" / candidate.mission_id / candidate.id).exists()


@pytest.mark.asyncio
async def test_real_bandit_report_is_bounded_and_has_no_code_snippets():
    executor = ContainerExecutor()
    if not await executor.available():
        pytest.skip("Docker Desktop Linux Engine unavailable")
    directory = Path(__file__).resolve().parents[3] / "sample-repos" / "security"
    result = await executor.run(directory, "python_bandit")
    assert result["exit_code"] == 1
    assert any(issue["test_id"] == "B605" and issue["issue_severity"] == "HIGH" for issue in result["report"]["results"])
    assert not any("code" in issue for issue in result["report"]["results"])


@pytest.mark.asyncio
async def test_proof_card_exposes_causal_links_without_raw_check_output(guild, monkeypatch):
    from app.main import app
    from tests.unit.test_m4_guild import plan_and_execute
    controller, mission, _, _, _ = guild
    await plan_and_execute(guild)
    monkeypatch.setattr("app.storage.database._db_instance", controller.db)
    monkeypatch.setattr("app.services.guild_service._controller", controller)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.get(f"/api/missions/{mission.id}/proof")
        assert result.status_code == 200
        card = result.json()
        assert card["mission_status"] == "REPAIRING"
        assert card["causal_links"] and all(item["finding_id"] for item in card["causal_links"])
        assert card["candidate"]["fingerprint"]
        assert all("stdout" not in item for item in card["checks"])
        markdown = await client.get(f"/api/missions/{mission.id}/proof?format=markdown")
        assert markdown.status_code == 200 and "Decision timeline" in markdown.text


@pytest.mark.asyncio
async def test_sentinel_persists_real_bandit_findings_without_losing_report(tmp_path):
    executor = ContainerExecutor()
    if not await executor.available():
        pytest.skip("Docker Desktop Linux Engine unavailable")
    workspace = WorkspaceService(tmp_path / "workspaces")
    directory = workspace.get_candidate_dir("mission", "candidate")
    directory.mkdir(parents=True)
    (directory / "runner.py").write_text("import os\n\ndef run(command):\n    return os.system(command)\n")
    fingerprint, _ = workspace._compute_dir_hash(directory)
    candidate = Candidate(id="candidate", mission_id="mission", workspace_snapshot_id="candidate", content_fingerprint=fingerprint,
                          state=CandidateState.FROZEN)
    result = await SentinelRunner(executor, workspace, ArtifactStorage(tmp_path / "artifacts")).run(candidate, ["python_bandit"])
    assert result.evidence[0].metadata["report"]["results"]
    assert any(f.title.startswith("Bandit B605") for f in result.findings)


@pytest.mark.asyncio
async def test_surviving_variant_changes_review_and_routes_repair(guild, monkeypatch):
    controller, mission, model, executor, _ = guild
    executor.final_code = 0
    model.review_finding = True
    await (await controller.start(mission.id, "plan"))
    context = await controller.store.context(mission.id)
    context["challenge_enabled"] = True
    async with controller.store.transaction() as db:
        await db.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission.id))

    async def fake_challenge(candidate, *args, **kwargs):
        evidence = Evidence(mission_id=mission.id, candidate_id=candidate.id, kind=EvidenceKind.MUTATION,
                            source="SENTINEL", fingerprint=candidate.content_fingerprint,
                            metadata={"status": "COMPLETE", "attempts": [{"path": "app.py", "function": "get_value",
                                                                            "outcome": "SURVIVED", "exit_code": 0}]})
        finding = Finding(mission_id=mission.id, candidate_id=candidate.id, source_agent="SENTINEL",
                          severity=FindingSeverity.MEDIUM, title="Variant survived", description="Review relevance",
                          observed_behavior="Tests passed", expected_behavior="Consider counterexample", evidence_ids=[evidence.id])
        return evidence, [finding]

    monkeypatch.setattr("app.services.guild_service.challenge_candidate", fake_challenge)
    original = model.respond

    def review_cites_challenge(request):
        reply = original(request)
        payload = reply.json()
        if "SHADOW_COUNCIL" in json.loads(request.content)["system"]:
            for block in payload["content"]:
                if block.get("name") == "submit_review":
                    evidence = json.loads(json.loads(request.content)["messages"][0]["content"])["evidence"]
                    challenge = next((item for item in evidence if item["kind"] == "MUTATION"), None)
                    if challenge:
                        block["input"]["findings"][0]["evidence_ids"] = [challenge["id"]]
                    else:
                        block["input"]["findings"] = []
        return httpx.Response(200, json=payload)

    model.respond = review_cites_challenge
    await (await controller.start(mission.id, "execute", 1))
    result = await controller.db.get_mission(mission.id)
    assert result.status == MissionStatus.REPAIRING
    from app.schemas.agent_message import AgentMessage
    from app.schemas.finding import Finding as FindingRecord
    findings = await controller.store.records(FindingRecord, mission.id)
    assert any(f.source_agent == "SHADOW_COUNCIL" and f.severity == FindingSeverity.HIGH and f.evidence_ids for f in findings)
    assert any(m.recipient == "SAMURAI" and m.payload.get("finding_id") for m in await controller.store.records(AgentMessage, mission.id))


@pytest.mark.asyncio
async def test_real_pipeline_proposes_missing_tests_before_authorized_edit(guild):
    controller, mission, model, _, repo = guild

    class FakeContainer(ContainerExecutor):
        async def run(self, directory, profile, selector=None):
            if profile == "python_bandit":
                return {"status": "SUCCEEDED", "exit_code": 0, "stdout": "", "stderr": "", "duration_ms": 1,
                        "command": ["docker", "bandit"], "report": {"results": [], "errors": [], "truncated": False}}
            return {"status": "SUCCEEDED", "exit_code": 0, "stdout": "1 passed", "stderr": "", "duration_ms": 1,
                    "command": ["docker", "pytest"]}

    controller.executor = FakeContainer()
    original = model.respond

    def with_designer(request):
        body = json.loads(request.content)
        if not any(t["name"] == "submit_acceptance_tests" for t in body["tools"]):
            return original(request)
        from tests.unit.test_m4_guild import tool
        if len(body["messages"]) == 1:
            calls = [tool("read_file", {"relative_path": "app.py"}, "design-read")]
        else:
            calls = [tool("submit_acceptance_tests", {"summary": "Check the new value",
                "files": [{"path": "test_kage_value.py", "content": "def test_value_two():\n    from app import value\n    assert value == 2\n"}],
                "mappings": [{"criterion_description": "Return value 2", "test_selectors": ["test_kage_value.py::test_value_two"]}]}, "design-submit")]
        return httpx.Response(200, json={"content": calls, "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1}})

    model.respond = with_designer
    model.plan["test_gaps"] = [{"criterion_description": "Return value 2", "expected_behavior": "Value 2 is returned",
                                "suggested_test": "test_value_two", "rationale": "No accepted test has been mapped"}]
    await (await controller.start(mission.id, "plan"))
    state = await controller.db.get_mission(mission.id)
    assert state.status == MissionStatus.READY_FOR_AUTHORIZATION, state.failure_reason
    context = await controller.store.context(mission.id)
    assert context["test_gaps"] == ["Return value 2"]
    assert context["test_gap_proposals"][0]["suggested_test"] == "test_value_two"
    assert context["acceptance_tests"]["accepted"] is False
    from app.storage.guild import GuildConflict
    with pytest.raises(GuildConflict, match="human review"):
        await controller.start(mission.id, "execute", 1)
    assert model.turns.get("SAMURAI", 0) == 0
    assert (repo / "app.py").read_text() == "value = 1\n"
