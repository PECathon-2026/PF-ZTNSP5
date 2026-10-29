"""M6 trusted approval and guarded application; never executes repository code."""

from app.schemas.approval import Approval, ApprovalDecision
from app.schemas.candidate import Candidate, CandidateState
from app.schemas.mission import MissionStatus
from app.services.verifier import verify
from app.storage.guild import GuildConflict, GuildStore, now
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.task import MissionTask
from app.services.patch_application import PatchApplication
from app.services.activity import safe_label
from app.services.criterion_checks import verification_contract_hash
from app.services.test_reports import object_hash
from app.schemas.evidence import EvidenceKind
import json


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

    async def _evaluate(self, mission, candidate, context):
        criteria = await self.controller.db.get_criteria(mission.id)
        directory = self.controller.workspaces.get_candidate_dir(mission.id, candidate.id)
        contract = verification_contract_hash(directory, criteria)
        evidence = await self.store.records(Evidence, mission.id)
        for item in evidence:
            if item.metadata.get("report"):
                raw = self.controller.artifacts.read_artifact(mission.id, item.metadata.get("report_artifact_id", "missing"))
                try:
                    if raw is None or object_hash(json.loads(raw)) != item.metadata.get("report_hash"):
                        item.metadata["report"] = None
                except ValueError:
                    item.metadata["report"] = None
        findings = await self.store.records(Finding, mission.id)
        tasks = [t for t in await self.controller.db.get_tasks(mission.id) if t.id in context["task_ids"]]
        passed, criteria = verify(candidate, criteria, evidence, findings, tasks, contract_hash=contract)
        if context.get("challenge_enabled"):
            challenges = [e for e in evidence if e.kind == EvidenceKind.MUTATION and e.candidate_id == candidate.id
                          and e.fingerprint == candidate.content_fingerprint]
            passed &= len(challenges) == 1 and challenges[0].metadata.get("status") in {"COMPLETE", "NOT_APPLICABLE"}
        return passed, criteria, contract

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
            passed, criteria, contract = await self._evaluate(mission, candidate, context)
            context["verified_contract_hash"] = contract if passed else None
            candidate.ui_badge = "VERIFIED" if passed else "IN_CANDIDATE"
            await self.store.commit(mission_id, token, status=MissionStatus.VERIFIED_AWAITING_APPROVAL if passed else MissionStatus.FAILED_VERIFICATION,
                                    entities=[*criteria, candidate], context=context, event="VERIFICATION_PASSED" if passed else "VERIFICATION_FAILED")
            await self.controller.db.emit_event(mission_id, "AGENT_ACTIVITY", "VERIFIER", {
                "stage": "outcome", "action": "verify",
                "summary": (f"Independent verifier matched {len(criteria)} acceptance checks to this frozen candidate; human approval is still required."
                            if passed else "Independent verifier could not validate every criterion against this candidate; approval remains blocked."),
                "candidate_fingerprint": candidate.content_fingerprint,
            }, candidate_id=candidate.id, evidence_ids=[item for criterion in criteria for item in criterion.evidence_ids])
            return await self.controller.db.get_mission(mission_id)
        finally:
            await self.store.release(mission_id, token)

    async def decide(self, mission_id, request):
        mission, candidate = await self._candidate(mission_id, request.candidate_id, request.candidate_fingerprint)
        if mission.status != MissionStatus.VERIFIED_AWAITING_APPROVAL or candidate.state != CandidateState.FROZEN:
            raise GuildConflict("Candidate has not passed independent verification")
        self.controller.workspaces.validate_candidate(candidate)
        context = await self.store.context(mission_id)
        valid, _, contract = await self._evaluate(mission, candidate, context)
        if not valid or context.get("verified_contract_hash") != contract:
            raise GuildConflict("Verification evidence or contract changed; approval refused")
        async with self.store.transaction() as connection:
            row = await (await connection.execute("SELECT status,active_candidate_id FROM missions WHERE id=?", (mission_id,))).fetchone()
            if row[0] != MissionStatus.VERIFIED_AWAITING_APPROVAL.value or row[1] != candidate.id:
                raise GuildConflict("Approval became stale")
            previous = await (await connection.execute("SELECT id FROM approvals WHERE mission_id=?", (mission_id,))).fetchone()
            if previous:
                raise GuildConflict("Candidate decision already recorded")
            approval = Approval(mission_id=mission_id, candidate_id=candidate.id, candidate_fingerprint=candidate.content_fingerprint,
                                intended_action="APPLY_PATCH:" + contract, decision=request.decision)
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
        valid, _, contract = await self._evaluate(mission, candidate, context)
        approvals = await self.store.records(Approval, mission_id)
        if not valid or not any(a.candidate_id == candidate.id and a.intended_action == "APPLY_PATCH:" + contract for a in approvals):
            raise GuildConflict("Approved verification contract is stale")
        return await PatchApplication(self.controller).apply(mission, candidate, context)
