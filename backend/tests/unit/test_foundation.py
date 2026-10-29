import asyncio
import tempfile
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.settings import Settings
from app.storage.database import Database
from app.storage.artifacts import ArtifactStorage
from app.schemas.mission import (
    Mission,
    MissionStatus,
    AcceptanceCriterion,
    CriterionStatus,
    MissionBudgets,
    CreateMissionRequest,
)
from app.schemas.task import MissionTask, TaskStatus
from app.schemas.agent_message import AgentMessage, MessageType
from app.schemas.candidate import Candidate, CandidateState
from app.schemas.evidence import Evidence, EvidenceKind
from app.schemas.finding import Finding, FindingSeverity, FindingStatus
from app.schemas.approval import Approval, ApprovalDecision
from app.schemas.events import MissionEvent
from app.schemas.common import HealthResponse, PreflightStatus, PreflightResult


# --- 1. Schema Validation Tests ---

def test_mission_schema_defaults_and_validation():
    m = Mission(repository_id="repo-123", request_text="Add status filter")
    assert m.id.startswith("miss-")
    assert m.status == MissionStatus.CREATED
    assert m.scope_version == 1
    assert m.budgets.max_repair_rounds == 3
    assert not m.cancel_requested


def test_criteria_schema():
    c = AcceptanceCriterion(
        mission_id="miss-123",
        description="Must filter by active status",
        status=CriterionStatus.PENDING,
    )
    assert c.id.startswith("crit-")
    assert c.status == CriterionStatus.PENDING
    assert c.criteria_version == 1


def test_task_schema():
    t = MissionTask(
        mission_id="miss-123",
        title="Inspect repository",
        description="Search for task controllers",
        owner_agent="SHOGUN",
        dependencies=["task-001"],
    )
    assert t.id.startswith("task-")
    assert t.status == TaskStatus.PENDING
    assert t.owner_agent == "SHOGUN"
    assert t.dependencies == ["task-001"]


def test_agent_message_schema():
    msg = AgentMessage(
        mission_id="miss-123",
        sender="SENTINEL",
        recipient="SAMURAI",
        type=MessageType.FINDING,
        summary="Test failure on candidate v1",
        payload={"exit_code": 1, "failed_test": "test_sorting"},
    )
    assert msg.id.startswith("msg-")
    assert msg.type == MessageType.FINDING
    assert msg.payload["exit_code"] == 1


def test_candidate_schema():
    cand = Candidate(
        mission_id="miss-123",
        workspace_snapshot_id="snap-001",
        content_fingerprint="sha256:abc123",
        changed_files=["tasks.py"],
        state=CandidateState.MUTABLE,
    )
    assert cand.id.startswith("cand-")
    assert cand.state == CandidateState.MUTABLE
    assert cand.ui_badge == "PROPOSED"


def test_evidence_schema():
    ev = Evidence(
        mission_id="miss-123",
        candidate_id="cand-001",
        kind=EvidenceKind.TEST,
        source="SENTINEL",
        command=["pytest", "-q"],
        exit_code=0,
        fingerprint="sha256:fedcba",
    )
    assert ev.id.startswith("ev-")
    assert ev.kind == EvidenceKind.TEST
    assert ev.exit_code == 0


def test_finding_schema():
    f = Finding(
        mission_id="miss-123",
        source_agent="SHADOW_COUNCIL",
        severity=FindingSeverity.BLOCKING,
        title="Unsanitized subprocess call",
        description="Found os.system without validation",
        file_path="src/executor.py",
        line_start=42,
        observed_behavior="Runs input string in shell",
        expected_behavior="Use parameterized array",
    )
    assert f.id.startswith("find-")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.status == FindingStatus.OPEN


def test_approval_schema():
    appr = Approval(
        mission_id="miss-123",
        candidate_id="cand-002",
        candidate_fingerprint="sha256:verified_hash",
        decision=ApprovalDecision.APPROVED,
    )
    assert appr.id.startswith("appr-")
    assert appr.decision == ApprovalDecision.APPROVED


# --- 2. Database Persistence & Event Monotonicity Tests ---

