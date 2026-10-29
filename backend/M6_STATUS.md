# M6 — Independent verification and approval

Date: 2026-10-30

M6's deterministic unit/integration suite passes. The Docker engine and check
image are available; a restricted container run of the concrete pytest selector
`test_metrics.py::test_average` completed with exit code 0 and `1 passed`.

## Implemented

- Each behavioral criterion needs its own approved single-test pytest selector.
  Sentinel records separate candidate-fingerprint-bound evidence per criterion
  alongside a full-suite regression check. The verifier rejects missing,
  duplicate, controlled, failed, truncated, stale or wrong-selector evidence;
  each selected check must report exactly `1 passed`. An unbound criterion can
  no longer pass on a generic suite result.
- Verification changes mission state to `VERIFIED_AWAITING_APPROVAL` only when
  criteria, current check/review tasks, and blocking findings allow it.
- `POST /api/missions/{id}/approve` requires the active candidate ID, exact
  fingerprint, and an explicit human `APPROVED` or `REJECTED` decision. Decisions
  are durable, one per mission; stale or duplicate decisions return 409.
- `POST /api/missions/{id}/apply` requires recorded approval and a pristine
  baseline manifest/content. A durable pre-write journal supports multi-file
  replacements, file additions and deletions with rollback on failure and on
  startup after interruption. Duplicate applications return 409.
- `GET /api/missions/{id}/patch` and `/report` expose the current patch and
  cited evidence/approval metadata without executing repository code.

**Atomicity boundary:** replacements are atomic per file; concurrent external
readers may see intermediate multi-file state. On an incomplete operation the
startup recovery restores the journaled baseline before the API serves requests.
If recovery cannot distinguish an external edit from the operation's own effect,
it stops at `BLOCKED` and keeps the journal rather than overwriting that edit.

## Verification

From `backend/`:

```powershell
python -m pytest tests/unit -q --junitxml=data/m6-regression.xml
```

Full regression: **172 passed** with one dependency deprecation warning;
`data/m6-enhanced-regression.xml`.

The M6 tests cover successful verify/approve/apply, stale fingerprints,
candidate and original repository tampering, new files, failed/empty check
records, rejection, repeat approvals and application, and API patch/report
reads. The tests use controlled model/executor responses plus real SQLite and
filesystem operations; they do not claim live Docker evidence.
Additional tests in `tests/unit/test_m6_multifile.py` cover per-criterion
verification, modify/add/delete apply, conflicts, mid-write rollback, simulated
crash/startup recovery and a failed final database write. Frontend flow is not
changed here.
