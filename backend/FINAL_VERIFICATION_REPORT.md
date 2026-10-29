# Backend verification report — KAGE AI

Date: 2026-10-30 · Scope: backend and agent pipeline; browser walkthrough deferred.

## Live mission: frozen three-file candidate, real model, real Docker

- Mission: `miss-13c8da8b`.
- Synthetic source: `backend/data/demo-repos/backend-m6-2e348b473cce/` (ignored runtime storage).
- Candidate: `cand-c987cb65e4694cb2`.
- Candidate fingerprint: `d2681775afdf773fdf5c2577bd2b57c992a09dc6298682243a4a6fd10f9559c9`.
- Status: **`VERIFIED_AWAITING_APPROVAL`**. No approval has been recorded and the original demo repository is unchanged.
- Planned changes: add `NOTES.md`, add an empty-safe `average(items)` in `math_ops.py`, remove `legacy.py`, leave the existing `total` function and all tests untouched.
- Recorded full-suite check: **3 passed** in Docker. Three separate criterion-specific, candidate-bound checks each reported **1 passed**, using `test_math_ops.py::test_total`, `test_math_ops.py::test_average`, and `test_math_ops.py::test_no_legacy`.
- All three acceptance criteria have `PASS` and distinct evidence IDs; independent deterministic verification, not a model statement, promoted the mission.
- Unabridged reviewable diff and criterion/evidence IDs: `backend/data/demos/miss-13c8da8b.json` (local, ignored). Also available through `GET /api/missions/miss-13c8da8b/report` and the candidate diff endpoint when the same backend data directory is used.

The first synthetic run (`miss-66e8bf5f`) reached `BUDGET_EXHAUSTED` after building the correct candidate and running all checks; Shadow Council still needed model turns. The successful second run was a **new** mission with a higher, bounded demo budget (60 turns, 100 tool calls); no partially executed write was replayed. Application still requires the user's explicit decision for that exact fingerprint.

## Automated and scenario evidence

| Check | Observed |
| --- | --- |
| Backend unit/integration tests | 193 passed, one dependency deprecation warning (`python -m pytest tests/unit -q`) |
| Criterion-specific Docker check | `test_metrics.py::test_average`: exit 0, 1 passed, restricted container |
| Multi-file apply | Modification + addition + deletion, conflict rejection, rollback after a write failure and after interrupted startup: tests pass on synthetic repositories |
| M8 live evaluation | All five real-model/Docker scenario runs passed; `evaluation/results/run-20261029T200847Z-c8bec9cb/summary.json` |
| Frontend build | 6 unit tests, TypeScript typecheck and production build passed; manual browser journey pending |

## Live agent activity evidence

A separate synthetic live run `miss-1295636f` completed its M4
failure-routing demonstration at `REPAIRING`. Real model calls and restricted
Docker checks produced **38 persisted `AGENT_ACTIVITY` events** from Shogun,
Samurai, Sentinel, Shadow Council and the controller. Its SQLite timeline
includes relative-file reads and diffs, criterion test intent, failed check
results linked to evidence, and routing of two findings to the planner and
developer. The trace is stored in `backend/data/devpilot.db` and its report in
`backend/data/artifacts/miss-1295636f/` (ignored runtime storage). The summaries
omit raw model text, repository file contents and check output. Latest test
report: `backend/data/activity-regression.xml`.

## Latest evidence-first mission (no file/test-name hints)

The newer live run `miss-b186039f` on `sample-repos/unfamiliar/` used a natural-language
request without paths or pytest selectors. Shogun discovered `ledger.py` and
`test_ledger.py`; Sentinel ran pytest JSON reports, Bandit and two bounded
candidate challenge variants in restricted Docker containers. Both challenge
variants were **DETECTED** by the accepted tests. Independent verification marked
both acceptance criteria `PASS` and moved candidate `cand-2541b169178e4db4`
(fingerprint `7d383dd2c0f7d39a492f0679670b74626e4b75f631be8522d62d4cc97ce21706`)
to `VERIFIED_AWAITING_APPROVAL`. No original fixture file was changed or
approved. The latest JSON/Markdown evidence is available at
`GET /api/missions/miss-b186039f/proof` and in ignored local storage
`backend/data/demos/unfamiliar-miss-b186039f.json`.

Current verification: **193 backend tests**, **6 frontend tests**, TypeScript
typecheck and Next.js production build pass. See
`backend/data/cli-regression.xml` and `backend/INNOVATION_STATUS.md`.

## Backend CLI terminal walkthrough

`python -m app.cli run` was exercised on `sample-repos/unfamiliar/` with a
natural-language request and two criteria but **no source/test filename hints**.
After the operator typed `AUTHORIZE` for the disposable workspace, the terminal
replayed 56 durable mission events: Shogun's repository map/read and plan,
Samurai's read/edit/diff/handoff, Sentinel's real Docker pytest/Bandit results
and two detected Challenge the Fix variants, Shadow Council's review, then an
independent deterministic verification. Mission `miss-05bc0e01` reached
`VERIFIED_AWAITING_APPROVAL`; candidate `cand-cb22074510b94252`, fingerprint
`7d383dd2c0f7d39a492f0679670b74626e4b75f631be8522d62d4cc97ce21706`.
The CLI displayed the unified diff. The original fixture was not modified and
no human approval or apply request was made. Replay from another terminal with
`python -m app.cli watch miss-05bc0e01 --after 42`; inspect the proof card with
`python -m app.cli proof miss-05bc0e01 --format markdown`.

## Remaining boundaries

1. Explicit human approval and application of the current synthetic three-file candidate have **not happened**. Review the report/diff and provide an explicit approval decision before those endpoints are called.
2. A manual browser walkthrough of the complete lifecycle is deferred until frontend changes are finished.
3. Per-criterion mapping proves execution of its approved named test, not the semantic adequacy of the test itself; this should be reviewed when authorizing a plan.
4. Application is recoverable across process interruption with a durable journal; replacement of each file is atomic, not simultaneous global atomicity across several files for external readers.
