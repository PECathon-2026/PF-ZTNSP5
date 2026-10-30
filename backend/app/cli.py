"""Interactive DevPilot CLI over the same durable guild used by the REST API.

Usage (from backend/): python -m app.cli run --repo PATH --request TEXT --criterion TEXT
No model edits are applied to the original repository without a separate exact
candidate fingerprint approval and apply confirmation.
"""

import argparse
import asyncio
import json
import sys
from getpass import getpass
from time import monotonic
from collections.abc import Callable
import aiosqlite
from pydantic import ValidationError

from app.schemas.approval import ApprovalDecision, ApprovalRequest
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.agent_message import AgentMessage
from app.schemas.guild import Clarification, AcceptanceTestDecision
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


async def get_cli_model_credentials(console, base_url=None):
    from app.agents.model_adapter import ModelAdapterError
    from app.services.mission_credentials import check_model_connection

    url = base_url if base_url is not None else await console.prompt(
        "Model base URL (Enter uses configured backend endpoint): ")
    key = await console.prompt_secret("Model API key (input hidden): ")
    try:
        await check_model_connection(key, url or None)
    except ModelAdapterError:
        raise ValueError("Model provider rejected the API key, base URL or configured model; no mission was created") from None
    console.say("Model key and base URL connection verified. Credentials remain in backend memory for this run.")
    return key, url or None


