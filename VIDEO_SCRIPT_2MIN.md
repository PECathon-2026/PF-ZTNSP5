# KAGE AI — two-minute demo video

**Format:** 1920×1080, English narration, screen recording.  
**Duration:** target **1:55**, leaving five seconds below the two-minute limit.  
**Pace:** approximately 200 spoken words at 125–135 words/minute, with short pauses for clicks. Keep the final export under **2:00**.

Use the saved real run for predictable timing. Do not wait for live model calls
during the two-minute recording. Label saved-run footage as recorded evidence.

## Timed script

| Time | Screen / action | Say this |
| --- | --- | --- |
| **0:00–0:12** | Landing page. Hold on KAGE AI and the four-role visual. Overlay: **“AI code needs evidence.”** | “AI-generated code is easy to get. Knowing what changed, whether it works, and when to trust it is harder. That’s why we built KAGE AI.” |
| **0:12–0:26** | Show New mission with the local demo repo and pagination request. Cut to the saved task/criteria panel. | “I request a pagination fix without breaking existing behavior. KAGE inspects the repository, proposes tasks and acceptance checks, and waits for my authorization.” |
| **0:26–0:43** | Workspace: show Dojo, then Agent Graph and one recorded handoff. Active highlights require genuine recorded footage of a running mission; completed saved runs remain idle. | “Shogun plans. Samurai develops. Sentinel runs Docker tests and security checks. Shadow Council reviews. The Dojo highlights working agents, while the graph connects recorded handoffs to their evidence.” |
| **0:43–0:59** | Saved successful mission: show evidence, the four criteria, and the pagination diff. Overlay: **“Previously recorded real run · 4 criteria passed.”** | “This saved real run passed four acceptance criteria. I can inspect commands, output and the candidate fingerprint, then compare the patch with its frozen baseline.” |
| **0:59–1:15** | Cut to the boxed CLI dashboard. Show the active-agent row, latest handoff and a test-review/diff pane from genuine recorded CLI footage. Overlay: **“CLI · previously recorded agent activity.”** | “The same guild also runs from the command line. Its dashboard highlights active agents and the latest handoff, shows recorded activity and budgets, and lets me review tests and diffs.” |
| **1:15–1:37** | Review screen: show fingerprint and criteria. Use the genuine pre-approval screenshot, then the recorded applied result. Do not apply an already-applied candidate again. | “An independent verifier evaluates the recorded evidence. Human approval is tied to the exact candidate fingerprint. Applying it to the original repository is a separate action, in either interface. Until then, the original stays unchanged.” |
| **1:37–1:48** | Show Applied and the source diff. Overlay: **“Automated browser walkthrough · disposable repo · real model + Docker.”** | “This disposable demo reached Applied. The saved files matched the approved candidate, and the original tests were preserved.” |
| **1:48–1:55** | Landing page or clean Agent Graph. Overlay: **“KAGE AI · PECATHON 2026 · PS-001.”** | “KAGE AI: four roles, one traceable change, and the final decision stays with you.” |

## Open these tabs and terminal before recording

1. Landing: <http://127.0.0.1:3001/>
2. New mission: <http://127.0.0.1:3001/missions/new>
3. Successful workspace: <http://127.0.0.1:3001/missions/miss-aef4cc8a/workspace>
4. Successful graph: <http://127.0.0.1:3001/missions/miss-aef4cc8a/graph>
5. Applied result: <http://127.0.0.1:3001/missions/miss-aef4cc8a/review>
6. Mission archive: <http://127.0.0.1:3001/missions>
7. CLI terminal: from `backend/`, run `python -m app.cli` to open the boxed dashboard. Prepare genuine active-run footage separately; show its highlighted agent, latest handoff, and review pane during the 16-second CLI segment. Do not wait for model calls in the final recording.

These IDs refer to the local saved run, not data bundled into a clone. If unavailable,
generate a fresh real run using `frontend-v2/scripts/live-walkthrough.mjs` and replace
the IDs before recording.

For the approval gate, the genuine earlier screenshot is:
`frontend-v2/test-results/live-1793326118241/review-before-approval.png`.
The successful raw integrity check is in `integrity-recheck.json` beside it.
The initial line-ending test-oracle failure remains recorded in `report.json`.

## Exact request to display

> Fix the off-by-one slicing bug in paginate so full pages contain the requested
> number of items. Preserve partial pages, empty input, and existing invalid-page
> validation. Keep tests unchanged; make only the necessary source change.

## Recording preparation — five minutes

- Prefer production frontend mode for recording: stop **only the frontend dev
  terminal**, then run `npm run build` followed by `npm start` from `frontend-v2/`.
  Keep the backend running. This avoids development hot reloads and dev overlays;
  real application status, warnings and errors remain visible.
- Start the backend and `frontend-v2/`; verify that the saved mission and artifacts open.
- Use browser zoom around 110–125% if needed so code and criteria are readable at 1080p.
- Open the exact file, evidence and graph connection in advance. Keep the full Mission brief collapsed unless demonstrating it.
- Prepare the CLI clip at a readable terminal size. Use genuine activity from the same mission where possible; label a different mission as **“Separate recorded CLI run.”** Saved history must not be presented as agents executing live.
- Hide unrelated tabs/notifications and use demo data. Do not show `.env`, API keys or password fields.
- Record the eight segments separately, then trim to the listed boundaries. Keep real status/error information intact; cut idle waiting rather than inventing progress.
- Keep the cursor deliberate. Pause on the diff and fingerprint long enough to read.
- Record narration in a quiet room; keep any background music substantially quieter than the voice.
- Preview once at small size to check readability. Finish on the closing frame at **1:55**; shorten pauses if necessary to keep the export under **2:00**.

## Claims to keep precise

- The successful example had four passing criteria, 13 model turns and 24 tool calls.
- It was an automated approval/apply walkthrough on a generated fixture; it did not approve changes to a user project.
- The independent verifier validates recorded evidence; it is not another LLM reviewer.
- CLI and browser use the same backend workflow; showing the CLI dashboard does not claim that the browser demo was also applied through the CLI. Active highlights indicate observed work, not a completed task or a historical replay.
- Earlier Docker and test-coverage failures are retained in [DEMO.md](frontend-v2/DEMO.md).
- Do not claim all bugs are caught, every mission succeeds, or that a baseline speed/cost comparison has been proven.

**Short delivery tip:** keep the narration natural—demo the evidence, not every menu.
