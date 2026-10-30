import io
import asyncio
from types import SimpleNamespace

import pytest
from rich.console import Console as RichConsole
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from app.cli_tui import GuildDashboard
from app.schemas.events import MissionEvent
from app.schemas.mission import Mission, MissionStatus
from tests.unit.test_m4_guild import guild
from tests.unit.test_m5_recovery import recovery
from tests.unit.test_m6_approval import prepared
from app.schemas.candidate import Candidate


def ui():
    output = io.StringIO()
    console = RichConsole(file=output, width=112, height=28, color_system=None, force_terminal=False)
    return GuildDashboard(rich_console=console), console, output


def activity(sequence, source, summary, stage="intent"):
    return MissionEvent(sequence=sequence, mission_id="miss-test", event_type="AGENT_ACTIVITY", source=source,
                        display_payload={"stage": stage, "summary": summary})


def test_dashboard_shows_switches_and_real_response_not_hardcoded():
    dashboard, console, output = ui()
    dashboard.mission_state(Mission(id="miss-test", repository_id="repo-test", request_text="Fix ledger",
                                    status=MissionStatus.RUNNING))
    dashboard.event(activity(1, "SHOGUN", "Shogun inspected ledger.py"))
    dashboard.event(activity(2, "SAMURAI", "Samurai edited ledger.py", "outcome"))
    dashboard.event(activity(3, "SENTINEL", "Sentinel test_ledger.py failed", "failed"))
    assert dashboard.active_agent == "SENTINEL"
    assert dashboard.cursor == 3
    assert list(dashboard.handoffs)[-1] == "Samurai / Developer  ->  Sentinel / Tester"
    console.print(dashboard.render())
    rendered = output.getvalue()
    assert "KAGE AI" in rendered and "GUILD / ACTIVE AGENT" in rendered
    assert "HANDOFFS" in rendered and "Sentinel / Tester" in rendered
    assert "ledger.py" in rendered and "test_ledger.py failed" in rendered
    dashboard.mission_state(Mission(id="miss-test", repository_id="repo-test", request_text="Fix ledger",
                                    status=MissionStatus.VERIFIED_AWAITING_APPROVAL))
    assert dashboard.active_agent is None


@pytest.mark.asyncio
async def test_dashboard_keeps_screen_and_input_alive_during_consecutive_prompts():
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        dashboard.start()
        try:
            await asyncio.sleep(.05)
            first = asyncio.create_task(dashboard.prompt("Type AUTHORIZE: "))
            await asyncio.sleep(.05)
            assert dashboard.live.is_running
            assert dashboard.prompt_text == "Type AUTHORIZE: "
            pipe.send_text("AUTHORIZE\r")
            assert await asyncio.wait_for(first, 3) == "AUTHORIZE"
            second = asyncio.create_task(dashboard.prompt("Explain the change: "))
            await asyncio.sleep(.05)
            assert dashboard.live.is_running
            pipe.send_text("looks right\r")
            assert await asyncio.wait_for(second, 3) == "looks right"
            assert dashboard.live.is_running
        finally:
            dashboard.stop()
            await dashboard.wait_closed()


@pytest.mark.asyncio
async def test_dashboard_masks_api_key_and_never_appends_it_to_activity():
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        dashboard.start()
        try:
            waiting = asyncio.create_task(dashboard.prompt_secret("Model API key (input hidden): "))
            await asyncio.sleep(.05)
            assert dashboard._secret_input
            pipe.send_text("private-demo-key\r")
            assert await asyncio.wait_for(waiting, 3) == "private-demo-key"
            assert not dashboard._secret_input
            assert "private-demo-key" not in repr(dashboard.lines)
            assert any("[API key supplied]" in text for text, _ in dashboard.lines)
        finally:
            dashboard.stop()
            await dashboard.wait_closed()


