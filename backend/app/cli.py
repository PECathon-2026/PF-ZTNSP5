"""Interactive DevPilot CLI over the same durable guild used by the REST API.

Usage (from backend/): python -m app.cli run --repo PATH --request TEXT --criterion TEXT
No model edits are applied to the original repository without a separate exact
candidate fingerprint approval and apply confirmation.
"""

import argparse
import asyncio
import json
from time import monotonic
from collections.abc import Callable
import aiosqlite
from pydantic import ValidationError

from app.schemas.approval import ApprovalDecision, ApprovalRequest
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.agent_message import AgentMessage
from app.schemas.guild import Clarification
from app.schemas.mission import AcceptanceCriterion, ClarificationAnswerRequest, Mission, MissionBudgets, MissionStatus
from app.schemas.task import MissionTask
from app.schemas.approval import Approval
from app.security.redaction import redact_secrets
from app.services.activity import safe_label
from app.services.approval_service import ApprovalService
from app.services.guild_service import GuildController
from app.services.repository_service import get_repository_service
from app.services.proof_card import proof_card, proof_markdown
from app.storage.database import get_database
from app.storage.guild import GuildConflict


STOPPED = {MissionStatus.BLOCKED, MissionStatus.BUDGET_EXHAUSTED, MissionStatus.FAILED_VERIFICATION,
           MissionStatus.CANCELLED, MissionStatus.REJECTED, MissionStatus.APPLIED, MissionStatus.INTERRUPTED}


def show_event(event) -> str:
    source = event.source.replace("_", " ").title()
    data = event.display_payload
    summary = safe_label(data.get("summary", "") if isinstance(data.get("summary"), str) else "", 360)
    stage = data.get("stage") if data.get("stage") in {"intent", "outcome", "failed", "handoff", "proposal"} else None
    description = summary or safe_label(data.get("title", "") if isinstance(data.get("title"), str) else "", 180) or event.event_type
    return f"[{event.sequence:04d}] {source}{f' / {stage}' if stage else ''}: {description}"


