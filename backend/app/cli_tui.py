"""KAGE terminal dashboard inspired by OpenCode's split workspace layout.

This renders existing persisted mission events; it has no agent, approval or
execution authority of its own. The CLI's plain renderer remains available.
"""

import asyncio
import io
import re
from collections import deque

from rich.console import Console as RichConsole, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from prompt_toolkit import Application
from prompt_toolkit.formatted_text import ANSI, FormattedText
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import HSplit, Layout as PromptLayout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.widgets import TextArea

from app.cli import Console, show_event
from app.security.redaction import redact_secrets
from app.services.activity import safe_label


GOLD = "#e8c66a"
WASHI = "#efe4cd"
MUTED = "#c7bca9"
CRIMSON = "#e07b7b"
FOREST = "#86b89a"
AGENTS = ("SHOGUN", "SAMURAI", "SENTINEL", "SHADOW_COUNCIL", "VERIFIER")
NAMES = {"SHOGUN": "Shogun / Planner", "SAMURAI": "Samurai / Developer",
         "SENTINEL": "Sentinel / Tester", "SHADOW_COUNCIL": "Shadow Council",
         "VERIFIER": "Independent Verifier"}
STOPPED = {"APPLIED", "REJECTED", "CANCELLED", "BLOCKED", "FAILED_VERIFICATION", "BUDGET_EXHAUSTED", "INTERRUPTED"}
WAITING = {"READY_FOR_AUTHORIZATION", "AWAITING_CLARIFICATION", "VERIFIED_AWAITING_APPROVAL"}
PHASE_AGENT = {"SHOGUN_STARTED": "SHOGUN", "REPAIR_ROUND_STARTED": "SHOGUN",
               "SAMURAI_STARTED": "SAMURAI", "SENTINEL_STARTED": "SENTINEL",
               "SHADOW_COUNCIL_STARTED": "SHADOW_COUNCIL", "ACCEPTANCE_TEST_DESIGN_STARTED": "SENTINEL",
               "VERIFIER_STARTED": "VERIFIER"}
PHASE_DONE = {"PLAN_READY": "SHOGUN", "SENTINEL_FINISHED": "SENTINEL", "REVIEW_FINISHED": "SHADOW_COUNCIL",
              "VERIFICATION_PASSED": "VERIFIER", "VERIFICATION_FAILED": "VERIFIER",
              "ACCEPTANCE_TESTS_PROPOSED": "SENTINEL"}