async def create_cli_mission(controller, mission, criteria, *, key=None, base_url=None):
    from app.services.mission_credentials import set_mission_key, forget_mission_key

    if key is not None:
        set_mission_key(mission.id, key, base_url)
    try:
        await controller.db.create_mission(mission, [AcceptanceCriterion(mission_id=mission.id, description=text)
                                                    for text in criteria])
        if key is not None:
            async with controller.store.transaction() as connection:
                await connection.execute("INSERT INTO guild_context VALUES (?,?)", (mission.id, '{"own_api_key":true}'))
    except Exception:
        forget_mission_key(mission.id)
        raise


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
    def __init__(self, ask: Callable[[str], str] = input, say: Callable[[str], None] = print,
                 *, offer_save: bool = False):
        self.ask = ask
        self.say = say
        self.offer_save = offer_save

    async def prompt(self, text: str) -> str:
        return (await asyncio.to_thread(self.ask, text)).strip()

    async def prompt_secret(self, text: str) -> str:
        return (await asyncio.to_thread(getpass, text)).strip() if self.ask is input else await self.prompt(text)

    async def collect_criteria(self):
        """Manual criteria are opt-in; normal language is never a CLI command."""
        self.say("Shogun will propose success conditions from your request for you to review.")
        choice = await self.prompt("Press Enter for Shogun to plan, or type /manual to enter your own criteria: ")
        while choice not in {"", "/auto", "/manual"}:
            self.say("A criterion describes a result you expect. Enter = let Shogun propose them; /manual = write your own.")
            choice = await self.prompt("Enter or /manual: ")
        if choice != "/manual":
            return []
        criteria = []
        self.say("Manual criteria: one expected result per line. /help explains, /clear resets, /auto lets Shogun decide, /done finishes.")
        while len(criteria) < 20:
            value = await self.prompt("Expected result (or /done): ")
            if value in {"", "/done"}:
                break
            if value == "/auto":
                return []
            if value == "/clear":
                criteria.clear()
                self.say("Manual criteria cleared.")
                continue
            if value == "/help":
                self.say("Example: 'Pagination preserves the last partial page'. Use /auto if you want the planner to derive these.")
                continue
            if value.startswith("/"):
                self.say("Unknown command. Use /help, /clear, /auto or /done.")
                continue
            if len(value) > 2000:
                self.say("Keep each expected result under 2000 characters.")
                continue
            criteria.append(value)
        if criteria:
            self.say("These will be binding requirements:\n" + "\n".join(f"  - {item}" for item in criteria))
            if await self.prompt("Type KEEP to use these exact requirements; Enter lets Shogun propose them: ") != "KEEP":
                return []
        return criteria

    def event(self, event):
        self.say(show_event(event))

    def mission_state(self, mission):
        """Display hook; the boxed TUI keeps its sidebar in sync with SQLite."""
        pass

    def show_clarification(self, question):
        self.say("\nShogun asks: " + redact_secrets(question.question))

    async def pause_at_end(self):
        """Interactive displays may let the user inspect a finished/paused view."""

    async def show_saved_plan(self, controller, mission):
        """Optional read-only inspection of earlier decisions on a stopped run."""

    def show_follow_up(self, source, request, criteria, repository):
        self.say("\nFollow-up to " + source.id + " (old mission remains " + source.status.value + ")")
        self.say("Repository: " + safe_label(repository["path"], 300))
        self.say("New request for review:\n" + redact_secrets(request))
        self.say("Success conditions to review again: " + ("; ".join(criteria) if criteria else "Shogun will propose them"))
        self.say("This starts a fresh mission from the current original repository. Unfinished workspace edits, old test evidence and approval are not copied.")

    async def follow_up(self, controller, source_id, *, return_to_view=False):
        """Carry confirmed conversation context into a *new* mission, never replay writes."""
        source = await controller.db.get_mission(source_id)
        if not source:
            raise KeyError("Mission not found")
        if source.status not in STOPPED | {MissionStatus.VERIFIED_AWAITING_APPROVAL}:
            raise GuildConflict("This mission can still be resumed; use resume " + source.id)
        context = await controller.store.context(source_id) or {}
        path = context.get("repository", {}).get("path")
        if not path:
            path = await self.prompt("Old repository path is unavailable. Enter its current path (blank to cancel): ")
        if not path:
            self.say("No new mission created.")
            return "back" if return_to_view else 0
        extra = await self.prompt("What else should the follow-up do? (Enter keeps the old request): ")
        if extra in {"/cancel", "/back"}:
            return "back" if return_to_view else 0
        answers = [item for item in await controller.store.records(Clarification, source_id)
                   if item.status == "ANSWERED" and item.answer]
        base_request = ("Follow-up to " + source.id + ". Begin from the current original repository; "
                        "prior unfinished edits are not verified or inherited.\n\nOriginal request: " + source.request_text)
        if answers:
            base_request += "\nPrior user clarifications (re-evaluate against the repository):\n" + "\n".join(
                f"- Question: {redact_secrets(item.question)} Answer: {redact_secrets(item.answer)}" for item in answers)
        if len(base_request) > 20000:
            raise ValueError("Old request and carried answers exceed new mission limits; start a narrower new mission")
        additions = [extra] if extra else []
        criteria = [item.description for item in await controller.db.get_criteria(source_id)]
        if len(criteria) > 20 or any(len(item) > 2000 for item in criteria):
            raise ValueError("Previous criteria exceed new mission limits; start a new mission with a narrower scope")
        record = get_repository_service().connect_repository(path)
        if record["repository_id"] != source.repository_id:
            raise GuildConflict("Repository path does not match the old mission; choose its original repository")
        preflight = record["preflight"]
        if context.get("repository", {}).get("fingerprint") != record["fingerprint"]:
            self.say("Repository files changed since the old mission. The new plan will inspect the current files.")
        for warning in preflight.warnings:
            self.say("Warning: " + safe_label(warning, 250))
        if preflight.blockers:
            for blocker in preflight.blockers:
                self.say("Blocked: " + safe_label(blocker, 300))
            return "back" if return_to_view else 1
        instruction = "Type CREATE FOLLOW-UP to create a new mission; /edit adds text; /cancel returns: "
        while True:
            request = base_request + ("\nNew user instructions:\n" + "\n".join(f"- {text}" for text in additions)
                                      if additions else "")
            if len(request) > 20000:
                additions.pop()
                self.say("The follow-up is too long; last instruction was not added. Keep it under 20000 characters.")
                continue
            self.show_follow_up(source, request, criteria, record)
            choice = await self.prompt(instruction)
            if choice == "CREATE FOLLOW-UP":
                break
            if choice in {"", "/cancel", "/back"}:
                self.say("No new mission created. Original mission unchanged.")
                return "back" if return_to_view else 0
            if choice == "/clear":
                additions.clear()
                instruction = "Extra instructions cleared. Type CREATE FOLLOW-UP, /edit, or /cancel: "
                continue
            if choice == "/edit":
                choice = await self.prompt("Add another instruction (Enter keeps the current draft): ")
                if not choice:
                    instruction = "Type CREATE FOLLOW-UP to create; /edit to add; /cancel to return: "
                    continue
            if choice.startswith("/"):
                instruction = "Unknown command. Use CREATE FOLLOW-UP, /edit, /clear, or /cancel: "
                continue
            if choice in additions:
                instruction = "Already included. Type CREATE FOLLOW-UP to create, /edit to add, /cancel to return: "
            else:
                additions.append(choice)
                instruction = "Instruction added. Review above, then type CREATE FOLLOW-UP, /edit, or /cancel: "
        mission = Mission(repository_id=record["repository_id"], request_text=request,
                          status=MissionStatus.PLANNING,
                          budgets=MissionBudgets(max_model_turns=60, max_tool_calls=100, max_time_seconds=600))
        key, base_url = await get_cli_model_credentials(self) if context.get("own_api_key") else (None, None)
        await create_cli_mission(controller, mission, criteria, key=key, base_url=base_url)
        self.mission_state(mission)
        self.say("New follow-up mission: " + mission.id + " (from " + source.id + ")")
        return await self.workflow(controller, mission.id, start_plan=True)

    def refresh_display(self):
        """Redraw hook for resizes while waiting on a model or container."""
        pass

    async def sync_state(self, db, mission_id):
        """Optional sidebar refresh using the authoritative mission snapshot."""
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
            await self.sync_state(db, mission_id)
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
            if job is None and monotonic() >= deadline:
                self.say("Watch timeout reached; the mission was not cancelled. Reconnect with --after " + str(cursor))
                return cursor
            self.refresh_display()
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
            label = "NEW TEST REVIEW REQUIRED" if context.get("acceptance_tests") else "UNMAPPED"
            self.say(f"  {label}: {safe_label(gap, 180)}")

    async def show_test_proposal(self, bundle):
        self.say("\nSentinel proposes NEW acceptance tests. Review the assertions before accepting.")
        self.say("These run only in a verification copy; existing repository tests are not changed.")
        self.say("Proposal hash: " + bundle["hash"])
        for mapping in bundle["proposal"]["mappings"]:
            self.say(mapping["criterion_description"] + " => " + ", ".join(mapping["test_selectors"]))
        for file in bundle["proposal"]["files"]:
            self.say("\n--- " + file["path"] + " ---\n" + redact_secrets(file["content"]))

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
        self.say("Original repository: " + safe_label(context["repository"]["path"], 300))
        self.say(f"\nCandidate {candidate.id} | SHA-256 {candidate.content_fingerprint}")
        self.say("Changed files: " + ", ".join(candidate.changed_files))
        self.say("--- Candidate diff (never the original repository) ---")
        self.say(("Original repository: " + context["repository"]["path"] + "\n"
                  "Candidate SHA-256: " + candidate.content_fingerprint + "\n\n" +
                  (redact_secrets(diff["unified_diff"][:40000]) or "(no text diff)")))
        if len(diff["unified_diff"]) > 40000:
            self.say("Diff truncated in CLI; inspect the REST diff before approval.")
        return candidate

    async def workflow(self, controller: GuildController, mission_id: str, *, start_plan=False):
        mission = await controller.db.get_mission(mission_id)
        if not mission:
            raise KeyError("Mission not found")
        self.mission_state(mission)
        from app.services.mission_credentials import has_mission_key, set_mission_key
        context = await controller.store.context(mission_id) or {}
        if (context.get("own_api_key") and not has_mission_key(mission_id) and
                mission.status in {MissionStatus.PLANNING, MissionStatus.AWAITING_CLARIFICATION,
                                   MissionStatus.READY_FOR_AUTHORIZATION}):
            self.say("Re-enter this mission's API key and base URL before resuming model work.")
            key, base_url = await get_cli_model_credentials(self)
            set_mission_key(mission_id, key, base_url)
        cursor = 0
        if start_plan:
            job = await controller.start(mission_id, "plan")
            cursor = await self.stream(controller.db, mission_id, job, after=cursor)
        elif getattr(self, "replay_history", False):
            cursor = await self.stream(controller.db, mission_id, after=cursor)
        while True:
            mission = await controller.db.get_mission(mission_id)
            self.mission_state(mission)
            if mission.status == MissionStatus.AWAITING_CLARIFICATION:
                questions = await controller.store.records(Clarification, mission_id)
                question = next((item for item in questions if item.status == "OPEN"), None)
                if question is None:
                    self.say("Clarification is pending but no open question was found. Mission paused.")
                    return 1
                self.show_clarification(question)
                answer = await self.prompt("Answer (blank to pause): ")
                if not answer:
                    self.say("Mission remains paused; use `python -m app.cli resume " + mission_id + "` later.")
                    return 0
                job = await controller.answer(mission_id, ClarificationAnswerRequest(question_id=question.id, answer=answer))
                cursor = await self.stream(controller.db, mission_id, job, after=cursor)
                continue
            if mission.status == MissionStatus.READY_FOR_AUTHORIZATION:
                await self.show_plan(controller, mission)
                context = await controller.store.context(mission_id) or {}
                bundle = context.get("acceptance_tests")
                if bundle and not bundle.get("accepted"):
                    await self.show_test_proposal(bundle)
                    try:
                        answer = await self.prompt("Type ACCEPT TESTS " + bundle["hash"] + " to accept the assertions, REJECT to decline, or Enter to pause: ")
                    except EOFError:
                        self.say("Input closed. Test proposal remains unaccepted; use resume later.")
                        return 0
                    if answer == "REJECT":
                        await controller.review_tests(mission_id, AcceptanceTestDecision(proposal_hash=bundle["hash"], accept=False))
                        self.say("Acceptance tests declined; mission stopped without implementation.")
                        return 1
                    if answer != "ACCEPT TESTS " + bundle["hash"]:
                        self.say("Test proposal remains unaccepted. Resume this mission after reviewing it.")
                        return 0
                    await controller.review_tests(mission_id, AcceptanceTestDecision(proposal_hash=bundle["hash"], accept=True))
                    self.say("Reviewed test expectations accepted. Source implementation still needs AUTHORIZE.")
                consent = await self.prompt("Type AUTHORIZE to allow bounded work in the disposable workspace: ")
                if consent != "AUTHORIZE":
                    self.say("Not authorized. Plan remains available; resume later.")
                    return 0
                job = await controller.start(mission_id, "execute", mission.scope_version)
                cursor = await self.stream(controller.db, mission_id, job, after=cursor)
                continue
            if mission.status == MissionStatus.VERIFYING:
                self.say("\nRunning the independent deterministic verifier on the frozen candidate...")
                job = asyncio.create_task(ApprovalService(controller).verify(mission_id))
                try:
                    cursor = await self.stream(controller.db, mission_id, job, after=cursor)
                finally:
                    if not job.done():
                        job.cancel()
                    await asyncio.gather(job, return_exceptions=True)
                continue
            if mission.status == MissionStatus.VERIFIED_AWAITING_APPROVAL:
                await self.show_candidate(controller, mission)
                self.say("Verification passed. Candidate is still in a disposable workspace; the existing repository has not been changed.")
                if self.offer_save:
                    if await self.prompt("Type SAVE to review and save this verified change in the existing repository (Enter leaves it unchanged): ") == "SAVE":
                        code = await self.approve(controller, mission_id)
                        await self.pause_at_end()
                        return code
                self.say("To review and decide later: python -m app.cli approve " + mission_id)
                while await self.pause_at_end() == "follow-up":
                    result = await self.follow_up(controller, mission_id, return_to_view=True)
                    if result != "back":
                        return result
                return 0
            self.say(f"Mission {mission_id}: {mission.status.value}" +
                      (f" — {safe_label(mission.failure_reason, 300)}" if mission.failure_reason else ""))
            if mission.active_candidate_id:
                await self.show_candidate(controller, mission)
            await self.show_saved_plan(controller, mission)
            while await self.pause_at_end() == "follow-up":
                result = await self.follow_up(controller, mission_id, return_to_view=True)
                if result != "back":
                    return result
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
        self.mission_state(result)
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
                criteria = await console.collect_criteria()
            if not path or not request:
                raise ValueError("Repository and a software request are required")
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
            key, base_url = await get_cli_model_credentials(console, args.base_url) if (args.own_api_key or args.base_url) else (None, None)
            await create_cli_mission(controller, mission, criteria, key=key, base_url=base_url)
            console.mission_state(mission)
            console.say("Mission created: " + mission.id)
            return await console.workflow(controller, mission.id, start_plan=True)
        if args.command == "resume":
            return await console.workflow(controller, args.mission_id)
        if args.command == "continue":
            return await console.follow_up(controller, args.mission_id)
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
    run.add_argument("--criterion", action="append", help="Optional explicit acceptance criterion (repeatable); otherwise Shogun proposes criteria")
    run.add_argument("--own-api-key", action="store_true", help="Ask for a hidden mission API key and test the provider connection")
    run.add_argument("--base-url", help="Mission-specific model base URL (prompts for a hidden key; HTTPS or loopback HTTP)")
    run.add_argument("--max-model-turns", type=int, default=60, help="Mission-wide model turns (1–100; default 60)")
    run.add_argument("--max-tool-calls", type=int, default=100, help="Mission-wide tool calls (1–500; default 100)")
    run.add_argument("--max-seconds", type=int, default=600, help="Active mission seconds (1–3600; default 600)")
    resume = commands.add_parser("resume", help="Resume a paused plan or clarification")
    resume.add_argument("mission_id")
    continuation = commands.add_parser("continue", help="Review an old mission and start a fresh linked follow-up")
    continuation.add_argument("mission_id")
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


