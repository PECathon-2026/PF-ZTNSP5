"""Deterministic, candidate-bound acceptance verification. No model decisions."""

import re

from app.schemas.mission import CriterionStatus
from app.schemas.finding import FindingSeverity, FindingStatus


def verify(candidate, criteria, evidence, findings, tasks):
    """Return (passed, updated criteria); reject missing/ambiguous check evidence."""
    required = {c.verification_method.removeprefix("test_profile:") for c in criteria}
    checks = {}
    for item in evidence:
        if item.candidate_id == candidate.id and item.fingerprint == candidate.content_fingerprint:
            profile = item.metadata.get("check_profile")
            if profile:
                checks.setdefault(profile, []).append(item)
    blocking = any(f.status != FindingStatus.RESOLVED and f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING}
                   for f in findings if f.candidate_id == candidate.id)
    active_tasks_done = all(task.status.value == "DONE" and task.candidate_id == candidate.id
                            for task in tasks if task.owner_agent in {"SENTINEL", "SHADOW_COUNCIL"})
    passed = bool(criteria) and bool(candidate.changed_files) and active_tasks_done and not blocking
    for criterion in criteria:
        profile = criterion.verification_method.removeprefix("test_profile:")
        records = checks.get(profile, [])
        # One unambiguous, complete execution on this candidate per profile.
        valid = (len(records) == 1 and records[0].exit_code == 0 and
                 records[0].metadata.get("execution_status") == "SUCCEEDED" and
                 not records[0].metadata.get("controlled_evaluation", False))
        if valid and profile == "python_pytest":
            text = records[0].metadata.get("stdout", "")
            valid = bool(re.search(r"\b[1-9]\d* passed\b", text)) and not re.search(r"\b\d+ failed\b|no tests ran", text, re.I)
        criterion.status = CriterionStatus.PASS if valid and active_tasks_done and not blocking else CriterionStatus.NOT_VERIFIED
        criterion.evidence_ids = [records[0].id] if valid and active_tasks_done and not blocking else []
        passed &= criterion.status == CriterionStatus.PASS
    return passed, criteria
