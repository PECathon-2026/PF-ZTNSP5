"""History pagination and immutable baseline endpoint regressions."""

import httpx
import pytest

from app.main import app
from app.schemas.mission import Mission
from app.services.guild_service import GuildController
from app.services.repository_service import RepositoryService
from app.services.workspace_service import WorkspaceService
from app.storage.artifacts import ArtifactStorage
from app.storage.database import Database


@pytest.mark.asyncio
async def test_history_pages_are_ordered_bounded_and_mission_scoped(tmp_path, monkeypatch):
    db = Database(tmp_path / "history.db")
    await db.init_db()
    mission = Mission(repository_id="repo", request_text="History")
    other = Mission(repository_id="repo", request_text="Other")
    await db.create_mission(mission)
    await db.create_mission(other)
    for _ in range(5):
        await db.emit_event(mission.id, "STEP", "SAMURAI", {"summary": "Read source"})
    await db.emit_event(other.id, "OTHER", "SHOGUN", {})
    monkeypatch.setattr("app.api.history.get_database", lambda: db)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        root = f"/api/missions/{mission.id}/history"
        first = (await client.get(root + "?limit=2")).json()
        assert [e["sequence"] for e in first["events"]] == [1, 2]
        assert first["has_more"] and first["next_cursor"] == 2
        last = (await client.get(root + "?after=2")).json()
        assert [e["sequence"] for e in last["events"]] == [3, 4, 5]
        assert not last["has_more"]
        assert all(e["mission_id"] == mission.id for e in last["events"])
        assert (await client.get(root + "?limit=101")).status_code == 422
        assert (await client.get(root + "?after=-1")).status_code == 422
        assert (await client.get("/api/missions/missing/history")).status_code == 404


@pytest.mark.asyncio
async def test_baseline_uses_frozen_snapshot_and_rejects_tamper(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "source.py").write_text("value = 1\n")
    repositories = RepositoryService()
    monkeypatch.setattr(repositories, "_check_docker", lambda: True)
    record = repositories.connect_repository(str(repo))
    monkeypatch.setattr("app.services.repository_service._repo_service_instance", repositories)
    db = Database(tmp_path / "baseline.db")
    await db.init_db()
    workspaces = WorkspaceService(tmp_path / "workspaces")
    controller = GuildController(db, workspaces, ArtifactStorage(tmp_path / "artifacts"))
    mission = Mission(repository_id=record["repository_id"], request_text="Baseline")
    await db.create_mission(mission)
    workspaces.create_disposable_workspace(mission.id, mission.repository_id)
    candidate = workspaces.freeze_candidate(mission.id, mission.repository_id)
    async with controller.store.transaction() as connection:
        await controller.store._save(connection, candidate)
        import json
        await connection.execute("INSERT INTO guild_context VALUES (?,?)", (
            mission.id, json.dumps({"baseline_candidate_id": candidate.id})))
    monkeypatch.setattr("app.api.history.get_guild_controller", lambda: controller)
    (repo / "source.py").write_text("value = 99\n")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        root = f"/api/missions/{mission.id}/baseline/file"
        assert (await client.get(root, params={"path": "source.py"})).json()["content"] == "value = 1\n"
        assert (await client.get(root, params={"path": "../outside.py"})).status_code == 403
        assert (await client.get(root, params={"path": ".env"})).status_code == 403
        assert (await client.get(root, params={"path": "missing.py"})).status_code == 404
        (workspaces.get_candidate_dir(mission.id, candidate.id) / "source.py").write_text("tampered\n")
        assert (await client.get(root, params={"path": "source.py"})).status_code == 409
    await controller.close()