@pytest.mark.asyncio
async def test_tui_saves_verified_candidate_into_existing_repository_after_exact_confirmations(recovery):
    controller, mission, repo, service, candidate_id = await prepared(recovery)
    await service.verify(mission.id)
    candidate = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == candidate_id)
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        dashboard.start()
        async def wait_for_prompt(fragment):
            for _ in range(80):
                if fragment in dashboard.prompt_text or running.done():
                    break
                await asyncio.sleep(.05)
            assert fragment in dashboard.prompt_text
        try:
            running = asyncio.create_task(dashboard.workflow(controller, mission.id))
            await wait_for_prompt("Type SAVE")
            assert (repo / "app.py").read_text() == "value = 1\n"
            pipe.send_text("SAVE\r")
            await wait_for_prompt("complete SHA-256")
            assert candidate.content_fingerprint in dashboard.reviews[dashboard.review_index][1]
            pipe.send_text(candidate.content_fingerprint + "\r")
            await wait_for_prompt("Type APPLY")
            assert (repo / "app.py").read_text() == "value = 1\n"
            pipe.send_text("APPLY " + candidate.content_fingerprint + "\r")
            await wait_for_prompt("Choose 1-6")
            assert (repo / "app.py").read_text() == "value = 2\n"
            pipe.send_text("\r")
            assert await asyncio.wait_for(running, 5) == 0
            assert (await controller.db.get_mission(mission.id)).status == MissionStatus.APPLIED
        finally:
            dashboard.stop()
            await dashboard.wait_closed()


def test_dashboard_keeps_file_content_out_of_event_log():
    dashboard, rich, output = ui()
    dashboard.event(activity(1, "SAMURAI", "Samurai inspected source.py"))
    rich.print(dashboard.render())
    assert "source.py" in output.getvalue()
    assert "SECRET_KEY=" not in output.getvalue()


@pytest.mark.asyncio
async def test_authorization_plan_is_reviewable_without_closing_screen(guild):
    controller, mission, _, _, _ = guild
    await (await controller.start(mission.id, "plan"))
    dashboard, rich, output = ui()
    await dashboard.show_plan(controller, mission)
    assert dashboard.review_index == 0
    assert "SHOGUN PLAN" in dashboard.reviews[0][0]
    assert "test_profile:python_pytest" in dashboard.reviews[0][1]
    rich.print(dashboard.render())
    assert "SHOGUN PLAN" in output.getvalue() and "KAGE AI" in output.getvalue()


@pytest.mark.asyncio
async def test_opening_existing_stopped_mission_keeps_window_open_until_dismissed(guild):
    controller, mission, _, _, _ = guild
    await (await controller.start(mission.id, "plan"))
    async with controller.store.transaction() as db:
        await db.execute("UPDATE missions SET status='BLOCKED' WHERE id=?", (mission.id,))
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        dashboard.start()
        try:
            active = asyncio.create_task(dashboard.workflow(controller, mission.id))
            for _ in range(40):
                if dashboard.prompt_text or active.done():
                    break
                await asyncio.sleep(.05)
            if active.done():
                await active
            assert dashboard.live.is_running and not active.done()
            assert "Choose 1-6" in dashboard.prompt_text
            assert dashboard.reviews[-1][0] == "SAVED MISSION / CHOOSE AN ACTION"
            assert "1   Recorded activity" in dashboard.reviews[-1][1]
            assert "3   Next page of saved review" in dashboard.reviews[-1][1]
            assert dashboard.cursor > 0  # persisted event history is replayed
            title, text = dashboard.reviews[0]
            dashboard.reviews[0] = (title, text + "\n" + "\n".join(f"Recorded task detail {i}" for i in range(75)))
            pipe.send_text("3\r")
            await asyncio.sleep(.1)
            assert dashboard.reviews[dashboard.review_index][0] == "SAVED PLAN / RECORDED TASKS AND CHECKS"
            first_offset = dashboard.review_offset
            assert first_offset > 0
            assert not active.done() and dashboard._input_future is not None
            pipe.send_text("3\r")
            await asyncio.sleep(.1)
            assert dashboard.review_offset > first_offset and dashboard.live.is_running
            pane_width = dashboard.rich.width - (38 if dashboard.rich.width >= 96 else 4)
            last = len(dashboard._review_rows(pane_width)) - max(1, dashboard.rich.height - 10)
            dashboard.review_offset = last
            pipe.send_text("3\r")
            await asyncio.sleep(.1)
            assert "End of review" in dashboard.prompt_text
            assert dashboard.review_offset == last and not active.done()
            pipe.send_text("4\r")
            await asyncio.sleep(.1)
            assert dashboard.review_offset < last
            assert dashboard._input_future is not None and not active.done()
            frame = io.StringIO()
            RichConsole(file=frame, width=120, height=30, color_system=None).print(dashboard.render())
            assert "review 1/1" in frame.getvalue() and "1 of 2" not in frame.getvalue()
            pipe.send_text("1\r")
            await asyncio.sleep(.1)
            assert dashboard.review_index == -1 and dashboard.live.is_running and not active.done()
            pipe.send_text("2\r")
            await asyncio.sleep(.1)
            assert dashboard.reviews[dashboard.review_index][0] == "SAVED PLAN / RECORDED TASKS AND CHECKS"
            assert "test_profile:python_pytest" in dashboard.reviews[dashboard.review_index][1]
            assert not active.done()
            pipe.send_text("5\r")
            await asyncio.sleep(.1)
            assert dashboard.reviews[dashboard.review_index][0] == "SAVED MISSION / CHOOSE AN ACTION"
            pipe.send_text("\r")
            assert await asyncio.wait_for(active, 3) == 1
            assert (await controller.db.get_mission(mission.id)).status == MissionStatus.BLOCKED
        finally:
            dashboard.stop()
            await dashboard.wait_closed()


