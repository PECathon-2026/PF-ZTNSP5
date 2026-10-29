import asyncio
import json

import httpx
import pytest

from app.api.events import event_stream, frame, mission_events
from app.main import app
from app.schemas.mission import Mission, MissionStatus
from app.storage.database import Database


class Connected:
    async def is_disconnected(self):
        return False


@pytest.mark.asyncio
async def test_persisted_replay_cursor_and_live_follow_up(tmp_path):
    db = Database(tmp_path / "events.db")
    await db.init_db()
    mission = Mission(repository_id="repo", request_text="test")
    await db.create_mission(mission)
    for number in range(3):
        await db.emit_event(mission.id, f"STEP_{number}", "CONTROLLER", {"status": "RUNNING"})
    source = event_stream(db, mission.id, Connected(), 1, interval=0)
    second = await anext(source)
    third = await anext(source)
    assert second.startswith("id: 2\nevent: mission\ndata: ")
    assert third.startswith("id: 3\nevent: mission\ndata: ")
    await db.emit_event(mission.id, "DONE", "CONTROLLER", {"status": "VERIFYING"})
    fourth = await asyncio.wait_for(anext(source), 2)
    assert fourth.startswith("id: 4\n")
    assert json.loads(fourth.split("data: ")[1])["event_type"] == "DONE"
    await source.aclose()
    replay = event_stream(Database(db.db_path), mission.id, Connected(), 3, interval=0)
    assert (await anext(replay)).startswith("id: 4\n")
    await replay.aclose()


@pytest.mark.asyncio
async def test_sse_heartbeat_is_not_an_event(tmp_path):
    db = Database(tmp_path / "heartbeat.db")
    await db.init_db()
    mission = Mission(repository_id="repo", request_text="test")
    await db.create_mission(mission)
    source = event_stream(db, mission.id, Connected(), 0, interval=0)
    assert await asyncio.wait_for(anext(source), 2) == ": heartbeat\n\n"
    await source.aclose()


@pytest.mark.asyncio
async def test_sse_endpoint_validates_cursor_and_mission(tmp_path, monkeypatch):
    db = Database(tmp_path / "endpoint.db")
    await db.init_db()
    mission = Mission(repository_id="repo", request_text="test")
    await db.create_mission(mission)
    monkeypatch.setattr("app.api.events.get_database", lambda: db)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/missions/missing/events")).status_code == 404
        assert (await client.get(f"/api/missions/{mission.id}/events", headers={"Last-Event-ID": "abc"})).status_code == 400
        assert (await client.get(f"/api/missions/{mission.id}/events?after=-1")).status_code == 422


@pytest.mark.asyncio
async def test_guild_events_show_real_status_and_redact_key(tmp_path, monkeypatch):
    from app.settings import get_settings
    from app.storage.guild import GuildStore
    monkeypatch.setattr(get_settings(), "azure_openai_api_key", "synthetic-secret")
    db = Database(tmp_path / "guild.db")
    await db.init_db()
    mission = Mission(repository_id="repo", request_text="test", status=MissionStatus.PLANNING)
    await db.create_mission(mission)
    token = await GuildStore(db).claim(mission.id, "plan")
    await GuildStore(db).commit(mission.id, token, event="PREFLIGHT_STARTED")
    event = (await db.get_events(mission.id))[0]
    assert event.display_payload["status"] == "PREFLIGHT"
    payload = frame(event)
    assert "synthetic-secret" not in payload and "PREFLIGHT" in payload
