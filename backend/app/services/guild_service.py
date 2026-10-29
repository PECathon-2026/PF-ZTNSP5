"""Durable guild coordination with bounded adaptive repair and safe clarification checkpoints."""

import asyncio
import json
from datetime import datetime, timezone

from app.agents.guild import ShogunRunner, ShadowCouncilRunner, SentinelRunner, RepairPlanner
from app.agents.model_adapter import ModelAdapter
from app.agents.samurai import SamuraiConfig, SamuraiRunner
from app.schemas.agent_message import AgentMessage, MessageType
from app.schemas.candidate import Candidate, CandidateState
from app.schemas.evidence import Evidence, EvidenceKind
from app.schemas.finding import Finding, FindingSeverity, FindingStatus
from app.schemas.guild import GuildPlan, Clarification, ClarificationProposal
from app.schemas.mission import AcceptanceCriterion, MissionStatus, ClarificationAnswerRequest
from app.schemas.task import MissionTask, TaskStatus
from app.services.execution_service import ContainerExecutor
from app.services.repository_service import get_repository_service
from app.services.workspace_service import get_workspace_service
from app.storage.artifacts import get_artifact_storage
from app.storage.database import get_database
from app.storage.guild import GuildConflict, GuildStore
from app.services.budgets import BudgetMeter, BudgetedAdapter, BudgetExceeded
from app.settings import get_settings
from app.security.paths import PathSecurityError
from app.services.criterion_checks import criterion_profile, planned_selectors, verification_contract_hash
from app.services.repo_map import repository_map
from app.services.challenge import challenge_candidate
from app.services.activity import safe_label