def display_text(value: str) -> str:
    """Literal text only: repository output cannot inject terminal escape controls."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]", "", redact_secrets(value))


class GuildDashboard(Console):
    """A persistent terminal workspace with in-place input and paged reviews."""

    replay_history = True

    def __init__(self, *, rich_console: RichConsole | None = None, terminal_input=None, terminal_output=None):
        super().__init__(offer_save=True)
        # Console's injected plain writer would otherwise shadow this method.
        del self.say
        self.rich = rich_console or RichConsole(highlight=False)
        self._terminal_input = terminal_input
        self._terminal_output = terminal_output
        self.live: Application | None = None
        self._runner: asyncio.Task | None = None
        self._owner_task: asyncio.Task | None = None
        self._input_future: asyncio.Future | None = None
        self._secret_input = False
        self.prompt_text = ""
        self.reviews: list[tuple[str, str]] = []
        self._menu_review_index: int | None = None
        self.review_index = -1
        self.review_offset = 0
        self.lines: deque[tuple[str, str]] = deque(maxlen=200)
        self.handoffs: deque[str] = deque(maxlen=7)
        self.active_agent: str | None = None
        self.last_agent: str | None = None
        self.agent_states = {agent: "--" for agent in AGENTS}
        self.mission_id: str | None = None
        self.mission_status = "NOT STARTED"
        self.failure_reason = ""
        self.last_action = "Waiting for a repository and a mission request."
        self.cursor = 0
        self.request = ""
        self.budget_text = ""
        self._diff_next = False

    def _text(self, text: str, style: str = MUTED) -> Text:
        return Text(display_text(text), style=style, overflow="fold", no_wrap=False)

    def _tail_rows(self, entries, width, height):
        rows = []
        for text, style in reversed(list(entries)):
            wrapped = list(self._text(text, style).wrap(self.rich, max(1, width)))
            available = height - len(rows)
            rows = wrapped[-available:] + rows
            if len(rows) >= height:
                break
        return rows

    def _review_rows(self, width):
        return [row for line in self.reviews[self.review_index][1].splitlines()
                for row in (list(self._text(line, WASHI).wrap(self.rich, max(1, width))) or [self._text("")])]

    def _scroll_review(self, direction):
        if self.review_index < 0:
            return False
        pane_width = self.rich.width - (38 if self.rich.width >= 96 else 4)
        visible = max(1, self.rich.height - 10)
        last = max(0, len(self._review_rows(pane_width)) - visible)
        old = self.review_offset
        self.review_offset = min(last, max(0, old + direction * max(1, self.rich.height - 12)))
        self._refresh()
        return self.review_offset != old

    def render(self) -> Layout:
        width = self.rich.size.width
        height = self.rich.size.height
        root = Layout(name="root")
        root.split_column(Layout(name="header", size=4), Layout(name="body", ratio=1), Layout(name="footer", size=4))
        header = Text.assemble(("  KAGE AI", f"bold {GOLD}"),
                               ("  /  ENGINEERING GUILD", f"bold {WASHI}"),
                               (f"     {self.mission_id or 'NEW MISSION'}", MUTED))
        root["header"].update(Panel(header, border_style=GOLD, style="on #141719", subtitle="Plan  ·  Build  ·  Test  ·  Review  ·  Verify"))
        visible = max(1, height - 10)
        pane_width = width - 38 if width >= 96 else width - 4
        items = self._tail_rows(self.lines, pane_width, visible) if self.lines else [
            self._text("Welcome to KAGE AI", "bold " + GOLD),
            self._text("Your engineering guild. Your repository. Your approval."),
            self._text("Connect a small Python project and describe the mission."),
            self._text("Agent responses and execution results appear here as they arrive."),
        ]
        activity_title = f"MISSION ACTIVITY  /  EVENT {self.cursor}"
        if self.review_index >= 0:
            title, content = self.reviews[self.review_index]
            wrapped = self._review_rows(pane_width)
            items = wrapped[self.review_offset:self.review_offset + visible] or [self._text("(empty review)")]
            available = self._saved_reviews()
            if self.review_index in available:
                step = max(1, height - 12)
                max_offset = max(0, len(wrapped) - visible)
                pages = (max_offset + step - 1) // step + 1
                page = min(pages, (self.review_offset + step - 1) // step + 1) if self.review_offset else 1
                activity_title = (f"{title} · review {available.index(self.review_index) + 1}/{len(available)}"
                                  f" · page {page}/{pages} · 3/4 {'scroll' if len(available) == 1 else 'change review'}")
            else:
                activity_title = title + " · 1 activity · 2 review · 5 menu"
        activity = Panel(Group(*items), title=activity_title,
                         title_align="left", border_style="#c99a3a", style="on #090a0c")

        if width < 96:
            root["body"].update(activity)
        else:
            root["body"].split_row(Layout(name="activity", ratio=3, minimum_size=44),
                                   Layout(name="sidebar", size=34))
            root["activity"].update(activity)
            root["sidebar"].split_column(Layout(name="agents", ratio=2), Layout(name="handoffs", ratio=1))
            statuses = Table.grid(expand=True, padding=(0, 1))
            statuses.add_column(ratio=3)
            statuses.add_column(justify="right", ratio=1, min_width=9)
            for agent in AGENTS:
                active = (self.agent_states[agent] == "LIVE" or agent == self.active_agent) and self.mission_status not in WAITING | STOPPED
                marker = "> " if active else "  "
                label = self._text(marker + NAMES[agent], f"bold {GOLD} on #304033" if active else MUTED)
                state = "WAIT" if agent == "SHOGUN" and self.mission_status == "AWAITING_CLARIFICATION" else "LIVE" if active else self.agent_states[agent]
                statuses.add_row(label, self._text(state, f"bold #102018 on {FOREST}" if active else MUTED),
                                 style="on #304033" if active else "")
            statuses.add_row(self._text("  YOU / Answer" if self.mission_status == "AWAITING_CLARIFICATION" else "  YOU / Approval", GOLD),
                               self._text("ANSWER" if self.mission_status == "AWAITING_CLARIFICATION" else "WAIT" if self.mission_status in WAITING else "--",
                                         GOLD if self.mission_status in WAITING else MUTED))
            root["agents"].update(Panel(statuses, title="GUILD / ACTIVE AGENT", title_align="left",
                                        border_style=GOLD, style="on #141719"))
            moves = self._tail_rows([
                ("> " + item if index == len(self.handoffs) - 1 else item,
                 f"bold {GOLD} on #304033" if index == len(self.handoffs) - 1 else MUTED)
                for index, item in enumerate(self.handoffs)
            ], 30, max(1, (height - 8) // 3 - 2))
            root["handoffs"].update(Panel(Group(*(moves or [self._text("Waiting for the first handoff.")])),
                                         title="HANDOFFS / LATEST", title_align="left", border_style=GOLD if self.handoffs else "#65523b",
                                         style="on #141719"))
        state_style = (CRIMSON if self.mission_status in STOPPED - {"APPLIED"} else FOREST if self.mission_status in
                       {"APPLIED", "VERIFIED_AWAITING_APPROVAL"} else GOLD)
        footer = Group(Text.assemble(("STATUS  ", "bold " + GOLD), (self.mission_status, state_style),
                                     ("    ·    ", MUTED), ("CURRENT  ", "bold " + GOLD),
                                       ("Waiting for your answer · YOUR TURN" if self.mission_status == "AWAITING_CLARIFICATION"
                                        else NAMES.get(self.active_agent, "Awaiting input"),
                                        f"bold {GOLD}" if self.active_agent else WASHI)),
                       self._text(self.budget_text or self.last_action[:180], MUTED))
        root["footer"].update(Panel(footer, border_style=GOLD, style="on #111916"))
        return root

    def _screen(self):
        size = self.live.output.get_size()
        self.rich.width = size.columns
        self.rich.height = max(12, size.rows - 6)
        output = io.StringIO()
        canvas = RichConsole(file=output, width=size.columns, height=max(12, size.rows - 6),
                             force_terminal=True, color_system="truecolor", legacy_windows=False)
        canvas.print(self.render())
        return ANSI(output.getvalue())

    def _submit(self, buffer):
        if self._input_future is not None and not self._input_future.done():
            self._input_future.set_result(buffer.text.strip())
            buffer.text = ""
        return True

    def _create_application(self):
        keys = KeyBindings()

        @keys.add("pageup")
        def scroll_up(event):
            self._scroll_review(-1)

        @keys.add("pagedown")
        def scroll_down(event):
            self._scroll_review(1)

        @keys.add("f6")
        def previous_review(event):
            if self.reviews:
                self.review_index = (self.review_index - 1) % len(self.reviews)
                self.review_offset = 0
                event.app.invalidate()

        @keys.add("f7")
        def next_review(event):
            if self.reviews:
                self.review_index = (self.review_index + 1) % len(self.reviews)
                self.review_offset = 0
                event.app.invalidate()

        @keys.add("f8")
        def activity(event):
            self.review_index = -1
            event.app.invalidate()

        @keys.add("c-c")
        @keys.add("c-d")
        def interrupt(event):
            if self._input_future is not None and not self._input_future.done():
                self._input_future.set_exception(EOFError() if event.key_sequence[-1].key == Keys.ControlD else KeyboardInterrupt())
            else:
                event.app.exit()
                if self._owner_task is not None:
                    self._owner_task.cancel()

        self._input = TextArea(height=1, prompt="  > ", multiline=False,
                               password=Condition(lambda: self._secret_input), accept_handler=self._submit)
        self.live = Application(
            layout=PromptLayout(HSplit([
                Window(FormattedTextControl(self._screen), height=Dimension(weight=1)),
                Window(FormattedTextControl(lambda: FormattedText([("class:question", "  " + self.prompt_text)])),
                       height=3, wrap_lines=True),
                self._input,
            ]), focused_element=self._input),
            key_bindings=keys, full_screen=True, mouse_support=False,
            input=self._terminal_input, output=self._terminal_output)

    def start(self):
        if self.live is None:
            self._owner_task = asyncio.current_task()
            self._create_application()
            self._runner = asyncio.get_running_loop().create_task(self.live.run_async())

    def stop(self):
        if self.live is not None:
            if self.live.is_running:
                self.live.exit()
            elif self._runner is not None and not self._runner.done():
                self._runner.cancel()
            # prompt_toolkit redraws once while leaving the alternate screen.
            # Keep the application available to _screen until that redraw ends.

    async def wait_closed(self):
        if self._runner is not None:
            try:
                await self._runner
            except asyncio.CancelledError:
                pass
            finally:
                self._runner = None
        self.live = None
        self._owner_task = None

    def _refresh(self):
        if self.live is not None:
            self.live.invalidate()

    def _review(self, title, content):
        self.reviews.append((title, display_text(content)))
        self.review_index = len(self.reviews) - 1
        self.review_offset = 0
        self._refresh()

    def _saved_menu(self):
        count = len(self._saved_reviews())
        options = ("  3   Next page of saved review\n  4   Previous page of saved review\n" if count == 1 else
                   "  3   Next review\n  4   Previous review\n" if count > 1 else
                   "  3 / 4   No saved reviews yet (opens explanation)\n")
        interrupted = ("\nINTERRUPTED: An agent operation stopped before finishing.\n"
                       "Its disposable edits are not a verified candidate and cannot be replayed safely.\n"
                       "Start a fresh mission with the same request to try again.\n"
                       if self.mission_status == "INTERRUPTED" else "")
        return ("SAVED MISSION  /  " + (self.mission_id or "") + "\n"
                + "Status: " + self.mission_status + "\n"
                + "Request: " + self.request + "\n"
                + ("Reason: " + self.failure_reason + "\n" if self.failure_reason else "")
                + interrupted + "\n"
                + "Choose a number and press Enter:\n"
                + "  1   Recorded activity\n"
                + "  2   Latest review / mission summary\n"
                + options
                + "  5   This menu\n"
                + "  6   Continue as a fresh follow-up (review first)\n"
                + "  /up, /down   Scroll a long review\n"
                + "  Enter   Close this view (mission stays unchanged)\n\n"
                + f"{count} saved review pane(s) available. F-keys are optional shortcuts.")

    def _saved_reviews(self):
        return [i for i, (title, _) in enumerate(self.reviews) if title not in {
            "MISSION SUMMARY", "NO SAVED REVIEWS", "FOLLOW-UP / REVIEW BEFORE CREATION"}
            and not title.startswith("SAVED MISSION /")]

    def _show_saved_menu(self):
        title, content = "SAVED MISSION / CHOOSE AN ACTION", display_text(self._saved_menu())
        if self._menu_review_index is None:
            self.reviews.append((title, content))
            self._menu_review_index = len(self.reviews) - 1
        else:
            self.reviews[self._menu_review_index] = (title, content)
        self.review_index = self._menu_review_index
        self.review_offset = 0
        self._refresh()

    def _saved_summary(self):
        return ("Saved mission: " + (self.mission_id or "") + "\n"
                + "Status: " + self.mission_status + "\n"
                + ("Reason: " + self.failure_reason + "\n" if self.failure_reason else "")
                + "Request: " + self.request + "\n\n"
                + ("The interrupted write did not produce a verified change. Start a fresh mission; do not replay it.\n"
                   if self.mission_status == "INTERRUPTED" else "")
                + "No reviewable plan or diff was recorded for this mission.\n"
                + "Choose 1 to inspect the recorded activity; Enter closes the view.")

    def _saved_prompt(self):
        if self.review_index in self._saved_reviews() and len(self._saved_reviews()) == 1:
            width = self.rich.width - (38 if self.rich.width >= 96 else 4)
            last = max(0, len(self._review_rows(width)) - max(1, self.rich.height - 10))
            step = max(1, self.rich.height - 12)
            pages = (last + step - 1) // step + 1
            page = min(pages, (self.review_offset + step - 1) // step + 1) if self.review_offset else 1
            return f"Review page {page}/{pages}: 3 next, 4 previous, 5 menu, 6 follow-up, Enter closes: "
        return "Choose 1-6 (5 menu, 6 follow-up); Enter closes: "

    async def pause_at_end(self):
        self._show_saved_menu()
        hint = ""
        while True:
            answer = await self.prompt(hint or self._saved_prompt())
            hint = ""
            if not answer:
                return
            if answer in {"6", "/continue"}:
                return "follow-up"
            if answer in {"5", "/menu", "?"}:
                self._show_saved_menu()
            elif answer in {"1", "/activity"}:
                self.review_index = -1
                self._refresh()
            elif answer in {"2", "/reviews"}:
                # Always offer a review even if an early mission never produced
                # a plan, candidate or clarification.
                available = self._saved_reviews()
                if available:
                    self.review_index = available[-1]
                    self.review_offset = 0
                    self._refresh()
                else:
                    self._review("MISSION SUMMARY", self._saved_summary())
            elif answer in {"3", "/next", "4", "/prev"}:
                available = self._saved_reviews()
                if available:
                    direction = 1 if answer in {"3", "/next"} else -1
                    if len(available) == 1:
                        if self.review_index != available[0]:
                            self.review_index = available[0]
                            self.review_offset = 0
                        if not self._scroll_review(direction):
                            hint = ("End of review. 4 goes back, 5 opens menu, Enter closes: " if direction > 0 else
                                    "Start of review. 3 goes forward, 5 opens menu, Enter closes: ")
                    else:
                        position = available.index(self.review_index) if self.review_index in available else (-1 if direction > 0 else 0)
                        self.review_index = available[(position + direction) % len(available)]
                        self.review_offset = 0
                        self._refresh()
                else:
                    self._review("NO SAVED REVIEWS", self._saved_summary())
            elif answer in {"/up", "/down"}:
                self._scroll_review(-1 if answer == "/up" else 1)
            else:
                self._show_saved_menu()

    def show_follow_up(self, source, request, criteria, repository):
        content = ("Previous mission: " + source.id + " (" + source.status.value + ")\n"
                   "Repository: " + repository["path"] + "\n\n"
                   "NEW REQUEST (review before creating):\n" + request + "\n\n"
                   "SUCCESS CONDITIONS TO RE-REVIEW:\n" +
                   ("\n".join("- " + item for item in criteria) if criteria else "Shogun will propose them") + "\n\n"
                   "This follow-up starts from the current original repository. No unfinished workspace edits,\n"
                   "test results or approvals are inherited. A new source authorization is required.")
        title = "FOLLOW-UP / REVIEW BEFORE CREATION"
        if self.review_index >= 0 and self.reviews[self.review_index][0] == title:
            self.reviews[self.review_index] = (title, display_text(content))
            self.review_offset = 0
            self._refresh()
        else:
            self._review(title, content)

    def refresh_display(self):
        self._refresh()

    async def sync_state(self, db, mission_id):
        mission = await db.get_mission(mission_id)
        if mission:
            self.mission_state(mission)
            tasks = [t for t in await db.get_tasks(mission_id) if t.status.value != "CANCELLED"]
            for agent in AGENTS:
                statuses = {t.status.value for t in tasks if t.owner_agent == agent}
                if not statuses:
                    continue
                self.agent_states[agent] = next(label for status, label in (
                    ("RUNNING", "LIVE"), ("FAILED", "FAIL"), ("BLOCKED", "WAIT"),
                    ("READY", "READY"), ("PENDING", "WAIT"), ("DONE", "DONE")) if status in statuses)
            live_agents = [a for a in AGENTS if self.agent_states[a] == "LIVE"]
            if self.active_agent not in live_agents and live_agents and self.mission_status not in WAITING | STOPPED:
                self.active_agent = live_agents[0]
            if not live_agents and self.active_agent in {t.owner_agent for t in tasks}:
                self.active_agent = None
            if self.mission_status == "AWAITING_CLARIFICATION":
                self.agent_states["SHOGUN"] = "WAIT"
                self.active_agent = None
            self._refresh()

    def say(self, value: str):
        text = display_text(str(value))
        if self._diff_next:
            self._diff_next = False
            self._review("CANDIDATE DIFF / REVIEW BEFORE APPROVAL", text[:40000])
            return
        if text.startswith("--- Candidate diff (never the original repository) ---"):
            self._diff_next = True
            return
        for line in text.splitlines() or [""]:
            style = CRIMSON if "Blocked:" in line or "did not pass" in line else GOLD if "AUTHORIZE" in line or "approval" in line.lower() else MUTED
            self.lines.append((line[:400], style))
        self.last_action = safe_label(text, 180) or self.last_action
        if self.live is None:
            self.rich.print(self._text(text))
        else:
            self._refresh()

    def show_clarification(self, question):
        self.mission_status = "AWAITING_CLARIFICATION"
        self.active_agent = None
        self.agent_states["SHOGUN"] = "WAIT"
        self._review("SHOGUN / QUESTION / READ BEFORE ANSWERING", question.question)
        self.last_action = "Shogun needs your answer. Read the complete question in the review pane."
        self._refresh()

    async def show_plan(self, controller, mission):
        """Print the complete authorization contract outside the cropped Live log."""
        tasks = await controller.db.get_tasks(mission.id)
        criteria = await controller.db.get_criteria(mission.id)
        context = await controller.store.context(mission.id) or {}
        table = Table.grid(expand=True, padding=(0, 2))
        table.add_column(ratio=1)
        table.add_column(ratio=3)
        for task in tasks:
            table.add_row(self._text(task.owner_agent, GOLD), self._text(task.title + "\n" + task.description, WASHI))
        for item in criteria:
            table.add_row(self._text("CHECK", GOLD), self._text(item.description + " => " + item.verification_method, WASHI))
        for gap in context.get("test_gaps", []):
            label = "REVIEW NEW TEST" if context.get("acceptance_tests") else "UNMAPPED"
            table.add_row(self._text(label, CRIMSON), self._text(safe_label(gap, 180), CRIMSON))
        output = io.StringIO()
        RichConsole(file=output, width=max(60, self.rich.width - 4), color_system=None).print(table)
        self._review("SHOGUN PLAN / REVIEW BEFORE AUTHORIZE", output.getvalue())
        self.last_action = "Review tasks and criterion mappings before typing AUTHORIZE."

    async def show_saved_plan(self, controller, mission):
        tasks = await controller.db.get_tasks(mission.id)
        criteria = await controller.db.get_criteria(mission.id)
        if not tasks and not criteria:
            return
        content = "Recorded plan and checks (read-only; this view does not restart agents):\n\n"
        for task in tasks:
            content += f"{task.owner_agent} [{task.status.value}] {task.title}\n{task.description}\n\n"
        for criterion in criteria:
            content += f"CHECK [{criterion.status.value}] {criterion.description}\n{criterion.verification_method}\n\n"
        self._review("SAVED PLAN / RECORDED TASKS AND CHECKS", content)

    async def show_test_proposal(self, bundle):
        content = ("Sentinel proposes new acceptance tests. Review assertions below. Existing repository tests remain unchanged.\n"
                   "Proposal hash: " + bundle["hash"] + "\n\n")
        for mapping in bundle["proposal"]["mappings"]:
            content += mapping["criterion_description"] + " => " + ", ".join(mapping["test_selectors"]) + "\n"
        for file in bundle["proposal"]["files"]:
            content += "\n--- " + file["path"] + " ---\n" + file["content"] + "\n"
        self._review("ACCEPTANCE TEST REVIEW", content)

    def event(self, event):
        if self.mission_id and event.mission_id != self.mission_id:
            return
        if event.sequence <= self.cursor:
            return
        self.mission_id = event.mission_id
        self.cursor = event.sequence
        state = event.display_payload.get("status")
        if isinstance(state, str):
            self.mission_status = state
        source = PHASE_AGENT.get(event.event_type, event.source)
        if source in AGENTS:
            if source != self.last_agent:
                before = NAMES.get(self.last_agent, "Mission")
                self.handoffs.append(f"{before}  ->  {NAMES[source]}")
                self.last_agent = source
            if self.mission_status not in WAITING | STOPPED:
                self.active_agent = source
            if event.event_type in PHASE_AGENT:
                self.agent_states[source] = "LIVE"
        if event.event_type == "ACCEPTANCE_TEST_DESIGN_STARTED":
            self.agent_states["SHOGUN"] = "DONE"
        if event.event_type in PHASE_DONE:
            self.agent_states[PHASE_DONE[event.event_type]] = "DONE"
            if self.active_agent == PHASE_DONE[event.event_type]:
                self.active_agent = None
        if event.event_type == "VERIFICATION_PASSED":
            self.agent_states["VERIFIER"] = "PASS"
        elif event.event_type in {"VERIFICATION_FAILED", "VERIFIER_ERROR"}:
            self.agent_states["VERIFIER"] = "FAIL"
            if self.active_agent == "VERIFIER":
                self.active_agent = None
        if self.mission_status in WAITING | STOPPED:
            self.active_agent = None
        if self.mission_status == "AWAITING_CLARIFICATION":
            self.agent_states["SHOGUN"] = "WAIT"
        message = show_event(event)
        self.lines.append((message[:400], CRIMSON if event.display_payload.get("stage") == "failed" or
                           "did not pass" in message else GOLD if event.display_payload.get("stage") in
                           {"handoff", "proposal"} else MUTED))
        self.last_action = safe_label(event.display_payload.get("summary") if isinstance(
            event.display_payload.get("summary"), str) else event.event_type, 180)
        self._refresh()

    def mission_state(self, mission):
        if self.mission_id and self.mission_id != mission.id:
            self.lines.clear()
            self.handoffs.clear()
            self.reviews.clear()
            self._menu_review_index = None
            self.review_index = -1
            self.review_offset = 0
            self.cursor = 0
            self.active_agent = self.last_agent = None
            self.agent_states = {agent: "--" for agent in AGENTS}
        self.mission_id = mission.id
        self.mission_status = mission.status.value
        self.failure_reason = mission.failure_reason or ""
        self.request = mission.request_text
        self.budget_text = (f"Turns {mission.budgets.model_turns_used}/{mission.budgets.max_model_turns} | "
                            f"Tools {mission.budgets.tool_calls_used}/{mission.budgets.max_tool_calls} | "
                            f"Repairs {mission.budgets.repair_rounds_used}/{mission.budgets.max_repair_rounds} | Ctrl+C to exit")
        if self.mission_status in WAITING | STOPPED:
            self.active_agent = None
        if self.mission_status == "AWAITING_CLARIFICATION":
            self.agent_states["SHOGUN"] = "WAIT"
        self._refresh()

    async def prompt(self, text: str) -> str:
        if self.live is None:
            raise RuntimeError("The interactive dashboard is not running")
        self.prompt_text = display_text(text)
        self._input_future = asyncio.get_running_loop().create_future()
        self._refresh()
        try:
            answer = await self._input_future
            self.lines.append(("You: [API key supplied]" if self._secret_input else
                               "You: " + safe_label(answer or "(left unchanged)", 180), GOLD))
            return answer
        finally:
            self._input_future = None
            self.prompt_text = ""
            self._refresh()

    async def prompt_secret(self, text: str) -> str:
        self._secret_input = True
        try:
            return await self.prompt(text)
        finally:
            self._secret_input = False
            self._refresh()
