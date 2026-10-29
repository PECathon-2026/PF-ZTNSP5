import json

import pytest

from app import evaluation
from app.schemas.mission import MissionStatus
from app.services.approval_service import ApprovalService
from app.services.guild_service import GuildController
from app.services.workspace_service import WorkspaceService
from app.storage.artifacts import ArtifactStorage
from app.storage.database import Database


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", evaluation.SCENARIOS, ids=lambda item: item.name)
async def test_five_scenario_trajectories_are_isolated_and_truthful(tmp_path, scenario):
    result = await evaluation.evaluate_one(scenario, "controlled", tmp_path)
    assert result["exit_check_passed"] is True
    assert result["mode"] == "controlled" and result["status"] == "VERIFYING"
    assert result["original_unchanged"] is True
    assert result["verifier_invoked"] is False and result["original_patch_applied"] is False
    assert result["repair_rounds"] == scenario.repairs
    assert all(item["controlled_evaluation"] for item in result["evidence"] if item["kind"] in {"TEST", "BASELINE"})
    assert all(item["candidate_dir"].startswith(str(tmp_path)) for item in result["checks"])
    roles = {item["role"] for item in result["model_tool_trajectory"]}
    assert {"plan", "developer", "review"} <= roles
    if scenario.repairs:
        assert "repair" in roles
        assert any(item["recipient"] == "SAMURAI" and item["type"] == "FINDING" for item in result["messages"])
    if scenario.name == "security":
        assert any(f["source"] == "SHADOW_COUNCIL" and f["severity"] == "BLOCKING" and f["status"] == "RESOLVED" for f in result["findings"])
    if scenario.clarification:
        assert result["clarifications"][0]["status"] == "ANSWERED"
    assert json.loads((tmp_path / f"{scenario.name}.json").read_text())["exit_check_passed"]


@pytest.mark.asyncio
async def test_controlled_checks_cannot_pass_independent_verification(tmp_path):
    scenario = evaluation.SCENARIOS[1]
    report = await evaluation.evaluate_one(scenario, "controlled", tmp_path)
    mission_dir = next((tmp_path / "workspaces").iterdir())
    db = Database(tmp_path / "bug.db")
    controller = GuildController(database=db, workspaces=WorkspaceService(tmp_path / "workspaces"),
                                 artifacts=ArtifactStorage(tmp_path / "artifacts"))
    try:
        mission_id = mission_dir.name
        assert (await db.get_mission(mission_id)).status == MissionStatus.VERIFYING
        result = await ApprovalService(controller).verify(mission_id)
        assert result.status == MissionStatus.FAILED_VERIFICATION
    finally:
        await controller.close()


@pytest.mark.asyncio
async def test_missing_docker_records_five_blocked_live_scenarios(tmp_path, monkeypatch):
    async def unavailable(self):
        return False

    monkeypatch.setattr(evaluation, "RESULTS", tmp_path)
    monkeypatch.setattr(evaluation.ContainerExecutor, "available", unavailable)
    assert await evaluation.main("live") == 1
    run_dir = next(tmp_path.iterdir())
    summary = json.loads((run_dir / "summary.json").read_text())
    assert len(summary["scenarios"]) == 5
    assert all(item["status"] == "BLOCKED" and not item["passed"] for item in summary["scenarios"])
    for scenario in evaluation.SCENARIOS:
        detail = json.loads((run_dir / f"{scenario.name}.json").read_text())
        assert detail["mode"] == "live" and detail["exit_check_passed"] is False
