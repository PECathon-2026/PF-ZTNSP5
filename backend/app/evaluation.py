"""M8 five-scenario evaluator. Run: python -m app.evaluation --mode controlled|live.

Controlled mode uses the real controller, SQLite, workspace tools and model wire
format; its model and check results are scripted, NEVER executed on the host.
Live mode requires Docker and uses real model/container checks (no automatic apply).
"""

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from app.agents.model_adapter import ModelAdapter, ModelAdapterConfig
from app.agents.guild import ShadowCouncilRunner
from app.schemas.agent_message import AgentMessage, MessageType
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding, FindingSeverity, FindingStatus
from app.schemas.guild import Clarification
from app.schemas.mission import AcceptanceCriterion, ClarificationAnswerRequest, Mission, MissionStatus
from app.services.execution_service import ContainerExecutor
from app.services.guild_service import GuildController
from app.services.repository_service import get_repository_service
from app.services.workspace_service import WorkspaceService
from app.settings import Settings
from app.storage.artifacts import ArtifactStorage
from app.storage.database import Database

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "sample-repos"
RESULTS = ROOT / "evaluation" / "results"


@dataclass(frozen=True)
class Scenario:
    name: str
    request: str
    criterion: str
    file: str
    initial: str
    final: str
    repairs: int = 0
    clarification: bool = False


SCENARIOS = (
    Scenario("feature", "Add active/completed status filtering, reject unsupported statuses and preserve sorting.",
             "Status filtering rejects unsupported values and preserves sorting", "tasks.py",
             '    return sorted([task for task in TASKS if status == "active" and task["status"] == status], key=lambda task: task["title"])',
             '    if status is not None and status not in {"active", "completed"}:\n        raise ValueError("unsupported status")\n    return sorted([task for task in TASKS if status is None or task["status"] == status], key=lambda task: task["title"])', 1),
    Scenario("bug", "Fix pagination off-by-one; preserve full page size and the last partial page.",
             "Pagination returns complete and partial pages", "pagination.py", "    return items[start:start + size]", "    return items[start:start + size]"),
    Scenario("recovery", "Investigate pre-existing failed test for completed task status and fix the implementation.",
             "Completed tasks have completed status", "status.py", '    return "completed" if done else "active"',
             '    return "completed" if done else "active"'),
    Scenario("security", "Remove unsanitized shell execution and use an allowlisted, shell-free subprocess call.",
             "Untrusted command strings never reach a shell", "runner.py", "    return os.system(command.strip())",
             'import subprocess\n\n\ndef run_command(command):\n    if command not in {"echo"}:\n        raise ValueError("unsupported command")\n    return subprocess.run([command], shell=False, check=False).returncode\n', 1),
    Scenario("unexpected", "Make average fast; clarify how an empty input should behave before editing.",
             "Empty input returns zero and nonempty input preserves the average", "metrics.py",
             "    return 0 if not values else sum(values) / len(values)",
             "    return 0 if not values else sum(values) / len(values)", clarification=True),
)


def _call(name, arguments, ident):
    return {"type": "tool_use", "id": ident, "name": name, "input": arguments}


