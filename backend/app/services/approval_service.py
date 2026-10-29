"""M6 trusted approval and guarded application; never executes repository code."""

import os
import tempfile
from pathlib import Path

from app.schemas.approval import Approval, ApprovalDecision
from app.schemas.candidate import Candidate, CandidateState
from app.schemas.mission import MissionStatus
from app.security.paths import canonicalize_and_validate_path, is_path_excluded
from app.services.verifier import verify
from app.storage.guild import GuildConflict, GuildStore, now
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.task import MissionTask
from app.services.repository_service import RepositoryService


class ApprovalService:
    def __init__(self, controller):
        self.controller = controller
        self.store = GuildStore(controller.db)

    async def _candidate(self, mission_id, candidate_id, fingerprint=None):
        mission = await self.controller.db.get_mission(mission_id)
        if not mission:
            raise KeyError("Mission not found")
        candidates = await self.store.records(Candidate, mission_id)
        candidate = next((c for c in candidates if c.id == candidate_id), None)
        if not candidate or mission.active_candidate_id != candidate_id or (fingerprint and candidate.content_fingerprint != fingerprint):
            raise GuildConflict("Candidate is stale or its fingerprint differs")
        return mission, candidate

    async def verify(self, mission_id):
        mission = await self.controller.db.get_mission(mission_id)
        if not mission:
            raise KeyError("Mission not found")
        if mission.status != MissionStatus.VERIFYING or not mission.active_candidate_id:
            raise GuildConflict("Mission is not ready for independent verification")
        token = await self.store.claim_verification(mission_id)
        try:
            mission, candidate = await self._candidate(mission_id, mission.active_candidate_id)
            self.controller.workspaces.validate_candidate(candidate)
            context = await self.store.context(mission_id)
            if not context or candidate.criteria_version != mission.scope_version:
                raise GuildConflict("Candidate criteria version is stale")
            criteria = await self.controller.db.get_criteria(mission_id)
            evidence = await self.store.records(Evidence, mission_id)
            findings = await self.store.records(Finding, mission_id)
            tasks = [t for t in await self.controller.db.get_tasks(mission_id) if t.id in context["task_ids"]]
            passed, criteria = verify(candidate, criteria, evidence, findings, tasks)
            candidate.ui_badge = "VERIFIED" if passed else "IN_CANDIDATE"
            await self.store.commit(mission_id, token, status=MissionStatus.VERIFIED_AWAITING_APPROVAL if passed else MissionStatus.FAILED_VERIFICATION,
                                    entities=[*criteria, candidate], event="VERIFICATION_PASSED" if passed else "VERIFICATION_FAILED")
            return await self.controller.db.get_mission(mission_id)
        finally:
            await self.store.release(mission_id, token)

    async def decide(self, mission_id, request):
        mission, candidate = await self._candidate(mission_id, request.candidate_id, request.candidate_fingerprint)
        if mission.status != MissionStatus.VERIFIED_AWAITING_APPROVAL or candidate.state != CandidateState.FROZEN:
            raise GuildConflict("Candidate has not passed independent verification")
        self.controller.workspaces.validate_candidate(candidate)
        async with self.store.transaction() as connection:
            row = await (await connection.execute("SELECT status,active_candidate_id FROM missions WHERE id=?", (mission_id,))).fetchone()
            if row[0] != MissionStatus.VERIFIED_AWAITING_APPROVAL.value or row[1] != candidate.id:
                raise GuildConflict("Approval became stale")
            previous = await (await connection.execute("SELECT id FROM approvals WHERE mission_id=?", (mission_id,))).fetchone()
            if previous:
                raise GuildConflict("Candidate decision already recorded")
            approval = Approval(mission_id=mission_id, candidate_id=candidate.id, candidate_fingerprint=candidate.content_fingerprint, decision=request.decision)
            await self.store._save(connection, approval)
            candidate.state = CandidateState.APPROVED if request.decision == ApprovalDecision.APPROVED else CandidateState.REJECTED
            await self.store._save(connection, candidate)
            if request.decision == ApprovalDecision.REJECTED:
                await connection.execute("UPDATE missions SET status=?,updated_at=? WHERE id=?", (MissionStatus.REJECTED.value, now(), mission_id))
            await self.store._event(connection, mission_id, "CANDIDATE_APPROVED" if request.decision == ApprovalDecision.APPROVED else "CANDIDATE_REJECTED", candidate.id)
        return approval

    async def apply(self, mission_id, candidate_id):
        mission, candidate = await self._candidate(mission_id, candidate_id)
        if mission.status != MissionStatus.VERIFIED_AWAITING_APPROVAL or candidate.state != CandidateState.APPROVED:
            raise GuildConflict("Candidate needs a matching human approval")
        context = await self.store.context(mission_id)
        if not context or candidate.criteria_version != mission.scope_version:
            raise GuildConflict("Candidate scope is stale")
        repo = Path(context["repository"]["path"])
        baseline = self.controller.workspaces.get_baseline_dir(mission_id)
        snapshot = self.controller.workspaces.get_candidate_dir(mission_id, candidate_id)
        self.controller.workspaces._compute_dir_hash(baseline)
        if candidate.state != CandidateState.APPROVED:
            raise GuildConflict("Candidate has not been approved")
        if self.controller.workspaces._compute_dir_hash(snapshot)[0] != candidate.content_fingerprint:
            raise GuildConflict("Approved candidate snapshot changed")
        # An atomic replacement is possible for one file. Refuse multi-file changes
        # rather than advertise atomicity without a crash-recovery journal.
        if len(candidate.changed_files) != 1:
            raise GuildConflict("Atomic application currently requires exactly one changed file; export the patch for multi-file changes")
        relative = candidate.changed_files[0]
        if is_path_excluded(Path(relative)):
            raise GuildConflict("Restricted path in candidate")
        target = canonicalize_and_validate_path(repo, relative)
        base_file = canonicalize_and_validate_path(baseline, relative)
        source = canonicalize_and_validate_path(snapshot, relative)
        if not source.is_file() or source.is_symlink() or target.is_symlink() or not target.is_file() or not base_file.is_file():
            raise GuildConflict("Application requires an existing regular file")
        original = base_file.read_bytes()
        if target.read_bytes() != original:
            raise GuildConflict("Original file differs from the captured baseline")
        changed = source.read_bytes()
        if changed == original:
            raise GuildConflict("Candidate has no file change")
        if len(changed) > 524288:
            raise GuildConflict("Candidate file exceeds the size limit")
        # Check the whole approved manifest, including new/unapproved files.
        repo_service = RepositoryService()
        current_files, _, _ = repo_service._scan_files(repo)
        if current_files != context["repository"]["included_files"]:
            raise GuildConflict("Original repository file manifest changed since preflight")
        for name in current_files:
            actual = canonicalize_and_validate_path(repo, name)
            saved = canonicalize_and_validate_path(baseline, name)
            if not actual.is_file() or actual.is_symlink() or actual.read_bytes() != saved.read_bytes():
                raise GuildConflict("Original repository changed since preflight")
        async with self.store.transaction() as connection:
            mission_row = await (await connection.execute("SELECT status,active_candidate_id FROM missions WHERE id=?", (mission_id,))).fetchone()
            approval = await (await connection.execute("SELECT * FROM approvals WHERE mission_id=? AND candidate_id=?", (mission_id, candidate_id))).fetchone()
            if not mission_row or mission_row[0] != MissionStatus.VERIFIED_AWAITING_APPROVAL.value or mission_row[1] != candidate_id or not approval or approval["decision"] != "APPROVED" or approval["candidate_fingerprint"] != candidate.content_fingerprint or approval["application_result_id"]:
                raise GuildConflict("Approval or candidate changed before application")
            # One-file atomic os.replace. Hold the DB write lock through the final
            # baseline recheck and replacement, so duplicate API calls cannot race.
            if target.read_bytes() != original or target.is_symlink():
                raise GuildConflict("Original repository changed before application")
            if self.controller.workspaces._compute_dir_hash(snapshot)[0] != candidate.content_fingerprint or source.read_bytes() != changed:
                raise GuildConflict("Approved candidate changed before application")
            latest_files, _, _ = repo_service._scan_files(repo)
            if latest_files != current_files or any(
                canonicalize_and_validate_path(repo, name).read_bytes() != canonicalize_and_validate_path(baseline, name).read_bytes()
                for name in current_files
            ):
                raise GuildConflict("Original repository changed before application")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".devpilot-", delete=False) as fp:
                    temporary = Path(fp.name)
                    fp.write(changed)
                    fp.flush()
                    os.fsync(fp.fileno())
                os.chmod(temporary, target.stat().st_mode)
                os.replace(temporary, target)
                temporary = None
                await connection.execute("UPDATE approvals SET application_result_id=? WHERE id=?", (candidate.id, approval["id"]))
                candidate.state = CandidateState.APPLIED
                await self.store._save(connection, candidate)
                await connection.execute("UPDATE missions SET status=?,updated_at=? WHERE id=?", (MissionStatus.APPLIED.value, now(), mission_id))
                await self.store._event(connection, mission_id, "PATCH_APPLIED", candidate.id)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return await self.controller.db.get_mission(mission_id)
