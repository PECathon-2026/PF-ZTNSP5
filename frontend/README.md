# KAGE AI frontend

Phase 1 migrated the frontend to Next.js App Router + TypeScript + Tailwind CSS. It preserves the existing mission-draft criteria editor and read-only health check. The entrance, setup, and `/dojo` routes use the shared KAGE ink/crimson/gold theme.

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Run `npm test`, `npm run typecheck`, and `npm run build` to verify this phase.

## Implementation map

- `src/app/layout.tsx`, `src/components/site-header.tsx`: shared application shell.
- `src/styles/tokens.css`, `src/app/globals.css`: color/type/motion tokens, Tailwind, and responsive components.
- `src/app/page.tsx`: KAGE landing, actual guild roles, mission method, health and honest archive state.
- `src/app/setup/page.tsx`, `src/components/mission-setup.tsx`: local draft request/path and editable criteria.
- `src/app/dojo/page.tsx`, `src/components/inspection-tabs.tsx`: unconnected workspace and accessible inspection tabs; no fake file, diff, event, or check data.
- `src/lib/mission-draft.ts`, `tests/mission-draft.test.mjs`: criteria validation and health classification.

The only API request is `GET /api/health`. The backend in this repository does not yet expose an HTTP route, so this request currently returns unavailable. No folder is connected, no file is saved, and the Start Mission control stays disabled until real repository/preflight/mission APIs exist.

## Approved future phases

2. Landing: lazy-loaded React Three Fiber scene, GSAP ScrollTrigger and Lenis; add their packages only when used. Preserve a non-WebGL/reduced-motion fallback.
3. Dojo: Monaco IDE layout and agent-aware views driven by real state.
4. Folder and live sync: permission-gated File System Access API and, where needed, a separately authorized local watcher/WS server. Backend candidate/approval operations must remain authoritative; browser edits must not silently overwrite external changes.

Each phase is intentionally separate so the UI never claims unsupported engineering operations.
