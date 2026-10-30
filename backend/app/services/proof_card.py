"""Candidate-bound proof card: references and outcomes, never raw source/logs."""

from app.schemas.evidence import EvidenceKind
from app.services.activity import safe_label


def proof_card(detail, context, events):
    candidate = next((c for c in detail.candidates if c.id == detail.mission.active_candidate_id), None)
    evidence = [e for e in detail.evidence if candidate and e.candidate_id == candidate.id
                and e.fingerprint == candidate.content_fingerprint]
    timeline = [{"sequence": e.sequence, "source": e.source, "event_type": e.event_type,
                 "task_id": e.task_id, "candidate_id": e.candidate_id, "evidence_ids": e.evidence_ids,
                 "summary": safe_label(e.display_payload.get("summary", e.event_type), 360)}
                for e in events if e.event_type == "AGENT_ACTIVITY" or e.event_type in
                {"PLAN_REVISED", "FINDINGS_ROUTED", "VERIFICATION_PASSED", "VERIFICATION_FAILED", "PATCH_APPLIED"}]
    known_findings = {item.id: item for item in detail.findings}
    links = []
    for message in detail.messages:
        finding_id = message.payload.get("finding_id")
        if finding_id not in known_findings:
            continue
        finding = known_findings[finding_id]
        links.append({"finding_id": finding_id, "trigger_evidence_ids": finding.evidence_ids,
                      "from_candidate_id": finding.candidate_id, "recipient": message.recipient,
                      "reopened_task_ids": message.payload.get("reopened_task_ids", [])})
    return {"mission_id": detail.mission.id, "mission_status": detail.mission.status.value,
            "request": safe_label(detail.mission.request_text, 1000),
            "candidate": {"id": candidate.id, "fingerprint": candidate.content_fingerprint,
                          "changed_files": candidate.changed_files} if candidate else None,
            "plan_revisions": context.get("plan_history", []),
            "test_gaps": context.get("test_gaps", []),
            "test_gap_proposals": context.get("test_gap_proposals", []),
            "reviewed_acceptance_tests": {"proposal_hash": context["acceptance_tests"]["hash"],
                                           "accepted": context["acceptance_tests"].get("accepted", False),
                                           "files": [file["path"] for file in context["acceptance_tests"]["proposal"]["files"]]}
                                           if context.get("acceptance_tests") else None,
            "causal_links": links[:200],
            "criteria": [{"id": c.id, "description": safe_label(c.description, 500), "status": c.status.value,
                          "method": c.verification_method, "evidence_ids": c.evidence_ids}
                         for c in detail.criteria],
            "checks": [{"id": e.id, "kind": e.kind.value, "criterion_id": e.criterion_id,
                        "profile": e.metadata.get("check_profile"), "selector": e.metadata.get("test_selector"),
                        "exit_code": e.exit_code, "classification": e.metadata.get("classification"),
                        "report_hash": e.metadata.get("report_hash"), "contract_hash": e.metadata.get("verification_contract_hash"),
                        "report_summary": e.metadata.get("report", {}).get("summary") if isinstance(e.metadata.get("report"), dict) else None,
                        "controlled_evaluation": e.metadata.get("controlled_evaluation", False)}
                       for e in evidence if e.kind in {EvidenceKind.TEST, EvidenceKind.BUILD, EvidenceKind.STATIC_SCAN}],
            "challenge": [{"id": e.id, "status": e.metadata.get("status"), "attempts": e.metadata.get("attempts", [])}
                          for e in evidence if e.kind == EvidenceKind.MUTATION],
            "findings": [{"id": f.id, "candidate_id": f.candidate_id, "severity": f.severity.value,
                          "status": f.status.value, "title": safe_label(f.title, 160),
                          "evidence_ids": f.evidence_ids, "resolution_evidence_ids": f.resolution_evidence_ids}
                         for f in detail.findings],
            "budgets": detail.mission.budgets.model_dump(),
            "approvals": [{"candidate_id": a.candidate_id, "fingerprint": a.candidate_fingerprint,
                           "decision": a.decision.value} for a in detail.approvals],
            "timeline": timeline[-200:], "timeline_truncated": len(timeline) > 200}


def proof_markdown(card):
    lines = [f"# Mission {card['mission_id']}", "", f"Status: {card['mission_status']}",
             f"Request: {card['request']}", ""]
    if card["candidate"]:
        lines += [f"Candidate: {card['candidate']['id']} ({card['candidate']['fingerprint']})", ""]
    lines += ["## Acceptance criteria"]
    for item in card["criteria"]:
        lines.append(f"- {item['status']}: {item['description']} - evidence {', '.join(item['evidence_ids']) or 'none'}")
    lines += ["", "## Tests and security checks"]
    for item in card["checks"]:
        lines.append(f"- {item['kind']} ({item['profile'] or 'n/a'}): exit {item['exit_code']}, {item['classification'] or 'unclassified'}, evidence {item['id']}")
    lines += ["", "## Unmapped criteria", *[f"- {gap}" for gap in card["test_gaps"]],
              "", "## Findings and routing"]
    for item in card["causal_links"]:
        lines.append(f"- Finding {item['finding_id']} -> {item['recipient']}; tasks {', '.join(item['reopened_task_ids']) or 'no reopened task'}")
    lines += ["", "## Challenge", *[f"- {item['status']}: {len(item['attempts'])} variants ({item['id']})" for item in card["challenge"]],
              "", "## Decision timeline"]
    for item in card["timeline"]:
        lines.append(f"- {item['sequence']} {item['source']}: {item['summary']}")
    return "\n".join(lines) + "\n"
