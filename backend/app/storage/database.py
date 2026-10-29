import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import aiosqlite
from app.schemas.mission import (
    AcceptanceCriterion,
    CriterionStatus,
    Mission,
    MissionBudgets,
    MissionStatus,
)
from app.schemas.task import MissionTask, TaskStatus
from app.schemas.agent_message import AgentMessage, MessageType
from app.schemas.candidate import Candidate, CandidateState
from app.schemas.evidence import Evidence, EvidenceKind
from app.schemas.finding import Finding, FindingSeverity, FindingStatus
from app.schemas.approval import Approval, ApprovalDecision
from app.schemas.events import MissionEvent
from app.settings import get_settings
from app.security.redaction import redact_secrets


SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    request_text TEXT NOT NULL,
    status TEXT NOT NULL,
    scope_version INTEGER DEFAULT 1,
    active_candidate_id TEXT,
    budgets_json TEXT NOT NULL,
    unresolved_issues_json TEXT NOT NULL,
    cancel_requested BOOLEAN DEFAULT 0,
    failure_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS criteria (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    description TEXT NOT NULL,
    verification_method TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    criteria_version INTEGER DEFAULT 1,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    dependencies_json TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt INTEGER DEFAULT 1,
    candidate_id TEXT,
    completion_condition TEXT,
    result_summary TEXT,
    evidence_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    type TEXT NOT NULL,
    task_id TEXT,
    candidate_id TEXT,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    parent_candidate_id TEXT,
    workspace_snapshot_id TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL,
    changed_files_json TEXT NOT NULL,
    criteria_version INTEGER DEFAULT 1,
    state TEXT NOT NULL,
    ui_badge TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    criterion_id TEXT,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    command_json TEXT NOT NULL,
    exit_code INTEGER,
    duration_ms INTEGER DEFAULT 0,
    stdout_artifact_id TEXT,
    stderr_artifact_id TEXT,
    fingerprint TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    observed_behavior TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    candidate_id TEXT,
    status TEXT NOT NULL,
    resolution_evidence_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    candidate_fingerprint TEXT NOT NULL,
    intended_action TEXT NOT NULL,
    decision TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    application_result_id TEXT,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER NOT NULL,
    mission_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    task_id TEXT,
    candidate_id TEXT,
    evidence_ids_json TEXT NOT NULL,
    display_payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(mission_id, sequence),
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS guild_context (
    mission_id TEXT PRIMARY KEY REFERENCES missions(id) ON DELETE CASCADE,
    context_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS guild_operations (
    mission_id TEXT PRIMARY KEY REFERENCES missions(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    phase TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clarifications (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    reason TEXT NOT NULL,
    phase TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    candidate_fingerprint TEXT NOT NULL,
    scope_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    answer TEXT,
    created_at TEXT NOT NULL,
    answered_at TEXT
);
"""


class Database:
    """Async SQLite Database Manager for DevPilot / KAGE AI."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_settings().db_path
        if self.db_path.parent:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """Initialize database tables and WAL mode."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA_SQL)
            await db.commit()

    # --- Mission Operations ---

    async def create_mission(
        self,
        mission: Mission,
        criteria: list[AcceptanceCriterion] | None = None,
    ) -> Mission:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO missions (
                    id, repository_id, request_text, status, scope_version,
                    active_candidate_id, budgets_json, unresolved_issues_json,
                    cancel_requested, failure_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mission.id,
                    mission.repository_id,
                    mission.request_text,
                    mission.status.value,
                    mission.scope_version,
                    mission.active_candidate_id,
                    mission.budgets.model_dump_json(),
                    json.dumps(mission.unresolved_issues),
                    1 if mission.cancel_requested else 0,
                    mission.failure_reason,
                    mission.created_at.isoformat(),
                    mission.updated_at.isoformat(),
                ),
            )

            if criteria:
                for c in criteria:
                    await db.execute(
                        """
                        INSERT INTO criteria (
                            id, mission_id, description, verification_method,
                            status, evidence_ids_json, criteria_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c.id,
                            c.mission_id,
                            c.description,
                            c.verification_method,
                            c.status.value,
                            json.dumps(c.evidence_ids),
                            c.criteria_version,
                        ),
                    )

            await db.commit()
        return mission

    async def get_mission(self, mission_id: str) -> Mission | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
            row = await cursor.fetchone()
            if not row:
                return None

            return Mission(
                id=row["id"],
                repository_id=row["repository_id"],
                request_text=row["request_text"],
                status=MissionStatus(row["status"]),
                scope_version=row["scope_version"],
                active_candidate_id=row["active_candidate_id"],
                budgets=MissionBudgets.model_validate_json(row["budgets_json"]),
                unresolved_issues=json.loads(row["unresolved_issues_json"]),
                cancel_requested=bool(row["cancel_requested"]),
                failure_reason=row["failure_reason"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    async def update_mission_status(
        self,
        mission_id: str,
        status: MissionStatus,
        failure_reason: str | None = None,
        active_candidate_id: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            if active_candidate_id:
                await db.execute(
                    """
                    UPDATE missions
                    SET status = ?, failure_reason = ?, active_candidate_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status.value, failure_reason, active_candidate_id, now, mission_id),
                )
            else:
                await db.execute(
                    """
                    UPDATE missions
                    SET status = ?, failure_reason = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status.value, failure_reason, now, mission_id),
                )
            await db.commit()

    async def list_missions(self, limit: int = 50) -> list[Mission]:
        missions: list[Mission] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM missions ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
            for row in rows:
                missions.append(
                    Mission(
                        id=row["id"],
                        repository_id=row["repository_id"],
                        request_text=row["request_text"],
                        status=MissionStatus(row["status"]),
                        scope_version=row["scope_version"],
                        active_candidate_id=row["active_candidate_id"],
                        budgets=MissionBudgets.model_validate_json(row["budgets_json"]),
                        unresolved_issues=json.loads(row["unresolved_issues_json"]),
                        cancel_requested=bool(row["cancel_requested"]),
                        failure_reason=row["failure_reason"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                )
        return missions

    # --- Criteria Operations ---

    async def get_criteria(self, mission_id: str) -> list[AcceptanceCriterion]:
        criteria: list[AcceptanceCriterion] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM criteria WHERE mission_id = ?", (mission_id,))
            rows = await cursor.fetchall()
            for row in rows:
                criteria.append(
                    AcceptanceCriterion(
                        id=row["id"],
                        mission_id=row["mission_id"],
                        description=row["description"],
                        verification_method=row["verification_method"],
                        status=CriterionStatus(row["status"]),
                        evidence_ids=json.loads(row["evidence_ids_json"]),
                        criteria_version=row["criteria_version"],
                    )
                )
        return criteria

    # --- Task Operations ---

    async def create_task(self, task: MissionTask) -> MissionTask:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO tasks (
                    id, mission_id, title, description, owner_agent,
                    dependencies_json, status, attempt, candidate_id,
                    completion_condition, result_summary, evidence_ids_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.mission_id,
                    task.title,
                    task.description,
                    task.owner_agent,
                    json.dumps(task.dependencies),
                    task.status.value,
                    task.attempt,
                    task.candidate_id,
                    task.completion_condition,
                    task.result_summary,
                    json.dumps(task.evidence_ids),
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                ),
            )
            await db.commit()
        return task

    async def get_tasks(self, mission_id: str) -> list[MissionTask]:
        tasks: list[MissionTask] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM tasks WHERE mission_id = ? ORDER BY created_at ASC", (mission_id,))
            rows = await cursor.fetchall()
            for row in rows:
                tasks.append(
                    MissionTask(
                        id=row["id"],
                        mission_id=row["mission_id"],
                        title=row["title"],
                        description=row["description"],
                        owner_agent=row["owner_agent"],
                        dependencies=json.loads(row["dependencies_json"]),
                        status=TaskStatus(row["status"]),
                        attempt=row["attempt"],
                        candidate_id=row["candidate_id"],
                        completion_condition=row["completion_condition"],
                        result_summary=row["result_summary"],
                        evidence_ids=json.loads(row["evidence_ids_json"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                )
        return tasks

    # --- Events & SSE Monotonic Ordering ---

    async def emit_event(
        self,
        mission_id: str,
        event_type: str,
        source: str,
        display_payload: dict[str, Any],
        task_id: str | None = None,
        candidate_id: str | None = None,
        evidence_ids: list[str] | None = None,
    ) -> MissionEvent:
        now = datetime.now(timezone.utc)
        evidence_list = evidence_ids or []
        async with aiosqlite.connect(self.db_path) as db:
            # Determine next sequence monotonically
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE mission_id = ?",
                (mission_id,),
            )
            seq_row = await cursor.fetchone()
            next_seq = seq_row[0] if seq_row else 1

            await db.execute(
                """
                INSERT INTO events (
                    sequence, mission_id, event_type, source, task_id,
                    candidate_id, evidence_ids_json, display_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    next_seq,
                    mission_id,
                    event_type,
                    source,
                    task_id,
                    candidate_id,
                    json.dumps(evidence_list),
                    redact_secrets(json.dumps(display_payload)),
                    now.isoformat(),
                ),
            )
            await db.commit()

            return MissionEvent(
                sequence=next_seq,
                mission_id=mission_id,
                event_type=event_type,
                source=source,
                task_id=task_id,
                candidate_id=candidate_id,
                evidence_ids=evidence_list,
                display_payload=display_payload,
                created_at=now,
            )

    async def get_events(self, mission_id: str, after_sequence: int = 0, limit: int = 100) -> list[MissionEvent]:
        events: list[MissionEvent] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM events
                WHERE mission_id = ? AND sequence > ?
                ORDER BY sequence ASC LIMIT ?
                """,
                (mission_id, after_sequence, min(max(limit, 1), 100)),
            )
            rows = await cursor.fetchall()
            for row in rows:
                events.append(
                    MissionEvent(
                        sequence=row["sequence"],
                        mission_id=row["mission_id"],
                        event_type=row["event_type"],
                        source=row["source"],
                        task_id=row["task_id"],
                        candidate_id=row["candidate_id"],
                        evidence_ids=json.loads(row["evidence_ids_json"]),
                        display_payload=json.loads(row["display_payload_json"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
        return events


    async def get_candidates(self, mission_id: str) -> list[Candidate]:
        candidates: list[Candidate] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM candidates WHERE mission_id = ? ORDER BY created_at ASC",
                (mission_id,),
            )
            rows = await cursor.fetchall()
            for row in rows:
                candidates.append(
                    Candidate(
                        id=row["id"],
                        mission_id=row["mission_id"],
                        parent_candidate_id=row["parent_candidate_id"],
                        workspace_snapshot_id=row["workspace_snapshot_id"],
                        content_fingerprint=row["content_fingerprint"],
                        changed_files=json.loads(row["changed_files_json"]),
                        criteria_version=row["criteria_version"],
                        state=CandidateState(row["state"]),
                        ui_badge=row["ui_badge"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
        return candidates

    async def get_evidence(self, mission_id: str) -> list[Evidence]:
        records: list[Evidence] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM evidence WHERE mission_id = ? ORDER BY created_at ASC",
                (mission_id,),
            )
            rows = await cursor.fetchall()
            for row in rows:
                records.append(
                    Evidence(
                        id=row["id"],
                        mission_id=row["mission_id"],
                        candidate_id=row["candidate_id"],
                        criterion_id=row["criterion_id"],
                        kind=EvidenceKind(row["kind"]),
                        source=row["source"],
                        command=json.loads(row["command_json"]),
                        exit_code=row["exit_code"],
                        duration_ms=row["duration_ms"],
                        stdout_artifact_id=row["stdout_artifact_id"],
                        stderr_artifact_id=row["stderr_artifact_id"],
                        fingerprint=row["fingerprint"],
                        metadata=json.loads(row["metadata_json"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
        return records

    async def get_findings(self, mission_id: str) -> list[Finding]:
        records: list[Finding] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM findings WHERE mission_id = ? ORDER BY created_at ASC",
                (mission_id,),
            )
            rows = await cursor.fetchall()
            for row in rows:
                records.append(
                    Finding(
                        id=row["id"],
                        mission_id=row["mission_id"],
                        source_agent=row["source_agent"],
                        severity=FindingSeverity(row["severity"]),
                        title=row["title"],
                        description=row["description"],
                        file_path=row["file_path"],
                        line_start=row["line_start"],
                        line_end=row["line_end"],
                        observed_behavior=row["observed_behavior"],
                        expected_behavior=row["expected_behavior"],
                        evidence_ids=json.loads(row["evidence_ids_json"]),
                        candidate_id=row["candidate_id"],
                        status=FindingStatus(row["status"]),
                        resolution_evidence_ids=json.loads(row["resolution_evidence_ids_json"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
        return records

    async def get_approvals(self, mission_id: str) -> list[Approval]:
        records: list[Approval] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM approvals WHERE mission_id = ? ORDER BY decided_at ASC",
                (mission_id,),
            )
            rows = await cursor.fetchall()
            for row in rows:
                records.append(
                    Approval(
                        id=row["id"],
                        mission_id=row["mission_id"],
                        candidate_id=row["candidate_id"],
                        candidate_fingerprint=row["candidate_fingerprint"],
                        intended_action=row["intended_action"],
                        decision=ApprovalDecision(row["decision"]),
                        decided_at=datetime.fromisoformat(row["decided_at"]),
                        application_result_id=row["application_result_id"],
                    )
                )
        return records


_db_instance: Database | None = None


def get_database() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance

