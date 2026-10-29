import json
from pathlib import Path

import pytest
import pytest_asyncio

from app.schemas.approval import Approval, ApprovalDecision
from app.schemas.candidate import Candidate, CandidateState
from app.schemas.evidence import Evidence, EvidenceKind
from app.schemas.mission import AcceptanceCriterion, CriterionStatus, Mission, MissionStatus
from app.schemas.task import MissionTask, TaskStatus
from app.services.criterion_checks import validate_selector
from app.services.guild_service import GuildController
from app.services.patch_application import PatchApplication
from app.services.repository_service import RepositoryService
from app.services.verifier import verify
from app.agents.guild import SentinelRunner
from app.schemas.guild import GuildPlan
from pydantic import ValidationError
from app.services.workspace_service import WorkspaceService
from app.storage.artifacts import ArtifactStorage
from app.storage.database import Database
from app.storage.guild import GuildConflict
from tests.report_fixtures import passing_report
from app.services.test_reports import object_hash


@pytest_asyncio.fixture
async def approved(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src.py").write_text("value = 1\n")
    (repo / "retire.py").write_text("deprecated = True\n")
    (repo / "keep.py").write_text("keep = True\n")
    (repo / "test_src.py").write_text("def test_a():\n    assert True\n\ndef test_b():\n    assert True\n")
    service = RepositoryService()
    monkeypatch.setattr(service, "_check_docker", lambda: True)
    record = service.connect_repository(str(repo))
    monkeypatch.setattr("app.services.repository_service._repo_service_instance", service)
    workspaces = WorkspaceService(tmp_path / "workspaces")
    mission = Mission(repository_id=record["repository_id"], request_text="modify, add, delete", status=MissionStatus.VERIFIED_AWAITING_APPROVAL)
    ws = workspaces.create_disposable_workspace(mission.id, mission.repository_id)
    baseline = workspaces.freeze_candidate(mission.id, mission.repository_id)
    (ws / "src.py").write_text("value = 2\n")
    (ws / "retire.py").unlink()
    (ws / "nested").mkdir()
    (ws / "nested" / "new.py").write_text("added = True\n")
    candidate = workspaces.freeze_candidate(mission.id, mission.repository_id, baseline.id)
    candidate.state = CandidateState.APPROVED
    mission.active_candidate_id = candidate.id
    db = Database(tmp_path / "test.db")
    await db.init_db()
    await db.create_mission(mission)
    controller = GuildController(db, workspaces, ArtifactStorage(tmp_path / "artifacts"))
    async with controller.store.transaction() as connection:
        await controller.store._save(connection, baseline)
        await controller.store._save(connection, candidate)
        await controller.store._save(connection, Approval(
            mission_id=mission.id, candidate_id=candidate.id, candidate_fingerprint=candidate.content_fingerprint,
            decision=ApprovalDecision.APPROVED,
        ))
        context = {"repository": {key: record[key] for key in ("repository_id", "name", "path", "included_files", "fingerprint")},
                   "baseline_candidate_id": baseline.id}
        await connection.execute("INSERT INTO guild_context VALUES (?,?)", (mission.id, json.dumps(context)))
    application = PatchApplication(controller)
    application.journals = tmp_path / "journals"
    application.journals.mkdir()
    yield controller, mission, candidate, context, repo, application
    await controller.close()


@pytest.mark.asyncio
async def test_applies_modification_addition_and_deletion(approved):
    controller, mission, candidate, context, repo, application = approved
    assert set(candidate.changed_files) == {"src.py", "retire.py", "nested/new.py"}
    result = await application.apply(mission, candidate, context)
    assert result.status == MissionStatus.APPLIED
    assert (repo / "src.py").read_text() == "value = 2\n"
    assert (repo / "nested" / "new.py").read_text() == "added = True\n"
    assert not (repo / "retire.py").exists()
    assert (repo / "keep.py").read_text() == "keep = True\n"
    assert (repo / "test_src.py").is_file()
    assert not list(application.journals.iterdir())
    with pytest.raises(GuildConflict):
        await application.apply(mission, candidate, context)


@pytest.mark.asyncio
async def test_file_failure_rolls_back_all_changes(approved, monkeypatch):
    controller, mission, candidate, context, repo, application = approved
    original = application._replace_entry
    calls = 0

    def fail_after_first(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        return original(*args)

    monkeypatch.setattr(application, "_replace_entry", fail_after_first)
    with pytest.raises(OSError):
        await application.apply(mission, candidate, context)
    assert (repo / "src.py").read_text() == "value = 1\n"
    assert (repo / "retire.py").is_file()
    assert not (repo / "nested" / "new.py").exists()
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.INTERRUPTED
    assert not list(application.journals.iterdir())


@pytest.mark.asyncio
async def test_crash_after_first_replace_recovers_at_startup(approved, monkeypatch):
    controller, mission, candidate, context, repo, application = approved
    original = application._replace_entry
    calls = 0

    class SimulatedCrash(BaseException):
        pass

    def crash(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SimulatedCrash()
        return original(*args)

    monkeypatch.setattr(application, "_replace_entry", crash)
    with pytest.raises(SimulatedCrash):
        await application.apply(mission, candidate, context)
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.APPLYING
    assert (repo / "nested" / "new.py").exists()
    restarted = PatchApplication(controller)
    restarted.journals = application.journals
    await restarted.recover_pending()
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.INTERRUPTED
    assert (repo / "src.py").read_text() == "value = 1\n"
    assert (repo / "retire.py").exists()
    assert not (repo / "nested").exists()
    assert not list(application.journals.iterdir())


@pytest.mark.asyncio
async def test_external_conflicts_do_not_overwrite_original(approved):
    controller, mission, candidate, context, repo, application = approved
    (repo / "keep.py").write_text("external = True\n")
    with pytest.raises(GuildConflict):
        await application.apply(mission, candidate, context)
    assert (repo / "keep.py").read_text() == "external = True\n"
    assert not (repo / "nested" / "new.py").exists()


@pytest.mark.asyncio
async def test_new_file_collision_blocks_without_overwrite(approved):
    _, mission, candidate, context, repo, application = approved
    (repo / "nested").mkdir()
    (repo / "nested" / "new.py").write_text("external = True\n")
    with pytest.raises(GuildConflict):
        await application.apply(mission, candidate, context)
    assert (repo / "nested" / "new.py").read_text() == "external = True\n"


@pytest.mark.asyncio
async def test_journal_tamper_preserves_manual_recovery_blocker(approved, monkeypatch):
    controller, mission, candidate, context, repo, application = approved
    original = application._replace_entry

    class SimulatedCrash(BaseException):
        pass

    calls = 0

    def crash(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SimulatedCrash()
        return original(*args)

    monkeypatch.setattr(application, "_replace_entry", crash)
    with pytest.raises(SimulatedCrash):
        await application.apply(mission, candidate, context)
    journal = next(application.journals.iterdir())
    (journal / "before-0").write_bytes(b"tampered") if (journal / "before-0").exists() else (journal / "after-0").write_bytes(b"tampered")
    restarted = PatchApplication(controller)
    restarted.journals = application.journals
    await restarted.recover_pending()
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.BLOCKED
    assert journal.exists()


@pytest.mark.asyncio
async def test_db_finalize_failure_rolls_back_files(approved, monkeypatch):
    controller, mission, candidate, context, repo, application = approved
    original_save = application.store._save

    async def fail_when_applied(connection, entity):
        if isinstance(entity, Candidate) and entity.state == CandidateState.APPLIED:
            raise OSError("database commit failed")
        return await original_save(connection, entity)

    monkeypatch.setattr(application.store, "_save", fail_when_applied)
    with pytest.raises(OSError, match="database commit failed"):
        await application.apply(mission, candidate, context)
    assert (repo / "src.py").read_text() == "value = 1\n"
    assert (repo / "retire.py").is_file()
    assert not (repo / "nested").exists()
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.INTERRUPTED
    assert not list(application.journals.iterdir())


def test_selector_rejects_traversal_and_non_test_paths(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_good(): pass\n")
    assert validate_selector(tmp_path, "test_ok.py::test_good") == "test_ok.py::test_good"
    for selector in ("../test_ok.py::test_good", "test_ok.py", "test_ok.py::foo", "x.py::test_good", "test_ok.py::test_missing", "test_ok.py::test_good;id"):
        with pytest.raises(ValueError):
            validate_selector(tmp_path, selector)


def test_each_criterion_requires_unique_matching_candidate_evidence():
    candidate = Candidate(mission_id="mission", workspace_snapshot_id="snapshot", content_fingerprint="hash", changed_files=["src.py"])
    criteria = [AcceptanceCriterion(mission_id="mission", description=name, verification_method=f"test_profile:python_pytest|test_src.py::{test}")
                for name, test in (("a", "test_a"), ("b", "test_b"))]
    tasks = [MissionTask(mission_id="mission", owner_agent=role, title="check", description="check", candidate_id=candidate.id, status=TaskStatus.DONE)
             for role in ("SENTINEL", "SHADOW_COUNCIL")]
    full = Evidence(mission_id="mission", candidate_id=candidate.id, kind=EvidenceKind.TEST, source="SENTINEL", fingerprint="hash",
                    exit_code=0, metadata={"check_profile": "python_pytest", "execution_status": "SUCCEEDED"})
    proof = Evidence(mission_id="mission", candidate_id=candidate.id, criterion_id=criteria[0].id, kind=EvidenceKind.TEST,
                     source="SENTINEL", fingerprint="hash", exit_code=0,
                     command=["docker", "run", "--", "test_src.py::test_a"],
                     metadata={"check_profile": "python_pytest", "test_selector": "test_src.py::test_a", "execution_status": "SUCCEEDED",
                               "stdout": "1 passed", "output_truncated": False})
    for entry in (full, proof):
        report = passing_report("test_src.py::test_a")
        entry.metadata.update(report=report, report_hash=object_hash(report), verification_contract_hash="contract", output_truncated=False)
    passed, decisions = verify(candidate, criteria, [full, proof], [], tasks, contract_hash="contract")
    assert not passed and [c.status for c in decisions] == [CriterionStatus.PASS, CriterionStatus.NOT_VERIFIED]
    second = proof.model_copy(update={"id": "new-proof", "criterion_id": criteria[1].id, "command": ["docker", "run", "--", "test_src.py::test_b"],
                                      "metadata": {**proof.metadata, "test_selector": "test_src.py::test_b"}})
    report = passing_report("test_src.py::test_b")
    second.metadata.update(report=report, report_hash=object_hash(report))
    passed, decisions = verify(candidate, criteria, [full, proof, second], [], tasks, contract_hash="contract")
    assert passed and all(c.status == CriterionStatus.PASS for c in decisions)
    second.fingerprint = "stale"
    assert not verify(candidate, criteria, [full, proof, second], [], tasks, contract_hash="contract")[0]


@pytest.mark.asyncio
async def test_sentinel_runs_full_suite_and_one_check_per_criterion(approved):
    controller, mission, candidate, _, _, _ = approved
    class Checks:
        def __init__(self):
            self.calls = []

        async def run(self, directory, profile, selector=None):
            self.calls.append(selector)
            return {"status": "SUCCEEDED", "exit_code": 0, "duration_ms": 1,
                    "command": ["docker", "run", "python", "-m", "pytest", "--", selector] if selector else ["docker", "run", "python", "-m", "pytest"],
                    "stdout": "1 passed", "stderr": "", "report": passing_report(selector or "test_src.py::test_a")}

    criteria = [AcceptanceCriterion(mission_id=mission.id, description=name,
                                    verification_method=f"test_profile:python_pytest|test_src.py::{test}")
                for name, test in (("a", "test_a"), ("b", "test_b"))]
    checks = Checks()
    frozen = candidate.model_copy(update={"state": CandidateState.FROZEN})
    evidence = (await SentinelRunner(checks, controller.workspaces, controller.artifacts).run(
        frozen, ["python_pytest"], criteria=criteria, contract_hash="contract")).evidence
    assert checks.calls == [None, "test_src.py::test_a", "test_src.py::test_b"]
    assert [item.criterion_id for item in evidence] == [None, criteria[0].id, criteria[1].id]
    tasks = [MissionTask(mission_id=mission.id, owner_agent=owner, title="check", description="check",
                         status=TaskStatus.DONE, candidate_id=candidate.id) for owner in ("SENTINEL", "SHADOW_COUNCIL")]
    assert verify(frozen, criteria, evidence, [], tasks, contract_hash="contract")[0]
    assert not verify(frozen, criteria, evidence[:2], [], tasks, contract_hash="contract")[0]


def test_shared_criterion_selector_is_allowed():
    plan = GuildPlan.model_validate({"summary": "plan", "criteria": [
            {"description": "first", "test_selector": "test_src.py::test_a"},
            {"description": "second", "test_selector": "test_src.py::test_a"},
        ], "tasks": [{"key": "task", "title": "fix", "description": "fix"}]})
    assert len(plan.criteria) == 2
