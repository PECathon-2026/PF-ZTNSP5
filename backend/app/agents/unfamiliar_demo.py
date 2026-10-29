"""Real model discovers source/test files from a new repo without name hints."""

import asyncio
import json
from pathlib import Path

from app.schemas.mission import Mission, MissionBudgets, MissionStatus, AcceptanceCriterion
from app.services.repository_service import get_repository_service
from app.services.guild_service import GuildController
from app.services.approval_service import ApprovalService
from app.settings import get_settings


async def main():
    repo_path = Path(__file__).resolve().parents[3] / "sample-repos" / "unfamiliar"
    files_before = {p.name: p.read_bytes() for p in repo_path.iterdir() if p.is_file()}
    repo = get_repository_service().connect_repository(str(repo_path))
    controller = GuildController()
    await controller.db.init_db()
    mission = Mission(repository_id=repo["repository_id"], status=MissionStatus.PLANNING,
                      request_text="Prevent negative debit amounts while preserving the behavior of valid amounts and zero. Discover relevant code and tests from the repository.",
                      budgets=MissionBudgets(max_model_turns=60, max_tool_calls=100, max_tokens=300000))
    await controller.db.create_mission(mission, [
        AcceptanceCriterion(mission_id=mission.id, description="Negative amounts are rejected"),
        AcceptanceCriterion(mission_id=mission.id, description="Positive and zero amounts preserve existing behavior"),
    ])
    try:
        await (await controller.start(mission.id, "plan"))
        planned = await controller.db.get_mission(mission.id)
        if planned.status == MissionStatus.READY_FOR_AUTHORIZATION:
            await (await controller.start(mission.id, "execute", planned.scope_version))
        result = await controller.db.get_mission(mission.id)
        if result.status == MissionStatus.VERIFYING:
            result = await ApprovalService(controller).verify(mission.id)
        from app.schemas.candidate import Candidate
        candidates = await controller.store.records(Candidate, mission.id)
        candidate = next((c for c in candidates if c.id == result.active_candidate_id), None)
        from app.schemas.evidence import Evidence, EvidenceKind
        evidence = [e for e in await controller.store.records(Evidence, mission.id) if candidate and e.candidate_id == candidate.id]
        report = {"mission_id": mission.id, "status": result.status.value, "reason": result.failure_reason,
                  "candidate_id": candidate.id if candidate else None,
                  "candidate_fingerprint": candidate.content_fingerprint if candidate else None,
                  "criteria": [c.model_dump(mode="json") for c in await controller.db.get_criteria(mission.id)],
                  "challenge": [e.metadata for e in evidence if e.kind == EvidenceKind.MUTATION],
                  "original_unchanged": files_before == {p.name: p.read_bytes() for p in repo_path.iterdir() if p.is_file()},
                  "approval_recorded": False}
        target = get_settings().data_dir.resolve() / "demos" / f"unfamiliar-{mission.id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        print("Report:", target)
        return 0 if result.status == MissionStatus.VERIFIED_AWAITING_APPROVAL and report["original_unchanged"] else 1
    finally:
        await controller.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