@pytest.mark.asyncio
async def test_interrupted_mission_explains_missing_reviews_instead_of_cycling_menu():
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        dashboard.mission_state(Mission(id="miss-interrupted", repository_id="repo", request_text="Fix status helper",
                                        status=MissionStatus.INTERRUPTED, failure_reason="Backend operation interrupted"))
        dashboard.start()
        try:
            paused = asyncio.create_task(dashboard.pause_at_end())
            await asyncio.sleep(.1)
            menu = dashboard.reviews[dashboard.review_index][1]
            assert "Start a fresh mission" in menu and "cannot be replayed safely" in menu
            assert "No saved reviews yet" in menu
            pipe.send_text("3\r")
            await asyncio.sleep(.1)
            assert dashboard.reviews[dashboard.review_index][0] == "NO SAVED REVIEWS"
            assert "Start a fresh mission" in dashboard.reviews[dashboard.review_index][1]
            assert not paused.done()
            pipe.send_text("5\r")
            await asyncio.sleep(.1)
            assert dashboard.reviews[dashboard.review_index][0] == "SAVED MISSION / CHOOSE AN ACTION"
            pipe.send_text("\r")
            await asyncio.wait_for(paused, 3)
        finally:
            dashboard.stop()
            await dashboard.wait_closed()


@pytest.mark.asyncio
async def test_saved_mission_menu_follow_up_requires_separate_creation_confirmation():
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        dashboard.mission_state(Mission(id="miss-interrupted", repository_id="repo", request_text="Fix status helper",
                                        status=MissionStatus.INTERRUPTED))
        dashboard.start()
        try:
            paused = asyncio.create_task(dashboard.pause_at_end())
            await asyncio.sleep(.1)
            assert "6   Continue as a fresh follow-up" in dashboard.reviews[dashboard.review_index][1]
            pipe.send_text("6\r")
            assert await asyncio.wait_for(paused, 3) == "follow-up"
            assert dashboard.live.is_running
        finally:
            dashboard.stop()
            await dashboard.wait_closed()


