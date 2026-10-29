# M7 — Frontend and SSE integration

Date: 2026-10-30

## Implemented

- SQLite-backed `GET /api/missions/{id}/events` streams persisted mission events
  as SSE `id`, `event: mission`, and JSON `data` frames. `Last-Event-ID` and
  `?after=` cursors replay missed events, and idle connections receive comment
  heartbeats. Invalid cursors fail before starting a stream.
- Guild event records include the committed mission status; events are written
  before stream polling publishes them. No in-memory event-only delivery path.
- Next.js rewrites `/api/*` to the local FastAPI service. Setup connects the
  repository, displays preflight, creates a real mission and starts planning.
- Dojo renders mission status, tasks, candidate source, diff, findings, check
  output, criteria/evidence, clarifications, and exact-fingerprint approvals.
  It handles authorization, verify, reject/approve, apply and cancel via REST.
- Landing page shows actual model/Docker readiness and recent saved missions.
- The UI ignores old-candidate evidence/approvals, deduplicates event sequences,
  detects gaps, refreshes canonical mission state on reconnection and closes
  SSE on terminal events.

## Checks

From `backend/`: `python -m pytest tests/unit -q --junitxml=data/m7-regression.xml`.

From `frontend/`: `npm test`, `npm run typecheck`, `npm run build`.

Results: **151 backend tests passed**, **5 frontend tests passed**, TypeScript
typecheck and Next.js production build passed. The backend run has one dependency
deprecation warning; JUnit output is `backend/data/m7-regression.xml`.

SSE tests cover persisted replay after reconstructing the database, monotonic
cursor delivery, heartbeat formatting, missing missions and bad cursors.
Frontend tests cover stale candidate badges and event gap/duplicate handling.

**Live browser mission execution remains blocked** while Docker Desktop's Linux
engine is unavailable. Startup instructions are in `frontend/README.md` and
the check image build instructions are in `backend/README.md`.