@pytest.mark.asyncio
async def test_database_lifecycle_and_monotonic_events(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_path=db_file)
    await db.init_db()

    # Create mission with 2 criteria
    mission = Mission(repository_id="repo-demo", request_text="Feature test")
    c1 = AcceptanceCriterion(mission_id=mission.id, description="Criterion 1")
    c2 = AcceptanceCriterion(mission_id=mission.id, description="Criterion 2")
    await db.create_mission(mission, [c1, c2])

    # Fetch mission
    fetched = await db.get_mission(mission.id)
    assert fetched is not None
    assert fetched.id == mission.id
    assert fetched.request_text == "Feature test"

    # Fetch criteria
    criteria = await db.get_criteria(mission.id)
    assert len(criteria) == 2
    assert criteria[0].description == "Criterion 1"

    # Emit sequential events and assert strictly monotonic sequence numbers
    e1 = await db.emit_event(mission.id, "TEST_EVENT_1", "SHOGUN", {"step": 1})
    e2 = await db.emit_event(mission.id, "TEST_EVENT_2", "SAMURAI", {"step": 2})
    e3 = await db.emit_event(mission.id, "TEST_EVENT_3", "SENTINEL", {"step": 3})

    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e3.sequence == 3

    # Query all events
    all_events = await db.get_events(mission.id, after_sequence=0)
    assert len(all_events) == 3

    # Replay query after sequence 1
    replayed = await db.get_events(mission.id, after_sequence=1)
    assert len(replayed) == 2
    assert replayed[0].sequence == 2
    assert replayed[1].sequence == 3

    # Create and fetch task
    task = MissionTask(
        mission_id=mission.id,
        title="Implement filter",
        description="Edit tasks.py",
        owner_agent="SAMURAI",
    )
    await db.create_task(task)
    tasks = await db.get_tasks(mission.id)
    assert len(tasks) == 1
    assert tasks[0].id == task.id
    assert tasks[0].owner_agent == "SAMURAI"

    # Update status
    await db.update_mission_status(mission.id, MissionStatus.RUNNING)
    updated_mission = await db.get_mission(mission.id)
    assert updated_mission.status == MissionStatus.RUNNING


# --- 3. Artifact Storage Tests ---

def test_artifact_storage_sha256_and_bounding(tmp_path):
    storage = ArtifactStorage(base_dir=tmp_path)
    storage.max_size = 50  # Low cap to test truncation

    # Small artifact
    aid1, fp1 = storage.save_artifact("miss-001", "check.log", "Normal small output")
    assert aid1.startswith("art-")
    content1 = storage.read_artifact("miss-001", aid1)
    assert content1 == "Normal small output"

    # Large artifact exceeding cap
    large_payload = "A" * 200
    aid2, fp2 = storage.save_artifact("miss-001", "huge.log", large_payload)
    content2 = storage.read_artifact("miss-001", aid2)
    assert len(content2.encode("utf-8")) <= 50
    assert "[TRUNCATED" in content2


# --- 4. API Endpoints Tests ---

def test_api_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "kage-backend"
    assert "docker_available" in data
    assert "model_configured" in data
    assert "storage_ready" in data


def test_api_mission_crud_lifecycle():
    client = TestClient(app)

    # 1. Create Mission
    payload = {
        "repository_id": "repo-unit-test",
        "request_text": "Add status filter endpoint",
        "criteria": ["Accept active filter", "Reject invalid status"],
    }
    create_res = client.post("/api/missions", json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    mission_id = created_data["mission"]["id"]
    assert created_data["mission"]["status"] == "PLANNING"
    assert len(created_data["criteria"]) == 2

    # 2. Get Mission
    get_res = client.get(f"/api/missions/{mission_id}")
    assert get_res.status_code == 200
    fetched_data = get_res.json()
    assert fetched_data["mission"]["id"] == mission_id
    assert fetched_data["mission"]["request_text"] == "Add status filter endpoint"
    assert len(fetched_data["criteria"]) == 2

    # 3. Get Unknown Mission (404)
    res_404 = client.get("/api/missions/miss-nonexistent")
    assert res_404.status_code == 404

    # 4. Cancel Mission
    cancel_res = client.post(f"/api/missions/{mission_id}/cancel")
    assert cancel_res.status_code == 200
    cancelled_data = cancel_res.json()
    assert cancelled_data["mission"]["status"] == "CANCELLED"

    # 5. Cancel Already Cancelled Mission (409 Conflict)
    repeat_cancel = client.post(f"/api/missions/{mission_id}/cancel")
    assert repeat_cancel.status_code == 409

