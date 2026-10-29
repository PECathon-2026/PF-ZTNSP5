# M8 — Five-scenario evaluation

Five scenarios in `sample-repos/` now have reproducible evaluation traces.
Run from `backend/`:

```powershell
python -m app.evaluation --mode controlled
python -m app.evaluation --mode live
python -m pytest tests/unit -q --junitxml=data/m8-regression.xml
```

## Controlled evaluation: five scenario trajectories passed

Results: `evaluation/results/run-20261029T195050Z-037d1d31/summary.json`
(plus one JSON report for each scenario). This exercises the real SQLite
controller and tool gateway with a scripted model and a **source-level fixture
oracle**, not Docker/pytest.

| Scenario | Controlled result | Evidence captured |
| --- | --- | --- |
| Feature | `VERIFYING` | Status filtering, failure/repair, preserved sorting in final source |
| Bug | `VERIFYING` | Pagination baseline defect, fixed candidate |
| Recovery | `VERIFYING` | Pre-existing failing baseline, passing new candidate |
| Security | `VERIFYING` | `BLOCKING` shell finding, repair, new-candidate resolution evidence |
| Unexpected | `VERIFYING` | Clarification requested and answered before editing |

The controlled reports **do not imply behavioral tests ran**. Controlled check
records are tagged `controlled_evaluation: true`; the independent verifier
explicitly rejects them. No original sample repository is modified or applied.

## Live evaluation: five scenarios passed with real model and Docker checks

Results: `evaluation/results/run-20261029T200847Z-c8bec9cb/summary.json`.
All five scenario reports are `VERIFYING` with `exit_check_passed: true`.
They record the real-model trajectory, candidate fingerprints, real container
check commands, stdout/stderr artifact IDs, timings and finding resolutions.
The original fixture directories remained unchanged. Security includes a
separate **real Shadow Council pre-implementation baseline review**, a
`BLOCKING` shell finding, and resolution against the repaired candidate.
Unexpected conditions record a real clarification answer before the final
candidate; checks passed on its immutable snapshot. As in M6, `VERIFYING`
means a candidate is ready for independent verification, **not approved or
applied**.

Docker was started and `devpilot-checks:py312` built before this run.
A restricted `python_syntax` check passed (exit 0); the seeded feature
fixture's restricted pytest check reproduced two expected failures (exit 1).

### Earlier blocked run (retained as prerequisite evidence)

Results: `evaluation/results/run-20261029T194709Z-59c7af17/summary.json`.
All five earlier live scenario reports were `BLOCKED`: Docker Desktop Linux
engine was unavailable. No host fallback, model call or container check was
attempted on that run. The successful run above supersedes this prerequisite
failure as M8's exit evidence.

## Regression checks

`python -m pytest tests/unit -q --junitxml=data/m8-regression.xml`:
**158 passed**, one existing dependency deprecation warning. The seven M8
tests verify all five trajectories, independent verifier refusal of controlled
check evidence, and the five blocked live-mode artifacts when Docker is down.
