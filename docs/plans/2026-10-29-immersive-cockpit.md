# Immersive Cockpit Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan inline, task-by-task. The approved work is closely coupled; no delegation is needed.

**Goal:** Deliver a visibly different, interactive desktop mission cockpit and full-viewport entrance.

**Architecture:** A frontend-only cockpit composes the existing mission hooks and lifecycle controls with a new map model, camera, node renderer, contextual inspector, and chronicle. Pure graph/camera helpers support deterministic tests. The existing R3F scene becomes a full-bleed entrance environment.

**Tech Stack:** Next.js, React, TypeScript, CSS, SVG, React Three Fiber, Drei, native dialogs, Python Playwright.

---

## Task 1 — Map model and camera
- [ ] Create `frontend/src/components/cockpit/map-model.ts`: entity node/edge contracts; guild/task/evidence layouts; camera fit and cursor-preserving zoom.
- [ ] Create `frontend/tests/cockpit-map.test.mjs`: actual dependencies, absent entity bindings, zoom clamping, and coordinate invariance.
- [ ] Create `frontend/src/components/cockpit/mission-map.tsx`: pointer pan, drag with threshold, keyboard node movement, fit/zoom toolbar, selected state, and camera focus.

## Task 2 — Cockpit composition
- [ ] Create `frontend/src/components/cockpit/cockpit-screen.tsx`: live mission state, entity selection, lens state, resizable inspector, palette, and chronicle.
- [ ] Create `frontend/src/components/cockpit/context-inspector.tsx`: mission/agent/task/candidate/evidence/finding dossiers and lifecycle controls.
- [ ] Create `frontend/src/components/cockpit/activity-dock.tsx` and `cockpit-palette.tsx`: recorded activity and searchable real entities/files.
- [ ] Create `frontend/src/components/cockpit/cockpit.css`: viewport architecture, map visual hierarchy, node states, inspector, rail, and reduced motion.
- [ ] Replace `frontend/src/components/command/command-screen.tsx` with the cockpit entry.

## Task 3 — Immersive entrance
- [ ] Rework `frontend/src/components/entrance/entrance-hero.tsx`, `gate-scene.tsx`, and `frontend/src/app/entrance.css`: full-bleed scene, large typographic foreground, pointer depth, camera crossing, and motion controls.
- [ ] Simplify `mission-entrance.tsx` to the threshold and compact recent missions, with the guild/readiness details available on demand.

## Task 4 — Verification
- [ ] Run `npm run typecheck`, `npm test`, and `npm run build` from `frontend`; all must exit zero.
- [ ] Run native Python Playwright against the production server, covering map gestures, contextual selection, lenses, palette, chronicle, fallback/error states, and reduced motion.
- [ ] Inspect screenshots at 1280/1440/1920 and resolve confirmed visual/accessibility defects.
- [ ] Update `FRONTEND_OVERHAUL_PROGRESS.md` with implemented scope and actual results.
