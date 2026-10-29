import io

import pytest
from rich.console import Console as RichConsole

from app.cli_tui import GuildDashboard
from app.schemas.events import MissionEvent
from app.schemas.mission import Mission, MissionStatus
from tests.unit.test_m4_guild import guild


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
async def test_dashboard_stops_live_display_during_human_input(monkeypatch):
    dashboard, rich, output = ui()
    observations = []

    def answer(prompt):
        observations.append((dashboard.live, prompt))
        return "AUTHORIZE"

    monkeypatch.setattr(rich, "input", answer)
    dashboard.start()
    try:
        assert await dashboard.prompt("Type AUTHORIZE: ") == "AUTHORIZE"
        assert observations == [(None, "Type AUTHORIZE: ")]
        assert dashboard.live is not None
    finally:
        dashboard.stop()
    assert "KAGE AI" in output.getvalue()


def test_dashboard_keeps_file_content_out_of_event_log():
    dashboard, rich, output = ui()
    dashboard.event(activity(1, "SAMURAI", "Samurai inspected source.py"))
    rich.print(dashboard.render())
    assert "source.py" in output.getvalue()
    assert "SECRET_KEY=" not in output.getvalue()


@pytest.mark.asyncio
async def test_authorization_plan_is_fully_visible_outside_cropped_activity_log(guild):
    controller, mission, _, _, _ = guild
    await (await controller.start(mission.id, "plan"))
    dashboard, rich, output = ui()
    dashboard.start()
    await dashboard.show_plan(controller, mission)
    assert dashboard.live is None
    text = output.getvalue()
    assert "SHOGUN PLAN" in text and "test_profile:python_pytest" in text
