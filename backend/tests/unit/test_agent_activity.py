import asyncio
import json

import httpx
import pytest

from app.agents.model_adapter import ModelAdapter
from app.agents.samurai import SamuraiConfig, SamuraiRunner
from app.api.events import event_stream
from app.schemas.evidence import Evidence
from app.schemas.mission import Mission
from app.services.activity import tool_activity
from app.services.repository_service import RepositoryService
from app.services.workspace_service import WorkspaceService
from app.settings import Settings, get_settings
from app.storage.database import Database
from app.storage.guild import GuildStore
from tests.unit.test_m4_guild import guild, plan_and_execute


def response(calls, text=None):
    content = ([{"type": "text", "text": text}] if text else []) + [
        {"type": "tool_use", "id": ident, "name": name, "input": args} for ident, name, args in calls
    ]
    return httpx.Response(200, json={"content": content, "stop_reason": "tool_use",
                                     "usage": {"input_tokens": 5, "output_tokens": 5}})


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["ledger.py", "project_tasks.py"])
async def test_dynamic_samurai_activity_is_factual_and_replayable(tmp_path, monkeypatch, filename):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / filename).write_text("value = 1\nprivate_text = 'DO_NOT_STREAM'\n", encoding="utf-8")
    service = RepositoryService()
    monkeypatch.setattr(service, "_check_docker", lambda: True)
    record = service.connect_repository(str(repo))
    monkeypatch.setattr("app.services.repository_service._repo_service_instance", service)
    workspaces = WorkspaceService(tmp_path / "workspaces")
    db = Database(tmp_path / "activity.db")
    await db.init_db()
    mission = Mission(repository_id=record["repository_id"], request_text="Change the value")
    await db.create_mission(mission)
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        body = json.loads(request.content)
        if calls == 1:
            return response([("read", "read_file", {"relative_path": filename})], "private model analysis SHOULD_NOT_STREAM")
        if calls == 2:
            result = json.loads(body["messages"][-1]["content"][0]["content"])
            return response([("edit", "apply_patch", {"relative_path": filename, "target": "value = 1",
                                                        "replacement": "value = 2", "expected_fingerprint": result["fingerprint"]})])
        if calls == 3:
            return response([("readback", "read_file", {"relative_path": filename}),
                             ("diff", "read_diff", {"relative_path": filename})])
        return response([("submit", "submit_candidate", {"summary": "Changed the candidate"})])

    async def progress(payload, candidate_id=None):
        await db.emit_event(mission.id, "AGENT_ACTIVITY", "SAMURAI", payload, candidate_id=candidate_id)

    async with ModelAdapter(settings=Settings(model_provider="anthropic", anthropic_api_key="test-key",
                                              anthropic_base_url="https://example.test/v1"),
                            transport=httpx.MockTransport(handle)) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces, on_activity=progress,
                                     task_title="Change value").run(record["repository_id"], "Change the value", mission_id=mission.id)
    assert result.status == "CANDIDATE_READY"
    events = await Database(db.db_path).get_events(mission.id)
    assert [item.sequence for item in events] == list(range(1, len(events) + 1))
    assert any(item.display_payload.get("action") == "apply_patch" and item.display_payload.get("stage") == "intent" for item in events)
    changed = next(item for item in events if item.display_payload.get("action") == "apply_patch" and item.display_payload.get("stage") == "outcome")
    assert filename in changed.display_payload["summary"] and "workspace" in changed.display_payload["summary"]
    assert any(item.candidate_id == result.candidate.id and item.display_payload.get("candidate_fingerprint") == result.candidate.content_fingerprint for item in events)
    assert "SHOULD_NOT_STREAM" not in json.dumps([e.model_dump(mode="json") for e in events])
    assert "DO_NOT_STREAM" not in json.dumps([e.model_dump(mode="json") for e in events])
    assert (repo / filename).read_text().startswith("value = 1")

    class OpenConnection:
        async def is_disconnected(self):
            return False

    stream = event_stream(Database(db.db_path), mission.id, OpenConnection(), events[-2].sequence, interval=0)
    assert f"id: {events[-1].sequence}\n" in await asyncio.wait_for(anext(stream), 2)
    await stream.aclose()