@pytest.mark.asyncio
async def test_saved_menu_six_previews_follow_up_without_creating_until_confirmed(guild):
    controller, mission, _, _, repo = guild
    await (await controller.start(mission.id, "plan"))
    async with controller.store.transaction() as db:
        await db.execute("UPDATE missions SET status='INTERRUPTED' WHERE id=?", (mission.id,))
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        dashboard.start()
        try:
            running = asyncio.create_task(dashboard.workflow(controller, mission.id))
            for _ in range(50):
                if dashboard.prompt_text or running.done():
                    break
                await asyncio.sleep(.05)
            assert "Choose 1-6" in dashboard.prompt_text
            pipe.send_text("6\r")
            for _ in range(50):
                if "What else" in dashboard.prompt_text or running.done():
                    break
                await asyncio.sleep(.05)
            assert "What else" in dashboard.prompt_text
            pipe.send_text("Keep the helper\r")
            for _ in range(50):
                if "CREATE FOLLOW-UP" in dashboard.prompt_text or running.done():
                    break
                await asyncio.sleep(.05)
            assert "CREATE FOLLOW-UP" in dashboard.prompt_text
            assert dashboard.reviews[dashboard.review_index][0] == "FOLLOW-UP / REVIEW BEFORE CREATION"
            pipe.send_text("Add an example too\r")
            for _ in range(50):
                if "Instruction added" in dashboard.prompt_text or running.done():
                    break
                await asyncio.sleep(.05)
            assert "Instruction added" in dashboard.prompt_text and not running.done()
            preview = dashboard.reviews[dashboard.review_index][1]
            assert "Keep the helper" in preview and "Add an example too" in preview
            pipe.send_text("/cancel\r")
            for _ in range(50):
                if "Choose 1-6" in dashboard.prompt_text or running.done():
                    break
                await asyncio.sleep(.05)
            assert "Choose 1-6" in dashboard.prompt_text and not running.done()
            assert dashboard.reviews[dashboard.review_index][0] == "SAVED MISSION / CHOOSE AN ACTION"
            pipe.send_text("\r")
            assert await asyncio.wait_for(running, 5) == 1  # The old run remains interrupted.
            assert len(await controller.db.list_missions()) == 1
            assert (await controller.db.get_mission(mission.id)).status == MissionStatus.INTERRUPTED
            assert (repo / "app.py").read_text() == "value = 1\n"
        finally:
            dashboard.stop()
            await dashboard.wait_closed()


@pytest.mark.asyncio
async def test_long_proposal_paging_keeps_input_and_other_reviews_available():
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        dashboard.start()
        try:
            await asyncio.sleep(.05)
            dashboard._review("PLAN", "keep this plan")
            await dashboard.show_test_proposal({"hash": "a" * 64, "proposal": {
                "mappings": [{"criterion_description": "new behavior", "test_selectors": ["test_kage_x.py::test_x"]}],
                "files": [{"path": "test_kage_x.py", "content": "\n".join(f"assert {i} == {i}" for i in range(80))}]}})
            pending = asyncio.create_task(dashboard.prompt("Type ACCEPT TESTS " + "a" * 64 + ": "))
            await asyncio.sleep(.05)
            assert dashboard.live.is_running and dashboard.review_index == 1
            assert "assert 79 == 79" in dashboard.reviews[1][1]
            pipe.send_text("\x1b[6~")  # PageDown scrolls review without changing or submitting input.
            await asyncio.sleep(.05)
            assert dashboard.review_offset > 0 and not pending.done()
            pipe.send_text("\x1b[17~")  # F6: previous review.
            await asyncio.sleep(.05)
            assert dashboard.review_index == 0 and dashboard.reviews[0][1] == "keep this plan"
            pipe.send_text("\x1b[18~")  # F7: return to acceptance test proposal.
            await asyncio.sleep(.05)
            assert dashboard.review_index == 1 and dashboard.review_offset == 0
            pipe.send_text("ACCEPT TESTS ")
            await asyncio.sleep(.05)
            dashboard.event(activity(1, "SENTINEL", "new status while typing"))
            await asyncio.sleep(.05)
            assert dashboard._input.text == "ACCEPT TESTS " and not pending.done()
            pipe.send_text("a" * 64 + "\r")
            assert await asyncio.wait_for(pending, 3) == "ACCEPT TESTS " + "a" * 64
            assert dashboard.live.is_running
        finally:
            dashboard.stop()
            await dashboard.wait_closed()


