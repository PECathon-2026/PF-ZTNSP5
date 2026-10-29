import asyncio
import httpx
import pytest

from app.schemas.approval import ApprovalRequest, ApplyPatchRequest, ApprovalDecision
from app.schemas.candidate import Candidate
from app.schemas.evidence import Evidence
from app.schemas.mission import CriterionStatus, MissionStatus
from app.services.approval_service import ApprovalService
from app.storage.guild import GuildConflict
from tests.unit.test_m5_recovery import recovery, run


async def prepared(recovery):
    controller, mission, model, executor, repo = recovery
    executor.never_fail = True
    result = await run(recovery)
    assert result.status == MissionStatus.VERIFYING, result.failure_reason
    return controller, mission, repo, ApprovalService(controller), result.active_candidate_id


@pytest.mark.asyncio
async def test_verify_approve_apply_single_file_and_no_replay(recovery):
    controller, mission, repo, service, candidate_id = await prepared(recovery)
    verified = await service.verify(mission.id)
    assert verified.status == MissionStatus.VERIFIED_AWAITING_APPROVAL
    assert all(c.status == CriterionStatus.PASS for c in await controller.db.get_criteria(mission.id))
    candidate = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == candidate_id)
    request = ApprovalRequest(candidate_id=candidate_id, candidate_fingerprint=candidate.content_fingerprint, decision=ApprovalDecision.APPROVED)
    with pytest.raises(GuildConflict):
        await service.apply(mission.id, candidate_id)
    await service.decide(mission.id, request)
    applied = await service.apply(mission.id, candidate_id)
    assert applied.status == MissionStatus.APPLIED
    assert (repo / "app.py").read_text() == "value = 2\n"
    with pytest.raises(GuildConflict):
        await service.apply(mission.id, candidate_id)
    with pytest.raises(GuildConflict):
        await service.decide(mission.id, request)


@pytest.mark.asyncio
async def test_stale_fingerprint_and_reject_are_terminal(recovery):
    controller, mission, repo, service, candidate_id = await prepared(recovery)
    await service.verify(mission.id)
    with pytest.raises(GuildConflict):
        await service.decide(mission.id, ApprovalRequest(candidate_id=candidate_id, candidate_fingerprint="0" * 64, decision=ApprovalDecision.APPROVED))
    candidate = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == candidate_id)
    await service.decide(mission.id, ApprovalRequest(candidate_id=candidate_id, candidate_fingerprint=candidate.content_fingerprint, decision=ApprovalDecision.REJECTED))
    assert (await controller.db.get_mission(mission.id)).status == MissionStatus.REJECTED
    assert (repo / "app.py").read_text() == "value = 1\n"
    with pytest.raises(GuildConflict):
        await service.apply(mission.id, candidate_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["modified", "added", "snapshot"])
async def test_original_or_snapshot_changes_block_application(recovery, change):
    controller, mission, repo, service, candidate_id = await prepared(recovery)
    await service.verify(mission.id)
    candidate = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == candidate_id)
    await service.decide(mission.id, ApprovalRequest(candidate_id=candidate_id, candidate_fingerprint=candidate.content_fingerprint, decision=ApprovalDecision.APPROVED))
    if change == "modified":
        (repo / "app.py").write_text("external = True\n")
    elif change == "added":
        (repo / "new.py").write_text("external = True\n")
    else:
        (controller.workspaces.get_candidate_dir(mission.id, candidate_id) / "app.py").write_text("tampered = True\n")
    with pytest.raises((GuildConflict, ValueError)):
        await service.apply(mission.id, candidate_id)
    assert (await controller.db.get_mission(mission.id)).status != MissionStatus.APPLIED


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["missing_check", "fake_pass", "skipped", "failed", "stale_fingerprint"])
async def test_independent_verifier_rejects_untrustworthy_evidence(recovery, damage):
    controller, mission, _, service, candidate_id = await prepared(recovery)
    evidence = [e for e in await controller.store.records(Evidence, mission.id) if e.candidate_id == candidate_id and e.metadata.get("check_profile")]
    assert len(evidence) == 1
    record = evidence[0]
    async with controller.store.transaction() as db:
        if damage == "missing_check":
            await db.execute("DELETE FROM evidence WHERE id=?", (record.id,))
        elif damage == "fake_pass":
            await db.execute("UPDATE evidence SET metadata_json=? WHERE id=?", ('{"check_profile":"python_pytest","execution_status":"SUCCEEDED","stdout":"0 passed"}', record.id))
        elif damage == "skipped":
            await db.execute("UPDATE evidence SET metadata_json=? WHERE id=?", ('{"check_profile":"python_pytest","execution_status":"SUCCEEDED","stdout":"no tests ran"}', record.id))
        elif damage == "failed":
            await db.execute("UPDATE evidence SET exit_code=1 WHERE id=?", (record.id,))
        else:
            await db.execute("UPDATE evidence SET fingerprint=? WHERE id=?", ("stale", record.id))
    result = await service.verify(mission.id)
    assert result.status == MissionStatus.FAILED_VERIFICATION
    assert all(c.status == CriterionStatus.NOT_VERIFIED for c in await controller.db.get_criteria(mission.id))


@pytest.mark.asyncio
async def test_api_verification_and_approval_reject_stale_ids(recovery, monkeypatch):
    from app.main import app
    controller, mission, repo, service, candidate_id = await prepared(recovery)
    monkeypatch.setattr("app.storage.database._db_instance", controller.db)
    monkeypatch.setattr("app.services.guild_service._controller", controller)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        prefix = f"/api/missions/{mission.id}"
        assert (await client.post(prefix + "/verify")).status_code == 200
        assert (await client.post(prefix + "/verify")).status_code == 409
        assert (await client.post(prefix + "/approve", json={"candidate_id":"old","candidate_fingerprint":"0"*64,"decision":"APPROVED"})).status_code == 409
        assert (await client.post(prefix + "/apply", json={"candidate_id":candidate_id})).status_code == 409
        candidate = next(c for c in await controller.store.records(Candidate, mission.id) if c.id == candidate_id)
        approval = await client.post(prefix + "/approve", json={"candidate_id":candidate_id,"candidate_fingerprint":candidate.content_fingerprint,"decision":"APPROVED"})
        assert approval.status_code == 200 and len(approval.json()["approvals"]) == 1
        patch = await client.get(prefix + "/patch")
        assert patch.status_code == 200 and "+value = 2" in patch.text
        report = await client.get(prefix + "/report")
        assert report.status_code == 200 and report.json()["approvals"][0]["candidate_id"] == candidate_id
        assert (await client.post(prefix + "/apply", json={"candidate_id":candidate_id})).status_code == 200
        assert (repo / "app.py").read_text() == "value = 2\n"
