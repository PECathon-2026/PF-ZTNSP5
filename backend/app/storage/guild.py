"""Transactional M4 state, using the existing canonical SQLite entity tables."""

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

import aiosqlite

from app.schemas.agent_message import AgentMessage
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.mission import AcceptanceCriterion, MissionStatus
from app.schemas.task import MissionTask
from app.schemas.guild import Clarification
from app.schemas.approval import Approval
from app.security.redaction import redact_secrets


class GuildConflict(Exception):
    """A stale/duplicate operation or invalid lifecycle transition was refused."""


TABLES = {
    MissionTask: "tasks", Candidate: "candidates", Evidence: "evidence",
    Finding: "findings", AgentMessage: "messages", AcceptanceCriterion: "criteria", Clarification: "clarifications", Approval: "approvals",
}
UNSET = object()
JSON_FIELDS = {"dependencies", "evidence_ids", "changed_files", "metadata", "payload", "resolution_evidence_ids", "command"}


def now():
    return datetime.now(timezone.utc).isoformat()


class GuildStore:
    def __init__(self, database):
        self.database = database

    @asynccontextmanager
    async def transaction(self):
        async with aiosqlite.connect(self.database.db_path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("PRAGMA foreign_keys=ON")
            await connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                await connection.commit()
            except BaseException:
                await connection.rollback()
                raise

    async def _save(self, connection, entity):
        table = TABLES[type(entity)]
        values = json.loads(redact_secrets(entity.model_dump_json()))
        columns = [field + "_json" if field in JSON_FIELDS else field for field in values]
        parameters = [json.dumps(value) if field in JSON_FIELDS else value for field, value in values.items()]
        # Identifiers come exclusively from trusted model types and the fixed map above.
        updates = ",".join(f"{column}=excluded.{column}" for column in columns if column not in {"id", "mission_id"})
        cursor = await connection.execute(
            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates} WHERE {table}.mission_id=excluded.mission_id",
            parameters,
        )
        if cursor.rowcount != 1:
            raise GuildConflict("Entity belongs to a different mission")

    async def records(self, entity_type, mission_id):
        table = TABLES[entity_type]
        async with aiosqlite.connect(self.database.db_path) as connection:
            connection.row_factory = aiosqlite.Row
            cursor = await connection.execute(f"SELECT * FROM {table} WHERE mission_id=? ORDER BY rowid", (mission_id,))
            result = []
            for row in await cursor.fetchall():
                data = {}
                for column in row.keys():
                    field = column[:-5] if column.endswith("_json") else column
                    data[field] = json.loads(row[column]) if field in JSON_FIELDS else row[column]
                result.append(entity_type.model_validate(data))
            return result

    async def context(self, mission_id):
        async with aiosqlite.connect(self.database.db_path) as connection:
            cursor = await connection.execute("SELECT context_json FROM guild_context WHERE mission_id=?", (mission_id,))
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None

    async def claim(self, mission_id, phase, scope_version=None, auto_repair=True):
        expected = "PLANNING" if phase == "plan" else "READY_FOR_AUTHORIZATION"
        next_status = "PREFLIGHT" if phase == "plan" else "RUNNING"
        token = uuid4().hex
        async with self.transaction() as connection:
            row = await (await connection.execute("SELECT * FROM missions WHERE id=?", (mission_id,))).fetchone()
            if not row:
                raise KeyError("Mission not found")
            if row["status"] != expected or row["cancel_requested"]:
                raise GuildConflict(f"Mission must be {expected} before {phase}")
            if phase == "execute" and row["scope_version"] != scope_version:
                raise GuildConflict("Authorization refers to a stale plan version")
            if phase == "execute":
                context_row = await (await connection.execute("SELECT context_json FROM guild_context WHERE mission_id=?", (mission_id,))).fetchone()
                context = json.loads(context_row[0]) if context_row else {}
                from app.services.acceptance_tests import checked_bundle
                checked_bundle(context)
                context["auto_repair"] = auto_repair
                context["execution_authorized"] = True
                await connection.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission_id))
            try:
                await connection.execute("INSERT INTO guild_operations VALUES (?,?,?)", (mission_id, token, phase))
            except aiosqlite.IntegrityError:
                raise GuildConflict("Mission already has an active operation") from None
            await connection.execute("UPDATE missions SET status=?,updated_at=? WHERE id=?", (next_status, now(), mission_id))
        return token

    async def claim_verification(self, mission_id):
        token = uuid4().hex
        async with self.transaction() as connection:
            row = await (await connection.execute("SELECT status,cancel_requested FROM missions WHERE id=?", (mission_id,))).fetchone()
            if not row:
                raise KeyError("Mission not found")
            if row[0] != "VERIFYING" or row[1]:
                raise GuildConflict("Mission is not ready for verification")
            await connection.execute("INSERT INTO guild_operations VALUES (?,?,?)", (mission_id, token, "verify"))
        return token

    async def commit(self, mission_id, token, *, status=None, entities=(), context=None,
                     candidate_id=None, budgets=None, failure_reason=UNSET, event=None):
        async with self.transaction() as connection:
            row = await (await connection.execute(
                "SELECT m.cancel_requested FROM missions m JOIN guild_operations g ON g.mission_id=m.id "
                "WHERE m.id=? AND g.token=?", (mission_id, token),
            )).fetchone()
            if not row or row[0]:
                raise GuildConflict("Operation is cancelled or no longer owns the mission")
            for entity in entities:
                if entity.mission_id != mission_id:
                    raise GuildConflict("Cross-mission entity refused")
                await self._save(connection, entity)
            for entity in entities:
                bound_candidate = getattr(entity, "candidate_id", None)
                if bound_candidate:
                    candidate = await (await connection.execute(
                        "SELECT content_fingerprint FROM candidates WHERE id=? AND mission_id=?", (bound_candidate, mission_id),
                    )).fetchone()
                    if not candidate or (isinstance(entity, Evidence) and entity.fingerprint != candidate[0]):
                        raise GuildConflict("Candidate/evidence fingerprint or ownership mismatch")
                for evidence_id in getattr(entity, "evidence_ids", []):
                    evidence = await (await connection.execute(
                        "SELECT candidate_id FROM evidence WHERE id=? AND mission_id=?", (evidence_id, mission_id),
                    )).fetchone()
                    if not evidence or (bound_candidate and evidence[0] != bound_candidate):
                        raise GuildConflict("Evidence is absent or belongs to a different candidate")
                for evidence_id in getattr(entity, "resolution_evidence_ids", []):
                    resolution = await (await connection.execute(
                        "SELECT candidate_id FROM evidence WHERE id=? AND mission_id=?", (evidence_id, mission_id),
                    )).fetchone()
                    if not resolution or resolution[0] == bound_candidate:
                        raise GuildConflict("Resolution requires new-candidate evidence from this mission")
            if context is not None:
                await connection.execute(
                    "INSERT INTO guild_context VALUES (?,?) ON CONFLICT(mission_id) DO UPDATE SET context_json=excluded.context_json",
                    (mission_id, redact_secrets(json.dumps(context))),
                )
            await connection.execute(
                "UPDATE missions SET status=COALESCE(?,status),active_candidate_id=COALESCE(?,active_candidate_id),"
                "budgets_json=COALESCE(?,budgets_json),failure_reason=CASE WHEN ? THEN ? ELSE failure_reason END,updated_at=? WHERE id=?",
                (status.value if isinstance(status, MissionStatus) else status, candidate_id,
                 budgets.model_dump_json() if budgets else None, failure_reason is not UNSET,
                 None if failure_reason is UNSET else failure_reason, now(), mission_id),
            )
            if event:
                await self._event(connection, mission_id, event, candidate_id)
            if status == MissionStatus.AWAITING_CLARIFICATION:
                # A paused checkpoint survives a crash before the background job exits.
                await connection.execute("DELETE FROM guild_operations WHERE mission_id=? AND token=?", (mission_id, token))

    async def answer_and_claim(self, mission_id, question_id, answer):
        """Consume one answer and claim its read-only continuation in one transaction."""
        token = uuid4().hex
        async with self.transaction() as connection:
            mission = await (await connection.execute("SELECT * FROM missions WHERE id=?", (mission_id,))).fetchone()
            question = await (await connection.execute("SELECT * FROM clarifications WHERE id=? AND mission_id=?", (question_id, mission_id))).fetchone()
            if not mission or not question:
                raise KeyError("Mission or clarification not found")
            context_row = await (await connection.execute("SELECT context_json FROM guild_context WHERE mission_id=?", (mission_id,))).fetchone()
            context = json.loads(context_row[0]) if context_row else {}
            candidate_id = mission["active_candidate_id"] or context.get("baseline_candidate_id")
            candidate = await (await connection.execute("SELECT content_fingerprint FROM candidates WHERE id=? AND mission_id=?", (candidate_id, mission_id))).fetchone()
            if (mission["status"] != "AWAITING_CLARIFICATION" or mission["cancel_requested"]
                    or question["status"] != "OPEN" or question["scope_version"] != mission["scope_version"]
                    or context.get("pending_question_id") != question_id or question["candidate_id"] != candidate_id
                    or not candidate or question["candidate_fingerprint"] != candidate[0]):
                raise GuildConflict("Clarification is already answered, cancelled, or stale")
            phase = "resume_plan" if question["phase"] == "plan" else "resume_repair"
            try:
                await connection.execute("INSERT INTO guild_operations VALUES (?,?,?)", (mission_id, token, phase))
            except aiosqlite.IntegrityError:
                raise GuildConflict("Mission still has an active operation") from None
            await connection.execute("UPDATE clarifications SET status='ANSWERED',answer=?,answered_at=? WHERE id=?",
                                     (redact_secrets(answer), now(), question_id))
            context.pop("pending_question_id", None)
            await connection.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission_id))
            await connection.execute("UPDATE missions SET status=?,failure_reason=NULL,updated_at=? WHERE id=?",
                                     ("PLANNING" if phase == "resume_plan" else "REPAIRING", now(), mission_id))
            message = AgentMessage(mission_id=mission_id, sender="USER", recipient="SHOGUN", type="CLARIFICATION",
                                   candidate_id=candidate_id, summary="Clarification answered",
                                   payload={"question_id": question_id, "answer": answer})
            await self._save(connection, message)
            await self._event(connection, mission_id, "CLARIFICATION_ANSWERED", candidate_id)
        return token, phase

    async def _event(self, connection, mission_id, event, candidate_id=None, payload=None):
        sequence = (await (await connection.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE mission_id=?", (mission_id,),
        )).fetchone())[0]
        state = await (await connection.execute(
            "SELECT status,active_candidate_id FROM missions WHERE id=?", (mission_id,),
        )).fetchone()
        await connection.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
            (sequence, mission_id, event, "CONTROLLER", None, candidate_id or state["active_candidate_id"],
             "[]", redact_secrets(json.dumps({"status": state["status"], **(payload or {})})), now()),
        )

    async def release(self, mission_id, token):
        async with self.transaction() as connection:
            await connection.execute("DELETE FROM guild_operations WHERE mission_id=? AND token=?", (mission_id, token))

    async def request_cancel(self, mission_id):
        async with self.transaction() as connection:
            row = await (await connection.execute("SELECT status FROM missions WHERE id=?", (mission_id,))).fetchone()
            if not row:
                raise KeyError("Mission not found")
            if row[0] in {"APPLYING", "APPLIED", "REJECTED", "CANCELLED", "CANCEL_REQUESTED"}:
                raise GuildConflict("Mission is already terminal")
            await connection.execute(
                "UPDATE missions SET cancel_requested=1,status='CANCEL_REQUESTED',updated_at=? WHERE id=?", (now(), mission_id),
            )

    async def finish_cancel(self, mission_id):
        async with self.transaction() as connection:
            await connection.execute(
                "UPDATE missions SET status='CANCELLED',failure_reason='Cancelled by user',updated_at=? WHERE id=?", (now(), mission_id),
            )
            await connection.execute(
                "UPDATE tasks SET status='CANCELLED',updated_at=? WHERE mission_id=? AND status!='DONE'", (now(), mission_id),
            )
            await connection.execute("DELETE FROM guild_operations WHERE mission_id=?", (mission_id,))
            await self._event(connection, mission_id, "MISSION_CANCELLED")

    async def recover(self):
        """Single-process startup recovery: never replay interrupted side effects."""
        async with self.transaction() as connection:
            rows = await (await connection.execute("SELECT mission_id FROM guild_operations")).fetchall()
            for row in rows:
                mission_id = row[0]
                await connection.execute(
                    "UPDATE missions SET status='INTERRUPTED',failure_reason='Backend stopped during guild operation',updated_at=? WHERE id=?",
                    (now(), mission_id),
                )
                await connection.execute(
                    "UPDATE tasks SET status='BLOCKED',updated_at=? WHERE mission_id=? AND status='RUNNING'", (now(), mission_id),
                )
                await self._event(connection, mission_id, "MISSION_INTERRUPTED")
            await connection.execute("DELETE FROM guild_operations")
