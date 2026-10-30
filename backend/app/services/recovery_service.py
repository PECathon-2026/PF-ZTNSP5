"""Inspect and explicitly resume stopped missions without replaying write calls.

SQLite owns the continuation claim. A checkpoint digest binds the human decision
to the plan, counters, tasks and actual workspace. Snapshot files are written only
under a writer lease; the original repository is read-only throughout recovery.
"""

import asyncio
import difflib
import hashlib
import json
import os
import stat
from pathlib import Path
from uuid import uuid4

from app.agents.guild import SentinelRunner
from app.agents.samurai import SamuraiRunner
from app.schemas.approval import Approval
from app.schemas.candidate import Candidate, CandidateState
from app.schemas.finding import Finding, FindingSeverity, FindingStatus
from app.schemas.mission import CriterionStatus, MissionBudgets, MissionStatus
from app.schemas.task import MissionTask, TaskStatus
from app.security.paths import PathSecurityError, canonicalize_and_validate_path, is_path_excluded
from app.security.redaction import redact_secrets
from app.services.acceptance_tests import checked_bundle
from app.services.execution_service import ContainerExecutor
from app.services.repository_service import RepositoryService
from app.settings import get_settings
from app.storage.guild import GuildConflict, now
from app.tools.files import read_file


STOPPED = {"BUDGET_EXHAUSTED", "BLOCKED", "INTERRUPTED", "FAILED_VERIFICATION", "REPAIRING"}
EXTENDABLE = STOPPED | {"READY_FOR_AUTHORIZATION", "AWAITING_CLARIFICATION"}
NEXT_ACTION = {"PLANNING": "start_plan", "READY_FOR_AUTHORIZATION": "authorize",
               "AWAITING_CLARIFICATION": "answer", "VERIFYING": "verify",
               "VERIFIED_AWAITING_APPROVAL": "review", "APPLIED": "follow_up",
               "REJECTED": "follow_up", "CANCELLED": "follow_up"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def linked(path):
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


class RecoveryService:
    def __init__(self, controller):
        self.controller = controller
        self.db = controller.db
        self.store = controller.store
        self.ws = controller.workspaces

    def _checked_hash(self, root):
        if linked(root):
            raise GuildConflict("Linked snapshot directories cannot be recovered")
        for directory, dirs, files in os.walk(root):
            relative = Path(directory).relative_to(root)
            dirs[:] = [name for name in dirs if not is_path_excluded(relative / name)]
            for name in [*dirs, *files]:
                if is_path_excluded(relative / name):
                    continue
                path = Path(directory) / name
                if linked(path):
                    raise GuildConflict("Snapshot contains a symlink or junction")
                if name in files and (not stat.S_ISREG(path.stat().st_mode) or
                                      path.stat().st_size > get_settings().max_file_size_bytes):
                    raise GuildConflict("Snapshot contains an unsupported or oversized file")
        return self.ws._compute_dir_hash(root)

    def _validate_files(self, context, baseline, parent):
        baseline_dir = self.ws.get_baseline_dir(baseline.mission_id)
        baseline_hash, baseline_files = self._checked_hash(baseline_dir)
        if baseline_hash != baseline.content_fingerprint:
            raise GuildConflict("Captured baseline changed; recovery refused")
        for candidate in {baseline.id: baseline, parent.id: parent}.values():
            if candidate.state != CandidateState.FROZEN:
                raise GuildConflict("Checkpoint is not an unapproved frozen candidate")
            actual, _ = self._checked_hash(self.ws.get_candidate_dir(candidate.mission_id, candidate.id))
            if actual != candidate.content_fingerprint:
                raise GuildConflict("Frozen checkpoint changed; recovery refused")
        repo = Path(context["repository"]["path"])
        if not repo.is_dir() or linked(repo):
            raise GuildConflict("Original repository is missing or linked")
        manifest, _, _ = RepositoryService()._scan_files(repo)
        if manifest != context["repository"]["included_files"] or manifest != baseline_files:
            raise GuildConflict("Original repository manifest changed; start a new mission")
        for relative in manifest:
            raw = repo / relative
            if any(linked(path) for path in [raw, *raw.parents] if path == repo or path.is_relative_to(repo)):
                raise GuildConflict("Original repository has linked paths")
            target = canonicalize_and_validate_path(repo, relative)
            if not target.is_file() or target.read_bytes() != (baseline_dir / relative).read_bytes():
                raise GuildConflict("Original repository changed; start a new mission")
        workspace = self.ws.get_mission_workspace_dir(baseline.mission_id)
        workspace_hash, files = self._checked_hash(workspace)
        changed = []
        for relative in sorted(set(files) | set(baseline_files)):
            old, new = baseline_dir / relative, workspace / relative
            differs = not old.is_file() or not new.is_file() or old.read_bytes() != new.read_bytes()
            if differs:
                if SamuraiRunner._protected(relative):
                    raise GuildConflict("Protected tests or test configuration changed in the workspace")
                changed.append(relative)
        return workspace_hash, changed

    def _partial_diff(self, mission_id, parent, changed):
        root = self.ws.get_candidate_dir(mission_id, parent.id)
        workspace = self.ws.get_mission_workspace_dir(mission_id)
        text = ""
        partial_files = []
        # Compare against the last handoff; paths also include earlier task changes
        # so deletions and a recovery snapshot with no additional edits are visible.
        for relative in changed:
            old, new = root / relative, workspace / relative
            before = old.read_text(encoding="utf-8", errors="replace").splitlines(True) if old.is_file() else []
            after = new.read_text(encoding="utf-8", errors="replace").splitlines(True) if new.is_file() else []
            if before != after:
                partial_files.append(relative)
                if len(text) <= 20000:
                    text += "".join(difflib.unified_diff(before, after, fromfile=f"checkpoint/{relative}", tofile=f"workspace/{relative}"))
        return redact_secrets(text[:20000]), len(text) > 20000, partial_files

    async def inspect(self, mission_id):
        mission = await self.db.get_mission(mission_id)
        if not mission:
            raise KeyError("Mission not found")
        context = await self.store.context(mission_id) or {}
        tasks = await self.db.get_tasks(mission_id)
        criteria = await self.db.get_criteria(mission_id)
        approvals = await self.store.records(Approval, mission_id)
        candidates = await self.store.records(Candidate, mission_id)
        findings = await self.store.records(Finding, mission_id)
        async with self.store.transaction() as db:
            active = await (await db.execute("SELECT 1 FROM guild_operations WHERE mission_id=?", (mission_id,))).fetchone()
            applying = await (await db.execute("SELECT 1 FROM application_operations WHERE mission_id=?", (mission_id,))).fetchone()
            authorized = await (await db.execute("SELECT 1 FROM events WHERE mission_id=? AND event_type='PLAN_AUTHORIZED' LIMIT 1", (mission_id,))).fetchone()
        state = mission.status.value
        budget = mission.budgets
        remaining = {"model_turns": budget.max_model_turns - budget.model_turns_used,
                     "tool_calls": budget.max_tool_calls - budget.tool_calls_used,
                     "tokens": budget.max_tokens - budget.input_tokens_used - budget.output_tokens_used,
                     "time_seconds": budget.max_time_seconds - budget.time_used_seconds}
        result = {"mission_id": mission_id, "status": state, "stage": None, "checkpoint_token": None,
                  "can_continue": False, "can_extend_budget": state in EXTENDABLE and not active and not approvals and not applying and not mission.cancel_requested,
                  "next_action": NEXT_ACTION.get(state), "blockers": [], "budget_blockers": [],
                  "budgets": budget.model_dump(), "remaining": remaining, "partial_edits": False,
                  "changed_files": [], "partial_files": [], "diff": "", "diff_truncated": False,
                  "checkpoint_candidate_id": None, "new_agent_turn_limit": min(20, max(0, remaining["model_turns"]))}
        result["state_version"] = digest({"mission": mission.model_dump(), "context": context})
        if active or mission_id in self.ws._leases or (mission_id in self.controller.jobs and not self.controller.jobs[mission_id].done()):
            result["blockers"].append("A worker still owns this mission; wait for it to finish")
            result["can_extend_budget"] = False
        if applying or approvals:
            result["blockers"].append("Approval/application already exists; use the existing decision workflow")
        if mission.cancel_requested:
            result["blockers"].append("Cancelled missions require a new follow-up mission")
        from app.services.mission_credentials import has_mission_key
        if context.get("own_api_key") and not has_mission_key(mission_id):
            result["blockers"].append("Re-enter this mission's API key before continuing model work")
            result["can_extend_budget"] = False
        if state not in STOPPED:
            result["checkpoint_token"] = digest({"mission": mission.model_dump(), "context": context, "tasks": [t.model_dump() for t in tasks]})
            return result
        current_tasks = [t for t in tasks if t.id in context.get("task_ids", [])]
        baseline = next((c for c in candidates if c.id == context.get("baseline_candidate_id")), None)
        parent = next((c for c in candidates if c.id == mission.active_candidate_id), baseline)
        if not baseline or not parent or "repository" not in context:
            result["blockers"].append("No complete durable baseline exists; create a fresh mission")
            result["can_extend_budget"] = False
            return result
        workspace_hash = None
        try:
            workspace_hash, changed = self._validate_files(context, baseline, parent)
            result["changed_files"] = changed
            result["checkpoint_candidate_id"] = parent.id
            authorized = bool(authorized or context.get("execution_authorized"))
            if not authorized:
                if workspace_hash != baseline.content_fingerprint:
                    raise GuildConflict("Workspace changed before execution authorization")
                result["stage"] = "planning"
            else:
                if not context.get("plan") or not current_tasks:
                    raise GuildConflict("Authorized task plan is incomplete")
                checked_bundle(context)
                developers = [t for t in current_tasks if t.owner_agent == "SAMURAI"]
                if not developers:
                    raise GuildConflict("No implementation tasks in the saved plan")
                blocking = {f.id for f in findings if f.candidate_id == parent.id and f.status != FindingStatus.RESOLVED
                            and f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING}}
                pending = context.get("repair_round", {})
                needs_replan = bool(blocking and parent.id in context.get("routed_candidates", [])
                                    and not blocking <= set(context["plan"].get("finding_ids", [])))
                # Infrastructure failures re-run checks instead of requesting source repairs.
                environment = "environment" in (mission.failure_reason or "").lower() or "timeout" in (mission.failure_reason or "").lower()
                if (pending.get("pending") or needs_replan) and not environment:
                    if workspace_hash != parent.content_fingerprint:
                        raise GuildConflict("Workspace changed during a read-only repair checkpoint")
                    result["stage"] = "repair"
                    cap = min(3, budget.max_repair_rounds, get_settings().max_repair_rounds)
                    if budget.repair_rounds_used >= cap and not pending.get("pending"):
                        raise GuildConflict("Three-repair ceiling reached; budget extensions cannot authorize another repair")
                elif any(t.status != TaskStatus.DONE for t in developers):
                    result["stage"] = "development"
                    result["partial_edits"] = workspace_hash != parent.content_fingerprint or bool(context.get("developer_recovery"))
                else:
                    if workspace_hash != parent.content_fingerprint:
                        raise GuildConflict("Workspace changed after its final handoff; start a fresh mission")
                    result["stage"] = "checks_and_review"
            if result["partial_edits"]:
                result["diff"], result["diff_truncated"], result["partial_files"] = self._partial_diff(mission_id, parent, sorted(set(result["changed_files"]) | set(parent.changed_files)))
        except (GuildConflict, OSError, ValueError, KeyError, PathSecurityError) as exc:
            result["blockers"].append(str(exc) if isinstance(exc, GuildConflict) else "Checkpoint files are unavailable or invalid")
        for key, value in remaining.items():
            if value <= 0:
                result["budget_blockers"].append(f"No remaining {key.replace('_', ' ')} allowance")
        result["checkpoint_token"] = digest({"mission": mission.model_dump(), "context": context,
            "tasks": [t.model_dump() for t in tasks], "criteria": [c.model_dump() for c in criteria],
            "workspace": workspace_hash, "candidates": [c.model_dump() for c in candidates],
            "findings": [f.model_dump() for f in findings]})
        result["workspace_fingerprint"] = workspace_hash
        if result["blockers"]:
            result["can_extend_budget"] = False
        result["can_continue"] = bool(result["stage"] and not result["blockers"] and not result["budget_blockers"])
        return result

    async def _decision(self, mission_id, checkpoint_token):
        inspection = await self.inspect(mission_id)
        if inspection["checkpoint_token"] != checkpoint_token:
            raise GuildConflict("Recovery checkpoint changed; inspect it again")
        return inspection

    async def read_partial_file(self, mission_id, checkpoint_token, path):
        inspection = await self._decision(mission_id, checkpoint_token)
        if inspection["blockers"] or not inspection["partial_edits"]:
            raise GuildConflict("No inspectable partial-edit checkpoint")
        if path not in set(inspection["changed_files"]) | set(inspection["partial_files"]):
            raise GuildConflict("File is not part of the inspected recovery checkpoint")
        workspace = self.ws.get_mission_workspace_dir(mission_id)
        target = canonicalize_and_validate_path(workspace, path)
        result = read_file(workspace, path) if target.is_file() else {"file_path": path, "content": "", "deleted": True}
        if self._checked_hash(workspace)[0] != inspection["workspace_fingerprint"]:
            raise GuildConflict("Workspace changed while reading the checkpoint")
        return result

    async def extend_budget(self, mission_id, request):
        # Inspect outside the transaction, then use a version/counter CAS inside it.
        inspection = await self._decision(mission_id, request.checkpoint_token)
        if not inspection["can_extend_budget"]:
            raise GuildConflict("Budget can only be extended while an unapproved mission is paused")
        mission = await self.db.get_mission(mission_id)
        context = await self.store.context(mission_id) or {}
        if digest({"mission": mission.model_dump(), "context": context}) != inspection["state_version"]:
            raise GuildConflict("Mission changed after inspection; refresh recovery")
        old = mission.budgets.model_dump()
        limits = request.limits.model_dump()
        if any(limits[key] < old[key] for key in limits) or not any(limits[key] > old[key] for key in limits):
            raise GuildConflict("Raise at least one ceiling without reducing any other ceiling")
        updated = MissionBudgets(**{**old, **limits})
        async with self.store.transaction() as db:
            await self._cas(db, mission, context)
            context.setdefault("budget_extensions", []).append({"at": now(), "before": {k: old[k] for k in limits}, "after": limits})
            await db.execute("UPDATE missions SET budgets_json=?,updated_at=? WHERE id=?", (updated.model_dump_json(), now(), mission_id))
            await db.execute("INSERT INTO guild_context VALUES (?,?) ON CONFLICT(mission_id) DO UPDATE SET context_json=excluded.context_json", (mission_id, json.dumps(context)))
            await self.store._event(db, mission_id, "BUDGET_EXTENDED", payload={
                "previous_limits": {k: old[k] for k in limits}, "new_limits": limits, "usage_preserved": True})
        return await self.inspect(mission_id)

    async def _cas(self, db, mission, context):
        row = await (await db.execute("SELECT * FROM missions WHERE id=?", (mission.id,))).fetchone()
        stored = await (await db.execute("SELECT context_json FROM guild_context WHERE mission_id=?", (mission.id,))).fetchone()
        active = await (await db.execute("SELECT 1 FROM guild_operations WHERE mission_id=?", (mission.id,))).fetchone()
        approval = await (await db.execute("SELECT 1 FROM approvals WHERE mission_id=?", (mission.id,))).fetchone()
        applying = await (await db.execute("SELECT 1 FROM application_operations WHERE mission_id=?", (mission.id,))).fetchone()
        if (not row or row["status"] != mission.status.value or row["updated_at"] != mission.updated_at.isoformat()
                or json.loads(row["budgets_json"]) != mission.budgets.model_dump()
                or (json.loads(stored[0]) if stored else {}) != context or active or approval or applying or row["cancel_requested"]):
            raise GuildConflict("Mission changed or another operation already owns it; refresh recovery")

    async def continue_mission(self, mission_id, request):
        await self.controller._require_key(mission_id)
        inspection = await self._decision(mission_id, request.checkpoint_token)
        if not inspection["can_continue"]:
            raise GuildConflict("; ".join(inspection["blockers"] + inspection["budget_blockers"]) or "Use the mission's existing next action")
        if inspection["partial_edits"] and not request.accept_partial_edits:
            raise GuildConflict("Inspect and explicitly accept the unverified partial edits before continuing")
        mission = await self.db.get_mission(mission_id)
        context = await self.store.context(mission_id)
        if digest({"mission": mission.model_dump(), "context": context}) != inspection["state_version"]:
            raise GuildConflict("Mission changed after inspection; refresh recovery")
        tasks = [t for t in await self.db.get_tasks(mission_id) if t.id in context.get("task_ids", [])]
        candidates = await self.store.records(Candidate, mission_id)
        baseline = next(c for c in candidates if c.id == context["baseline_candidate_id"])
        parent = next(c for c in candidates if c.id == inspection["checkpoint_candidate_id"])
        criteria = await self.db.get_criteria(mission_id)
        token = uuid4().hex
        holder = "RECOVERY:" + token
        from app.services.workspace_service import WriterLeaseError
        try:
            self.ws.acquire_writer_lease(mission_id, holder)
        except WriterLeaseError:
            raise GuildConflict("Another operation already owns this workspace; refresh recovery") from None
        try:
            async with self.store.transaction() as db:
                await self._cas(db, mission, context)
                actual, _ = self._validate_files(context, baseline, parent)
                # Recompute the snapshot-bound decision before creating any snapshot.
                # The filesystem can change independently of SQLite after inspection.
                if actual != inspection["workspace_fingerprint"]:
                    raise GuildConflict("Workspace changed after recovery inspection")
                stage = inspection["stage"]
                snapshot = parent
                if stage != "repair":
                    self.controller._restore(context)
                    snapshot = self.ws.freeze_candidate(mission_id, mission.repository_id, parent.id)
                    if snapshot.content_fingerprint != inspection["workspace_fingerprint"]:
                        raise GuildConflict("Workspace changed while capturing the recovery snapshot")
                    snapshot.criteria_version = mission.scope_version
                    snapshot.ui_badge = "UNVERIFIED_RECOVERY"
                    await self.store._save(db, snapshot)
                context.setdefault("recovery_history", []).append({"at": now(), "from_status": mission.status.value,
                    "stage": stage, "from_candidate_id": parent.id, "snapshot_id": snapshot.id,
                    "partial_edits_accepted": request.accept_partial_edits, "checkpoint_token": request.checkpoint_token,
                    "usage": mission.budgets.model_dump()})
                context["recovery_operation"] = {"stage": stage, "snapshot_id": snapshot.id}
                context.pop("verified_contract_hash", None)
                for criterion in criteria:
                    criterion.status = CriterionStatus.PENDING
                    criterion.evidence_ids = []
                    await self.store._save(db, criterion)
                if stage in {"development", "checks_and_review"}:
                    developers = [t for t in tasks if t.owner_agent == "SAMURAI"]
                    done = {t.id for t in developers if t.status == TaskStatus.DONE}
                    for task in developers:
                        if task.status != TaskStatus.DONE:
                            task.status = TaskStatus.READY if set(task.dependencies) <= done else TaskStatus.PENDING
                            task.result_summary = "Explicit continuation from unverified recovery snapshot"
                            await self.store._save(db, task)
                    for task in tasks:
                        if task.owner_agent in {"SENTINEL", "SHADOW_COUNCIL"}:
                            task.status = TaskStatus.CANCELLED
                            await self.store._save(db, task)
                    checks = [MissionTask(mission_id=mission_id, owner_agent=role, title=title,
                               description="Inspect the recovered candidate with fresh candidate-bound evidence",
                               dependencies=[t.id for t in developers]) for role, title in (
                               ("SENTINEL", "Check recovered candidate"), ("SHADOW_COUNCIL", "Review recovered candidate"))]
                    for task in checks:
                        await self.store._save(db, task)
                    context["task_ids"] = [t.id for t in [*developers, *checks]]
                    if stage == "development":
                        task = next(t for t in developers if t.status == TaskStatus.READY)
                        context["developer_recovery"] = {"task_id": task.id, "snapshot_id": snapshot.id}
                context["recovery_parent_id"] = snapshot.id
                await db.execute("INSERT INTO guild_operations VALUES (?,?,?)", (mission_id, token, "continue"))
                await db.execute("UPDATE guild_context SET context_json=? WHERE mission_id=?", (json.dumps(context), mission_id))
                status = "PREFLIGHT" if stage == "planning" else "REPAIRING" if stage == "repair" else "RUNNING"
                await db.execute("UPDATE missions SET status=?,active_candidate_id=?,failure_reason=NULL,updated_at=? WHERE id=?", (
                    status, mission.active_candidate_id if stage == "planning" else snapshot.id, now(), mission_id))
                await self.store._event(db, mission_id, "MISSION_CONTINUED", snapshot.id, payload={
                    "stage": stage, "partial_edits_accepted": request.accept_partial_edits,
                    "from_candidate_id": parent.id, "snapshot_id": snapshot.id})
        finally:
            self.ws.release_writer_lease(mission_id, holder)
        job = asyncio.create_task(self.controller._guarded(mission_id, token, "continue"))
        self.controller.jobs[mission_id] = job
        return job

    async def run(self, mission, token, meter):
        context = await self.store.context(mission.id)
        stage = context["recovery_operation"]["stage"]
        if stage == "repair":
            return await self.controller._execute(mission, token, meter, resume_repair=True)
        if stage != "planning":
            return await self.controller._execute(mission, token, meter, continued=True)
        snapshot = next(c for c in await self.store.records(Candidate, mission.id)
                        if c.id == context["recovery_operation"]["snapshot_id"])
        self.controller._validate_checkpoint(mission.id, snapshot)
        old_tasks = [t for t in await self.db.get_tasks(mission.id) if t.id in context.get("task_ids", [])]
        for task in old_tasks:
            task.status = TaskStatus.CANCELLED
        context.setdefault("superseded_plans", []).append(context.get("plan_history", []))
        for key in ("plan", "task_ids", "plan_history", "approved_criteria", "acceptance_tests", "acceptance_baseline_checked", "test_gaps", "test_gap_proposals"):
            context.pop(key, None)
        context["baseline_candidate_id"] = snapshot.id
        await self.store.commit(mission.id, token, entities=old_tasks, context=context, event="RECOVERY_BASELINE_READY")
        profiles = ["python_pytest", "python_bandit"] if isinstance(self.controller.executor, ContainerExecutor) else ["python_pytest"]
        result = await SentinelRunner(self.controller.executor, self.ws, self.controller.artifacts, meter.before_tool,
            self.controller._activity(mission.id, "SENTINEL", candidate_id=snapshot.id)).run(snapshot, profiles, baseline=True)
        await self.store.commit(mission.id, token, entities=[*result.evidence, *result.findings], event="RECOVERY_BASELINE_CHECKED")
        if result.blocked:
            return await self.controller._stop(mission.id, token, MissionStatus.BLOCKED, "Recovery baseline checks remain unavailable")
        await self.controller._plan(mission, token, meter, resume=True)