class GuildController:
    def __init__(self, database=None, workspaces=None, artifacts=None, executor=None, adapter_factory=None, auto_repair=True):
        self.db = database or get_database()
        self.store = GuildStore(self.db)
        self.workspaces = workspaces or get_workspace_service()
        self.artifacts = artifacts or get_artifact_storage()
        self.executor = executor or ContainerExecutor()
        self.adapter_factory = adapter_factory or ModelAdapter
        self.auto_repair = auto_repair
        self.jobs: dict[str, asyncio.Task] = {}

    def _activity(self, mission_id, role, task_id=None, candidate_id=None):
        async def record(payload, actual_candidate_id=None, evidence_ids=None):
            allowed = {"stage", "action", "summary", "relative_path", "check_profile",
                       "test_selector", "criterion_id", "candidate_fingerprint", "finding_count", "task_count"}
            display = {key: safe_label(value, 360) if isinstance(value, str) else value
                       for key, value in payload.items() if key in allowed and value is not None}
            await self.db.emit_event(mission_id, "AGENT_ACTIVITY", role, display,
                                     task_id=task_id, candidate_id=actual_candidate_id or candidate_id,
                                     evidence_ids=evidence_ids or [])
        return record

    async def start(self, mission_id, phase, scope_version=None, auto_repair=None):
        if phase not in {"plan", "execute"}:
            raise ValueError("Unknown guild phase")
        token = await self.store.claim(mission_id, phase, scope_version, self.auto_repair if auto_repair is None else auto_repair)
        job = asyncio.create_task(self._guarded(mission_id, token, phase))
        self.jobs[mission_id] = job
        return job

    async def _guarded(self, mission_id, token, phase):
        meter = None
        try:
            mission = await self.db.get_mission(mission_id)
            meter = BudgetMeter(mission, self.store, token)
            remaining = mission.budgets.max_time_seconds - mission.budgets.time_used_seconds
            if remaining <= 0:
                raise BudgetExceeded("Mission active-time budget exhausted")
            async with asyncio.timeout(remaining):
                if phase in {"plan", "resume_plan"}:
                    await self._plan(mission, token, meter, resume=phase == "resume_plan")
                else:
                    await self._execute(mission, token, meter, resume_repair=phase == "resume_repair")
        except asyncio.CancelledError:
            await self._stop(mission_id, token, MissionStatus.INTERRUPTED, "Backend operation interrupted")
        except TimeoutError:
            await self._stop(mission_id, token, MissionStatus.BUDGET_EXHAUSTED, "Guild elapsed-time budget exhausted")
        except BudgetExceeded as exc:
            await self._stop(mission_id, token, MissionStatus.BUDGET_EXHAUSTED, str(exc))
        except GuildConflict:
            # A cancellation makes this write a no-op; other conflicts must stop visibly.
            await self._stop(mission_id, token, MissionStatus.BLOCKED, "Guild state or evidence binding conflict")
        except Exception as exc:
            def exhausted(error):
                return isinstance(error, (BudgetExceeded, TimeoutError)) or any(exhausted(child) for child in getattr(error, "exceptions", []))
            origin = exc.__traceback__
            while origin and origin.tb_next:
                origin = origin.tb_next
            location = f" in {origin.tb_frame.f_code.co_name}" if origin else ""
            await self._stop(mission_id, token, MissionStatus.BUDGET_EXHAUSTED if exhausted(exc) else MissionStatus.BLOCKED,
                             "Guild execution budget exhausted" if exhausted(exc) else f"Guild operation stopped ({type(exc).__name__}{location}); inspect configuration and evidence")
        finally:
            if meter:
                try:
                    await meter.flush()
                except GuildConflict:
                    pass
            await self.store.release(mission_id, token)
            if self.jobs.get(mission_id) is asyncio.current_task():
                self.jobs.pop(mission_id, None)

    async def _stop(self, mission_id, token, status, reason):
        tasks = await self.db.get_tasks(mission_id)
        for task in tasks:
            if task.status == TaskStatus.RUNNING or (status == MissionStatus.BUDGET_EXHAUSTED and task.status in {TaskStatus.PENDING, TaskStatus.READY}):
                task.status = TaskStatus.BLOCKED
                task.result_summary = reason
        try:
            await self.store.commit(mission_id, token, status=status, entities=tasks, failure_reason=reason, event="GUILD_STOPPED")
            await self._activity(mission_id, "CONTROLLER")({"stage": "outcome", "action": "stop",
                "summary": f"Mission stopped ({status.value}): {safe_label(reason, 200)}."})
        except GuildConflict:
            pass

    async def cancel(self, mission_id):
        await self.store.request_cancel(mission_id)
        job = self.jobs.get(mission_id)
        if job:
            job.cancel()
            await job
        await self.store.finish_cancel(mission_id)

    async def close(self):
        jobs = list(self.jobs.values())
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)

    async def answer(self, mission_id, request: ClarificationAnswerRequest):
        mission = await self.db.get_mission(mission_id)
        if not mission:
            raise KeyError("Mission not found")
        if mission.status != MissionStatus.AWAITING_CLARIFICATION:
            raise GuildConflict("Mission is not awaiting clarification")
        question = next((q for q in await self.store.records(Clarification, mission_id) if q.id == request.question_id), None)
        if not question:
            raise KeyError("Clarification not found")
        if question.status != "OPEN":
            raise GuildConflict("Clarification is already answered")
        candidate = next((c for c in await self.store.records(Candidate, mission_id) if c.id == question.candidate_id), None)
        if not candidate:
            raise GuildConflict("Clarification snapshot is missing")
        self._validate_checkpoint(mission_id, candidate)
        token, phase = await self.store.answer_and_claim(mission_id, request.question_id, request.answer)
        job = asyncio.create_task(self._guarded(mission_id, token, phase))
        self.jobs[mission_id] = job
        return job

    def _validate_checkpoint(self, mission_id, candidate):
        try:
            self.workspaces.validate_candidate(candidate)
            actual = self.workspaces._compute_dir_hash(self.workspaces.get_mission_workspace_dir(mission_id))[0]
            if actual != candidate.content_fingerprint:
                raise ValueError("Mutable workspace changed")
        except (ValueError, OSError, PathSecurityError):
            raise GuildConflict("Clarification/repair snapshot or workspace changed; it cannot be replayed") from None

    async def _answers(self, mission_id):
        return [{"question": q.question, "answer": q.answer} for q in await self.store.records(Clarification, mission_id) if q.status == "ANSWERED"]

    async def _pause(self, mission, token, meter, proposal, candidate, phase):
        if mission.budgets.clarifications_used >= mission.budgets.max_clarifications:
            raise BudgetExceeded("Mission clarification budget exhausted")
        self._validate_checkpoint(mission.id, candidate)
        mission.budgets.clarifications_used += 1
        await meter.flush()
        question = Clarification(mission_id=mission.id, question=proposal.question, reason=proposal.reason, phase=phase,
                                 candidate_id=candidate.id, candidate_fingerprint=candidate.content_fingerprint, scope_version=mission.scope_version)
        context = await self.store.context(mission.id)
        tasks = [t for t in await self.db.get_tasks(mission.id) if t.id in context.get("task_ids", [])]
        context["paused_tasks"] = {t.id: t.status.value for t in tasks if t.status not in {TaskStatus.DONE, TaskStatus.CANCELLED}}
        for task in tasks:
            if task.id in context["paused_tasks"]:
                task.status = TaskStatus.BLOCKED
        context["pending_question_id"] = question.id
        message = AgentMessage(mission_id=mission.id, candidate_id=candidate.id, sender="SHOGUN", recipient="USER",
                               type=MessageType.CLARIFICATION, summary=question.question,
                               payload={"question_id": question.id, "reason": question.reason, "phase": phase})
        await self.store.commit(mission.id, token, status=MissionStatus.AWAITING_CLARIFICATION,
                                entities=[question, message, *tasks], context=context, budgets=mission.budgets,
                                event="CLARIFICATION_REQUESTED")

    def _restore(self, context):
        repo = context["repository"]
        get_repository_service()._repositories.setdefault(repo["repository_id"], repo)

    async def _plan(self, mission, token, meter, resume=False):
        if resume:
            context = await self.store.context(mission.id)
            self._restore(context)
            baseline = next(c for c in await self.store.records(Candidate, mission.id) if c.id == context["baseline_candidate_id"])
            self._validate_checkpoint(mission.id, baseline)
            baseline_evidence = [e for e in await self.store.records(Evidence, mission.id) if e.candidate_id == baseline.id]
        else:
            repo = get_repository_service().get_repository(mission.repository_id)
            if not repo:
                raise ValueError("Connect the repository before planning")
            self.workspaces.create_disposable_workspace(mission.id, mission.repository_id)
            baseline = self.workspaces.freeze_candidate(mission.id, mission.repository_id)
            context = {
                "repository": {key: repo[key] for key in ("repository_id", "name", "path", "included_files", "fingerprint")},
                "baseline_candidate_id": baseline.id,
            }
            await self.store.commit(mission.id, token, entities=[baseline], context=context, event="BASELINE_FROZEN")
            profiles = ["python_pytest", "python_bandit"] if isinstance(self.executor, ContainerExecutor) else ["python_pytest"]
            sentinel = await SentinelRunner(self.executor, self.workspaces, self.artifacts, meter.before_tool,
                                            self._activity(mission.id, "SENTINEL", candidate_id=baseline.id)).run(baseline, profiles, baseline=True)
            await self.store.commit(mission.id, token, entities=[*sentinel.evidence, *sentinel.findings], event="BASELINE_CHECKED")
            for evidence in sentinel.evidence:
                await self._check_activity(mission.id, evidence)
            if sentinel.blocked:
                await self._stop(mission.id, token, MissionStatus.BLOCKED, "Baseline checks unavailable; start Docker Desktop and prepare the check image")
                return
            baseline_evidence = sentinel.evidence
        criteria = await self.db.get_criteria(mission.id)
        planner_context = {
            "request": mission.request_text, "criteria": [c.model_dump(mode="json") for c in criteria],
            "baseline_checks": [self._evidence_context(e) for e in baseline_evidence],
            "clarification_answers": await self._answers(mission.id),
            "repository_map": repository_map(self.workspaces.get_baseline_dir(mission.id)),
        }
        await self.store.commit(mission.id, token, status=MissionStatus.PLANNING, event="SHOGUN_STARTED")
        async with self.adapter_factory() as raw_adapter:
            result = await ShogunRunner(BudgetedAdapter(raw_adapter, meter), self.workspaces, meter.before_tool,
                                        self._activity(mission.id, "SHOGUN")).run(
                mission.id, self.workspaces.get_baseline_dir(mission.id), planner_context,
                max_turns=min(12, mission.budgets.max_model_turns), max_tools=mission.budgets.max_tool_calls,
            )
        plan = result.proposal
        if isinstance(plan, ClarificationProposal):
            await self._pause(mission, token, meter, plan, baseline, "plan")
            return
        existing = {criterion.description: criterion for criterion in criteria}
        planned_criteria = []
        for item in plan.criteria:
            criterion = existing.get(item.description) or AcceptanceCriterion(mission_id=mission.id, description=item.description)
            selectors = planned_selectors(item)
            criterion.verification_method = f"test_profile:{item.check_profile}" + ("|" + json.dumps(selectors) if selectors else "")
            planned_criteria.append(criterion)
        tasks = {item.key: MissionTask(mission_id=mission.id, title=item.title, description=item.description, owner_agent="SAMURAI") for item in plan.tasks}
        for item in plan.tasks:
            task = tasks[item.key]
            task.dependencies = [tasks[key].id for key in item.dependencies]
            task.status = TaskStatus.PENDING if task.dependencies else TaskStatus.READY
        dependencies = [task.id for task in tasks.values()]
        guild_tasks = list(tasks.values()) + [
            MissionTask(mission_id=mission.id, title="Check frozen candidate", description="Run required check profiles", owner_agent="SENTINEL", dependencies=dependencies),
            MissionTask(mission_id=mission.id, title="Review frozen candidate", description="Inspect candidate source and diffs", owner_agent="SHADOW_COUNCIL", dependencies=dependencies),
        ]
        context["plan"] = plan.model_dump(mode="json")
        context["plan_revision"] = 1
        context["task_ids"] = [t.id for t in guild_tasks]
        context["approved_criteria"] = context["plan"]["criteria"]
        context["plan_history"] = [{"revision": 1, "task_ids": context["task_ids"], "summary": plan.summary}]
        message = AgentMessage(mission_id=mission.id, sender="SHOGUN", recipient="CONTROLLER", type=MessageType.TASK_PROPOSAL,
                               summary=plan.summary, payload={"task_ids": [t.id for t in guild_tasks], "scope_version": mission.scope_version})
        missing_tests = [c.description for c in plan.criteria if c.check_profile == "python_pytest" and not planned_selectors(c)]
        if missing_tests and isinstance(self.executor, ContainerExecutor):
            context["test_gaps"] = missing_tests
            context["test_gap_proposals"] = [gap.model_dump(mode="json") for gap in plan.test_gaps
                                             if gap.criterion_description in missing_tests]
            for task in guild_tasks:
                task.status = TaskStatus.BLOCKED
            blocker = AgentMessage(mission_id=mission.id, sender="SHOGUN", recipient="USER", type=MessageType.BLOCKER,
                                   summary="Acceptance tests are missing; review/add tests to the original repository and start a new mission.",
                                   candidate_id=baseline.id, payload={"unmapped_criteria": missing_tests})
            await self.store.commit(mission.id, token, status=MissionStatus.BLOCKED,
                                    failure_reason="Acceptance tests missing for: " + "; ".join(missing_tests)[:350],
                                    entities=[*planned_criteria, *guild_tasks, message, blocker], context=context,
                                    budgets=mission.budgets, event="TEST_GAP_BLOCKED")
            return
        await self.store.commit(mission.id, token, status=MissionStatus.READY_FOR_AUTHORIZATION,
                                entities=[*planned_criteria, *guild_tasks, message], context=context,
                                budgets=mission.budgets, event="PLAN_READY")
        await self._activity(mission.id, "SHOGUN")({"stage": "proposal", "action": "submit_plan",
            "summary": f"Shogun proposed {len(plan.tasks)} implementation tasks and {len(plan.criteria)} acceptance checks; awaiting user authorization.",
            "task_count": len(plan.tasks)})

    def _evidence_context(self, evidence):
        data = evidence.model_dump(mode="json")
        for stream in ("stdout", "stderr"):
            artifact_id = getattr(evidence, stream + "_artifact_id")
            data[stream] = (self.artifacts.read_artifact(evidence.mission_id, artifact_id) or "")[:12000] if artifact_id else ""
        return data

    async def _execute(self, mission, token, meter, resume_repair=False):
        context = await self.store.context(mission.id)
        if not context or "plan" not in context:
            raise GuildConflict("No durable plan exists")
        # Upgrade already-authorized M4 plans without rebuilding their workspaces.
        if "task_ids" not in context:
            context["task_ids"] = [t.id for t in await self.db.get_tasks(mission.id) if t.status != TaskStatus.CANCELLED]
            context["plan_revision"] = 1
            context["approved_criteria"] = context["plan"]["criteria"]
            context["plan_history"] = [{"revision": 1, "task_ids": context["task_ids"], "summary": context["plan"]["summary"]}]
            await self.store.commit(mission.id, token, context=context)
        if "challenge_enabled" not in context:
            context["challenge_enabled"] = isinstance(self.executor, ContainerExecutor)
            await self.store.commit(mission.id, token, context=context)
        self._restore(context)
        candidates = await self.store.records(Candidate, mission.id)
        parent_id = mission.active_candidate_id if resume_repair else context["baseline_candidate_id"]
        parent = next(c for c in candidates if c.id == parent_id)
        self._validate_checkpoint(mission.id, parent)
        if not resume_repair:
            authorization = AgentMessage(mission_id=mission.id, sender="USER", recipient="CONTROLLER", type=MessageType.HANDOFF,
                                         summary="User authorized bounded disposable-workspace execution",
                                         payload={"scope_version": mission.scope_version, "auto_repair": context.get("auto_repair", True)})
            await self.store.commit(mission.id, token, entities=[authorization], event="PLAN_AUTHORIZED")
        async with self.adapter_factory() as raw_adapter:
            adapter = BudgetedAdapter(raw_adapter, meter)
            replan = resume_repair
            while True:
                if replan:
                    if not await self._replan(mission, token, meter, adapter, parent):
                        return
                    context = await self.store.context(mission.id)
                parent = await self._run_pass(mission, token, context, parent, adapter, meter)
                if parent is None:
                    return
                current = await self.db.get_mission(mission.id)
                if current.status != MissionStatus.REPAIRING or not context.get("auto_repair", True):
                    return
                replan = True

    async def _replan(self, mission, token, meter, adapter, candidate):
        self._validate_checkpoint(mission.id, candidate)
        context = await self.store.context(mission.id)
        pending = context.get("repair_round", {})
        if pending.get("pending"):
            if pending.get("candidate_id") != candidate.id:
                raise GuildConflict("Repair checkpoint is stale")
        else:
            cap = min(3, mission.budgets.max_repair_rounds, get_settings().max_repair_rounds)
            if mission.budgets.repair_rounds_used >= cap:
                raise BudgetExceeded("Repair round limit reached; no further edits are authorized")
            mission.budgets.repair_rounds_used += 1
            context["repair_round"] = {"number": mission.budgets.repair_rounds_used, "candidate_id": candidate.id, "pending": True}
            await self.store.commit(mission.id, token, status=MissionStatus.REPAIRING, context=context,
                                    budgets=mission.budgets, event="REPAIR_ROUND_STARTED")
        findings = [f for f in await self.store.records(Finding, mission.id)
                    if f.candidate_id == candidate.id and f.status != FindingStatus.RESOLVED
                    and f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING}]
        if not findings:
            raise GuildConflict("No current blocking findings justify a repair")
        evidence = [e for e in await self.store.records(Evidence, mission.id) if e.candidate_id == candidate.id]
        result = await RepairPlanner(adapter, self.workspaces, meter.before_tool,
                                     self._activity(mission.id, "SHOGUN", candidate_id=candidate.id)).run(
            mission.id, self.workspaces.get_candidate_dir(mission.id, candidate.id),
            {"request": mission.request_text, "criteria": context["approved_criteria"],
             "findings": [f.model_dump(mode="json") for f in findings],
             "evidence": [self._evidence_context(e) for e in evidence], "previous_plan": context["plan"],
             "clarification_answers": await self._answers(mission.id)},
        )
        if isinstance(result.proposal, ClarificationProposal):
            await self._pause(mission, token, meter, result.proposal, candidate, "repair")
            return False
        proposal = result.proposal
        old_tasks = [t for t in await self.db.get_tasks(mission.id) if t.id in context["task_ids"]]
        for task in old_tasks:
            task.status = TaskStatus.CANCELLED
            task.result_summary = "Superseded by evidence-driven repair plan"
        new_tasks = {item.key: MissionTask(mission_id=mission.id, owner_agent="SAMURAI", title=item.title,
                                          description=item.description, attempt=mission.budgets.repair_rounds_used + 1)
                     for item in proposal.tasks}
        for item in proposal.tasks:
            task = new_tasks[item.key]
            task.dependencies = [new_tasks[key].id for key in item.dependencies]
            task.status = TaskStatus.PENDING if task.dependencies else TaskStatus.READY
        dependencies = [t.id for t in new_tasks.values()]
        tasks = list(new_tasks.values()) + [
            MissionTask(mission_id=mission.id, title="Recheck repaired candidate", description="Run all approved checks again", owner_agent="SENTINEL", dependencies=dependencies),
            MissionTask(mission_id=mission.id, title="Re-review repaired candidate", description="Review new diff and prior findings", owner_agent="SHADOW_COUNCIL", dependencies=dependencies),
        ]
        context["plan"] = proposal.model_dump(mode="json")
        context["plan_revision"] += 1
        context["task_ids"] = [t.id for t in tasks]
        context["repair_round"]["pending"] = False
        context.pop("paused_tasks", None)
        context["plan_history"].append({"revision": context["plan_revision"], "task_ids": context["task_ids"],
                                        "summary": proposal.summary, "finding_ids": proposal.finding_ids, "candidate_id": candidate.id})
        for finding in findings:
            finding.status = FindingStatus.IN_PROGRESS
        message = AgentMessage(mission_id=mission.id, sender="SHOGUN", recipient="SAMURAI", type=MessageType.TASK_PROPOSAL,
                               candidate_id=candidate.id, summary=proposal.summary,
                               evidence_ids=sorted({e for f in findings for e in f.evidence_ids}),
                               payload={"plan_revision": context["plan_revision"], "finding_ids": proposal.finding_ids, "task_ids": context["task_ids"]})
        await self.store.commit(mission.id, token, status=MissionStatus.RUNNING, entities=[*old_tasks, *tasks, *findings, message],
                                context=context, event="PLAN_REVISED")
        await self._activity(mission.id, "SHOGUN", candidate_id=candidate.id)({"stage": "proposal", "action": "revise_plan",
            "summary": f"Shogun revised the task plan for {len(findings)} recorded findings; Samurai will work from this candidate.",
            "finding_count": len(findings), "task_count": len(proposal.tasks)}, evidence_ids=message.evidence_ids)
        return True

    async def _run_pass(self, mission, token, context, parent, adapter, meter):
        tasks = [t for t in await self.db.get_tasks(mission.id) if t.id in context["task_ids"]]
        while any(t.owner_agent == "SAMURAI" and t.status != TaskStatus.DONE for t in tasks):
            done = {t.id for t in tasks if t.status == TaskStatus.DONE}
            ready = [t for t in tasks if t.owner_agent == "SAMURAI" and t.status != TaskStatus.DONE and set(t.dependencies) <= done]
            if not ready:
                raise ValueError("No executable task in the approved DAG")
            task = ready[0]
            remaining_turns = mission.budgets.max_model_turns - mission.budgets.model_turns_used
            remaining_tools = mission.budgets.max_tool_calls - mission.budgets.tool_calls_used
            if min(remaining_turns, remaining_tools) <= 0:
                raise BudgetExceeded("Guild model/tool budget exhausted")
            task.status = TaskStatus.RUNNING
            await self.store.commit(mission.id, token, entities=[task], event="SAMURAI_STARTED")
            activity = self._activity(mission.id, "SAMURAI", task_id=task.id)
            await activity({"stage": "intent", "action": "implement_task",
                            "summary": f"Samurai is starting task: {safe_label(task.title, 140)}. Changes remain in a disposable workspace."})
            repair_findings = [f for f in await self.store.records(Finding, mission.id) if f.id in context["plan"].get("finding_ids", [])]
            request = json.dumps({"request": mission.request_text, "task": task.description, "criteria": context["plan"]["criteria"],
                                  "findings": [f.model_dump(mode="json") for f in repair_findings],
                                  "clarification_answers": await self._answers(mission.id)})
            result = await SamuraiRunner(adapter, workspace_service=self.workspaces, before_tool=meter.before_tool,
                                         on_activity=activity, config=SamuraiConfig(
                max_turns=min(20, remaining_turns), max_tool_calls=min(50, remaining_tools),
            )).run(mission.repository_id, request, mission_id=mission.id, prepared_workspace=True, parent_candidate=parent)
            if not result.candidate:
                await self._stop(mission.id, token, MissionStatus.BUDGET_EXHAUSTED if result.status == "BUDGET_EXHAUSTED" else MissionStatus.BLOCKED, result.summary)
                return None
            candidate = result.candidate
            if context["plan"].get("finding_ids") and any(
                previous.content_fingerprint == candidate.content_fingerprint
                for previous in await self.store.records(Candidate, mission.id)
            ):
                await self._stop(mission.id, token, MissionStatus.BLOCKED,
                                 "Repair repeated an existing candidate; unchanged checks were not replayed")
                return None
            candidate.criteria_version = mission.scope_version
            evidence = self._diff_evidence(candidate, mission.repository_id)
            task.status = TaskStatus.DONE
            task.candidate_id = candidate.id
            task.evidence_ids = [evidence.id]
            task.result_summary = result.summary
            task.updated_at = datetime.now(timezone.utc)
            entities = [candidate, evidence, task]
            if parent.id != context["baseline_candidate_id"]:
                parent.state = CandidateState.SUPERSEDED
                entities.append(parent)
            for recipient in ("SENTINEL", "SHADOW_COUNCIL"):
                entities.append(AgentMessage(mission_id=mission.id, sender="SAMURAI", recipient=recipient, type=MessageType.HANDOFF,
                                             task_id=task.id, candidate_id=candidate.id, summary="Candidate frozen for checks and review", evidence_ids=[evidence.id]))
            await self.store.commit(mission.id, token, entities=entities, candidate_id=candidate.id, event="CANDIDATE_FROZEN")
            await activity({"stage": "handoff", "action": "freeze_candidate",
                            "summary": f"Samurai handed off {len(candidate.changed_files)} changed files for checks and review; correctness is not yet verified.",
                            "candidate_fingerprint": candidate.content_fingerprint}, candidate.id, [evidence.id])
            parent = candidate
        check_task = next(t for t in tasks if t.owner_agent == "SENTINEL")
        review_task = next(t for t in tasks if t.owner_agent == "SHADOW_COUNCIL")
        for task in (check_task, review_task):
            task.status = TaskStatus.RUNNING
            task.candidate_id = parent.id
        await self.store.commit(mission.id, token, status=MissionStatus.CHECKING, entities=[check_task, review_task], event="CHECK_AND_REVIEW_STARTED")
        check_result = await self._check(mission, token, parent, check_task, context, meter)
        # Reviewer receives persisted test, security and challenge evidence so a
        # survived variant can influence its critique of this exact candidate.
        await self._review(mission, token, parent, review_task, adapter, context, meter)
        await self.route_findings(mission.id, token, parent, blocked=check_result.blocked)
        return parent

    def _diff_evidence(self, candidate, repository_id):
        diff = self.workspaces.generate_candidate_diff(candidate.mission_id, repository_id, candidate.id)
        artifact_id, _ = self.artifacts.save_artifact(candidate.mission_id, "candidate.diff", diff["unified_diff"])
        return Evidence(mission_id=candidate.mission_id, candidate_id=candidate.id, fingerprint=candidate.content_fingerprint,
                        kind=EvidenceKind.DIFF, source="SAMURAI", stdout_artifact_id=artifact_id,
                        metadata={"changed_files": candidate.changed_files})

    async def _check(self, mission, token, candidate, task, context, meter):
        criteria = await self.db.get_criteria(mission.id)
        profiles = {criterion_profile(item)[0] for item in criteria}
        if isinstance(self.executor, ContainerExecutor):
            profiles.add("python_bandit")
        result = await SentinelRunner(self.executor, self.workspaces, self.artifacts, meter.before_tool,
                                      self._activity(mission.id, "SENTINEL", task_id=task.id, candidate_id=candidate.id)).run(
            candidate, profiles, criteria=criteria,
            contract_hash=verification_contract_hash(self.workspaces.get_candidate_dir(mission.id, candidate.id), criteria))
        if context.get("challenge_enabled") and not result.blocked and not any(
                f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING} for f in result.findings) and all(
                e.metadata.get("classification") in {"PASS", "STATIC_SCAN"} for e in result.evidence):
            challenge, challenge_findings = await challenge_candidate(
                candidate, self.workspaces.get_baseline_dir(mission.id),
                self.workspaces.get_candidate_dir(mission.id, candidate.id), self.executor, self.artifacts,
                before_tool=meter.before_tool)
            self.workspaces.validate_candidate(candidate)
            result.evidence.append(challenge)
            result.findings.extend(challenge_findings)
            if challenge.metadata["status"] == "INCONCLUSIVE":
                result.blocked = True
                result.findings.append(Finding(
                    mission_id=mission.id, candidate_id=candidate.id, source_agent="SENTINEL",
                    severity=FindingSeverity.BLOCKING, title="Challenge execution inconclusive",
                    description="The candidate challenge could not be completed in its restricted container.",
                    observed_behavior="At least one variant has no valid test outcome.",
                    expected_behavior="A bounded challenge completes or explicitly reports not applicable.",
                    evidence_ids=[challenge.id]))
        task.status = TaskStatus.BLOCKED if result.blocked else (TaskStatus.FAILED if any(
            f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING} for f in result.findings) else TaskStatus.DONE)
        task.evidence_ids = [e.id for e in result.evidence]
        task.result_summary = "Required checks recorded against frozen candidate"
        prior_evidence = {e.id: e for e in await self.store.records(Evidence, mission.id)}
        passed = {(e.metadata["check_profile"], e.metadata.get("test_selector")): e for e in result.evidence if e.metadata.get("classification") == "PASS"}
        scan = next((e for e in result.evidence if e.metadata.get("check_profile") == "python_bandit"
                     and e.metadata.get("classification") == "STATIC_SCAN"), None)
        active_issues = {(item.get("test_id"), str(item.get("filename", "")).removeprefix("./").removeprefix("/workspace/"))
                         for item in (scan.metadata["report"]["results"] if scan else [])}
        resolved = []
        for finding in await self.store.records(Finding, mission.id):
            if finding.source_agent != "SENTINEL" or finding.candidate_id == candidate.id or finding.status == FindingStatus.RESOLVED:
                continue
            if scan and finding.title.startswith("Bandit "):
                old_key = (finding.title.split(":", 1)[0].removeprefix("Bandit "), finding.file_path)
                if old_key not in active_issues:
                    finding.status = FindingStatus.RESOLVED
                    finding.resolution_evidence_ids = [scan.id]
                    resolved.append(finding)
                continue
            profiles_for_finding = [(prior_evidence[e].metadata.get("check_profile"), prior_evidence[e].metadata.get("test_selector")) for e in finding.evidence_ids if e in prior_evidence]
            if profiles_for_finding and all(profile in passed for profile in profiles_for_finding):
                finding.status = FindingStatus.RESOLVED
                finding.resolution_evidence_ids = [passed[profile].id for profile in profiles_for_finding]
                resolved.append(finding)
        await self.store.commit(mission.id, token, entities=[*result.evidence, *result.findings, *resolved, task], event="SENTINEL_FINISHED")
        for evidence in result.evidence:
            if evidence.kind == EvidenceKind.MUTATION:
                await self._activity(mission.id, "SENTINEL", task_id=task.id, candidate_id=candidate.id)({
                    "stage": "outcome", "action": "challenge_candidate",
                    "summary": f"Sentinel challenged {len(evidence.metadata['attempts'])} isolated variants; {sum(a['outcome'] == 'SURVIVED' for a in evidence.metadata['attempts'])} survived, {sum(a['outcome'] == 'DETECTED' for a in evidence.metadata['attempts'])} were detected."
                }, evidence_ids=[evidence.id])
            else:
                await self._check_activity(mission.id, evidence, task.id)
        return result

    async def _check_activity(self, mission_id, evidence, task_id=None):
        classification = evidence.metadata.get("classification", "UNKNOWN")
        mode = "controlled check" if evidence.metadata.get("controlled_evaluation") else "container check"
        verdict = "passed" if classification == "PASS" else "did not pass"
        label = "criterion test" if evidence.criterion_id else "baseline suite" if evidence.kind == EvidenceKind.BASELINE else "full check suite"
        if evidence.kind == EvidenceKind.STATIC_SCAN and classification == "STATIC_SCAN":
            issues = evidence.metadata.get("report", {}).get("results", [])
            summary = (f"Sentinel Bandit scan completed with {len(issues)} security findings (exit {evidence.exit_code}); "
                       "review severity and evidence separately from pytest outcomes.")
        else:
            summary = f"Sentinel {mode} for {label} {verdict} (exit {evidence.exit_code}, {classification}); evidence recorded."
        await self._activity(mission_id, "SENTINEL", task_id=task_id, candidate_id=evidence.candidate_id)({
            "stage": "outcome", "action": "run_check", "check_profile": evidence.metadata.get("check_profile"),
            "test_selector": evidence.metadata.get("test_selector"), "criterion_id": evidence.criterion_id,
            "summary": summary
        }, evidence_ids=[evidence.id])

    async def _review(self, mission, token, candidate, task, adapter, context, meter):
        self.workspaces.validate_candidate(candidate)
        evidence = [e for e in await self.store.records(Evidence, mission.id) if e.candidate_id == candidate.id]
        remaining_turns = mission.budgets.max_model_turns - mission.budgets.model_turns_used
        remaining_tools = mission.budgets.max_tool_calls - mission.budgets.tool_calls_used
        if min(remaining_turns, remaining_tools) <= 0:
            raise BudgetExceeded("Review model/tool budget exhausted")
        prior = [f for f in await self.store.records(Finding, mission.id)
                 if f.source_agent == "SHADOW_COUNCIL" and f.candidate_id != candidate.id and f.status != FindingStatus.RESOLVED]
        result = await ShadowCouncilRunner(adapter, self.workspaces, meter.before_tool,
                                           self._activity(mission.id, "SHADOW_COUNCIL", task_id=task.id, candidate_id=candidate.id)).run(
            mission.id, self.workspaces.get_candidate_dir(mission.id, candidate.id),
            {"request": mission.request_text, "criteria": context["plan"]["criteria"], "changed_files": candidate.changed_files,
             "evidence": [self._evidence_context(e) for e in evidence], "prior_findings": [f.model_dump(mode="json") for f in prior]},
            baseline=self.workspaces.get_baseline_dir(mission.id), max_turns=min(12, remaining_turns), max_tools=remaining_tools,
        )
        self.workspaces.validate_candidate(candidate)
        findings = [Finding(mission_id=mission.id, candidate_id=candidate.id, source_agent="SHADOW_COUNCIL", **f.model_dump()) for f in result.proposal.findings]
        artifact_id, _ = self.artifacts.save_artifact(mission.id, "review.json", result.proposal.model_dump_json())
        review_evidence = Evidence(mission_id=mission.id, candidate_id=candidate.id, fingerprint=candidate.content_fingerprint,
                                   kind=EvidenceKind.REVIEW_FINDING, source="SHADOW_COUNCIL", stdout_artifact_id=artifact_id,
                                   metadata={"resolved_finding_ids": result.proposal.resolved_finding_ids})
        for finding in prior:
            if finding.id in result.proposal.resolved_finding_ids:
                finding.status = FindingStatus.RESOLVED
                finding.resolution_evidence_ids = [review_evidence.id]
            elif finding.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING}:
                findings.append(Finding(
                    mission_id=mission.id, candidate_id=candidate.id, source_agent="SHADOW_COUNCIL", severity=finding.severity,
                    title="Unresolved prior review finding", description=finding.description,
                    observed_behavior="The new review did not provide a resolution for the prior finding.",
                    expected_behavior=finding.expected_behavior, file_path=finding.file_path, evidence_ids=[review_evidence.id],
                ))
        task.status = TaskStatus.FAILED if any(f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING} for f in findings) else TaskStatus.DONE
        task.result_summary = result.proposal.summary
        task.evidence_ids = [e.id for e in evidence] + [review_evidence.id]
        report = AgentMessage(mission_id=mission.id, candidate_id=candidate.id, sender="SHADOW_COUNCIL", recipient="SHOGUN",
                              type=MessageType.TASK_RESULT, task_id=task.id, summary=result.proposal.summary,
                              evidence_ids=task.evidence_ids, payload={"finding_ids": [f.id for f in findings]})
        await self.store.commit(mission.id, token, entities=[review_evidence, *findings, *prior, task, report], event="REVIEW_FINISHED")
        await self._activity(mission.id, "SHADOW_COUNCIL", task_id=task.id, candidate_id=candidate.id)({
            "stage": "outcome", "action": "submit_review", "finding_count": len(findings),
            "summary": f"Shadow Council submitted its candidate review with {len(findings)} findings; this is not human approval."
        }, evidence_ids=[review_evidence.id])

    async def route_findings(self, mission_id, token, candidate, *, blocked=False):
        mission = await self.db.get_mission(mission_id)
        if not mission or candidate.mission_id != mission_id or mission.active_candidate_id != candidate.id:
            raise GuildConflict("Findings must target the mission's active candidate")
        context = await self.store.context(mission_id)
        if candidate.id in context.get("routed_candidates", []):
            return
        findings = [f for f in await self.store.records(Finding, mission_id) if f.candidate_id == candidate.id and f.status != FindingStatus.RESOLVED and f.severity in {FindingSeverity.HIGH, FindingSeverity.BLOCKING}]
        tasks = [t for t in await self.db.get_tasks(mission_id) if t.id in context.get("task_ids", [])]
        developers = [t for t in tasks if t.owner_agent == "SAMURAI"]
        entities = []
        if findings:
            # A failed aggregate check can implicate any implementation task. Reopen
            # conservatively, preserving the DAG, rather than guessing from test text.
            if not blocked:
                for task in developers:
                    task.status = TaskStatus.PENDING if task.dependencies else TaskStatus.READY
                    task.attempt += 1
                    task.result_summary = "Reopened by candidate-bound findings; awaiting Shogun repair planning"
                    task.updated_at = datetime.now(timezone.utc)
                for task in tasks:
                    if task.owner_agent != "SAMURAI":
                        task.status = TaskStatus.BLOCKED
                entities.extend(tasks)
            for finding in findings:
                for recipient in ("SHOGUN", "SAMURAI"):
                    entities.append(AgentMessage(
                        mission_id=mission_id, candidate_id=candidate.id, sender=finding.source_agent, recipient=recipient,
                        type=MessageType.BLOCKER if blocked else MessageType.FINDING,
                        task_id=developers[0].id, summary=finding.title, evidence_ids=finding.evidence_ids,
                        payload={"finding_id": finding.id, "reopened_task_ids": [] if blocked else [t.id for t in developers]},
                    ))
        context.setdefault("routed_candidates", []).append(candidate.id)
        status = MissionStatus.BLOCKED if blocked else MissionStatus.REPAIRING if findings else MissionStatus.VERIFYING
        await self.store.commit(mission_id, token, status=status, entities=entities, context=context,
                                failure_reason="Check environment or timeout requires intervention" if blocked else None,
                                event="FINDINGS_ROUTED" if findings else "READY_FOR_VERIFICATION")
        await self._activity(mission_id, "CONTROLLER", candidate_id=candidate.id)({
            "stage": "outcome", "action": "route_findings", "finding_count": len(findings),
            "summary": (f"Controller routed {len(findings)} blocking findings to Shogun and Samurai for repair."
                        if findings and not blocked else "Controller blocked execution because a check could not run safely."
                        if blocked else "Checks and review completed; the candidate awaits independent verification.")})


_controller = None


def get_guild_controller():
    global _controller
    if _controller is None:
        _controller = GuildController()
    return _controller
