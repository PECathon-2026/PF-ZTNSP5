"""Live M4 routing demo: real model + restricted Docker, never a host fallback."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.schemas.agent_message import AgentMessage, MessageType
from app.schemas.evidence import Evidence
from app.schemas.finding import Finding
from app.schemas.mission import AcceptanceCriterion, Mission, MissionStatus
from app.services.guild_service import GuildController
from app.services.repository_service import get_repository_service


async def smoke(recovery=False):
    milestone = "M5" if recovery else "M4"
    controller = GuildController(auto_repair=recovery)
    await controller.db.init_db()
    with TemporaryDirectory(prefix=f"devpilot-{milestone.lower()}-") as directory:
        repo = Path(directory)
        (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
        expected = 3 if recovery else 1
        (repo / "test_app.py").write_text(f"from app import value\n\ndef test_value():\n    assert value == {expected}\n", encoding="utf-8")
        repository = get_repository_service().connect_repository(str(repo))
        mission = Mission(
            repository_id=repository["repository_id"], status=MissionStatus.PLANNING,
            request_text=("M5 adaptive-recovery demonstration: the initial plan must have exactly one task, deliberately setting app.py value to 2. "
                          "After that candidate fails the existing test expecting 3, use the failure finding to replan and repair value to 3. "
                          "Keep tests unchanged; the final acceptance criterion is value 3." if recovery else
                          "M4 failure-routing demonstration: change app.py value from 1 to 2. "
                          "Keep the existing test unchanged; its expected failure demonstrates the Sentinel-to-Samurai feedback route. "
                          "Use one implementation task. Do not change tests."),
        )
        await controller.db.create_mission(mission, [AcceptanceCriterion(mission_id=mission.id, description=f"Source value becomes {3 if recovery else 2}")])
        try:
            await (await controller.start(mission.id, "plan"))
            planned = await controller.db.get_mission(mission.id)
            if planned.status == MissionStatus.READY_FOR_AUTHORIZATION:
                # Explicitly invoking this demo authorizes its synthetic-repository pass.
                await (await controller.start(mission.id, "execute", planned.scope_version))
            result = await controller.db.get_mission(mission.id)
            tasks = await controller.db.get_tasks(mission.id)
            messages = await controller.store.records(AgentMessage, mission.id)
            evidence = await controller.store.records(Evidence, mission.id)
            findings = await controller.store.records(Finding, mission.id)
            routed = {m.recipient for m in messages if m.type == MessageType.FINDING and m.sender == "SENTINEL"}
            passed = result.status == MissionStatus.REPAIRING and {"SHOGUN", "SAMURAI"} <= routed and any(t.owner_agent == "SAMURAI" and t.attempt == 2 for t in tasks)
            if recovery:
                passed = (result.status == MissionStatus.VERIFYING and result.budgets.repair_rounds_used >= 1
                          and {"SHOGUN", "SAMURAI"} <= routed and any(f.status.value == "RESOLVED" for f in findings))
            report = {
                "milestone": milestone, "mode": "real model and container-only checks", "exit_check_passed": passed,
                "original_unchanged": (repo / "app.py").read_text(encoding="utf-8") == "value = 1\n",
                "mission": result.model_dump(mode="json"), "tasks": [t.model_dump(mode="json") for t in tasks],
                "evidence": [e.model_dump(mode="json") for e in evidence],
                "findings": [f.model_dump(mode="json") for f in findings],
                "messages": [m.model_dump(mode="json") for m in messages],
            }
            filename = milestone.lower() + "-smoke.json"
            artifact_id, _ = controller.artifacts.save_artifact(mission.id, filename, json.dumps(report, indent=2))
            print(json.dumps({"status": result.status.value, "exit_check_passed": passed, "reason": result.failure_reason}))
            print(f"Evidence: {controller.artifacts.base_dir / mission.id / (artifact_id + '_' + filename)}")
            return 0 if passed and report["original_unchanged"] else 1
        finally:
            await controller.close()
            get_repository_service()._repositories.pop(repository["repository_id"], None)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(smoke()))
