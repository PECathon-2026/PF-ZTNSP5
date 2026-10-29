"""Run a real backend-only M6 mission; never approve or apply on behalf of a user.

From backend/: python -m app.agents.backend_live_demo
The disposable source repository and candidate persist under ignored backend/data/.
"""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from app.schemas.candidate import Candidate
from app.schemas.mission import AcceptanceCriterion, Mission, MissionBudgets, MissionStatus
from app.services.approval_service import ApprovalService
from app.services.guild_service import GuildController
from app.services.repository_service import get_repository_service
from app.settings import get_settings


async def main():
    settings = get_settings()
    repo = settings.data_dir.resolve() / "demo-repos" / f"backend-m6-{uuid4().hex[:12]}"
    repo.mkdir(parents=True)
    (repo / "math_ops.py").write_text("def total(items):\n    return sum(items)\n", encoding="utf-8")
    (repo / "legacy.py").write_text("def old_total(items):\n    return sum(items)\n", encoding="utf-8")
    (repo / "test_math_ops.py").write_text(
        "from pathlib import Path\nfrom math_ops import total, average\n\n"
        "def test_total():\n    assert total([1, 2]) == 3\n\n"
        "def test_average():\n    assert average([2, 4]) == 3\n    assert average([]) == 0\n\n"
        "def test_no_legacy():\n    assert not Path('legacy.py').exists()\n", encoding="utf-8",
    )
    record = get_repository_service().connect_repository(str(repo))
    if record["preflight"].blockers:
        print(json.dumps({"status": "BLOCKED", "blockers": record["preflight"].blockers}))
        return 1
    controller = GuildController()
    await controller.db.init_db()
    mission = Mission(repository_id=record["repository_id"], status=MissionStatus.PLANNING,
                      budgets=MissionBudgets(max_model_turns=60, max_tool_calls=100, max_tokens=300000),
                      request_text=("In this small existing Python repository, keep total(items) behavior, add "
                                    "average(items) to math_ops.py (return 0 for empty), create a small NOTES.md "
                                    "describing the two functions, and remove obsolete legacy.py. Preserve "
                                    "test_math_ops.py unchanged. For each of the THREE existing acceptance "
                                    "tests, map the matching criterion to a distinct pytest selector: "
                                    "test_math_ops.py::test_total, test_math_ops.py::test_average, "
                                    "test_math_ops.py::test_no_legacy. Use one implementation task for the "
                                    "three file changes; inspect the source before editing."))
    criteria = [AcceptanceCriterion(mission_id=mission.id, description=text) for text in (
        "Total remains correct for [1,2]", "Average works for [2,4] and empty lists", "Legacy file is removed",
    )]
    await controller.db.create_mission(mission, criteria)
    report_path = settings.data_dir.resolve() / "demos" / f"{mission.id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await (await controller.start(mission.id, "plan"))
        planned = await controller.db.get_mission(mission.id)
        if planned.status == MissionStatus.READY_FOR_AUTHORIZATION:
            # Running this explicit demo command authorizes edits to its synthetic
            # disposable workspace; it does not authorize applying to its source.
            await (await controller.start(mission.id, "execute", planned.scope_version))
        result = await controller.db.get_mission(mission.id)
        if result.status == MissionStatus.VERIFYING:
            result = await ApprovalService(controller).verify(mission.id)
        candidate = next((c for c in await controller.store.records(Candidate, mission.id)
            if c.id == result.active_candidate_id), None)
        diff = controller.workspaces.generate_candidate_diff(mission.id, mission.repository_id, candidate.id)["unified_diff"] if candidate else ""
        report = {"mission_id": mission.id, "repository_path": str(repo), "status": result.status.value,
                  "candidate_id": candidate.id if candidate else None,
                  "candidate_fingerprint": candidate.content_fingerprint if candidate else None,
                  "changed_files": candidate.changed_files if candidate else [],
                  "criteria": [c.model_dump(mode="json") for c in await controller.db.get_criteria(mission.id)],
                  "diff": diff[:40000], "failure_reason": result.failure_reason,
                  "approval_recorded": False, "original_files_unchanged": (
                      (repo / "math_ops.py").read_text(encoding="utf-8") == "def total(items):\n    return sum(items)\n"
                      and (repo / "legacy.py").exists() and not (repo / "NOTES.md").exists()),
                }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "diff"}, indent=2))
        print("Diff:\n" + diff[:12000])
        print("Report:", report_path)
        return 0 if result.status == MissionStatus.VERIFIED_AWAITING_APPROVAL and report["original_files_unchanged"] else 1
    finally:
        await controller.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
