# KAGE AI

### Four roles. One traceable code change. Your approval.

KAGE AI turns a plain-English request into a **reviewed, tested code candidate** in
an existing small Python repository. Watch the agents work, inspect the evidence,
and explicitly decide whether to apply the change to your original files.

**PECATHON 2026 · PS-001 · Project reference: PF-ZTNSP5**

[Quick start](#quick-start) · [Architecture](#architecture) ·
[Two-minute video script](VIDEO_SCRIPT_2MIN.md) · [Real demo evidence](frontend-v2/DEMO.md) ·
[Backend guide](backend/README.md) · [Recovery](backend/RECOVERY.md) · [MIT license](LICENSE)

## What you can do

| Capability | What the application provides |
| --- | --- |
| Start a mission | Connect a local repo, describe the change, review tasks and acceptance criteria |
| Inspect code | Read-only IDE with file tabs, frozen-baseline comparison and candidate diffs |
| Watch the guild | Four illustrated agents in the compact Dojo; recorded activity in the Agent Graph |
| Trace decisions | Click graph connections to inspect messages and linked evidence |
| Inspect agent history | Separate **Now**, **This mission** and **Previous missions** views |
| Recover stopped work | Inspect a saved checkpoint, extend a bounded budget and explicitly continue |
| Control application | Verify evidence, approve the exact candidate, then separately apply it |
| Bring a key | Use the configured server provider or supply a matching per-mission API key |

Long requests and prior clarifications live in the expandable **Mission brief**,
not in an oversized page heading. The built-in `/docs` field manual covers setup,
provider configuration, usage, recovery and troubleshooting.

## Quick start

### Prerequisites

- Python **3.12+** for the documented setup.
- Node.js **22.18+ or 24**, and npm.
- Docker Desktop using the **Linux engine** for repository checks.
- An Anthropic-compatible provider or Azure OpenAI deployment configured in the
  backend. Live missions make paid model calls using that provider.

### Terminal 1 — backend

Run these commands **from `backend/`**:

```powershell
python -m pip install -r requirements.txt
if (!(Test-Path -LiteralPath ".env")) { Copy-Item ".env.example" ".env" }
```

Configure `backend/.env` using [the provider setup guide](backend/README.md).
Keep keys out of version control and recordings. Then:

```powershell
docker build -f Dockerfile.checks -t devpilot-checks:py312 .
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Terminal 2 — current frontend

Run these commands **from `frontend-v2/`**:

```powershell
npm ci
npm run dev
```

Open **http://127.0.0.1:3001**. Documentation is at
**http://127.0.0.1:3001/docs**.

The Next.js server proxies `/api/backend/*` to the backend on port 8000, including
the event stream. To use another backend origin, set `KAGE_BACKEND_URL` in
`frontend-v2/.env.local`; see [`.env.example`](frontend-v2/.env.example).
The current UI is **`frontend-v2/`**, not the earlier `frontend/` implementation.

For a production frontend build, run `npm run build` and then `npm start` from
`frontend-v2/`. Restart the backend after pulling backend changes so new API routes
are registered.

## Mission lifecycle

1. **Connect:** choose a local repository path on the backend machine and inspect preflight results.
2. **Describe:** enter your request and optional acceptance criteria; select a budget.
3. **Plan:** Shogun inspects the repo, proposes tasks and test mappings, and asks questions when needed.
4. **Authorize:** review the plan. If new acceptance tests were proposed, review those separately before authorizing workspace edits.
5. **Build:** Samurai edits only the disposable workspace and freezes a candidate after source read-back and diff inspection.
6. **Check and review:** Sentinel runs approved checks; Shadow Council reviews the source and relevant evidence. Findings can trigger a revised repair plan.
7. **Verify:** the independent deterministic verifier checks candidate-bound evidence. Model prose cannot mark a criterion verified.
8. **Decide:** inspect the diff and proof, approve or reject that exact candidate, then separately apply an approved change to the original repository.

**Verified, approved and applied are separate states.** Approval alone does not
modify the original repository.

## Architecture

```text
                       Request + repository
                                │
                    Next.js IDE / Agent Graph
                                │ REST + replayable SSE
                       FastAPI controller
                                │
            ┌───────────────────┼───────────────────────┐
            │                   │                       │
       Shogun planner ──→ Samurai developer ──→ frozen candidate
            ↑                                           │
            │                         ┌─────────────────┴────────────┐
            │                         │                              │
            │                   Sentinel checks             Shadow Council review
            │                         │                              │
            └────── findings / repair plan ◀───────────────┬─────────┘
                                                          │
                                              Deterministic verifier
                                                          │
                                                Human decision
                                                          │
                                               Journaled application

 SQLite: missions · tasks · messages · events · evidence · approvals
 Files: captured baseline · disposable workspace · frozen candidates · artifacts
```

| Role | Responsibility |
| --- | --- |
| **Shogun — Planner** | Repository inspection, task dependencies, criteria, clarification and repair planning |
| **Samurai — Developer** | Bounded tool-use loop for source reads, edits, read-back, diffs and handoff |
| **Sentinel — Checks** | Approved container tests, structured reports, security scans and test-gap proposals |
| **Shadow Council — Reviewer** | Candidate review, evidence-linked findings and review of prior issues |

The verifier is trusted application logic, **not a fifth AI agent**. Sentinel's
required checks execute deterministically; model-assisted acceptance-test design is
a separate, human-reviewed operation. Preliminary source review can run alongside
container checks, followed by evidence-informed review when needed.

## Execution boundaries

- **Disposable workspaces:** source changes stay outside the original repo until approved application.
- **Role-restricted tools:** agents receive validated file/search/edit/diff or check tools; no arbitrary host shell tool is exposed.
- **Restricted checks:** Docker uses a non-root user, no network, read-only mounts/root filesystem, dropped capabilities and bounded resources/output.
- **Protected tests:** developers cannot weaken existing tests or accepted test configuration. New accepted expectations run in separate verification views.
- **Evidence binding:** tests, findings and decisions reference a frozen candidate ID and fingerprint. Stale evidence cannot certify another candidate.
- **Recoverable apply:** a journal protects multi-file edits, additions and deletions; original-file conflicts stop application rather than overwriting external changes.
- **Credential handling:** server keys live in backend configuration. Per-mission keys stay in memory and must be re-entered after stops/restarts when required.

Each file replacement is atomic; visibility across several files is not globally
atomic. This is a **local single-user, single-backend-process prototype**, not a
public multi-tenant service. Use the documented worker configuration.

## Budgets and continuing old missions

| Preset | Model turns | Tool calls | Reported tokens | Active time |
| --- | ---: | ---: | ---: | ---: |
| Standard | 25 | 50 | 160,000 | 10 minutes |
| Extended | 60 | 100 | 320,000 | 15 minutes |

These allowances are shared across the mission. For example, **13/60 turns** means
13 used and 47 remaining. Developer attempts also have local bounds.

From **Missions → Continue**, inspect the saved checkpoint and unverified files.
If needed, explicitly extend the total ceiling: **60 used / 60 limit → 60 used /
80 limit**. Counters are preserved. A separate Continue action claims the next
bounded operation; it never replays old patch calls or automatically approves work.

Changed originals, damaged snapshots, protected-test changes, active operations or
existing approvals can block continuation. The three-repair ceiling remains fixed.
Applied, rejected and cancelled missions offer a new follow-up instead.

See [the recovery API and invariants](backend/RECOVERY.md).

## Verification and reproducible evidence

```powershell
# From backend/
python -m pytest tests/unit -q

# From frontend-v2/
npm run test
npm run typecheck
npm run build
npm run test:browser
```

Browser tests use installed Google Chrome. If the development UI is already
running, reuse it rather than starting a second Next.js server in the same folder:

```powershell
$env:KAGE_TEST_BASE_URL="http://127.0.0.1:3001"
npm run test:browser
```

Latest observed local checks for this handoff:

| Check | Observed result |
| --- | --- |
| Backend regression suite | 257 passed in the most recent backend validation |
| Frontend unit tests | 11 passed |
| Browser workflows and documentation | 13 passed |
| TypeScript / production frontend build | Passed |

These counts come from executed checks, not model estimates. Re-run the commands
above after changing code; controlled test results do not prove live model success.

Unit/browser fixtures are controlled tests, **not evidence of live model success**.
The opt-in real walkthrough creates its own disposable pagination repo and uses
the real browser, configured model and Docker checks:

```powershell
# From frontend-v2/ — paid model calls; both servers must be running
node scripts/live-walkthrough.mjs
# Also exercise approval/apply, only on the freshly generated fixture:
node scripts/live-walkthrough.mjs --approve-demo
```

A recorded local run, **`miss-aef4cc8a`**, reached **APPLIED**, passed four acceptance
criteria, and preserved the original until the separate apply action. It used
13 model turns and 24 tool calls. This was an automated browser walkthrough on a
generated fixture, not approval of user project changes.

The initial test oracle compared Windows CRLF bytes with normalized API text; a
follow-up raw-fingerprint check confirmed the application. Both records are retained.
[DEMO.md](frontend-v2/DEMO.md) lists the successful run, earlier failures and artifacts.
These runtime artifacts are local/ignored; a fresh clone must generate its own runs.

Additional evaluation commands, from `backend/`:

```powershell
python -m app.evaluation --mode controlled
python -m app.evaluation --mode live
```

The documented five-scenario live evaluation reached `VERIFYING`, before independent
verification/approval; it is not a five-for-five applied-change claim. See
[evaluation](evaluation/README.md) and [backend milestone evidence](backend/FINAL_VERIFICATION_REPORT.md).

## CLI

From `backend/`, use `python -m app.cli` for the interactive terminal interface or
`python -m app.cli run` for a request-driven mission. Planning, acceptance-test
review, authorization and saving remain explicit. CLI follow-up commands and HTTP
same-mission recovery are described separately in the backend documentation.

## Known limits

- Best suited to small Python repositories with dependencies available in the prepared check image.
- Model behavior and Docker readiness can block a mission; completing every request is not guaranteed.
- Passing mapped tests demonstrates those checks, not complete semantic correctness or absence of vulnerabilities.
- Bounded mutation checks and static analysis can miss defects or flag issues requiring human judgment.
- Recovery requires an intact, compatible checkpoint; some interrupted or externally changed repos need a fresh mission.
- A complete single-agent versus multi-agent performance benchmark has not been established.

## Project map

```text
backend/             FastAPI, agents, controller, safety, persistence and tests
frontend-v2/         Current IDE, Dojo, Agent Graph, history, recovery and docs
sample-repos/        Small scenario repositories
evaluation/          Controlled/live evaluation tooling and run records
VIDEO_SCRIPT_2MIN.md Timed narration and screen-by-screen recording plan
```

## License

Project code is available under the [MIT License](LICENSE). Dependencies, model
providers and external services retain their own licenses and terms.
