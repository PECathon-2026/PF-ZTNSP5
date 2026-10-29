# FRONTEND OVERHAUL — PROGRESS (KAGE AI)

Single source of truth for resuming work after context compaction. Repo state wins over this file.

## Objective
Full frontend overhaul of KAGE AI (Next.js) into a Japanese-guild engineering workstation.
Priority order: IDE workspace > mission workflow > evidence/approval > entrance/polish.
Hard rules: no fabricated agents/events/tests/diffs/verification; backend contracts preserved;
all UI claims must be backed by real API data or an honest unavailable state.

## Environment / toolchain (verified)
- Node v22.21.1 exists but NO npm. Workaround: npm 10.9.2 unpacked at
  `/tmp/opencode/npmtool/package`, symlinked as `~/.local/bin/npm` and `~/.local/bin/npx`.
  If missing: re-extract from https://registry.npmjs.org/npm/-/npm-10.9.2.tgz
- Python: use conda env **ml** (`source /home/param/miniforge3/etc/profile.d/conda.sh && conda activate ml`,
  Python 3.11). Deps installed there: aiosqlite, pytest-asyncio added by me; fastapi/uvicorn/
  pydantic/dotenv/httpx/pytest already present.
- Docker: UNAVAILABLE in this environment (backend preflight therefore returns BLOCKED with
  the container-execution blocker — this is real backend data, must be surfaced honestly).

## Baseline results (recorded before edits)
- `npx tsc --noEmit` → exit 0 (PASS)
- `npm test` (frontend, node --test) → 3/3 PASS
- `npm run build` (next build) → exit 0 PASS
- `python -m pytest backend/tests -q` → 23 passed, **1 pre-existing failure**:
  `test_api_mission_crud_lifecycle` — TestClient(app) without context manager never runs
  lifespan → tables not created → "no such table: missions". PRE-EXISTING, not caused by me.
- Pre-existing bug fixed by me: `backend/app/storage/artifacts.py:35` f-string contained a
  backslash (SyntaxError on Python <3.12). Extracted to `normalized_name` first. Behavior identical.

## Backend contract inventory (read-only facts)
Routes that EXIST:
- GET  /api/health → {status, service, version, docker_available, model_configured, storage_ready, active_missions_count}
- POST /api/repositories/connect {path} → {repository_id, name, path, fingerprint, preflight{status: READY|WARNING|BLOCKED|CHECKING, detected_profile, file_count, excluded_count, existing_modifications, warnings[], blockers[]}}
  404 not exists, 422 not dir, 403 PathSecurityError
- GET  /api/repositories/{id}/tree → string[] (flat relative paths, sorted, exclusions applied)
- GET  /api/repositories/{id}/file?path= → {file_path, content} (404/403/413)
- POST /api/missions {repository_id, request_text, criteria[]} → 201 {mission, criteria, tasks}
- GET  /api/missions?limit= → Mission[]
- GET  /api/missions/{id} → {mission, criteria, tasks} (404)
- POST /api/missions/{id}/cancel → 200 detail | 409 terminal state
- GET  /api/missions/{mid}/candidates/{cid}/diff?repository_id= → {candidate_id, content_fingerprint, changed_files_count, files[{file_path, change_type: MODIFIED|ADDED|DELETED, diff}], unified_diff}
- GET  /api/missions/{mid}/candidates/{cid}/file?path= → {file_path, content}
- Mission statuses: CREATED PREFLIGHT AWAITING_CLARIFICATION PLANNING READY_FOR_AUTHORIZATION
  RUNNING CHECKING REPAIRING REVIEWING VERIFYING VERIFIED_AWAITING_APPROVAL APPLYING APPLIED
  REJECTED BLOCKED FAILED_VERIFICATION BUDGET_EXHAUSTED CANCEL_REQUESTED CANCELLED INTERRUPTED
- Criterion statuses: PENDING PASS FAIL PARTIAL NOT_VERIFIED BLOCKED
- Task fields: id, title, description, owner_agent, dependencies[], status, attempt, candidate_id,
  completion_condition, result_summary, evidence_ids[], created_at, updated_at
- Events table: {sequence(mono per mission), mission_id, event_type, source, task_id, candidate_id,
  evidence_ids[], display_payload{}, created_at} — emitted by create (MISSION_CREATED) and cancel
  (MISSION_CANCELLED) only.
- DB tables exist for candidates, evidence, findings, approvals, messages — **but no HTTP routes
  expose them and no orchestrator ever writes them** (no execution engine in backend at all;
  mission stays PLANNING forever except cancel).
- Repositories are stored IN-MEMORY in RepositoryService → lost on backend restart → frontend must
  handle 404 on tree/file with a reconnect (re-POST connect with stored path).
- SSE: NOT implemented in backend (doc SSE_Frontend_Event_Contractgit.md + spec §6.4 exist only).

## Decisions (with rationale)
1. **Additive backend endpoints (2)** implementing the project's own DEVPILOT_BACKEND_SPEC:
   - `GET /api/missions/{id}/events?after=<seq>` (+ SSE via `Accept: text/event-stream`)
     — spec §6.4; exposes already-persisted events. No existing route/schema modified.
   - `GET /api/missions/{id}/report` — spec §6.6; one authoritative payload
     {mission, criteria, tasks, events, candidates, findings, evidence, approvals}
     powering command center + evidence screens.
   Rationale: without these the required screens have no truthful data source at all.
   Disclosed in final report as additive (not invented) routes.
2. **No approval/apply endpoints** (spec §6.6 approve/apply/reject) — applying patches is M6 work
   and unreachable without candidates. Approval UI = honest "not available" state. Disclose.
3. **Live updates = polling with `after` cursor + reconcile-on-reconnect** (spec allows polling).
   No fake SSE client pretending to be connected; connection state shown honestly.