class Console:
    def __init__(self, ask: Callable[[str], str] = input, say: Callable[[str], None] = print):
        self.ask = ask
        self.say = say

    async def prompt(self, text: str) -> str:
        return (await asyncio.to_thread(self.ask, text)).strip()

    def event(self, event):
        self.say(show_event(event))

    def mission_state(self, mission):
        """Display hook; the boxed TUI keeps its sidebar in sync with SQLite."""
        pass

    async def stream(self, db, mission_id: str, job=None, *, after=0, follow=False, timeout=600):
        """Replay committed events, then follow a job without an untracked worker."""
        cursor = after
        deadline = monotonic() + timeout
        while True:
            events = await db.get_events(mission_id, after_sequence=cursor)
            for event in events:
                if event.sequence > cursor:
                    self.event(event)
                    cursor = event.sequence
            if job is not None and job.done():
                await job
                # A last commit can land after the final polling read.
                job = None
                continue
            if job is None and not follow:
                current = await db.get_mission(mission_id)
                if current:
                    self.mission_state(current)
                return cursor
            if job is None:
                current = await db.get_mission(mission_id)
                if not current or current.status in STOPPED | {
                    MissionStatus.READY_FOR_AUTHORIZATION, MissionStatus.AWAITING_CLARIFICATION,
                    MissionStatus.VERIFYING, MissionStatus.VERIFIED_AWAITING_APPROVAL,
                }:
                    if current:
                        self.mission_state(current)
                    return cursor
                async with aiosqlite.connect(db.db_path) as connection:
                    active = await (await connection.execute("SELECT 1 FROM guild_operations WHERE mission_id=?", (mission_id,))).fetchone()
                if not active:
                    self.say("No active guild operation is running for this mission; replay caught up.")
                    self.mission_state(current)
                    return cursor
            if monotonic() >= deadline:
                self.say("Watch timeout reached; the mission was not cancelled. Reconnect with --after " + str(cursor))
                return cursor
            await asyncio.sleep(0.4)

    async def show_plan(self, controller, mission):
        self.say("\nPlan awaiting authorization:")
        for task in await controller.db.get_tasks(mission.id):
            self.say(f"  {task.owner_agent}: {safe_label(task.title, 120)} [{task.status.value}]")
        self.say("Accepted check mappings (review these before authorization):")
        for item in await controller.db.get_criteria(mission.id):
            self.say(f"  - {safe_label(item.description, 180)} => {item.verification_method}")
        context = await controller.store.context(mission.id) or {}
        for gap in context.get("test_gaps", []):
            self.say(f"  UNMAPPED: {safe_label(gap, 180)}")

    async def show_candidate(self, controller, mission):
        if not mission.active_candidate_id:
            return None
        candidates = await controller.store.records(Candidate, mission.id)
        candidate = next((c for c in candidates if c.id == mission.active_candidate_id), None)
        if candidate is None:
            return None
        directory = controller.workspaces.get_candidate_dir(mission.id, candidate.id)
        if controller.workspaces._compute_dir_hash(directory)[0] != candidate.content_fingerprint:
            self.say("Candidate snapshot fingerprint mismatch; diff withheld.")
            return None
        context = await controller.store.context(mission.id)
        controller._restore(context)
        controller.workspaces._candidates[candidate.id] = candidate
        diff = controller.workspaces.generate_candidate_diff(mission.id, mission.repository_id, candidate.id)
        self.say(f"\nCandidate {candidate.id} | SHA-256 {candidate.content_fingerprint}")
        self.say("Changed files: " + ", ".join(candidate.changed_files))
        self.say("--- Candidate diff (never the original repository) ---")
        self.say(redact_secrets(diff["unified_diff"][:40000]) or "(no text diff)")
        if len(diff["unified_diff"]) > 40000:
            self.say("Diff truncated in CLI; inspect the REST diff before approval.")
        return candidate

    async def workflow(self, controller: GuildController, mission_id: str, *, start_plan=False):
        mission = await controller.db.get_mission(mission_id)
        if not mission:
            raise KeyError("Mission not found")
        self.mission_state(mission)
        cursor = 0
        if start_plan:
            job = await controller.start(mission_id, "plan")
            cursor = await self.stream(controller.db, mission_id, job, after=cursor)
        while True:
            mission = await controller.db.get_mission(mission_id)
            self.mission_state(mission)
            if mission.status == MissionStatus.AWAITING_CLARIFICATION:
                questions = await controller.store.records(Clarification, mission_id)
                question = next((item for item in questions if item.status == "OPEN"), None)
                if question is None:
                    self.say("Clarification is pending but no open question was found. Mission paused.")
                    return 1
                self.say(f"\nShogun asks: {safe_label(question.question, 600)}")
                answer = await self.prompt("Answer (blank to pause): ")
                if not answer:
                    self.say("Mission remains paused; use `python -m app.cli resume " + mission_id + "` later.")
                    return 0
                job = await controller.answer(mission_id, ClarificationAnswerRequest(question_id=question.id, answer=answer))
                cursor = await self.stream(controller.db, mission_id, job, after=cursor)
                continue
            if mission.status == MissionStatus.READY_FOR_AUTHORIZATION:
                await self.show_plan(controller, mission)
                consent = await self.prompt("Type AUTHORIZE to allow bounded work in the disposable workspace: ")
                if consent != "AUTHORIZE":
                    self.say("Not authorized. Plan remains available; resume later.")
                    return 0
                job = await controller.start(mission_id, "execute", mission.scope_version)
                cursor = await self.stream(controller.db, mission_id, job, after=cursor)
                continue
            if mission.status == MissionStatus.VERIFYING:
                self.say("\nRunning the independent deterministic verifier on the frozen candidate...")
                await ApprovalService(controller).verify(mission_id)
                cursor = await self.stream(controller.db, mission_id, after=cursor)
                continue
            if mission.status == MissionStatus.VERIFIED_AWAITING_APPROVAL:
                await self.show_candidate(controller, mission)
                self.say("Verification passed. Human approval/application is separate; nothing was applied.")
                self.say("To review and decide later: python -m app.cli approve " + mission_id)
                return 0
            self.say(f"Mission {mission_id}: {mission.status.value}" +
                     (f" — {safe_label(mission.failure_reason, 300)}" if mission.failure_reason else ""))
            if mission.active_candidate_id:
                await self.show_candidate(controller, mission)
            return 0 if mission.status == MissionStatus.APPLIED else 1

    async def approve(self, controller: GuildController, mission_id: str):
        mission = await controller.db.get_mission(mission_id)
        if not mission:
            raise KeyError("Mission not found")
        if mission.status != MissionStatus.VERIFIED_AWAITING_APPROVAL:
            raise GuildConflict("Only an independently verified candidate can be approved")
        self.mission_state(mission)
        candidate = await self.show_candidate(controller, mission)
        if candidate is None:
            raise GuildConflict("Current candidate is unavailable or stale")
        approvals = await controller.store.records(Approval, mission_id)
        if not approvals:
            typed = await self.prompt("Type the complete SHA-256 fingerprint to approve this exact candidate (blank to leave unchanged): ")
            if typed != candidate.content_fingerprint:
                self.say("No approval recorded. Candidate remains unchanged.")
                return 0
            await ApprovalService(controller).decide(mission_id, ApprovalRequest(
                candidate_id=candidate.id, candidate_fingerprint=candidate.content_fingerprint,
                decision=ApprovalDecision.APPROVED))
            self.say("Human approval recorded for this candidate only.")
        elif not any(a.candidate_id == candidate.id and a.decision == ApprovalDecision.APPROVED
                     and a.candidate_fingerprint == candidate.content_fingerprint for a in approvals):
            raise GuildConflict("Existing decision does not approve this candidate")
        typed = await self.prompt("Type APPLY " + candidate.content_fingerprint + " to change the original repository (blank to leave approved): ")
        if typed != "APPLY " + candidate.content_fingerprint:
            self.say("Original repository unchanged. Approval stays recorded for later application.")
            return 0
        result = await ApprovalService(controller).apply(mission_id, candidate.id)
        self.say("Application recorded: " + result.status.value)
        return 0 if result.status == MissionStatus.APPLIED else 1


