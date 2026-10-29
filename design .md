# KAGE AI — PECFEST-Inspired UI & Design System

**Project:** DevPilot / KAGE AI  
**Context:** PECATHON 2026 · PS-001  
**Purpose:** Frontend design and implementation handoff for the coding agent  
**Status:** Design specification; implementation and runtime behavior must be verified separately.

---

## 1. Design Mission

Build **KAGE AI** as a premium, cinematic engineering workspace inspired by PECFEST 2026's **"A Mystic Mikado"** visual language. The product should feel like entering a disciplined Japanese-inspired engineering guild—not a generic SaaS dashboard with a dark theme.

The PECFEST reference contributes its visual principles and interaction grammar:

- **Ma (間):** intentional negative space, clear focal points, uncluttered layouts.
- **Sumi-e (墨絵):** ink-like transitions, soft atmospheric layers, restrained brush details.
- **Kintsugi (金継ぎ):** delicate gold fracture details for interactive states and findings.
- **Kamon (家紋):** circular seals and orbit-like navigation motifs.
- **Thresholds and sliding panels:** transitions that feel like passing through a gate or opening shoji doors.
- **Editorial contrast:** cinematic dark scenes paired with warm paper-like surfaces for information-heavy sections.
- **Layered depth:** foreground, middle ground, distant atmosphere, and different movement rates.

These ideas must be adapted to an AI engineering product. Do not copy PECFEST branding, logo, festival content, or imagery directly. Do not make KAGE look like a festival landing page after the user has entered the actual engineering workspace.

## 2. Product Identity

### Name

**KAGE AI** — *Autonomous Engineering Guild*

"Kage" means "shadow" in Japanese. Use it as a product identity, not as a claim of fully autonomous or infallible engineering.

### Tagline

**Build in the Shadows. Prove in the Light.**

### Hero headline

**Your Code. Our Guild. Verified Results.**

### Supporting line

A multi-agent engineering workspace that plans, implements, tests, reviews, and verifies changes before you approve them.

### Core calls to action

- **INITIALIZE MISSION** — primary action
- **OPEN DEMO REPOSITORY** — secondary action
- **VIEW LAST MISSION** — only when a real previous mission exists

### Agent identities

Always pair themed names with plain-language roles:

| Guild name | Functional role | Suggested visual identity |
|---|---|---|
| **SHOGUN** | Planner | Gold seal, structured plan lines |
| **SAMURAI** | Developer | Vermilion accent, code/forge mark |
| **SENTINEL** | Tester | Jade/green verification mark |
| **SHADOW COUNCIL** | Reviewer | Muted silver/ink mark |
| **INDEPENDENT VERIFIER** | Deterministic verification process | Clear evidence/check icon; do not present as an LLM agent |

Keep labels understandable. The themed name should never hide what the agent does.

---

## 3. Visual Direction

### Overall feeling

- Cinematic, restrained, precise, premium.
- Japanese-inspired but not "cyber-samurai."
- Dark, tactile, atmospheric surfaces with warm, readable content areas.
- Strong typography and purposeful empty space.
- Gold is an accent for focus and interaction—not a color used on every border and label.

### Avoid

- Generic neon-purple AI gradients.
- Excessive glowing borders on every card.
- Anime characters, stock samurai portraits, or random Japanese symbols.
- Fake terminal logs, fabricated agent conversations, fake progress percentages, or scripted success states.
- Heavy 3D/WebGL effects that delay access to the real mission workflow.
- Overusing parallax or motion in dense engineering panels.

### Layering model

Use visual depth primarily through CSS, SVG, gradients, textures, shadows, and small motion cues. The application is a functional engineering tool; the interface must remain usable even if decorative effects are disabled.

1. **Base layer:** near-black ink surface with subtle grain.
2. **Atmosphere layer:** low-contrast mist/gradient and faint radial light.
3. **Structure layer:** charcoal panels, thin borders, dividers, and grid lines.
4. **Information layer:** high-contrast headings, readable body text, code, status and evidence.
5. **Accent layer:** gold seals, restrained crimson actions, jade verification states.

---

## 4. Design Tokens

Create one shared token file (for example `frontend/src/styles/tokens.css`). Components should consume tokens instead of hardcoding colors and radii.

```css
:root {
  /* Core surfaces */
  --color-sumi: #090A0C;
  --color-ink: #141416;
  --color-panel: #191A1F;
  --color-panel-raised: #202127;
  --color-border: rgba(239, 228, 205, 0.12);
  --color-border-strong: rgba(201, 154, 58, 0.36);

  /* Accents */
  --color-gold: #C99A3A;
  --color-gold-bright: #E8C66A;
  --color-gold-dark: #73501D;
  --color-crimson: #A70D16;
  --color-crimson-bright: #D81E28;
  --color-jade: #829B91;

  /* Text */
  --color-washi: #EFE4CD;
  --color-text: #E7E3DA;
  --color-text-muted: #A6A39D;
  --color-text-subtle: #777872;
  --color-success: #8FB7A0;
  --color-warning: #E3B96C;
  --color-danger: #E07B7B;
  --color-info: #91B5D4;

  /* Typography */
  --font-display: "Cinzel Decorative", "Cinzel", Georgia, serif;
  --font-heading: "Shippori Mincho", "Noto Serif", Georgia, serif;
  --font-body: "Plus Jakarta Sans", Inter, sans-serif;
  --font-mono: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;

  /* Spacing and shape */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-12: 3rem;
  --space-16: 4rem;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-pill: 999px;

  /* Motion */
  --ease-cinematic: cubic-bezier(0.25, 1, 0.5, 1);
  --ease-katana: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 140ms;
  --duration-normal: 240ms;
  --duration-slow: 480ms;
}
```