def select_console(args, *, stdout=None, stdin=None):
    output = sys.stdout if stdout is None else stdout
    incoming = sys.stdin if stdin is None else stdin
    if (not args.plain and args.command in {"run", "resume", "continue", "watch", "approve"}
            and output.isatty() and incoming.isatty()):
        from app.cli_tui import GuildDashboard
        return GuildDashboard()
    return Console(offer_save=args.command in {"run", "resume"} and output.isatty() and incoming.isatty())


def main(argv=None, *, console=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments == ["--plain"]:
        arguments.append("run")
    args = parser().parse_args(arguments)
    if args.command == "watch" and args.after < 0:
        parser().error("--after must be zero or positive")
    if args.command == "watch" and not 1 <= args.timeout <= 3600:
        parser().error("--timeout must be between 1 and 3600 seconds")
    if console is None:
        console = select_console(args)
    async def run():
        try:
            if hasattr(console, "start"):
                console.start()
            return await execute(args, console)
        finally:
            if hasattr(console, "stop"):
                console.stop()
            if hasattr(console, "wait_closed"):
                await console.wait_closed()

    try:
        return asyncio.run(run())
    except (KeyboardInterrupt, EOFError, asyncio.CancelledError):
        console.say("CLI stopped. An active in-process guild operation was interrupted; check mission status before retrying.")
        return 130
    except (GuildConflict, KeyError, ValueError, OSError, ValidationError) as error:
        console.say("Blocked: " + safe_label(str(error), 300))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