async def execute(args, console: Console):
    db = get_database()
    await db.init_db()
    if args.command == "watch":
        mission = await db.get_mission(args.mission_id)
        if not mission:
            raise KeyError("Mission not found")
        console.mission_state(mission)
        await console.stream(db, args.mission_id, after=args.after, follow=args.follow, timeout=args.timeout)
        return 0
    if args.command == "list":
        for mission in await db.list_missions(limit=20):
            console.say(f"{mission.id}  {mission.status.value}  {safe_label(mission.request_text, 100)}")
        return 0
    controller = GuildController(database=db)
    # Same local-only single-process scheduler as the API. Do not recover while
    # merely watching; an independent watcher must not mark another process's
    # in-progress mission interrupted.
    try:
        if args.command == "run":
            path = args.repo or await console.prompt("Local repository path: ")
            request = args.request or await console.prompt("What should the guild build or fix? ")
            criteria = list(args.criterion or [])
            if not criteria:
                console.say("Enter acceptance criteria, one per line. Blank line finishes.")
                while len(criteria) < 20:
                    value = await console.prompt("Criterion: ")
                    if not value:
                        break
                    criteria.append(value)
            if not path or not request or not criteria:
                raise ValueError("Repository, request and at least one criterion are required")
            if len(request) > 20000 or any(not criterion.strip() or len(criterion) > 2000 for criterion in criteria) or len(criteria) > 20:
                raise ValueError("Request or criteria exceed mission limits")
            record = get_repository_service().connect_repository(path)
            preflight = record["preflight"]
            console.say(f"Repository: {safe_label(record['name'])} | {preflight.file_count} approved files | {preflight.detected_profile}")
            for warning in preflight.warnings:
                console.say("Warning: " + safe_label(warning, 250))
            if preflight.blockers:
                for blocker in preflight.blockers:
                    console.say("Blocked: " + safe_label(blocker, 300))
                return 1
            mission = Mission(repository_id=record["repository_id"], request_text=request,
                              status=MissionStatus.PLANNING,
                              budgets=MissionBudgets(max_model_turns=args.max_model_turns,
                                                     max_tool_calls=args.max_tool_calls,
                                                     max_time_seconds=args.max_seconds))
            await db.create_mission(mission, [AcceptanceCriterion(mission_id=mission.id, description=text)
                                              for text in criteria])
            console.mission_state(mission)
            console.say("Mission created: " + mission.id)
            return await console.workflow(controller, mission.id, start_plan=True)
        if args.command == "resume":
            return await console.workflow(controller, args.mission_id)
        if args.command == "approve":
            return await console.approve(controller, args.mission_id)
        if args.command == "proof":
            from app.api.missions import MissionDetailResponse
            mission = await db.get_mission(args.mission_id)
            if not mission:
                raise KeyError("Mission not found")
            detail = MissionDetailResponse(mission=mission, criteria=await db.get_criteria(mission.id),
                                           tasks=await db.get_tasks(mission.id),
                                           candidates=await controller.store.records(Candidate, mission.id),
                                           evidence=await controller.store.records(Evidence, mission.id),
                                           findings=await controller.store.records(Finding, mission.id),
                                           messages=await controller.store.records(AgentMessage, mission.id),
                                           approvals=await controller.store.records(Approval, mission.id))
            context = await controller.store.context(args.mission_id) or {}
            events = []
            while True:
                batch = await db.get_events(args.mission_id, after_sequence=events[-1].sequence if events else 0)
                if not batch:
                    break
                events.extend(batch)
                if len(events) > 2000:
                    events = events[-2000:]
            card = proof_card(detail, context, events)
            console.say(proof_markdown(card) if args.format == "markdown" else json.dumps(card, indent=2))
            return 0
        raise ValueError("Unsupported command")
    finally:
        await controller.close()