class ScriptedModel:
    def __init__(self, scenario):
        self.scenario = scenario
        self.developer_runs = 0
        self.review_runs = 0
        self.calls = []

    def factory(self):
        return ModelAdapter(settings=Settings(
            model_provider="anthropic", anthropic_api_key="controlled-placeholder", anthropic_base_url="https://controlled.invalid/v1"),
            config=ModelAdapterConfig(max_retries=0), transport=httpx.MockTransport(self.respond))

    def respond(self, request):
        body = json.loads(request.content)
        names = {tool["name"] for tool in body["tools"]}
        role = "repair" if "submit_repair_plan" in names else "plan" if "submit_plan" in names else "review" if "submit_review" in names else "developer"
        turn = sum(item["role"] == "assistant" for item in body["messages"]) + 1
        context = json.loads(body["messages"][0]["content"]) if role in {"plan", "repair", "review"} else {}
        if role == "plan" and self.scenario.clarification and not context["clarification_answers"]:
            calls = [_call("request_clarification", {"question": "What should average([]) return?", "reason": "Undefined behavior in the request"}, "clarify")]
        elif role in {"plan", "repair"}:
            if turn == 1:
                calls = [_call("read_file", {"relative_path": self.scenario.file}, "inspect")]
            else:
                proposal = {
                    "summary": "Repair findings" if role == "repair" else "Inspect and implement request",
                    "criteria": [{"description": self.scenario.criterion, "check_profile": "python_pytest"}],
                    "tasks": [{"key": "fix", "title": "Make targeted change", "description": self.scenario.request, "dependencies": []}],
                }
                if role == "repair":
                    proposal["finding_ids"] = [f["id"] for f in context["findings"]]
                calls = [_call("submit_repair_plan" if role == "repair" else "submit_plan", proposal, "plan-result")]
        elif role == "developer":
            if turn == 1:
                self.developer_runs += 1
                calls = [_call("read_file", {"relative_path": self.scenario.file}, "read")]
            elif turn == 2:
                previous = json.loads(body["messages"][-1]["content"][0]["content"])
                old = previous["content"]
                replacement = self.scenario.final if self.developer_runs > 1 else self.scenario.initial
                if self.scenario.name == "security" and self.developer_runs > 1:
                    target = old
                elif self.scenario.name == "feature" and self.developer_runs > 1:
                    target = self.scenario.initial
                elif self.scenario.name == "bug":
                    target = "    return items[start:start + size - 1]"
                elif self.scenario.name == "recovery":
                    target = '    return "active"'
                elif self.scenario.name == "security":
                    target = "    return os.system(command)"
                elif self.scenario.name == "unexpected":
                    target = "    return sum(values) / len(values)"
                else:
                    target = '    return sorted(TASKS, key=lambda task: task["title"])'
                calls = [_call("apply_patch", {"relative_path": self.scenario.file, "expected_fingerprint": previous["fingerprint"],
                                               "target": target, "replacement": replacement}, "patch")]
            elif turn == 3:
                calls = [_call("read_file", {"relative_path": self.scenario.file}, "read-back"),
                         _call("read_diff", {"relative_path": self.scenario.file}, "diff")]
            else:
                calls = [_call("submit_candidate", {"summary": "Source prepared for independent checks"}, "handoff")]
        else:
            if turn == 1:
                self.review_runs += 1
                calls = [_call("read_file", {"relative_path": self.scenario.file}, "review-read"),
                         _call("read_diff", {"relative_path": self.scenario.file}, "review-diff")]
            else:
                findings = []
                if self.scenario.name == "security" and self.review_runs == 1:
                    findings = [{"severity": "BLOCKING", "title": "Shell injection via os.system", "description": "Untrusted input still reaches the shell",
                                 "observed_behavior": "os.system accepts an untrusted command", "expected_behavior": "Allowlist and shell-free subprocess",
                                 "file_path": self.scenario.file, "evidence_ids": [context["evidence"][0]["id"]]}]
                report = {"summary": "Diff inspected", "findings": findings,
                          "resolved_finding_ids": [f["id"] for f in context.get("prior_findings", [])]}
                calls = [_call("submit_review", report, "review-result")]
        self.calls.append({"role": role, "step": turn, "tool_calls": [call["name"] for call in calls]})
        return httpx.Response(200, json={"content": calls, "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 5}})


class FixtureOracle:
    """Source-level oracle, not pytest and not a real check execution."""

    def __init__(self, scenario):
        self.scenario = scenario
        self.calls = []

    async def run(self, directory, profile):
        source = (directory / self.scenario.file).read_text(encoding="utf-8")
        if self.scenario.name == "feature":
            passed = self.scenario.final in source
        elif self.scenario.name == "security":
            passed = "os.system(" not in source and "shell=False" in source and "unsupported command" in source
        else:
            passed = self.scenario.final in source
        self.calls.append({"candidate_dir": str(directory), "profile": profile, "oracle_passed": passed})
        return {"status": "SUCCEEDED" if passed else "FAILED", "exit_code": 0 if passed else 1,
                "duration_ms": 0, "stdout": "1 passed (controlled oracle; not pytest)" if passed else "FAILED controlled fixture oracle",
                "stderr": "", "command": ["controlled-fixture-oracle", profile], "controlled_evaluation": True}


def serialize_report(scenario, mode, mission, checks, candidates, evidence, findings, messages, questions, model_calls, original_unchanged):
    return {
        "scenario": scenario.name, "mode": mode, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": mission.status.value, "failure_reason": mission.failure_reason,
        "original_unchanged": original_unchanged, "request": scenario.request,
        "checks": checks, "candidate_chain": [{"id": c.id, "fingerprint": c.content_fingerprint,
                                                 "parent": c.parent_candidate_id, "changed_files": c.changed_files} for c in candidates],
        "evidence": [{"id": e.id, "candidate_id": e.candidate_id, "fingerprint": e.fingerprint,
                      "kind": e.kind.value, "exit_code": e.exit_code, "duration_ms": e.duration_ms,
                      "stdout_artifact_id": e.stdout_artifact_id, "stderr_artifact_id": e.stderr_artifact_id,
                      "command": e.command, "classification": e.metadata.get("classification"),
                      "controlled_evaluation": e.metadata.get("controlled_evaluation", False)} for e in evidence],
        "findings": [{"id": f.id, "candidate_id": f.candidate_id, "source": f.source_agent, "severity": f.severity.value,
                      "status": f.status.value, "evidence_ids": f.evidence_ids, "resolution_evidence_ids": f.resolution_evidence_ids} for f in findings],
        "messages": [{"type": m.type.value, "sender": m.sender, "recipient": m.recipient, "candidate_id": m.candidate_id} for m in messages],
        "clarifications": [{"id": q.id, "status": q.status, "phase": q.phase, "question": q.question} for q in questions],
        "model_tool_trajectory": model_calls, "repair_rounds": mission.budgets.repair_rounds_used,
        "verifier_invoked": False, "original_patch_applied": False,
    }


async def evaluate_one(scenario, mode, run_dir):
    source_dir = SAMPLES / scenario.name
    repo_service = get_repository_service()
    original_bytes = {path.relative_to(source_dir).as_posix(): path.read_bytes() for path in source_dir.rglob("*") if path.is_file()}
    repo = repo_service.connect_repository(str(source_dir))
    db = Database(run_dir / f"{scenario.name}.db")
    await db.init_db()
    model = ScriptedModel(scenario) if mode == "controlled" else None
    executor = FixtureOracle(scenario) if mode == "controlled" else ContainerExecutor()
    controller = GuildController(db, WorkspaceService(run_dir / "workspaces"), ArtifactStorage(run_dir / "artifacts"),
                                 executor, model.factory if model else None)
    mission = Mission(repository_id=repo["repository_id"], request_text=scenario.request, status=MissionStatus.PLANNING)
    await db.create_mission(mission, [AcceptanceCriterion(mission_id=mission.id, description=scenario.criterion)])
    try:
        await (await controller.start(mission.id, "plan"))
        current = await db.get_mission(mission.id)
        if current.status == MissionStatus.AWAITING_CLARIFICATION:
            question = (await controller.store.records(Clarification, mission.id))[0]
            answer = ("Allow only the echo command, reject all others with ValueError; use subprocess.run([command], shell=False)."
                      if scenario.name == "security" else "Return zero for an empty list.")
            await (await controller.answer(mission.id, ClarificationAnswerRequest(question_id=question.id, answer=answer)))
            current = await db.get_mission(mission.id)
        if scenario.name == "security" and mode == "live" and current.status == MissionStatus.READY_FOR_AUTHORIZATION:
            await audit_security_baseline(controller, mission)
        if current.status == MissionStatus.READY_FOR_AUTHORIZATION:
            await (await controller.start(mission.id, "execute", current.scope_version))
        current = await db.get_mission(mission.id)
        candidates = await controller.store.records(Candidate, mission.id)
        evidence = await controller.store.records(Evidence, mission.id)
        findings = await controller.store.records(Finding, mission.id)
        messages = await controller.store.records(AgentMessage, mission.id)
        questions = await controller.store.records(Clarification, mission.id)
        unchanged = original_bytes == {path.relative_to(source_dir).as_posix(): path.read_bytes() for path in source_dir.rglob("*") if path.is_file()}
        report = serialize_report(scenario, mode, current, executor.calls if mode == "controlled" else [], candidates,
                                  evidence, findings, messages, questions, model.calls if model else [], unchanged)
        assert len(report["candidate_chain"]) <= 5
        if mode == "controlled":
            passed = current.status == MissionStatus.VERIFYING and current.budgets.repair_rounds_used == scenario.repairs
            passed &= unchanged and bool(candidates) and all(e.metadata.get("controlled_evaluation") for e in evidence if e.metadata.get("check_profile"))
            passed &= all(f.status == FindingStatus.RESOLVED for f in findings if f.candidate_id != current.active_candidate_id and f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING})
            if scenario.clarification:
                passed &= len(questions) == 1 and questions[0].status == "ANSWERED"
            if scenario.name == "security":
                passed &= any(f.source_agent == "SHADOW_COUNCIL" and f.severity == FindingSeverity.BLOCKING for f in findings)
            if scenario.name == "recovery":
                passed &= any(e.metadata.get("classification") == "BASELINE_DEFECT" for e in evidence)
            if scenario.name == "bug":
                passed &= any(e.metadata.get("classification") == "BASELINE_DEFECT" for e in evidence)
            final_candidate = next((c for c in candidates if c.id == current.active_candidate_id), None)
            if final_candidate:
                source = (controller.workspaces.get_candidate_dir(mission.id, final_candidate.id) / scenario.file).read_text(encoding="utf-8")
                passed &= scenario.final in source
            else:
                passed = False
        else:
            current_checks = [e for e in evidence if e.candidate_id == current.active_candidate_id and e.metadata.get("check_profile")]
            passed = (current.status == MissionStatus.VERIFYING and unchanged and bool(current_checks)
                      and all(e.exit_code == 0 and e.metadata.get("classification") == "PASS"
                              and not e.metadata.get("controlled_evaluation") for e in current_checks))
            if scenario.name in {"bug", "recovery"}:
                passed &= any(e.metadata.get("classification") == "BASELINE_DEFECT" for e in evidence)
            if scenario.name == "security":
                passed &= any(f.source_agent == "SHADOW_COUNCIL" and f.severity == FindingSeverity.BLOCKING
                              and f.status == FindingStatus.RESOLVED for f in findings)
            if scenario.clarification:
                passed &= len(questions) >= 1 and all(q.status == "ANSWERED" for q in questions)
        report["exit_check_passed"] = bool(passed)
        report["evidence_scope"] = "Scripted model and source-level oracle; checks were NOT executed" if mode == "controlled" else "Real model with restricted Docker checks"
        target = run_dir / f"{scenario.name}.json"
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        await controller.close()
        repo_service._repositories.pop(repo["repository_id"], None)


async def audit_security_baseline(controller, mission):
    """Real Shadow Council pre-implementation review of the planted shell flaw."""
    context = await controller.store.context(mission.id)
    baseline = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == context["baseline_candidate_id"])
    directory = controller.workspaces.get_candidate_dir(mission.id, baseline.id)
    evidence = [e for e in await controller.store.records(Evidence, mission.id) if e.candidate_id == baseline.id]
    async with ModelAdapter() as adapter:
        review = await ShadowCouncilRunner(adapter, controller.workspaces).run(
            mission.id, directory,
            {"request": "Pre-implementation security audit: inspect the EXISTING source for the planted unsanitized os.system(command) flaw. "
                        "This baseline has no diff yet; cite the baseline check evidence and report a BLOCKING finding if you confirm it.",
             "criteria": context["plan"]["criteria"], "changed_files": [],
             "evidence": [controller._evidence_context(e) for e in evidence], "prior_findings": []},
            baseline=controller.workspaces.get_baseline_dir(mission.id),
        )
    controller.workspaces.validate_candidate(baseline)
    findings = [Finding(mission_id=mission.id, candidate_id=baseline.id, source_agent="SHADOW_COUNCIL", **item.model_dump())
                for item in review.proposal.findings]
    if not findings:
        return
    async with controller.store.transaction() as connection:
        for finding in findings:
            if not finding.evidence_ids or not set(finding.evidence_ids) <= {e.id for e in evidence}:
                raise ValueError("Baseline reviewer cited missing evidence")
            await controller.store._save(connection, finding)
            for recipient in ("SHOGUN", "SAMURAI"):
                await controller.store._save(connection, AgentMessage(
                    mission_id=mission.id, sender="SHADOW_COUNCIL", recipient=recipient, type=MessageType.FINDING,
                    candidate_id=baseline.id, summary=finding.title, evidence_ids=finding.evidence_ids,
                    payload={"finding_id": finding.id, "pre_implementation_audit": True},
                ))
        await controller.store._event(connection, mission.id, "BASELINE_SECURITY_REVIEWED", baseline.id)