def test_full_clarification_is_kept_in_review_and_plain_output():
    from app.cli import Console

    question = "The existing task status test fails. " + "Which direction should we take? " * 55 + "Choose a CLI, API, or habit tracker."
    plain = []
    Console(say=plain.append).show_clarification(SimpleNamespace(question=question))
    assert question in plain[0]

    dashboard, rich, output = ui()
    dashboard.show_clarification(SimpleNamespace(question=question))
    assert dashboard.reviews[0][1] == question
    assert dashboard.review_index == 0
    rich.print(dashboard.render())
    assert "SHOGUN / QUESTION" in output.getvalue()
    assert "The existing task status test fails" in output.getvalue()
    dashboard.review_offset = max(0, len(dashboard._review_rows(74)) - 18)
    output.seek(0)
    output.truncate()
    rich.print(dashboard.render())
    assert "Choose a CLI, API, or habit tracker." in output.getvalue()


def test_wrapped_activity_keeps_latest_update_visible_and_markup_literal():
    dashboard, rich, output = ui()
    dashboard.mission_state(Mission(id="miss-test", repository_id="repo", request_text="test", status=MissionStatus.RUNNING))
    for index in range(1, 30):
        dashboard.event(activity(index, "SAMURAI", "Long previous activity " * 16))
    dashboard.event(activity(30, "SAMURAI", "LATEST [red]literal[/red] \x1b[2J update"))
    rich.print(dashboard.render())
    result = output.getvalue()
    assert "LATEST" in result and "[red]literal[/red]" in result
    assert "\x1b" not in result


def test_waiting_state_clears_live_agent_and_replay_is_deduplicated():
    dashboard, rich, output = ui()
    dashboard.mission_state(Mission(id="miss-test", repository_id="repo", request_text="test", status=MissionStatus.RUNNING))
    dashboard.event(activity(1, "SHOGUN", "Read files"))
    dashboard.event(activity(1, "SHOGUN", "Duplicated event"))
    assert dashboard.cursor == 1 and len(dashboard.lines) == 1
    dashboard.event(MissionEvent(sequence=2, mission_id="miss-test", event_type="PLAN_READY", source="CONTROLLER",
                                display_payload={"status": "READY_FOR_AUTHORIZATION"}))
    assert dashboard.active_agent is None
    dashboard.event(activity(3, "SHOGUN", "Plan needs approval", "proposal"))
    assert dashboard.active_agent is None
    rich.print(dashboard.render())
    assert "WAIT" in output.getvalue() and "LIVE" not in output.getvalue()


def test_clarification_highlights_user_and_verifier_shows_actual_start_and_verdict():
    dashboard, rich, output = ui()
    dashboard.mission_state(Mission(id="miss-test", repository_id="repo", request_text="Two Sum",
                                    status=MissionStatus.AWAITING_CLARIFICATION))
    dashboard.agent_states["SHOGUN"] = "LIVE"
    rich.print(dashboard.render())
    assert "YOU / Answer" in output.getvalue() and "ANSWER" in output.getvalue()
    assert dashboard.active_agent is None
    output.seek(0); output.truncate()
    dashboard.event(MissionEvent(sequence=1, mission_id="miss-test", source="VERIFIER", event_type="VERIFIER_STARTED",
                                 display_payload={"status": "VERIFYING", "summary": "Inspect recorded test evidence"}))
    assert dashboard.active_agent == "VERIFIER" and dashboard.agent_states["VERIFIER"] == "LIVE"
    dashboard.event(MissionEvent(sequence=2, mission_id="miss-test", source="CONTROLLER", event_type="VERIFICATION_PASSED",
                                 display_payload={"status": "VERIFIED_AWAITING_APPROVAL"}))
    assert dashboard.active_agent is None and dashboard.agent_states["VERIFIER"] == "PASS"
    dashboard.event(MissionEvent(sequence=3, mission_id="miss-test", source="VERIFIER", event_type="VERIFIER_ERROR",
                                 display_payload={"stage": "failed", "summary": "Evidence check stopped"}))
    assert dashboard.agent_states["VERIFIER"] == "FAIL"