def parser():
    cli = argparse.ArgumentParser(prog="python -m app.cli", description="Run and inspect KAGE AI missions locally.")
    cli.add_argument("--plain", action="store_true", help="Use readable text output instead of the boxed terminal UI")
    commands = cli.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Connect a repo, plan, and watch real guild activity")
    run.add_argument("--repo", help="Absolute path of an existing local repository")
    run.add_argument("--request", help="Natural-language software request")
    run.add_argument("--criterion", action="append", help="Acceptance criterion (repeatable)")
    run.add_argument("--max-model-turns", type=int, default=25, help="Mission-wide model turns (1–100; default 25)")
    run.add_argument("--max-tool-calls", type=int, default=50, help="Mission-wide tool calls (1–500; default 50)")
    run.add_argument("--max-seconds", type=int, default=600, help="Active mission seconds (1–3600; default 600)")
    resume = commands.add_parser("resume", help="Resume a paused plan or clarification")
    resume.add_argument("mission_id")
    watch = commands.add_parser("watch", help="Replay recorded activity; optional live follow")
    watch.add_argument("mission_id")
    watch.add_argument("--after", type=int, default=0, help="Replay only events after this sequence")
    watch.add_argument("--follow", action="store_true", help="Keep watching while a mission is active")
    watch.add_argument("--timeout", type=int, default=600, help="Maximum live follow seconds (1–3600; default 600)")
    approve = commands.add_parser("approve", help="Review exact candidate and explicitly approve/apply")
    approve.add_argument("mission_id")
    proof = commands.add_parser("proof", help="Print the candidate proof card")
    proof.add_argument("mission_id")
    proof.add_argument("--format", choices=("json", "markdown"), default="markdown")
    commands.add_parser("list", help="List recent missions")
    return cli


def main(argv=None, *, console=None):
    args = parser().parse_args(argv)
    if args.command == "watch" and args.after < 0:
        parser().error("--after must be zero or positive")
    if args.command == "watch" and not 1 <= args.timeout <= 3600:
        parser().error("--timeout must be between 1 and 3600 seconds")
    if console is None:
        import sys
        if not args.plain and args.command in {"run", "resume", "watch", "approve"} and sys.stdout.isatty() and sys.stdin.isatty():
            from app.cli_tui import GuildDashboard
            console = GuildDashboard()
        else:
            console = Console()
    console.start() if hasattr(console, "start") else None
    try:
        return asyncio.run(execute(args, console))
    except (KeyboardInterrupt, EOFError):
        console.say("CLI stopped. An active in-process guild operation was interrupted; check mission status before retrying.")
        return 130
    except (GuildConflict, KeyError, ValueError, OSError, ValidationError) as error:
        console.say("Blocked: " + safe_label(str(error), 300))
        return 1
    finally:
        console.stop() if hasattr(console, "stop") else None


if __name__ == "__main__":
    raise SystemExit(main())
