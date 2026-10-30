"""BYOK isolation, restart behavior and secret persistence regressions."""

import json
import httpx
import pytest

from app.main import app
from app.schemas.mission import CreateMissionRequest, Mission, MissionStatus
from app.security.redaction import redact_secrets
from app.services import mission_credentials as credentials
from app.services.guild_service import GuildController
from app.agents.model_adapter import ModelAdapter
from app.settings import Settings
from app.storage.database import Database
from tests.unit.test_m4_guild import guild


@pytest.fixture(autouse=True)
def configured_keys(monkeypatch):
    credentials.clear_mission_keys()
    settings = Settings(model_provider="anthropic", anthropic_api_key="server-demo-secret",
                        anthropic_base_url="https://provider.example/v1", model_name="demo-model")
    monkeypatch.setattr("app.settings._settings_instance", settings)
    yield settings
    credentials.clear_mission_keys()


def test_keys_are_isolated_redacted_and_settings_unchanged(configured_keys):
    credentials.set_mission_key("one", "first-demo-secret")
    credentials.set_mission_key("two", "second-demo-secret")
    assert credentials.mission_settings("one").model_api_key == "first-demo-secret"
    assert credentials.mission_settings("two").model_api_key == "second-demo-secret"
    assert configured_keys.model_api_key == "server-demo-secret"
    assert redact_secrets("first-demo-secret second-demo-secret server-demo-secret") == "[REDACTED] [REDACTED] [REDACTED]"
    request = CreateMissionRequest(repository_id="repo", request_text="Fix", api_key="first-demo-secret")
    assert "first-demo-secret" not in repr(request)
    assert "api_key" not in request.model_dump()
    credentials.clear_mission_keys()
    with pytest.raises(ValueError, match="Re-enter"):
        credentials.mission_settings("one")


@pytest.mark.parametrize("url", ["https://provider.example/v1/", "http://localhost:11434/v1", "https://[::1]:8080/v1"])
def test_mission_specific_base_url_is_normalized_and_overrides_only_that_mission(configured_keys, url):
    credentials.set_mission_key("one", "first-demo-secret", url)
    configured = credentials.mission_settings("one")
    assert configured.model_base_url == url.rstrip("/")
    assert configured.model_api_key == "first-demo-secret"
    assert configured_keys.model_base_url == "https://provider.example/v1"


@pytest.mark.parametrize("url", ["http://provider.example/v1", "https://user:password@provider.example/v1",
                                 "https://provider.example/v1?key=bad", "https://provider.example/#fragment",
                                 "http://192.168.1.10/v1", "https://169.254.169.254/v1", "file:///etc/passwd",
                                 "https://provider.example/v1\nheader", "https://provider.example:0/v1",
                                 "http://127.1/v1", "http://0x7f000001/v1"])
def test_malformed_or_unsafe_base_url_is_rejected_without_storing_key(url):
    with pytest.raises(ValueError):
        credentials.set_mission_key("bad", "secret-key", url)
    assert not credentials.has_mission_key("bad")


@pytest.mark.asyncio
async def test_creation_never_persists_or_returns_key_and_restart_has_no_fallback(tmp_path, monkeypatch):
    db = Database(tmp_path / "credentials.db")
    await db.init_db()
    monkeypatch.setattr("app.api.missions.get_database", lambda: db)
    controller = GuildController(database=db)
    monkeypatch.setattr("app.api.guild.get_guild_controller", lambda: controller)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/missions", json={"repository_id": "repo", "request_text": "Fix", "api_key": "user-demo-secret"})
        assert response.status_code == 201, response.text
        assert "user-demo-secret" not in response.text
        detail = response.json()
        mission_id = detail["mission"]["id"]
        assert detail["own_api_key"] and detail["api_key_ready"]
        context = await controller.store.context(mission_id)
        assert context == {"own_api_key": True}
        events = await db.get_events(mission_id)
        assert "user-demo-secret" not in json.dumps([e.model_dump(mode="json") for e in events])
        adapter = await controller._model_adapter(mission_id)
        assert adapter._api_key == "user-demo-secret"
        await adapter._client.aclose()
        credentials.clear_mission_keys()
        response = await client.post(f"/api/missions/{mission_id}/plan")
        assert response.status_code == 409 and "Re-enter" in response.text
        assert not controller.jobs
        response = await client.post(f"/api/missions/{mission_id}/credentials", json={"api_key": "replacement-demo-secret"})
        assert response.status_code == 200 and response.json()["api_key_ready"]
        assert "replacement-demo-secret" not in response.text
        assert (await controller.store.context(mission_id)) == {"own_api_key": True}
        malformed = await client.post(f"/api/missions/{mission_id}/credentials", json={"api_key": ["must-not-be-echoed-secret"]})
        assert malformed.status_code == 422
        assert "must-not-be-echoed-secret" not in malformed.text
        controller.jobs[mission_id] = object()
        rejected = await client.post(f"/api/missions/{mission_id}/credentials", json={"api_key": "mid-flight-secret"})
        assert rejected.status_code == 409
        assert credentials.mission_settings(mission_id).model_api_key == "replacement-demo-secret"
        controller.jobs.clear()
    await controller.close()
    assert not credentials.has_mission_key(mission_id)


