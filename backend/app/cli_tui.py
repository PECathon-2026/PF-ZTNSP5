"""KAGE terminal dashboard inspired by OpenCode's split workspace layout.

This renders existing persisted mission events; it has no agent, approval or
execution authority of its own. The CLI's plain renderer remains available.
"""

import asyncio
from collections import deque

from rich.console import Console as RichConsole, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
         "SENTINEL": "Sentinel / Tester", "SHADOW_COUNCIL": "Shadow Council / Review",
         "VERIFIER": "Independent Verifier"}
STOPPED = {"APPLIED", "REJECTED", "CANCELLED", "BLOCKED", "FAILED_VERIFICATION", "BUDGET_EXHAUSTED", "INTERRUPTED"}
WAITING = {"READY_FOR_AUTHORIZATION", "AWAITING_CLARIFICATION", "VERIFIED_AWAITING_APPROVAL"}


class GuildDashboard(Console):
    """A two-pane live view, safe across input prompts and terminal resize."""

    def __init__(self, *, rich_console: RichConsole | None = None):
        super().__init__()
        # Console's injected plain writer would otherwise shadow this method.
        del self.say
        self.rich = rich_console or RichConsole(highlight=False)
        self.live: Live | None = None
        self.lines: deque[tuple[str, str]] = deque(maxlen=200)
        self.handoffs: deque[str] = deque(maxlen=7)
        self.active_agent: str | None = None
        self.mission_id: str | None = None
        self.mission_status = "NOT STARTED"
        self.last_action = "Waiting for a repository and a mission request."
        self.cursor = 0
        self._diff_next = False

    def _text(self, text: str, style: str = MUTED) -> Text:
        return Text(redact_secrets(text), style=style, overflow="fold", no_wrap=False)

    def render(self) -> Layout:
        width = self.rich.size.width
        height = self.rich.size.height
        root = Layout(name="root")
        root.split_column(Layout(name="header", size=4), Layout(name="body", ratio=1), Layout(name="footer", size=4))
        header = Text.assemble(("  KAGE AI", f"bold {GOLD}"),
                               ("  /  ENGINEERING GUILD", f"bold {WASHI}"),
                               (f"     {self.mission_id or 'NEW MISSION'}", MUTED))
        root["header"].update(Panel(header, border_style=GOLD, style="on #141719", subtitle="Plan  ·  Build  ·  Test  ·  Review  ·  Verify"))
        visible = max(5, height - 10)
        transcript = list(self.lines)[-visible:]
        items = [self._text(text, style) for text, style in transcript] if transcript else [self._text("No mission events yet.")]
        activity = Panel(Group(*items), title=f"MISSION ACTIVITY  /  EVENT {self.cursor}",
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
            statuses.add_column(justify="right", ratio=1)
            for agent in AGENTS:
                active = agent == self.active_agent and self.mission_status not in WAITING | STOPPED
                marker = "> " if active else "  "
                label = self._text(marker + NAMES[agent], WASHI if active else MUTED)
                statuses.add_row(label, self._text("LIVE" if active else "--", FOREST if active else MUTED))
            statuses.add_row(self._text("  YOU / Approval", GOLD),
                             self._text("WAIT" if self.mission_status in WAITING else "--",
                                        GOLD if self.mission_status in WAITING else MUTED))
            root["agents"].update(Panel(statuses, title="GUILD / ACTIVE AGENT", title_align="left",
                                        border_style=GOLD, style="on #141719"))
            moves = [self._text(item, WASHI) for item in list(self.handoffs)[-max(2, height // 4):]]
            root["handoffs"].update(Panel(Group(*(moves or [self._text("Waiting for the first handoff.")])),
                                         title="HANDOFFS", title_align="left", border_style="#65523b",
                                         style="on #141719"))
        state_style = (CRIMSON if self.mission_status in STOPPED - {"APPLIED"} else FOREST if self.mission_status in
                       {"APPLIED", "VERIFIED_AWAITING_APPROVAL"} else GOLD)
        footer = Group(Text.assemble(("STATUS  ", "bold " + GOLD), (self.mission_status, state_style),
                                     ("    ·    ", MUTED), ("CURRENT  ", "bold " + GOLD),
                                     (NAMES.get(self.active_agent, "Awaiting input"), WASHI)),
                       self._text(self.last_action[:180], MUTED))
        root["footer"].update(Panel(footer, border_style=GOLD, style="on #111916"))
        return root

    def start(self):
        if self.live is None:
            self.live = Live(self.render(), console=self.rich, refresh_per_second=4,
                             auto_refresh=False, transient=False, vertical_overflow="crop")
            self.live.start()

    def stop(self):
        if self.live is not None:
            self.live.update(self.render(), refresh=True)
            self.live.stop()
            self.live = None

    def _refresh(self):
        if self.live is not None:
            self.live.update(self.render(), refresh=True)

    def say(self, value: str):
        text = redact_secrets(str(value))
        if self._diff_next:
            self._diff_next = False
            self.stop()
            self.rich.print(Panel(self._text(text[:40000], WASHI), title="CANDIDATE DIFF / REVIEW BEFORE APPROVAL",
                                  title_align="left", border_style=GOLD))
            return
        if text.startswith("--- Candidate diff (never the original repository) ---"):
            self._diff_next = True
            return
        for line in text.splitlines() or [""]:
            style = CRIMSON if "Blocked:" in line or "did not pass" in line else GOLD if "AUTHORIZE" in line or "approval" in line.lower() else MUTED
            self.lines.append((line[:400], style))
        self.last_action = safe_label(text, 180) or self.last_action
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
            table.add_row(self._text(task.owner_agent, GOLD), self._text(safe_label(task.title, 180), WASHI))
        for item in criteria:
            table.add_row(self._text("CHECK", GOLD), self._text(safe_label(item.description, 180) + " => " +
                                                               safe_label(item.verification_method, 300), WASHI))
        for gap in context.get("test_gaps", []):
            table.add_row(self._text("UNMAPPED", CRIMSON), self._text(safe_label(gap, 180), CRIMSON))
        self.stop()
        self.rich.print(Panel(table, title="SHOGUN PLAN / REVIEW BEFORE AUTHORIZE", border_style=GOLD))
        self.last_action = "Review tasks and criterion mappings before typing AUTHORIZE."
        # prompt() restarts Live after the human has answered.

    def event(self, event):
        self.cursor = event.sequence
        source = event.source
        if source in AGENTS and source != self.active_agent:
            before = NAMES.get(self.active_agent, "Mission")
            self.handoffs.append(f"{before}  ->  {NAMES[source]}")
            self.active_agent = source
        state = event.display_payload.get("status")
        if isinstance(state, str):
            self.mission_status = state
        message = show_event(event)
        self.lines.append((message[:400], CRIMSON if event.display_payload.get("stage") == "failed" or
                           "did not pass" in message else GOLD if event.display_payload.get("stage") in
                           {"handoff", "proposal"} else MUTED))
        self.last_action = safe_label(event.display_payload.get("summary") if isinstance(
            event.display_payload.get("summary"), str) else event.event_type, 180)
        self._refresh()

    def mission_state(self, mission):
        self.mission_id = mission.id
        self.mission_status = mission.status.value
        if self.mission_status in WAITING | STOPPED:
            self.active_agent = None
        self._refresh()

    async def prompt(self, text: str) -> str:
        self.stop()
        try:
            return (await asyncio.to_thread(self.rich.input, redact_secrets(text))).strip()
        finally:
            self.start()