### Token usage rules

- Use `--color-sumi` for the app shell and large backgrounds.
- Use `--color-panel` / `--color-panel-raised` for panels and cards.
- Use gold for the active state, primary CTA, focused navigation, or meaningful emphasis.
- Use crimson for destructive actions and rare high-priority alerts.
- Use jade/green for verified or passing results; never rely on color alone.
- Use monospace for code, file paths, tool names, command output, and identifiers.
- Keep body copy readable at typical laptop viewing distance. Do not make functional labels tiny just to preserve atmosphere.

---

## 5. Typography and Content Hierarchy

- **Display:** Cinzel/Cinzel Decorative for the product wordmark and a few large editorial headings only.
- **Section headings:** Shippori Mincho or a reliable serif fallback.
- **Body/UI:** Plus Jakarta Sans or Inter.
- **Technical content:** JetBrains Mono or system monospace.
- If external fonts fail to load, layout must remain stable with fallbacks.

### Type scale

- Hero headline: `clamp(2.8rem, 6vw, 6.5rem)`, compact line-height.
- Page title: `clamp(2rem, 3vw, 3.2rem)`.
- Section title: `1.35rem–1.8rem`.
- Body: `0.95rem–1.05rem`.
- Labels and metadata: normally `0.75rem–0.875rem`, with sufficient contrast.
- Code/output: `0.82rem–0.95rem`, line-height around 1.55.

Use uppercase, letter-spaced labels sparingly for section markers such as `MISSION STATUS` or `GUILD ACTIVITY`. Do not set all interface text in uppercase.

---

## 6. App Shell and Navigation

### Desktop shell

- Full-height app shell with a restrained fixed or sticky top bar.
- Left brand mark: circular KAGE seal + wordmark.
- Main navigation: `Missions`, `Repositories`, `Evidence` (only include destinations that are implemented).
- Right side: connection/readiness status, settings if implemented, and profile/session control if applicable.
- Use a fine gold-tinted bottom border; keep the header opaque enough for legibility over any background.

### Brand mark

Create a simple original circular seal:

- Ink-black circle.
- Thin gold ring with a small intentional gap or brush-like break.
- One abstract K-shaped stroke or minimal shadow mark.
- Avoid copying PECFEST's logo or its exact Ensō artwork.

### Navigation behavior

- Active destination receives a small gold marker and stronger text contrast.
- Hover produces a restrained gold line/fracture detail.
- Keyboard focus is always visible.
- Do not use the cinematic page transition for every small tab or panel change. Reserve major transitions for entering/leaving a mission or switching top-level screens if it does not obstruct work.

---

## 7. Screen A — Mission Entrance

### Purpose

Make the product feel distinctive and immediately communicate what it does. The main action should be obvious without scrolling.

### Composition

- Dark, asymmetric hero with a quiet text region on the left and a layered abstract "gate / gateway" motif on the right.
- Large wordmark `KAGE AI`.
- Small eyebrow: `AUTONOMOUS ENGINEERING GUILD`.
- Headline: `Your Code. Our Guild. Verified Results.`
- Supporting line describing the real workflow.
- Primary CTA: `INITIALIZE MISSION`.
- Secondary CTA: `OPEN DEMO REPOSITORY`.
- A small, honest readiness strip for model connection, execution environment, and supported repository type.

### Hero artwork

Use CSS/SVG rather than requiring a 3D scene:

- A thin, architectural Torii-inspired frame made from simple lines/planes.
- One warm gold solar disc or radial glow behind the frame.
- Very subtle fog/grain and a few drifting particles only if performance allows.
- The visual should occupy the right half and never reduce contrast behind text.
- The artwork is a metaphor for entering a mission, not a clickable control unless the interaction is implemented.

### Below the hero

1. **Recent missions:** show real saved missions and their actual outcomes. Empty state should invite the user to initialize a mission.
2. **Mission flow:** `Plan → Build → Test → Review → Verify → Approve`.
3. **Guild overview:** four compact agent cards with name, role, and responsibility.
4. **Proof-first statement:** explain that final claims are tied to execution evidence.

### Empty and unavailable states

- If no previous missions exist, show a purposeful empty state rather than placeholder mission cards.
- If the model or execution environment is unavailable, show a visible status and next step. Do not show a green "ready" state unless the health check actually passed.

---

## 8. Screen B — Repository and Mission Setup

### Layout

Use a two-column setup view on desktop:

- **Repository panel** on the left.
- **Mission brief panel** on the right.

Stack panels vertically on narrow screens.

### Repository panel

Show:

- Selected local repository path or folder name.
- Detected project type and supported-language status.
- File tree or a concise repository summary.
- Included file count and excluded-file summary.
- Existing changes indicator.
- Selected execution profile.
- Preflight blockers and warnings with actionable remediation.

Do not expose sensitive absolute paths unnecessarily. Treat file names and repository contents as untrusted text.

### Mission brief panel

- Request textarea with a clear prompt label.
- Suggested acceptance criteria derived from the request.
- Allow the user to edit/confirm criteria before execution.
- Show scope boundaries and any destructive or ambiguous action that needs clarification.
- Display execution budget/time limits if the backend actually enforces them.
- Primary action: `START MISSION`.

### Preflight states

Use distinct visible states:

- `READY`
- `WARNING`
- `BLOCKED`
- `CHECKING`

Each state must include text/icon and a reason. A warning must not be styled like a blocker; a blocker must not be bypassable by a decorative CTA.

---