4. **No orchestration added.** Missions remain PLANNING; timeline/guild/evidence show only what
   backend really reports, with designed empty states explaining why.
5. **2.5D CSS entrance** from the supplied photo instead of WebGL (prompt prefers good 2.5D over
   weak 3D). Existing three/gsap/lenis deps currently unused by the new design → decide removal
   at cleanup (only after confirming no references).
6. Custom drag-resizable panels (no new layout dep). Icons: add `lucide-react`.
   Editor: add `monaco-editor` + `@monaco-editor/react` bundled locally (no CDN at runtime);
   fallback custom read-only viewer if bundling fails.

## Assets
- `images/54d5e3b5-4b83-4a04-82b8-241ffa984049.jpg` — 1600×900 JPEG, cinematic Japanese night
  village + samurai + pagoda + moon. Plan: copy to `frontend/public/images/entrance-night.jpg`
  (do NOT copy the `*.jpg:Zone.Identifier` junk file).
- No other images exist in repo.

## Route plan (Next App Router)
- `/` entrance (hero + recent real missions + lifecycle + guild + trust + readiness)
- `/missions` real mission list
- `/setup` repository connect + preflight + brief + criteria + START MISSION
- `/missions/[id]` command center (header, guild, timeline, inspector)
- `/missions/[id]/forge` IDE workspace (explorer/editor/guild/bottom panel/diff)
- `/missions/[id]/evidence` evidence + approval (washi surface)
- `/dojo` legacy → redirect `/`
- next.config.ts: rewrite `/api/:path*` → `${KAGE_BACKEND_URL||http://127.0.0.1:8000}/api/:path*`
  (fixes current broken relative fetch of /api/health)

## Phase status
- [x] Phase 1 Reconnaissance + baseline
- [x] Phase 2 Design system + app shell (tokens, globals, header/nav, UI primitives)
- [x] Phase 3 Entrance + setup screens (real APIs) — desktop verified
- [x] Phase 4 Command center (mission header, guild, timeline, inspector) — verified in browser with real mission miss-38a011a7
- [ ] Phase 5 IDE workspace (tree, monaco, tabs, bottom panel, diff, panels)
- [ ] Phase 6 Evidence + approval
- [ ] Phase 7 Motion/polish/asset integration
- [ ] Phase 8 QA: build/typecheck/tests + browser screenshots at desktop viewports only
      (USER INSTRUCTION 2026-10-29: skip mobile side entirely, PC only → 1280/1440/1920)

## Phase 2–3 notes (2026-10-29)
- Files delivered:
  - `src/styles/tokens.css`, `src/app/globals.css`, `src/app/layout.tsx` (Cinzel Decorative +
    JetBrains Mono + existing JP fonts), `next.config.ts` (API rewrite + allowedDevOrigins)
  - `src/lib/{types,api,status,repository-session,use-missions,tree}.ts`
  - `src/components/shell/{brand-seal,mission-context,connection-status,site-header}.tsx`
  - `src/app/page.tsx` + `entrance.css` + `src/components/entrance/*`
  - `src/app/setup/page.tsx` + `setup/setup.css` + `src/app/tree.css` (shared tree styles)
  - `src/components/setup/{setup-screen,repository-panel,mission-brief}.tsx`
- CRITICAL FIX: access via `127.0.0.1` blocked `/_next` dev chunks until `allowedDevOrigins` was
  added to next.config.ts → React never hydrated (fiber 0), header stuck "Checking API". After
  fix: fiber attaches, health = "Backend connected". Restart `next dev` after config changes.
- Kill dev server without self-matching pkill:
  `ps -eo pid,args | grep -E "[n]ext dev|[n]ext-server" | awk '{print $1}' | xargs -r kill`
- css path gotcha: page inside `app/setup/` must import `./setup.css` (file moved into setup/).
- Setup verified in browser (Playwright, LD_LIBRARY_PATH=/tmp/opencode/libs/...):
  hero image loads (1600w), INITIALIZE MISSION → /setup, connect real repo
  `/home/param/PF-ZTNSP5` → preflight BLOCKED (Docker missing, real), 2 notes, tree preview
  renders (~34 nodes), START MISSION gating: disabled without brief → disabled without ack while
  BLOCKED → enabled with brief+ack → real POST created `miss-38a011a7` → routed to /missions/…
  (404 until Phase 4). Criteria add works (`.criterion-add button`). Playwright `button:has-text`
  matches sample chips containing "Add" — use exact/narrow selectors.
- localStorage repo session is per-browser-profile (fresh Playwright profile = empty on reload);
  not a bug. Backend restart → tree 404 → panel shows Reconnect.
- Pre-existing backend test failure now FIXED (TestClient context manager) → backend 25 pass.
- Verification: `tsc --noEmit` PASS · `npm test` 3/3 · `npm run build` PASS (rerun at Phase 8).

## Verification commands (rerun after changes)
```
cd frontend && npx tsc --noEmit && npm test && npm run build
source /home/param/miniforge3/etc/profile.d/conda.sh && conda activate ml && \
  python -m pytest backend/tests -q     # expect 23 pass + 1 known pre-existing fail
# backend run: conda activate ml && cd backend && uvicorn app.main:app --port 8000
# frontend: cd frontend && npm run dev  (proxies /api → 127.0.0.1:8000)
```

## Known blockers / open items
- Docker unavailable → repository preflight BLOCKED in this env (real; surface, do not bypass).
- No orchestrator → missions never leave PLANNING; no candidates/findings/evidence ever created.
- Pre-existing backend test failure (see Baseline) — do not attribute to redesign.
- Frontend browser QA (Playwright/screenshot) still to be done in Phase 8.
