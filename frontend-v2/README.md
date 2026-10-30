# KAGE AI — frontend v2

A fresh developer workspace with an illustrated Dojo and a separate interactive
agent graph. This application lives independently of `../frontend`.

[Two-minute video script](../VIDEO_SCRIPT_2MIN.md) · [Real demo evidence](DEMO.md) ·
[Project setup and architecture](../README.md)

## Run locally

Requires Node.js 22.18+ (or Node.js 24), npm, and the existing Python backend.

From `backend/`, in the first terminal:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Configure model credentials and the Docker check image using `../backend/README.md`.
Planning and mission execution use the backend's configured model and may incur
provider charges. Repository checks require the backend's restricted Docker image.

From `frontend-v2/`, in another terminal:

```powershell
npm ci
npm run dev
```

Open **http://localhost:3001**. For a production build, run `npm run build` followed
by `npm start`. Both frontend commands use port 3001 by default.

For video recording, stop the frontend dev server before building/starting the
production frontend. Keep the backend running; production mode avoids dev-server
hot reloads without hiding actual mission warnings or results.

The Next.js server proxies `/api/backend/*` to `http://127.0.0.1:8000/api/*`, including
SSE. To change the backend origin, set `KAGE_BACKEND_URL` in `.env.local` using
`.env.example` as a reference. Never put model credentials in the frontend.

This is a local, single-user application; the underlying backend does not provide
multi-user authentication. Use its documented single mission worker configuration.

### Use your own API key

On **New mission**, enable **Use my API key** and paste a key matching the backend's
configured provider, endpoint and model/deployment (Anthropic-compatible or Azure
OpenAI). This overrides the server key only for that mission; it does not change
`.env`. The key stays in backend memory, never in mission records or browser
storage. Planning, execution and clarification resumes use the same mission key,
with no server-key fallback. After a backend restart, the workspace asks for the
key again before further model work. Keys are cleared when execution ends, a
mission is cancelled, or the backend shuts down. This is not multi-user login.

## Journey

1. **New mission:** connect a repository by a local backend-machine path, enter the
   request and optional criteria, choose Standard or Extended budget, then create the mission.
2. **Start planning:** explicitly start the backend's inspection and planning.
3. **Review:** answer clarification questions, inspect tasks and test mappings,
   and accept/decline proposed acceptance tests when the backend supplies them.
4. **Authorize workspace work:** explicitly authorize bounded agent execution.
5. **Workspace:** inspect frozen source, candidate diffs, checks, evidence,
   findings, and the four illustrated agents in the compact Dojo tab.
6. **Agent graph:** click any agent to open **Now**, **This mission**, or
   **Previous missions**. Historical inspection does not run or approve agents.
7. **Verify:** when checks and review are ready, invoke independent verification.
8. **Review & apply:** inspect the full diff and evidence, approve/reject the exact
   candidate, then separately confirm application to the original repository.

The file viewer is read-only. There is no fake terminal or human-editing endpoint.
Missing output is shown as missing, rather than synthesized.

### Budget exhaustion

Standard allows 25 model turns, 50 tool calls, 160,000 cumulative reported tokens,
and 600 active seconds. Extended explicitly allows 60/100/320,000/900. These are
shared mission ceilings, including planning, clarification and acceptance-test
design; they are not all reserved for the developer. Larger limits can cost more.
Developer tasks still have local ceilings of 20 turns, 50 tools, 300 seconds and
250,000 context characters. Their token allowance follows the remaining mission
budget (capped at 500,000 per task), rather than a hidden 60,000-token default.

The mission budget panel shows actual usage. For an exhausted run, **Prepare a new
mission with extended budget** copies the request/criteria into a fresh form. It
does not resume partial writes, run models or approve anything. Reconnect the
original repository, review the allowance, and explicitly create/start the new
mission. Restart the backend after updating to enable the new `limits` creation
field; the UI detects a server that ignores the requested allowance.

### Continue a previous mission

Open **Missions → Continue**. The same mission can resume from a validated planning,
developer, check/review or repair checkpoint. The recovery panel explains blockers
and allows inspection of partial workspace files before accepting them.

If a budget is exhausted, open **Extend this mission's budget**, enter larger total
ceilings (or use the bounded suggestion), then **Confirm budget extension**. Used
counters do not reset and no model call starts. Inspect/accept any partial edits,
then separately choose **Continue developer work** or the displayed next stage.
New checks, review, verification and candidate approval remain required.

Changed original files, protected test edits, missing snapshots, active workers and
existing approvals block continuation. Completed/cancelled/rejected missions offer
**Start follow-up** instead. The three-repair cap remains fixed. Own-key missions
require their key to be re-entered after a stop/restart.

Backend endpoint contracts and recovery boundaries: [RECOVERY.md](../backend/RECOVERY.md).

## Screen map

| Route | View |
| --- | --- |
| `/` | Original moonlit sanctuary illustration and guild introduction |
| `/docs` | Searchable setup, API-key, mission, evidence, troubleshooting and license guide |
| `/license` | Downloadable MIT license text |
| `/missions/new` | Repository and mission setup |
| `/missions` | Search loaded saved missions; progressively load older records |
| `/missions/:id/workspace` | IDE, diff, criteria, findings, checks, Dojo and activity |
| `/missions/:id/graph` | Recorded inter-agent connections and agent history drawer |
| `/missions/:id/review` | Verification evidence, fingerprint-bound decision and apply |

