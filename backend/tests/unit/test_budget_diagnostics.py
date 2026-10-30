"""Explicit new-mission ceilings and precise developer budget diagnostics."""

import json

import httpx
import pytest

from app.main import app
from app.agents.samurai import SamuraiConfig, SamuraiRunner
from app.schemas.mission import MissionBudgets
from app.services.budgets import BudgetExceeded
from app.storage.database import Database
from tests.unit.test_m3_agents import workspace, scripted_adapter, happy_actions, adapter_for, envelope


@pytest.mark.asyncio
@pytest.mark.parametrize("config,dimension", [
    (SamuraiConfig(max_turns=1), "model_turns"),
    (SamuraiConfig(max_tool_calls=1), "tool_calls"),
    (SamuraiConfig(max_tokens=1), "reported_tokens"),
    (SamuraiConfig(max_context_chars=1000), "context_chars"),
])
async def test_exact_exhausted_dimension_and_original_preservation(workspace, config, dimension):
    repo, repo_id, workspaces = workspace
    request = "x" * 1200 if dimension == "context_chars" else "Change value to two"
    async with scripted_adapter(happy_actions()) as adapter:
        result = await SamuraiRunner(adapter, config=config, workspace_service=workspaces).run(repo_id, request)
    assert result.status == "BUDGET_EXHAUSTED"
    assert result.exhausted_budget == dimension
    assert result.budget_used >= result.budget_limit
    assert dimension.replace("_", " ") in result.summary
    assert "new mission" in result.summary
    assert result.candidate is None and not workspaces._leases
    assert (repo / "app.py").read_text() == "value = 1\n"


def test_task_limits_use_remaining_authorized_tokens_and_keep_hard_caps():
    budgets = MissionBudgets(max_model_turns=60, model_turns_used=15, max_tool_calls=100,
                             tool_calls_used=10, max_tokens=320000, input_tokens_used=40000)
    config = SamuraiConfig.for_mission(budgets)
    assert config.max_turns == 20 and config.max_tool_calls == 50
    assert config.max_tokens == 280000
    budgets.model_turns_used = 59
    assert SamuraiConfig.for_mission(budgets).max_turns == 1
    budgets.model_turns_used = 60
    with pytest.raises(BudgetExceeded):
        SamuraiConfig.for_mission(budgets)


@pytest.mark.asyncio
async def test_handoff_above_old_60k_default_when_mission_authorizes_it(workspace):
    repo, repo_id, workspaces = workspace
    actions = iter(happy_actions())

    def handler(request):
        action = next(actions)
        body = json.loads(request.content)
        response = envelope(action(body) if callable(action) else action)
        response["usage"] = {"input_tokens": 20000, "output_tokens": 100}
        return httpx.Response(200, json=response)

    async with adapter_for(handler) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces,
            config=SamuraiConfig.for_mission(MissionBudgets())).run(repo_id, "Change value to two")
    assert result.status == "CANDIDATE_READY"
    assert result.input_tokens + result.output_tokens == 80400
    assert result.exhausted_budget is None
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_api_persists_selected_limits_without_accepting_usage_counters(tmp_path, monkeypatch):
    db = Database(tmp_path / "limits.db")
    await db.init_db()
    monkeypatch.setattr("app.api.missions.get_database", lambda: db)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        limits = {"max_model_turns": 60, "max_tool_calls": 100, "max_tokens": 320000, "max_time_seconds": 900}
        response = await client.post("/api/missions", json={"repository_id": "repo", "request_text": "Task", "limits": limits})
        assert response.status_code == 201
        mission = await db.get_mission(response.json()["mission"]["id"])
        for key, value in limits.items():
            assert getattr(mission.budgets, key) == value
        assert mission.budgets.model_turns_used == 0 and mission.budgets.max_repair_rounds == 3
        events = await db.get_events(mission.id)
        assert events[0].display_payload["limits"] == limits
        default = await client.post("/api/missions", json={"repository_id": "repo", "request_text": "Small task"})
        assert default.json()["mission"]["budgets"]["max_model_turns"] == 25
        for invalid in [{"max_model_turns": 101}, {"max_tokens": 0}, {"model_turns_used": 0}, {"max_repair_rounds": 99}]:
            denied = await client.post("/api/missions", json={"repository_id": "repo", "request_text": "Task", "limits": invalid})
            assert denied.status_code == 422
