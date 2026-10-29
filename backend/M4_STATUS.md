# M4 — Multi-agent coordination

Date: 2026-10-29

**Implementation and deterministic milestone exit checks pass. Live container
demonstration is blocked because Docker Desktop's Linux engine is unavailable.**

## Delivered

- Shogun: read-only repository inspection and strictly validated task DAG/criteria
  proposals; user criteria must be preserved.
- Samurai integration: prepared workspace support, dependency-ordered tasks,
  parent candidate chain, exclusive writer lease and frozen handoffs.
- Sentinel: approved container-only checks against exact candidate fingerprints,
  bounded output artifacts, exit codes/durations, and structured failure categories.
- Shadow Council: read-only source/diff inspection and evidence-citing review
  findings. Unknown or cross-candidate citations are rejected.
- Durable SQLite plans, tasks, candidates, messages, evidence, and findings.
- Atomic operation claims, plan-version authorization, cancellation, and safe
  restart interruption without replaying side effects.
- Background planning/authorization API endpoints and durable candidate/evidence
  reads. Concurrent event writes receive unique monotonic sequence numbers.
- Failed checks/high-severity reviews reopen tasks and route findings to both
  Shogun and Samurai. Environment failures stop separately.

## Exit evidence

Run from `backend/`:

```powershell
python -m pytest tests/unit -q --junitxml=data/m4-regression.xml
```

Result: **110 passed**, one existing dependency deprecation warning.
JUnit report: `data/m4-regression.xml`.

The key M4 exit test is
`tests/unit/test_m4_guild.py::test_m4_exit_failure_reopens_task_and_routes_evidence`:

1. A baseline check and Shogun plan complete.
2. Authorized Samurai work freezes a candidate without changing the original.
3. A controlled Sentinel failure records exit code 1, exact duration and output
   artifacts, bound to that candidate's fingerprint.
4. The implementation task reopens as `READY`, attempt 2.
5. Evidence-linked `FINDING` messages go to Shogun and Samurai.
6. A new store instance reads the same persisted candidate/task/evidence records.

These are deterministic scripted-model/executor tests, **not live Docker results**.
Additional checks cover multi-task dependencies and candidate chains, reviewer
failure routing, stale authorization, ownership boundaries, tampered snapshots,
invalid DAGs, permission enforcement, bounded output, process timeout/cancellation,
API reads after clearing in-memory caches, and no-host-fallback behavior.

## Live attempt

Command: `python -m app.agents.guild_smoke`

- Outcome: `BLOCKED` before model execution.
- Reason: Docker Desktop's Linux engine pipe could not be reached.
- The baseline failure was durably recorded; no repository code ran on the host.
- Evidence: `data/artifacts/miss-81e7cf60/art-b1bf14a30fed_m4-smoke.json`.

To run the real demonstration, start Docker Desktop and build the check image:

```powershell
docker build -f Dockerfile.checks -t devpilot-checks:py312 .
python -m app.agents.guild_smoke
```

## Next milestone

M4 intentionally stops at `REPAIRING` after routing a code finding. M5 consumes
those findings to revise the plan and perform bounded repair/re-test rounds, with
clarification pause/resume. Successful M4 checks stop at `VERIFYING`; only M6's
independent verifier may advance toward approval.
