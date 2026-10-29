# M6 — Independent verification and approval

Date: 2026-10-30

M6's deterministic unit/integration suite passes. The live multi-agent smoke
run remains blocked by the unavailable Docker Desktop Linux engine, as noted in
`M5_STATUS.md`.

## Implemented

- Independent verifier maps every acceptance criterion's approved check profile
  to exactly one candidate-bound check record; a passing pytest record must
  report at least one passed test. Missing, failed, skipped-only, ambiguous or
  fingerprint-mismatched evidence cannot verify the candidate.
- Verification changes mission state to `VERIFIED_AWAITING_APPROVAL` only when
  criteria, current check/review tasks, and blocking findings allow it.
- `POST /api/missions/{id}/approve` requires the active candidate ID, exact
  fingerprint, and an explicit human `APPROVED` or `REJECTED` decision. Decisions
  are durable, one per mission; stale or duplicate decisions return 409.
- `POST /api/missions/{id}/apply` requires recorded approval and a pristine
  baseline manifest/content, rejects snapshot changes, and uses atomic file
  replacement for a single regular-file change. Duplicate applications return 409.
- `GET /api/missions/{id}/patch` and `/report` expose the current patch and
  cited evidence/approval metadata without executing repository code.

**Scope of atomic application:** one existing regular file. A candidate changing
multiple files is refused at apply time; download its patch for manual review.
This explicitly avoids claiming an atomic multi-file transaction without crash
recovery. No API endpoint will silently apply a multi-file change.

## Verification

From `backend/`:

```powershell
python -m pytest tests/unit -q --junitxml=data/m6-regression.xml
```

Result: **147 passed**, one dependency deprecation warning. Results:
`data/m6-regression.xml`.

The M6 tests cover successful verify/approve/apply, stale fingerprints,
candidate and original repository tampering, new files, failed/empty check
records, rejection, repeat approvals and application, and API patch/report
reads. The tests use controlled model/executor responses plus real SQLite and
filesystem operations; they do not claim live Docker evidence.
