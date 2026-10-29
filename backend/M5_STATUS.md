# M5 — Adaptive recovery and bounded autonomy

Date: 2026-10-30

**Implementation and deterministic exit checks pass. The live container
demonstration is blocked by the unavailable Docker Desktop Linux engine.**

## Implemented

- Automatic Shogun replanning from current candidate findings and check output.
- Revised, persisted task DAGs and plan history, without changing authorized
  acceptance criteria or weakening required check profiles.
- Fresh Samurai candidates, re-tests, re-reviews, and new-candidate resolution
  evidence for earlier findings.
- Hard maximum of three repair rounds, plus shared model/tool/reported-token,
  active-time and clarification budgets.
- Durable pre-invocation model/tool accounting, including failed/rejected calls.
- No-progress detection that stops repeated candidate checks.
- Clarification questions during initial/repair planning and
  `POST /api/missions/{id}/clarifications` for atomic answer/resume.
- Snapshot/scope-bound answers, duplicate/concurrent-answer protection, restart
  continuity, and cancellation without replaying partial writes.
- `plan_revision` and clarification records in mission detail responses.

## Verified regression run

From `backend/`:

```powershell
python -m pytest tests/unit -vv -o faulthandler_timeout=30 --junitxml=data/m5-regression.xml
```

Result: **136 passed**, including **26 M5 tests**, in 47.40 seconds.
There is one existing dependency deprecation warning.
JUnit report: `data/m5-regression.xml`.

An earlier full-suite command exceeded its shell timeout. The M5-only run passed,
and the diagnostic full-suite rerun above completed successfully.

### M5 exit test

`tests/unit/test_m5_recovery.py::test_m5_seeded_failure_replans_repairs_and_retests`
proves:

1. Candidate v1 fails its controlled Sentinel check.
2. The failure's candidate/evidence references and output reach Shogun.
3. Shogun submits a revised plan that preserves the approved criteria.
4. Samurai produces v2, preserving the original repository.
5. The new check passes and the earlier finding resolves against v2's evidence.
6. The mission stops at `VERIFYING`, with one repair round used and criteria
   still pending independent verification.

These tests use scripted model responses and controlled check results with real
SQLite/filesystem operations. They do not claim that mocked output came from Docker.

## Live attempt

Command: `python -m app.agents.recovery_smoke`

- Outcome: `BLOCKED` before model execution.
- Reason: baseline container checks unavailable; Docker Desktop Linux engine must start.
- Evidence: `data/artifacts/miss-3e7588e9/art-fa3d62bcf220_m5-smoke.json`.
- No repository code was executed on the host.

After starting Docker Desktop:

```powershell
docker build -f Dockerfile.checks -t devpilot-checks:py312 .
python -m app.agents.recovery_smoke
```

## Next boundary

M5 does not certify acceptance criteria or apply patches. A recovered candidate
waits at `VERIFYING` for M6's independent deterministic verifier, candidate-bound
human approval and conflict-checked patch application.
