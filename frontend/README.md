# KAGE AI frontend

The Next.js App Router frontend uses TypeScript and Tailwind CSS. The entrance has a lazy-loaded, procedural React Three Fiber samurai, a pinned GSAP ScrollTrigger guild sequence, and Lenis-driven desktop scrolling. Setup and `/dojo` are wired to the local DevPilot backend.

```sh
cd frontend
npm install
npm run dev
```

Start the backend separately from `backend/` with `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, then open http://localhost:3000. Next.js forwards `/api/*` to the local backend. Run `npm test`, `npm run typecheck`, and `npm run build` to verify the UI.

## Implementation map

- `src/app/layout.tsx`, `src/components/site-header.tsx`: shared application shell.
- `src/styles/tokens.css`, `src/app/globals.css`: color/type/motion tokens, Tailwind, and responsive components.
- `src/app/page.tsx`: KAGE landing, actual guild roles, mission method, health and honest archive state.
- `src/components/landing/landing-experience.tsx`, `samurai-scene.tsx`, `src/app/landing.css`: desktop scene and scroll choreography, accessible mobile/reduced-motion poster and unpinned agent list. Decorative motion never represents actual mission progress.
- `src/app/setup/page.tsx`, `src/components/mission-setup.tsx`: backend repository connect/preflight and real mission creation/planning.
- `src/app/dojo/page.tsx`, `src/components/mission-dojo.tsx`, `src/components/inspection-tabs.tsx`: live mission detail, SSE replay, source files, findings/check output/diffs, clarification and candidate-specific verification/approval/apply.
- `src/lib/mission-draft.ts`, `tests/mission-draft.test.mjs`: criteria validation and health classification.

The landing page loads actual `/api/health` readiness and `/api/missions` history. Setup connects a local repository and requires a non-blocked preflight, a request and at least one acceptance criterion. After Shogun plans, the Dojo waits for explicit authorization. It refreshes canonical mission details on each persisted SSE event and on reconnect, deduplicates monotonic sequences, detects gaps and closes the stream on terminal events. Approval controls appear only for a verified current candidate, with its full fingerprint visible before the user decides.

The Dojo activity list renders the backend's concise `AGENT_ACTIVITY` summaries
with agent attribution, and falls back to event names for older records. A
summary describes validated tool intent or observed outcome; it is not raw model
reasoning. Backend progress records and replay remain authoritative.

Docker Desktop Linux engine and the prebuilt check image are required for live planning/checks; unavailable Docker is shown as blocked by the backend, not simulated as passing. For the M7 implementation/check report see `../backend/M7_STATUS.md`.

## Future phases

3. Dojo: Monaco IDE layout and agent-aware views driven by real state.
4. Folder and live sync: permission-gated File System Access API and, where needed, a separately authorized local watcher/WS server. Backend candidate/approval operations must remain authoritative; browser edits must not silently overwrite external changes.

Each phase is intentionally separate so the UI never claims unsupported engineering operations.

The scene is the project's original low-poly illustration; replace it with an authorized `.glb` only if one is provided. Desktop WebGL starts only while the journey is visible, pauses off-screen, caps device pixel ratio at 1.5, and is omitted on mobile or with reduced motion. No frame-rate guarantee has been measured.