def test_narrow_terminal_has_activity_and_current_agent_without_sidebar():
    dashboard, rich, output = ui()
    rich.width = 72
    dashboard.mission_state(Mission(id="miss-test", repository_id="repo", request_text="test", status=MissionStatus.RUNNING))
    dashboard.event(activity(1, "SAMURAI", "Working on custom.py"))
    rich.print(dashboard.render())
    assert "KAGE AI" in output.getvalue() and "Working on custom.py" in output.getvalue()
    assert "GUILD / ACTIVE AGENT" not in output.getvalue()


def test_cli_without_subcommand_starts_interactive_run(monkeypatch):
    from app import cli
    received = []

    async def fake_execute(args, console):
        received.append(args)
        return 0

    monkeypatch.setattr(cli, "execute", fake_execute)
    assert cli.main([], console=cli.Console(say=lambda _: None)) == 0
    assert received[0].command == "run"
    assert cli.main(["--plain"], console=cli.Console(say=lambda _: None)) == 0
    assert received[1].plain is True


def test_real_dashboard_starts_inside_main_event_loop_and_shuts_down(monkeypatch):
    from app import cli
    with create_pipe_input() as pipe:
        dashboard = GuildDashboard(terminal_input=pipe, terminal_output=DummyOutput())
        seen = []

        async def fake_execute(args, console):
            await asyncio.sleep(.05)
            seen.append((console.live.is_running, console._owner_task is asyncio.current_task()))
            return 0

        monkeypatch.setattr(cli, "execute", fake_execute)
        assert cli.main(["run"], console=dashboard) == 0
        assert seen == [(True, True)]
        assert dashboard.live is None and dashboard._runner is None


@pytest.mark.parametrize("arguments,terminal,expected", [
    (["run"], True, True), (["--plain", "run"], True, False),
    (["run"], False, False), (["proof", "miss-test", "--format", "json"], True, False),
])
def test_renderer_selection_preserves_plain_pipes_and_machine_readable_proof(arguments, terminal, expected):
    from types import SimpleNamespace
    from app.cli import parser, select_console
    stream = SimpleNamespace(isatty=lambda: terminal)
    console = select_console(parser().parse_args(arguments), stdout=stream, stdin=stream)
    assert isinstance(console, GuildDashboard) is expected


def test_status_changes_highlight_actual_agent_at_phase_start():
    dashboard, rich, output = ui()
    dashboard.mission_state(Mission(id="miss-test", repository_id="repo", request_text="test", status=MissionStatus.PLANNING))
    dashboard.event(MissionEvent(sequence=1, mission_id="miss-test", source="CONTROLLER", event_type="SHOGUN_STARTED",
                                display_payload={"status": "PLANNING"}))
    assert dashboard.active_agent == "SHOGUN"
    dashboard.event(MissionEvent(sequence=2, mission_id="miss-test", source="CONTROLLER", event_type="SAMURAI_STARTED",
                                display_payload={"status": "RUNNING"}))
    assert dashboard.active_agent == "SAMURAI"
    assert "Shogun / Planner  ->  Samurai / Developer" in dashboard.handoffs


@pytest.mark.asyncio
async def test_sidebar_uses_tasks_to_show_two_active_agents(guild):
    from app.schemas.task import TaskStatus
    controller, mission, _, _, _ = guild
    await (await controller.start(mission.id, "plan"))
    tasks = await controller.db.get_tasks(mission.id)
    async with controller.store.transaction() as db:
        await db.execute("UPDATE missions SET status='CHECKING' WHERE id=?", (mission.id,))
        for task in tasks:
            task.status = TaskStatus.RUNNING if task.owner_agent in {"SENTINEL", "SHADOW_COUNCIL"} else TaskStatus.DONE
            await controller.store._save(db, task)
    dashboard, rich, output = ui()
    await dashboard.sync_state(controller.db, mission.id)
    rich.print(dashboard.render())
    assert dashboard.agent_states["SENTINEL"] == dashboard.agent_states["SHADOW_COUNCIL"] == "LIVE"
    assert output.getvalue().count("LIVE") == 2