## 9. Screen C — Live Command Center

### Purpose

This is the primary product screen. It should feel like an operational command room, but retain the clarity of a professional developer tool.

### Desktop layout

Three main columns below a compact mission header:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ KAGE · Mission title · Candidate · Elapsed time · Budget · STOP      │
├────────────────┬──────────────────────────────┬──────────────────────┤
│ THE GUILD      │ LIVE MISSION ACTIVITY        │ INSPECTOR            │
│                │                              │                      │
│ Shogun         │ Real event timeline          │ Acceptance criteria  │
│ Samurai        │ Task assigned / file read    │ Selected tool call   │
│ Sentinel       │ Check failed / repair asked  │ File / diff          │
│ Shadow Council │ Candidate submitted          │ Check output         │
└────────────────┴──────────────────────────────┴──────────────────────┘
```

### Mission header

Show only real backend state:

- Mission title/request summary.
- Candidate version or identifier.
- Elapsed time.
- Enforced budget/usage, where measurable.
- Overall state.
- `STOP MISSION` control with clear confirmation/behavior.

Never use a fake animated percentage as a substitute for actual progress. If a reliable percentage is unavailable, use named lifecycle stages and event activity.

### Guild panel

Each agent row/card includes:

- Themed name and plain role.
- Actual status: `IDLE`, `WORKING`, `WAITING`, `BLOCKED`, `DONE`, `FAILED`.
- Current assigned task if available.
- Most recent event timestamp.
- A subtle status indicator.

Do not animate an agent as working unless the controller reports it is working. Avoid chat bubbles that imply private chain-of-thought. Show concise decision summaries, task updates, and evidence references only.

### Live activity timeline

- Chronological real events streamed from the backend.
- Distinguish task assignment, tool execution, check result, finding, repair request, candidate update, and verification.
- Each row shows timestamp, actor, action, and result.
- Expandable rows reveal safe bounded output or linked artifacts.
- New events may appear with a brief opacity/position transition; do not reorder old events unexpectedly.
- Provide reconnecting/paused/disconnected state if SSE is interrupted.

### Inspector panel

Contextual tabs or sections:

- `CRITERIA`
- `TASK`
- `FILE / DIFF`
- `TOOL OUTPUT`
- `FINDINGS`

Render repository text and tool output as plain text or safely escaped content. Never inject untrusted output as executable HTML.

### Signature interaction: evidence-driven repair

When a real check fails:

1. Show the failed check with its actual output.
2. Show the finding and affected acceptance criterion.
3. Show the repair task being reopened/assigned.
4. Show the new candidate identifier when produced.
5. Show the check being rerun and its real result.

Use a restrained gold fracture/line animation to connect the finding to the repair task. This visual effect must only run when the corresponding real events occur. Never simulate a failure-to-success sequence for the demo.
---

## 10. Screen D — Live IDE Workspace

### Purpose

Give the user an IDE-like environment where they can inspect repository files, watch real agent-proposed changes, review diffs, edit code where supported, and understand what has changed without leaving KAGE AI.

**The IDE is not a decorative mockup.** It must reflect the actual repository, candidate versions, change events, and execution evidence supplied by the backend.

### Design principles

- Familiar developer-tool layout.
- Dark ink surfaces with subtle gold active states.
- Readable syntax highlighting and clear diff colors.
- Real file paths, real code, real candidate changes.
- Clear separation between proposed, verified, and applied changes.
- User edits must not be silently overwritten by agent updates.
- No fabricated agent activity or fake terminal output.

### Desktop layout

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ KAGE AI │ Mission: Add Input Validation │ Candidate v3 │ VERIFIED │ Actions │
├─────────────────┬───────────────────────────────────────┬────────────────────┤
│ EXPLORER         │ EDITOR                                │ GUILD ACTIVITY     │
│                 │                                       │                    │
│ ▾ repository    │ validation.py  tests.py  README.md     │ SHOGUN             │
│   ▾ src         │───────────────────────────────────────│ Planning           │
│     app.py      │  1  def validate_input(value):        │                    │
│     validation.py│ 2      ...                           │ SAMURAI             │
│   ▾ tests       │  3                                     │ Proposed a change  │
│     test_app.py │                                       │                    │
│   README.md     │                                       │ SENTINEL            │
│                 │                                       │ Tests: real status │
├─────────────────┴───────────────────────────────────────┴────────────────────┤
│ PROBLEMS │ TESTS │ TERMINAL OUTPUT │ DIFF │ MISSION EVENTS                  │
│                                                                              │
│ Actual diagnostics, execution results, selected diff, or event details       │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Main regions

#### A. Repository Explorer

Display the repository tree using actual file and directory information.

Features:

- Expand and collapse directories.
- Select a file to open it.
- Display file type icons.
- Highlight the active file.
- Indicate files with proposed or modified changes.
- Show pending-change markers only when supported by real change metadata.
- Filter/search file names when supported.
- Display a loading, empty, or error state when the tree is unavailable.

Security requirements:

- Treat file paths as untrusted input.
- Do not expose files outside the approved repository boundary.
- Do not make ignored or secret files accessible just because they exist on disk.
- Respect backend exclusions and repository access permissions.

#### B. Code Editor

Use an editor component appropriate for the existing frontend stack.

Recommended behavior:

- Tabs for opened files.
- Syntax highlighting based on file type.
- Line numbers.
- Current line/cursor indication.
- Search within a file if supported.
- Read-only and editable modes.
- Unsaved-change indicator.
- Clear indication when the displayed content belongs to a candidate rather than the working tree.
- A visible error if a file cannot be loaded.

**Editing strategy:**

1. Inspect the existing frontend and available editor dependencies.
2. Reuse an existing editor if one is already configured.
3. If a new editor is needed, choose a maintained option compatible with the project.
4. Do not add a heavy dependency without checking its bundle-size and setup implications.
5. If editing is not supported by the backend, provide a read-only code viewer rather than a misleading editable editor.

#### C. Guild Activity Feed

Display actual engineering events relevant to the current mission.

Each event should include:

- Agent name and functional role.
- Timestamp.
- A concise action summary.
- Affected file or candidate, when available.
- Change status.
- A control to inspect the associated diff or evidence, when available.

Example event presentation:

```text
SAMURAI · Developer
Proposed an update to src/validation.py
Candidate: CANDIDATE-03
Status: Awaiting review
[Inspect diff]
```

The example above illustrates presentation only. Populate every field from actual backend data. Do not hardcode this event as if it occurred.

#### D. Bottom Panel

Provide resizable or collapsible tabs:

- **PROBLEMS:** actual diagnostics and review findings.
- **TESTS:** actual test runs, results, counts, and failure details.
- **TERMINAL OUTPUT:** bounded output from real authorized execution.
- **DIFF:** selected candidate diff.
- **MISSION EVENTS:** chronological event history.

If a panel's underlying data is unavailable, show an explicit empty/unavailable state.

### Live change lifecycle

Represent change state explicitly. A change can move through states such as:

1. `PROPOSED` — an agent has submitted a change proposal.
2. `REVIEWING` — the proposal is being inspected.
3. `IN_CANDIDATE` — the change is included in the current candidate.
4. `VERIFIED` — the exact candidate has passed the configured verification process.
5. `REJECTED` — the proposal was rejected.
6. `STALE` — the proposal or verification no longer matches the current candidate.
7. `APPLIED` — the change has been applied to the target working tree.

These states must reflect the backend's actual lifecycle. If the backend uses different names, map them consistently in the UI without losing meaning.

**Important distinction:** `VERIFIED` does not mean `APPLIED`. Verification proves something about a specific candidate; applying it is a separate operation.

### How live updates should work

1. Subscribe to the backend's supported live event stream, such as SSE.
2. Associate every event with its mission and candidate identity.
3. Update the repository markers, event feed, editor state, and diff viewer using the same authoritative event.
4. Fetch or request the actual changed file content when necessary.
5. Do not invent file contents from an event summary.
6. On reconnect, reconcile with authoritative backend state before declaring the workspace current.
7. Detect when an incoming update conflicts with an unsaved user edit.
8. Preserve the user's unsaved content and offer an explicit compare/reload/merge action.

### Editing code inside KAGE

The interface should support two distinct workflows where the backend allows them:

**Workflow A — Inspect agent changes**

- Select a changed file.
- Inspect the proposed code.
- Open the diff.
- Review the associated findings and test results.
- Navigate to the relevant evidence.

**Workflow B — Make a user edit**

- Open the file in editable mode.
- Modify the code.
- Mark the editor buffer as unsaved.
- Submit the change through a supported backend operation.
- Create or update the appropriate candidate.
- Rerun the relevant checks.
- Invalidate previous verification when the candidate changes.
- Display the new candidate identity and actual verification result.

If a safe editing or candidate-update endpoint does not exist, do not fake the workflow. Keep the code viewer read-only and clearly explain that editing through the UI is not currently available.

### Diff viewer

Use a standard side-by-side or unified diff layout.

Display:

- File path.
- Change type: added, modified, deleted, or renamed.
- Old and new line numbers.
- Added and removed lines.
- Context lines.
- Candidate identity.
- Proposal source, if available.
- Verification status for the candidate, not merely for an individual file.

Use restrained green/red or equivalent semantic styling. The diff must remain understandable without color.

Include empty states for:

- No changes.
- Diff unavailable.
- Candidate expired or stale.
- File deleted or renamed.
- Permission denied.

### Candidate integrity and conflict handling

- Bind every diff to a specific candidate/version.
- Do not mix files from different candidate versions.
- If the candidate changes while the user is reviewing it, show a visible stale-state banner.
- If the working tree changes outside the application, reconcile before applying updates.
- Do not silently overwrite external modifications.
- Keep proposal, verification, and apply operations separate.
- Record operation outcomes from the backend.
- Require explicit confirmation for consequential operations.

### Suggested UI controls

- `Open file`
- `Inspect diff`
- `Compare versions`
- `Save user edit`
- `Run checks`
- `Refresh candidate`
- `Review evidence`
- `Approve and apply` — only when supported by the actual backend.

Hide or disable unsupported operations with a clear explanation. Never present a button as functional if no operation backs it.

---

## 11. Screen E — Evidence and Human Approval

### Purpose

This screen is the trust boundary between AI-generated work and changes applied to the user's repository.

The visual language should be calmer and more document-like than the Live Command Center. Use a structured evidence layout, warm text contrast, clear decision labels, and restrained gold dividers.

### Header

Show:

- Mission title.
- Exact candidate ID/version.
- Candidate creation/update timestamp.
- Overall verification state.
- Approval state.
- Repository identity.

Never show a generic success badge without linking it to the candidate being reviewed.

### Evidence layout

#### A. Acceptance criteria

List each criterion from the mission brief with:

- Criterion text.
- Current status.
- Evidence supporting the status.
- Related test/check, when applicable.
- Explanation of any unresolved issue.

Possible statuses:

- `PASS`
- `FAIL`
- `PARTIAL`
- `NOT VERIFIED`
- `BLOCKED`

Use explicit text and icons, not color alone.

#### B. Test and verification results

Display only real results:

- Command or check name.
- Execution status.
- Exit code, if available.
- Start/end time or duration, if available.
- Passed/failed counts, if actually reported.
- Relevant output or artifact.
- Environment information needed to interpret the result.

Distinguish between a check that passed, a check that failed, and a check that never ran.

Do not equate an agent saying "tests should pass" with an executed passing test.

#### C. Code changes

Show a summary of the exact candidate:

- Files added.
- Files modified.
- Files deleted.
- Files renamed.
- Diff links.
- Any limitations in the diff or review.

The summary must be computed from authoritative change metadata.

#### D. Reviewer findings

For each finding, show:

- Severity.
- File and line reference, if available.
- Finding description.
- Supporting evidence.
- Resolution status.

Do not imply that a finding is resolved merely because a later agent message says it was fixed. Reconcile the finding with the current candidate and verification evidence.

#### E. Risk and limitations

Make known limitations visible:

- Checks not run.
- Incomplete acceptance criteria.
- Unsupported project areas.
- Environmental limitations.
- Remaining reviewer findings.
- Candidate staleness.
- Apply conflicts.

Never hide a failed check behind a polished success screen.

### Approval panel

Place the final decision panel on the right on large screens and below the evidence on smaller screens.

It should contain:

- Candidate identity.
- Verification summary.
- Unresolved risks.
- Explicit approval action.
- Reject action.
- Request-changes action, if supported.
- A clear statement of what applying the candidate will change.

Example action labels:

- `APPROVE & APPLY`
- `REJECT CANDIDATE`
- `REQUEST CHANGES`

Only display actions supported by the backend. If approval is supported but application is not, label the action accurately as approval rather than claiming it will apply code.

### Approval safety rules

1. The user must know exactly which candidate is being approved.
2. Approval must be tied to an immutable or version-checked candidate identity.
3. If the candidate changes after review, require review of the new version.
4. If verification is stale, do not present the candidate as verified.
5. If apply fails, report failure and preserve the actual repository state.
6. Do not treat a button click as proof that an operation succeeded; wait for backend confirmation.
7. Make rejection and cancellation behavior clear.
8. Never automatically apply an unreviewed candidate simply because the agents finished.

---

## 12. Interaction Design and Motion

### Motion philosophy

Motion should make state transitions easier to understand. It should not distract from code, evidence, or test results.

Use the design tokens for consistent timing and easing.

### Signature interactions

#### 1. Crossing the gate

On entering a mission, a thin architectural frame can expand or separate to reveal the workspace.

- Duration: approximately 350–500 ms.
- Respect reduced-motion preferences.
- Avoid blocking access to the interface.
- Do not replay on every small navigation action.

#### 2. Kamon navigation marker

A small circular marker may rotate or reveal a gold stroke when the active destination changes.

- Keep the movement subtle.
- Preserve a visible static active state.
- Do not use animation as the only active-state indicator.

#### 3. Agent status transitions

When a real event changes an agent's state:

- Update the status label.
- Animate a small opacity or border change.
- Add the event to the activity timeline.
- Keep the previous event available for inspection.

Do not animate idle agents to simulate activity.

#### 4. Diff reveal

When a user opens a diff:

- Reveal the panel with a short slide/fade.
- Preserve scroll position when switching between nearby files where practical.
- Highlight changed lines using normal diff conventions.
- Do not animate every line independently.

#### 5. Verification completion

When a real verification result arrives:

- Show the actual result.
- Update the candidate's verification badge.
- Link to the supporting evidence.
- Use a restrained gold or jade accent.
- Never show a success animation before the backend confirms success.

### Reduced motion

Support `prefers-reduced-motion: reduce`.

When enabled:

- Disable parallax.
- Remove nonessential floating particles.
- Replace large transitions with immediate or minimal state changes.
- Keep all functionality accessible.

---

## 13. Responsive Design

### Large desktop

- Full three-column command center.
- Full IDE workspace with explorer, editor, guild feed, and bottom panel.
- Side-by-side code diffs.
- Persistent mission header.

### Laptop

- Keep the editor as the primary focus.
- Allow the repository explorer and guild feed to collapse.
- Use a resizable inspector or slide-out panel.
- Keep important mission state visible.

### Tablet

- Switch from three columns to editor-first layout.
- Use a drawer for the repository explorer.
- Use a separate activity/inspector panel.
- Allow the bottom panel to expand vertically.
- Keep approval actions accessible without horizontal scrolling.

### Mobile

- Do not shrink the desktop IDE into an unreadable three-column layout.
- Use a single-column mission view with dedicated tabs:
  - `CODE`
  - `ACTIVITY`
  - `TESTS`
  - `DIFF`
  - `EVIDENCE`
- Use a file picker/drawer for repository navigation.
- Make code horizontally scrollable where necessary.
- Keep the mission status and candidate identity visible.
- Put approval actions in a clearly separated, accessible panel.
- Avoid sticky controls that cover code or important text.

### Responsive acceptance criteria

- No unintended horizontal overflow at common viewport sizes.
- Code and diffs remain readable.
- Important actions are reachable with touch and keyboard.
- No essential information is available only through hover.
- Status indicators and evidence remain visible on small screens.

---

## 14. Component Inventory

Build reusable components rather than creating one oversized screen component.

### Application shell

- `AppShell`
- `TopNavigation`
- `BrandSeal`
- `PrimaryNavigation`
- `ConnectionStatus`
- `PageTransition`

### Mission entrance and setup

- `MissionHero`
- `MissionFlow`
- `RecentMissions`
- `GuildOverview`
- `RepositorySelector`
- `RepositorySummary`
- `MissionBriefForm`
- `AcceptanceCriteriaEditor`
- `PreflightStatus`
- `StartMissionButton`

### Live Command Center

- `MissionHeader`
- `MissionStatusBadge`
- `GuildPanel`
- `AgentCard`
- `MissionEventTimeline`
- `MissionEventRow`
- `MissionInspector`
- `AcceptanceCriteriaList`
- `ToolOutputViewer`
- `StopMissionDialog`

### IDE workspace

- `IDEWorkspace`
- `RepositoryExplorer`
- `RepositoryTree`
- `RepositoryTreeItem`
- `CodeEditorTabs`
- `CodeViewer`
- `CodeEditor`
- `UnsavedChangesIndicator`
- `LiveChangeFeed`
- `ChangeEventCard`
- `CandidateDiffViewer`
- `DiffFileHeader`
- `BottomPanelTabs`
- `ProblemsPanel`
- `TestsPanel`
- `TerminalOutputPanel`
- `MissionEventsPanel`
- `StaleCandidateBanner`
- `EditorConflictDialog`

### Evidence and approval

- `EvidencePage`
- `CandidateIdentity`
- `CriteriaEvidenceTable`
- `VerificationSummary`
- `TestResultCard`
- `ReviewerFindingCard`
- `RiskDisclosure`
- `ApprovalPanel`
- `ApplyResultBanner`

### Shared components

- `StatusBadge`
- `EmptyState`
- `LoadingState`
- `ErrorState`
- `ConfirmationDialog`
- `Toast`
- `Tooltip`
- `KeyboardShortcutHint`
- `CopyButton`
- `CodeBlock`
- `AccessibleTabs`

Keep the component inventory aligned with the actual application. Do not build unused components simply because they appear in this specification.

---

## 15. Accessibility and Trust

### Accessibility

- Use semantic HTML landmarks and headings.
- All actions must be keyboard-accessible.
- Provide clear focus indicators.
- Use accessible names for icon-only buttons.
- Announce meaningful live status updates without announcing every streaming token.
- Ensure contrast for text, borders, badges, and code.
- Do not rely on color alone to distinguish states.
- Ensure dialogs manage focus correctly.
- Respect reduced-motion preferences.
- Keep code editor keyboard behavior compatible with surrounding page navigation.

### Trust and transparency

The interface must make these distinctions obvious:

- Agent proposal vs. accepted candidate change.
- Candidate change vs. working-tree change.
- Test suggestion vs. executed test.
- Test failure vs. test not run.
- Verified candidate vs. applied candidate.
- UI approval click vs. confirmed backend operation.
- Real-time stream vs. stale/disconnected state.

The application should never claim an operation succeeded before receiving authoritative confirmation.

### Privacy and security

- Do not expose API keys, environment variables, secrets, or sensitive command output in UI logs.
- Escape repository text and terminal output.
- Do not execute content rendered in the interface.
- Avoid logging secrets to browser consoles.
- Keep destructive actions explicit and separately confirmed.
- Follow backend authorization and repository-boundary restrictions.
- Treat agent-generated text and repository content as untrusted data.
---

## 16. Frontend Architecture and Integration

### Primary objective

Implement the design within the existing DevPilot/KAGE AI project without breaking its working backend, API contracts, mission lifecycle, candidate identity, evidence model, or approval workflow.

**First inspect the existing codebase. Do not rebuild the application from scratch before understanding its architecture.**

### Initial repository inspection

Before making changes, identify:

* Existing frontend framework and entry point.
* Current routes and screens.
* Existing CSS structure and design tokens.
* Backend API routes and response schemas.
* SSE endpoints and event formats.
* Mission lifecycle and candidate state handling.
* Repository browsing and file-content APIs.
* Diff-generation and candidate-update mechanisms.
* Test execution and verification endpoints.
* Approval and apply operations.
* Existing authentication, authorization, and execution restrictions.

Produce a short implementation map before starting major refactoring.

### Framework strategy

Preserve the framework and build system already used by the repository.

If the existing frontend is plain HTML, CSS, and JavaScript, continue with that approach unless there is a clear, justified reason to migrate.

If React and TypeScript are already configured and working, use them to build reusable screens and components.

Do not migrate frameworks solely to match this design specification.

### Suggested component organization

Adapt these paths to the actual repository:

```text
frontend/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell
│   │   │   ├── TopNavigation
│   │   │   └── BrandSeal
│   │   ├── mission/
│   │   │   ├── MissionHeader
│   │   │   ├── MissionEventTimeline
│   │   │   └── GuildPanel
│   │   ├── ide/
│   │   │   ├── IDEWorkspace
│   │   │   ├── RepositoryExplorer
│   │   │   ├── CodeEditorTabs
│   │   │   ├── CandidateDiffViewer
│   │   │   └── BottomPanelTabs
│   │   └── evidence/
│   │       ├── VerificationSummary
│   │       ├── CriteriaEvidenceTable
│   │       └── ApprovalPanel
│   ├── pages/
│   │   ├── MissionEntrance
│   │   ├── MissionSetup
│   │   ├── MissionCommandCenter
│   │   ├── IDEWorkspacePage
│   │   └── EvidenceApprovalPage
│   ├── services/
│   │   ├── api
│   │   ├── missionEvents
│   │   └── repository
│   ├── hooks/
│   ├── styles/
│   │   ├── tokens.css
│   │   ├── global.css
│   │   ├── layout.css
│   │   └── components.css
│   └── utils/
└── ...
```

This is an organizational suggestion, not a requirement to create every file. Match the current project structure and conventions.

---

## 17. Backend Contract and State Management

### Core principle

**The backend is the source of truth for mission state, candidate identity, code changes, verification, and application results.**

The frontend may maintain temporary UI state, such as open tabs and panel selection, but must not invent authoritative engineering state.

### State categories

Keep these categories distinct:

1. **Mission state:** lifecycle, current stage, and execution status.
2. **Agent state:** reported task and status for each agent.
3. **Repository state:** actual files, directories, and permitted contents.
4. **Candidate state:** candidate ID/version and its proposed changes.
5. **Verification state:** results associated with a particular candidate.
6. **Approval state:** user decision and backend confirmation.
7. **Apply state:** whether the candidate was actually applied.
8. **UI state:** selected file, open tabs, expanded panels, and unsaved local edits.
9. **Connection state:** live stream connected, reconnecting, disconnected, or failed.

Do not combine all these categories into one generic status variable.

### Data-contract rules

* Reuse existing backend schemas and endpoints.
* Preserve established field names and enum values.
* Do not invent endpoints simply because the UI requires them.
* If a capability is missing, document the gap rather than faking the behavior.
* Handle unknown or newly introduced event types safely.
* Validate data before rendering it.
* Keep candidate identity attached to diffs and verification results.
* Treat missing data as unavailable, not as a successful result.

### Live event handling

For a supported SSE or equivalent event stream:

1. Connect using the existing backend contract.
2. Associate events with the correct mission.
3. Parse and validate each event.
4. Update only the affected state.
5. Prevent duplicate events from creating duplicate activity entries where the protocol supports deduplication.
6. Reconnect after interruptions according to the supported protocol.
7. Reconcile with authoritative state after reconnecting.
8. Show a connection warning if the state may be stale.

If the backend exposes event IDs or replay cursors, use them according to the established contract. Do not assume those fields exist.

### Stale data

If an event or response belongs to an older candidate:

* Do not overwrite the current candidate state with it.
* Do not associate its verification result with a newer candidate.
* Preserve historical results as historical records where supported.
* Make stale state visible to the user.

### Error handling

Provide actionable errors for:

* Backend unavailable.
* Mission not found.
* Repository access denied.
* File unavailable.
* Unsupported file type.
* Event stream disconnected.
* Candidate changed during review.
* Verification failed.
* Apply operation rejected.
* Apply conflict.
* Request timeout.

Do not silently replace errors with empty successful-looking panels.

---

## 18. Visual Assets and Atmosphere

### Recommended approach

Use lightweight, original CSS/SVG artwork that complements the Japanese-inspired design.

Preferred elements:

* Original circular seal.
* Minimal geometric Torii-inspired frame.
* Fine gold dividers.
* Subtle paper/ink texture.
* Low-opacity radial gradients.
* Abstract brush-stroke details.
* Small ornamental marks used consistently.

### Avoid asset bloat

* Do not add large background videos.
* Do not require WebGL for the primary experience.
* Do not add multiple animation libraries for minor effects.
* Avoid heavy image assets behind code or evidence.
* Use decorative textures sparingly.
* Keep a CSS fallback if an external asset fails to load.

### Performance requirements

* Prioritize the first meaningful screen render.
* Avoid unnecessary rerenders during frequent event updates.
* Do not recreate the entire IDE tree for every incoming event.
* Debounce expensive search/filter operations where necessary.
* Keep large terminal output bounded.
* Virtualize very large file trees or event lists if needed.
* Clean up SSE subscriptions and event listeners when components unmount.
* Avoid background animations that compete with code readability.

---

## 19. Testing and Verification

The frontend should be validated against the actual running application and backend.

### Functional tests

Where supported by the existing test setup, verify:

* Mission entrance and navigation.
* Repository selection.
* Mission brief submission.
* Preflight warnings and blockers.
* Live mission event handling.
* Agent status updates.
* Repository tree expansion and file selection.
* Code viewer and editor behavior.
* Diff rendering.
* Candidate version changes.
* Stale verification handling.
* Test-result presentation.
* Approval workflow.
* Apply success and failure.
* SSE disconnection and reconnection.
* Unsaved-edit conflict handling.

### Visual checks

Review the application at:

* Large desktop viewport.
* Standard laptop viewport.
* Tablet viewport.
* Narrow mobile viewport.

Check:

* Text contrast.
* Spacing consistency.
* Overflow.
* Editor readability.
* Diff alignment.
* Sticky-header overlap.
* Dialog behavior.
* Loading and empty states.
* Reduced-motion behavior.

### Accessibility checks

Verify:

* Keyboard navigation.
* Visible focus states.
* Accessible tabs and dialogs.
* Screen-reader labels.
* Contrast.
* Status announcements.
* Reduced-motion preferences.

### Backend integration checks

Use real backend responses to verify that:

* Mission state is displayed accurately.
* Agent events appear when emitted.
* File contents match the selected repository and candidate.
* Diffs correspond to the displayed candidate.
* Test results match actual execution.
* Verification is invalidated when the candidate changes.
* Approval is tied to the reviewed candidate.
* Apply results reflect the backend's actual outcome.

Never fabricate passing tests to make a screenshot or demonstration look complete.

---

## 20. Recommended Implementation Order

Implement the system in small, verifiable increments.

### Phase 1 — Inspect and stabilize

* Inspect the repository and existing frontend.
* Map the current backend contracts.
* Identify which requested capabilities already exist.
* Document missing APIs and unsupported workflows.
* Run the existing tests and record the baseline.

### Phase 2 — Establish the design system

* Add shared design tokens.
* Define typography and global surfaces.
* Establish buttons, inputs, tabs, badges, dialogs, and empty states.
* Implement the application shell and responsive navigation.

### Phase 3 — Build mission screens

* Implement Mission Entrance.
* Implement Repository/Mission Setup.
* Implement the Live Command Center.
* Connect each screen to existing backend state.
* Verify loading, empty, error, and blocked states.

### Phase 4 — Build the IDE workspace

* Implement the repository explorer.
* Implement file selection and code viewing.
* Add editor tabs.
* Add live change events.
* Implement candidate-aware diff viewing.
* Add Problems, Tests, Terminal Output, Diff, and Mission Events panels.
* Implement safe editing only if the backend supports it.
* Handle stale candidates and unsaved-edit conflicts.

### Phase 5 — Build evidence and approval

* Show acceptance criteria.
* Present actual test and verification results.
* Show candidate-specific diffs.
* Present reviewer findings and limitations.
* Implement candidate-bound approval.
* Display the real outcome of apply operations.

### Phase 6 — Polish and validate

* Add restrained signature motion.
* Verify responsive layouts.
* Run functional and visual checks.
* Validate accessibility.
* Check performance under frequent event updates.
* Confirm that no existing backend behavior has regressed.

After each phase, run the relevant tests before continuing.

---

## 21. Coding-Agent Instructions

Use the following instructions when handing this design specification to a coding agent.

### Mission

Implement the KAGE AI design system in the existing DevPilot/KAGE AI repository.

### Mandatory rules

1. Inspect the repository before editing.
2. Preserve the existing working backend and its API contracts.
3. Do not replace real functionality with hardcoded mock data.
4. Do not invent agent activity, code changes, test results, or verification states.
5. Use the existing frontend framework unless a migration is demonstrably necessary.
6. Implement the screens in incremental, testable stages.
7. Keep candidate identity consistent across the editor, diffs, verification, and approval.
8. Keep verification and applying changes as separate lifecycle states.
9. Do not allow stale verification to authorize a newer candidate.
10. Do not silently overwrite user edits or external repository modifications.
11. Escape repository content and terminal output.
12. Respect repository boundaries and backend security restrictions.
13. Provide accessible loading, empty, error, and blocked states.
14. Respect reduced-motion settings.
15. Run the available tests and report actual results.
16. Clearly disclose any feature that cannot be completed because its backend support is missing.

### Expected deliverables

* Updated frontend implementation.
* Reusable design tokens and components.
* Mission screens integrated with real backend state.
* IDE workspace with real repository/file data wherever supported.
* Candidate-aware change and diff visualization.
* Evidence and human-approval screen.
* Responsive layouts.
* Tests or validation for implemented behavior.
* A concise implementation report.

### Implementation report format

At completion, report:

* What was implemented.
* Which files were changed.
* Which backend endpoints/events were integrated.
* Which tests were run.
* Actual test outcomes.
* Which features remain incomplete.
* Any backend/API changes that would be required.
* Any known security, usability, or performance limitations.

Do not claim completion for features that were only visually mocked.

---

## 22. Final Acceptance Checklist

### Design

* [ ] Original KAGE AI identity is consistent across all screens.
* [ ] Japanese-inspired visual elements are restrained and purposeful.
* [ ] The interface avoids generic neon-cyberpunk styling.
* [ ] Typography and spacing follow shared design tokens.
* [ ] Gold, crimson, and jade are used consistently.
* [ ] Motion is subtle and respects reduced-motion settings.

### Mission workflow

* [ ] The user can access the mission setup flow.
* [ ] Repository and mission information reflect real backend data.
* [ ] Preflight blockers and warnings are distinguishable.
* [ ] The command center displays real mission and agent states.
* [ ] Live events are not fabricated.
* [ ] Connection loss and stale state are visible.

### IDE workspace

* [ ] The repository explorer uses actual permitted repository data.
* [ ] File selection displays the correct file content.
* [ ] Candidate changes are clearly identified.
* [ ] Diff content corresponds to the correct candidate.
* [ ] Proposed, verified, rejected, stale, and applied states are distinguished.
* [ ] Tests and terminal output reflect actual execution.
* [ ] Unsupported editing capabilities are not falsely presented as functional.
* [ ] User edits are not silently overwritten.
* [ ] Incoming events cannot silently replace unsaved edits.
* [ ] Large event lists and outputs are handled responsibly.

### Evidence and approval

* [ ] Acceptance criteria are visible.
* [ ] Test and verification results link to actual evidence.
* [ ] Failed checks are not represented as passing.
* [ ] Unrun checks are distinguishable from passed checks.
* [ ] Candidate identity is visible during approval.
* [ ] Verification is invalidated or marked stale when the candidate changes.
* [ ] Applying changes requires the appropriate explicit approval.
* [ ] Apply outcomes reflect actual backend responses.

### Engineering quality

* [ ] Existing backend contracts remain intact.
* [ ] No unsupported endpoints are assumed to exist.
* [ ] Repository boundaries are respected.
* [ ] Untrusted file and terminal content is safely rendered.
* [ ] Keyboard navigation and focus indicators work.
* [ ] Responsive layouts are usable.
* [ ] Available tests have been run.
* [ ] Actual results and remaining limitations are documented.

---

## 23. Final Product Principle

KAGE AI should combine the atmosphere of a cinematic engineering guild with the precision of a professional IDE.

The visual design creates identity. The live workspace creates transparency. The evidence layer creates trust. Human approval preserves control.

**The governing principle is simple:**

> Build in the Shadows. Prove in the Light.

Every meaningful engineering claim must be traceable to real state, real changes, and real evidence.