`candidate`, `file` and `returnTo` query parameters preserve inspection context
across workspace/graph/review navigation. Previous-mission filtering uses missions
older than the selected mission. Details and tools are loaded on selection.

## Backend integration

Uses existing mission, repository, candidate, evidence, proof, clarification,
acceptance-test review, authorization, verification, approval, apply and cancel APIs.

Two additive read-only endpoints are implemented in `backend/app/api/history.py`:

- `GET /api/missions/:id/history?after=0&limit=100`: sequenced saved events,
  `next_cursor`, `has_more`, and a saved repository name when available. Limit 1–100.
- `GET /api/missions/:id/baseline/file?path=...`: a file from the original frozen
  baseline candidate, with integrity and path validation. It never reads the
  repository's present-day file as a historical substitute.

SSE uses the backend's named `mission` event. Events are deduplicated by sequence
and isolated by mission. Sequence gaps fetch recorded history; reconnects refresh
the canonical snapshot. Terminal historical missions use saved records without a
live stream. Current criterion verdicts are not reused to certify an older candidate.

The graph shows recorded agent-to-agent message edges, rather than invented
pipeline traffic. A reserved RUNNING task is not by itself enough to animate an
agent. Terminal missions leave all dolls idle; connection loss stops animation.
Historical tool arguments are not fabricated: the UI displays only the action,
file, result and evidence details that the backend actually retained.

Check cards use readable names and display only counts supplied by structured
reports. An exit code without a report is labelled as an exit code, not “tests
passed.” Complete commands remain available inside the evidence drawer.

Click a graph connection (or the **connections** list) to inspect its exact saved
messages and open their evidence. Filter connections to the selected candidate
without attributing another revision's feedback to it. Agent positions can be
dragged without resetting on activity refresh. The graph makes room for the
agent drawer on desktop. The IDE now retains multiple open file tabs; finding
links select the finding's candidate and reveal its recorded source line.

## Design and dependencies

- Next.js / TypeScript with custom responsive CSS.
- React Flow with original illustrated agent nodes, pan, zoom and keyboard controls.
- Monaco for source/diff inspection; a plain-text view is also available.
- Four original SVG figurines and a CSS sanctuary scene; no PECFEST assets copied.
- Motion respects `prefers-reduced-motion`; audio is not autoplayed.
- Fonts use Google Fonts with system fallbacks; repository code is not sent there.

Monaco is served **locally**, not loaded from a CDN. `npm ci`/`npm install` runs
`scripts/prepare-editor.mjs`, copying the installed editor assets into ignored
`public/monaco/`. Monaco is pinned; the diff component owns model/widget teardown
to detach models before disposal. Recheck browser navigation when upgrading it.

## Verification

```powershell
npm run test
npm run typecheck
npm run build
npm run test:browser
```

Browser tests use installed Google Chrome (`channel: chrome`) and start an isolated
Next dev server on port 3101. Change that channel in `playwright.config.ts` if your
machine uses another browser, or install Playwright Chromium and remove `channel`.

If the preview is already running, Next.js permits only one dev server per app
directory. Reuse it rather than stopping it:

```powershell
$env:KAGE_TEST_BASE_URL="http://127.0.0.1:3001"
npm run test:browser
```

The browser fixtures are explicitly synthetic and never count as real model or
Docker evidence. They exercise history separation, editor navigation, two-stage
approval/application, mobile layout, SSE replay and visible backend failures.
Screenshots and traces are generated under ignored `test-results/`.

From `backend/`:

```powershell
python -m pytest tests/unit/test_history_api.py -q
python -m pytest tests/unit -q
```

The endpoint tests use real temporary SQLite records and frozen files. They check
pagination, mission ownership, changed originals, path rejection and snapshot
tampering. Model/Docker behavior is checked separately by the opt-in live
walkthrough below; synthetic browser fixtures do not certify that outcome.

## Opt-in real browser walkthrough

With both servers running, the following script creates a **new disposable**
two-file pagination repo, then uses the real browser, model and Docker checks:

```powershell
node scripts/live-walkthrough.mjs
```

By default it stops after verification. `--approve-demo` additionally tests the
two separate approval/apply controls **only on the fixture created by this script**;
there is no arbitrary target-repository argument. This is an authorized automated
test of the approval workflow, not a claim that an actual human reviewed the code.
It makes paid model calls under the selected Extended budget.

Reports, proof and screenshots persist under `test-results/live-*/`. Regular
Playwright test cleanup is restricted to `test-results/browser/` to preserve those
live records. Failed runs remain as failed; do not replace them with fabricated
success output. Source integrity is checked using raw-byte directory fingerprints,
since the file-view API normalizes Windows CRLF to LF.

Latest walkthrough details and reproduction notes: [DEMO.md](DEMO.md).

## Documentation and license

Open `/docs` from the landing page or app header. The field manual works without
a running backend and includes searchable sections, copyable PowerShell commands,
provider setup, mission checkpoints, budgets, recovery, evidence, privacy and
troubleshooting. `/license` downloads the project's MIT license. Project code is
licensed under the root [MIT License](../LICENSE); third-party dependencies and
external services retain their own licenses and terms.
