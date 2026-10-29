# KAGE — immersive desktop cockpit

Approved by the user: replace the scrolling dashboard with a full-screen mission cockpit and make the entrance an immersive environment. Frontend experience is the priority.

## Direction
An ink-black architectural command chamber: sumi `#090A0C`, slate `#14171D`, washi `#EFE4CD`, muted gold `#C99A3A`, jade `#829B91`, and crimson `#A70D16`. Cinzel display, Jakarta body, JetBrains Mono for identifiers. Gold marks selection and navigation rather than decorating every surface.

## Cockpit
One viewport below the existing header: compact mission toolbar; narrow guild rail; large pannable, zoomable mission field; contextual right inspector; expandable bottom chronicle. The field is the main interaction, with draggable nodes and fit/zoom/focus controls. Keyboard users can select every node and move it with arrow keys.

Guild, tasks, and evidence lenses use one map and camera. Selecting a role, task, candidate, evidence item, or finding changes the inspector. A command palette searches actual entities and repository files. Controls retain real lifecycle actions and native confirmation dialogs.

Role nodes describe the configured guild. Task dependencies, candidate relationships, evidence, counts, execution states, and findings come exclusively from the backend. An empty mission still has an explorable role map, explicitly labeled as unassigned. No invented activity or progress.

## Entrance
Full-viewport night threshold: oversized typographic composition over a full-bleed interactive 3D gate avenue, with atmospheric depth and the supplied image as a fallback. Initialization moves the camera toward the gate before navigating. Visible motion controls, reduced-motion default, and WebGL failure fallback retain functional HTML navigation.

## State coverage
Initial loading keeps the cockpit outline stable. Refresh retains loaded entities and positions. Errors remain actionable with retry; missing missions link to the roster. Unavailable execution is stated in the inspector. Every mutation displays busy/error feedback and retains input on conflict. Map view preferences are local UI state, never server mission changes.

## Verification
Desktop checks at 1280, 1440, and 1920 pixels: viewport fit, node selection/dragging, camera zoom/pan/fit, lenses, palette, inspector resizing, chronicle, lifecycle controls, keyboard operation, reduced motion, and empty/error states. Run typecheck, tests, production build, Playwright, and axe; inspect screenshots. Fixture interactions are explicitly test-only.