@pytest.mark.asyncio
async def test_custom_url_create_and_reentry_are_ephemeral_and_redacted(tmp_path, monkeypatch):
    db = Database(tmp_path / "custom-url.db")
    await db.init_db()
    monkeypatch.setattr("app.api.missions.get_database", lambda: db)
    controller = GuildController(database=db)
    monkeypatch.setattr("app.api.guild.get_guild_controller", lambda: controller)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {"repository_id": "repo", "request_text": "Fix", "api_key": "mission-secret", "base_url": "https://custom.example/v1/"}
        response = await client.post("/api/missions", json=payload)
        assert response.status_code == 201
        mission_id = response.json()["mission"]["id"]
        assert "mission-secret" not in response.text and "custom.example" not in response.text
        assert credentials.mission_settings(mission_id).model_base_url == "https://custom.example/v1"
        assert (await controller.store.context(mission_id)) == {"own_api_key": True}
        credentials.clear_mission_keys()
        reentry = await client.post(f"/api/missions/{mission_id}/credentials",
                                    json={"api_key": "new-secret", "base_url": "https://second.example/v1"})
        assert reentry.status_code == 200 and reentry.json()["api_key_ready"]
        assert "new-secret" not in reentry.text and "second.example" not in reentry.text
        assert credentials.mission_settings(mission_id).model_base_url == "https://second.example/v1"
        assert (await controller.store.context(mission_id)) == {"own_api_key": True}
        rejected = await client.post("/api/missions", json={"repository_id": "repo", "request_text": "Fix", "base_url": "https://second.example/v1"})
        assert rejected.status_code == 422
        invalid = await client.post("/api/missions", json={**payload, "base_url": "https://secret:password@provider.example/v1"})
        assert invalid.status_code == 422 and "password" not in invalid.text
    await controller.close()


@pytest.mark.asyncio
async def test_connection_probe_uses_provider_protocol_without_echoing_secrets(configured_keys, monkeypatch):
    actual = ModelAdapter

    def handle(request):
        assert str(request.url) == "https://custom.example/v1/messages"
        assert request.headers["x-api-key"] == "probe-secret"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "OK"}],
                                         "stop_reason": "end_turn", "usage": {"input_tokens": 2, "output_tokens": 1}})

    monkeypatch.setattr("app.agents.model_adapter.ModelAdapter", lambda **kwargs: actual(
        **kwargs, transport=httpx.MockTransport(handle)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        checked = await client.post("/api/model-config/validate", json={"api_key": "probe-secret", "base_url": "https://custom.example/v1"})
        assert checked.status_code == 200 and checked.json()["valid"]
        assert "probe-secret" not in checked.text
        malformed = await client.post("/api/model-config/validate", json={"api_key": ["sensitive-secret"], "base_url": "https://custom.example/v1"})
        assert malformed.status_code == 422 and "sensitive-secret" not in malformed.text

    monkeypatch.setattr("app.agents.model_adapter.ModelAdapter", lambda **kwargs: actual(
        **kwargs, transport=httpx.MockTransport(lambda _: httpx.Response(401))))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.post("/api/model-config/validate", json={"api_key": "probe-secret", "base_url": "https://custom.example/v1"})
        assert denied.status_code == 400
        assert "probe-secret" not in denied.text and "custom.example" not in denied.text


@pytest.mark.asyncio
async def test_planning_preserves_byok_scope_and_custom_endpoint(guild, configured_keys, monkeypatch):
    controller, previous, model, _, _ = guild
    mission = Mission(repository_id=previous.repository_id, request_text="Return value 2", status=MissionStatus.PLANNING)
    await controller.db.create_mission(mission)
    credentials.set_mission_key(mission.id, "my-secret", "https://custom.example/v1")
    async with controller.store.transaction() as db:
        await db.execute("INSERT INTO guild_context VALUES (?,?)", (mission.id, '{"own_api_key":true}'))

    async def adapter(mission_id):
        assert mission_id == mission.id
        assert credentials.mission_settings(mission_id).model_base_url == "https://custom.example/v1"
        return model.factory()

    monkeypatch.setattr(controller, "_model_adapter", adapter)
    await (await controller.start(mission.id, "plan"))
    assert (await controller.db.get_mission(mission.id)).status.value == "READY_FOR_AUTHORIZATION"
    assert (await controller.store.context(mission.id))["own_api_key"] is True
    credentials.clear_mission_keys()
    with pytest.raises(Exception, match="Re-enter"):
        await controller.start(mission.id, "execute", 1)


@pytest.mark.asyncio
async def test_server_key_missions_keep_injected_adapter_and_azure_override(tmp_path, configured_keys):
    db = Database(tmp_path / "normal.db")
    await db.init_db()
    sentinel = object()
    controller = GuildController(database=db, adapter_factory=lambda: sentinel)
    mission = Mission(repository_id="repo", request_text="Normal")
    await db.create_mission(mission)
    assert await controller._model_adapter(mission.id) is sentinel
    configured_keys.model_provider = "azure_openai"
    configured_keys.azure_openai_base_url = "https://azure.example/openai/v1"
    configured_keys.azure_openai_deployment = "demo-deployment"
    configured_keys.azure_openai_api_key = "azure-server-secret"
    credentials.set_mission_key("azure", "azure-user-secret")
    assert credentials.mission_settings("azure").model_api_key == "azure-user-secret"
    assert configured_keys.azure_openai_api_key == "azure-server-secret"
    await controller.close()
