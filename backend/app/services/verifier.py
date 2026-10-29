"""Verify candidate/contract-bound structured results, never console summaries."""

from app.schemas.mission import CriterionStatus
from app.schemas.finding import FindingSeverity, FindingStatus
from app.services.criterion_checks import criterion_selectors
from app.services.test_reports import report_passes, object_hash


def evidence_passes(item, contract_hash, selectors=()):
    report = item.metadata.get("report")
    return bool(contract_hash and item.source == "SENTINEL" and item.exit_code == 0
                and item.metadata.get("execution_status") == "SUCCEEDED"
                and not item.metadata.get("controlled_evaluation")
                and item.metadata.get("output_truncated") is False
                and item.metadata.get("verification_contract_hash") == contract_hash
                and report and item.metadata.get("report_hash") == object_hash(report)
                and report_passes(report, item.exit_code, selectors))


def verify(candidate, criteria, evidence, findings, tasks, baseline=None, contract_hash=None):
    blocking = any(f.status != FindingStatus.RESOLVED and f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING}
                   for f in findings if f.candidate_id == candidate.id)
    check_tasks = [task for task in tasks if task.owner_agent in {"SENTINEL", "SHADOW_COUNCIL"}]
    done = {task.owner_agent for task in check_tasks} == {"SENTINEL", "SHADOW_COUNCIL"} and all(
        task.status.value == "DONE" and task.candidate_id == candidate.id for task in check_tasks)
    bound = [item for item in evidence if item.mission_id == candidate.mission_id and
             item.candidate_id == candidate.id and item.fingerprint == candidate.content_fingerprint
             and item.metadata.get("verification_contract_hash") == contract_hash]
    suites = [item for item in bound if item.criterion_id is None and item.metadata.get("check_profile") == "python_pytest"
              and not item.metadata.get("test_selector")]
    suite_ok = len(suites) == 1 and evidence_passes(suites[0], contract_hash)
    passed = bool(criteria and candidate.changed_files and done and not blocking and suite_ok)
    for criterion in criteria:
        profile, selectors = criterion_selectors(criterion)
        matched = []
        for selector in selectors:
            records = [item for item in bound if item.criterion_id == criterion.id and
                       item.metadata.get("check_profile") == profile and item.metadata.get("test_selector") == selector]
            if len(records) == 1 and evidence_passes(records[0], contract_hash, [selector]):
                matched.append(records[0].id)
        valid = (profile == "python_pytest" and bool(selectors) and len(matched) == len(selectors)
                 and done and not blocking and suite_ok and criterion.criteria_version == candidate.criteria_version)
        criterion.status = CriterionStatus.PASS if valid else CriterionStatus.NOT_VERIFIED
        criterion.evidence_ids = matched if valid else []
        passed &= valid
    return bool(passed), criteria