async def main(mode, names=None):
    run_dir = RESULTS / f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    run_dir.mkdir(parents=True)
    selected = [scenario for scenario in SCENARIOS if not names or scenario.name in names]
    if mode == "live" and not await ContainerExecutor().available():
        reports = []
        for scenario in selected:
            report = {"scenario": scenario.name, "mode": mode, "status": "BLOCKED", "exit_check_passed": False,
                      "reason": "Docker Desktop Linux engine is unavailable; no model or repository checks were run"}
            (run_dir / f"{scenario.name}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            reports.append(report)
    else:
        reports = []
        for scenario in selected:
            try:
                reports.append(await evaluate_one(scenario, mode, run_dir))
            except Exception as exc:
                report = {"scenario": scenario.name, "mode": mode, "status": "ERROR", "exit_check_passed": False,
                          "error_type": type(exc).__name__}
                (run_dir / f"{scenario.name}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                reports.append(report)
    summary = {"mode": mode, "all_passed": all(item["exit_check_passed"] for item in reports),
               "scenarios": [{"name": item["scenario"], "status": item["status"], "passed": item["exit_check_passed"]} for item in reports]}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Results:", run_dir)
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["controlled", "live"], required=True)
    parser.add_argument("--scenario", choices=[scenario.name for scenario in SCENARIOS], action="append",
                        help="Run selected scenarios only (default: all five).")
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(arguments.mode, arguments.scenario)))