@pytest.mark.asyncio
async def test_denied_edit_never_emits_success_and_does_not_expose_key(tmp_path, monkeypatch):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "inventory.py").write_text("value = 1\n")
    service = RepositoryService()
    monkeypatch.setattr(service, "_check_docker", lambda: True)
    record = service.connect_repository(str(repo))
    monkeypatch.setattr("app.services.repository_service._repo_service_instance", service)
    monkeypatch.setattr(get_settings(), "azure_openai_api_key", "test-private-key")
    workspaces = WorkspaceService(tmp_path / "workspaces")
    db = Database(tmp_path / "activity.db")
    await db.init_db()
    mission = Mission(repository_id=record["repository_id"], request_text="Try an invalid edit")
    await db.create_mission(mission)
    calls = 0

    def handle(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return response([("read", "read_file", {"relative_path": "inventory.py"})])
        return response([("stale", "apply_patch", {"relative_path": "inventory.py", "expected_fingerprint": "0" * 64,
                                                   "target": "value = 1", "replacement": "test-private-key"})])

    async def progress(payload, candidate_id=None):
        await db.emit_event(mission.id, "AGENT_ACTIVITY", "SAMURAI", payload, candidate_id=candidate_id)

    async with ModelAdapter(settings=Settings(model_provider="anthropic", anthropic_api_key="test-key",
                                              anthropic_base_url="https://example.test/v1"),
                            transport=httpx.MockTransport(handle)) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces, on_activity=progress,
                                     config=SamuraiConfig(max_consecutive_errors=1)).run(record["repository_id"], "Try invalid edit", mission_id=mission.id)
    events = await db.get_events(mission.id)
    assert result.status == "BLOCKED"
    assert any(e.display_payload.get("action") == "apply_patch" and e.display_payload.get("stage") == "failed" for e in events)
    assert not any(e.display_payload.get("action") == "apply_patch" and e.display_payload.get("stage") == "outcome" for e in events)
    assert "test-private-key" not in json.dumps([e.model_dump(mode="json") for e in events])
    assert (repo / "inventory.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_controller_activity_tracks_real_agent_roles_and_evidence(guild):
    controller, mission, _, _, _ = guild
    result = await plan_and_execute(guild)
    events = [event for event in await controller.db.get_events(mission.id) if event.event_type == "AGENT_ACTIVITY"]
    assert {event.source for event in events} >= {"SHOGUN", "SAMURAI", "SENTINEL", "SHADOW_COUNCIL", "CONTROLLER"}
    assert events and all(event.display_payload["summary"] for event in events)
    evidence = {item.id: item for item in await controller.store.records(Evidence, mission.id)}
    sentinel = [event for event in events if event.source == "SENTINEL" and event.display_payload.get("stage") == "outcome"]
    assert sentinel and all(event.evidence_ids and all(ref in evidence for ref in event.evidence_ids) for event in sentinel)
    failed = [event for event in sentinel if event.candidate_id == result.active_candidate_id]
    assert failed and all("did not pass" in event.display_payload["summary"] for event in failed)
    assert not any("passed" in event.display_payload["summary"] for event in failed)
    assert any(event.source == "CONTROLLER" and event.display_payload.get("action") == "route_findings" for event in events)


def test_activity_messages_are_bounded_and_never_echo_raw_content():
    message = tool_activity("SAMURAI", "apply_patch", "outcome", path="src/" + "example_" * 50 + ".py", mode="edit")
    assert len(message["summary"]) <= 360
    assert len(message["relative_path"]) <= 180
    assert "edited" in message["summary"]
