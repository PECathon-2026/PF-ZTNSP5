# DevPilot backend

Same-mission checkpoint continuation and explicit budget extensions are documented
in [RECOVERY.md](RECOVERY.md). Older notes about starting a new mission after every
interruption describe the previous behavior; recovery now supports validated
checkpoints without replaying interrupted tool calls.

## Interactive CLI (no frontend server required)

In Windows Terminal or another interactive terminal, launch the boxed KAGE UI:

```powershell
python -m pip install -r requirements.txt
python -m app.cli
```

The command prompts for your repository and request. Press Enter when asked for
success conditions to let Shogun propose them. `/manual` opts into your own
criteria; `/help`, `/clear`, `/auto` and `/done` are available. Manual entries
become binding only after you type `KEEP`. Normal conversational input is not a
CLI command. The gold/ink KAGE dashboard has an activity pane, active-agent
sidebar, recent handoffs, mission status and real budget counters. Shogun's plan and Shadow
Council's review summaries come from their recorded structured responses;
tool execution results remain separately labeled. The original code and
final approval/apply rules remain separate from authorization.

Use a terminal at least **96 columns wide** for the right sidebar. At narrower
widths the activity pane expands and the current agent remains in the footer.
The dashboard stays open while you type: the prompt is anchored at the bottom.
Plans, proposed test assertions and candidate diffs appear in a reviewable pane;
PageUp/PageDown scroll, F6/F7 switch between reviews and F8 returns to live
activity. When Shogun asks for clarification, its complete question appears in
that same pane above the reply field. These keys do not submit or change the typed answer. The activity
pane shows the newest wrapped lines; the complete event history remains in
SQLite and is available via `watch` or `proof`.
Opening a saved mission with `resume` replays its recorded activity. If that
mission is already stopped or has no input to collect, the dashboard shows
an on-screen action menu: type `1` for activity, `2` for the latest review or
summary, `3`/`4` to scroll forward/back when there is only one saved review
(or switch reviews when there are several), `5` to reopen the menu, `6` to
review a follow-up, or `/up` and `/down` to scroll; press Enter to close. The pane title shows the
actual saved-review count and page position. F-keys are optional
shortcuts. Saved tasks and check mappings appear as a read-only plan when
available. An interrupted mission identifies unfinished disposable edits and
offers a fresh follow-up instead of replaying an uncertain write. Opening
the saved view alone does not restart work or change the mission.

To continue an old conversation, use `python -m app.cli continue <old-mission-id>`
or type `6` in its saved-mission menu. Review the original repository path,
request, answered user clarifications and success conditions; optionally add
a new instruction. Only typing `CREATE FOLLOW-UP` creates a **new** mission,
replans against the current original repository and stops for fresh test review
and source authorization. Declining creates nothing. The old mission's history
is retained; unfinished edits, check results, budget and approval are not reused.
If you type more natural-language detail at the confirmation prompt, it is
added to the preview rather than closing the CLI. Use `/edit` to add another
instruction, `/clear` to clear additions, or `/cancel` to return to the saved
mission menu. Repeat `CREATE FOLLOW-UP` only when the preview is right.

```powershell
python -m app.cli watch miss-... --follow
python -m app.cli --plain run   # original scrolling log; --plain precedes the command
```

Piped/redirected input or output uses plain mode automatically, and `list`/`proof`
keep readable, exportable output. Rich supplies the layout and prompt_toolkit
coordinates the persistent screen and keyboard input. The split-layout design
takes inspiration from OpenCode. This UI does not run or require OpenCode.

From `backend/`, after configuring `backend/.env` and building the restricted
check image, run a mission against an **existing small Python repository**:

```powershell
python -m app.cli run --repo "D:/projects/task-service" --request "Add status filtering without changing sort order" --criterion "Active tasks can be filtered" --criterion "Existing sort order stays the same"
```

Missing flags are prompted for interactively. The CLI displays real, replayable
Shogun/Samurai/Sentinel/Shadow Council activity, check outcomes and findings.
Review its proposed tasks and criterion-to-test mappings; **type `AUTHORIZE`**
to let agents change only the disposable workspace. It then runs independent
verification and displays the exact candidate diff/fingerprint. In an interactive
terminal, type `SAVE` if you want the verified change in your existing repo:
the CLI then requires the exact candidate fingerprint for approval and a separate
`APPLY <fingerprint>` to write the original files. Enter leaves them untouched;
`approve <mission_id>` lets you save later. CLI defaults are 60 model turns / 100 tool calls; both remain
bounded. API-created missions still use the configured mission defaults.

If requested behavior lacks existing test coverage, Sentinel may propose
`test_kage_*.py` acceptance tests. Read their complete code and criterion
mappings before typing `ACCEPT TESTS <proposal-hash>`. This is separate from
`AUTHORIZE` for source edits. Approved test code runs in temporary verification
copies; neither source workspace nor original tests are modified. Declining
or pausing leaves source edits unauthorized. A paused review resumes via
`python -m app.cli resume <mission_id>`.

```powershell
python -m app.cli list
python -m app.cli watch miss-... --after 0  # replay committed events; --follow watches an active mission
python -m app.cli resume miss-...           # plan authorization or clarification after a pause
python -m app.cli continue miss-...         # review a fresh follow-up to an interrupted mission
python -m app.cli proof miss-... --format markdown
python -m app.cli approve miss-...          # review diff, type full SHA-256, then separately type APPLY SHA-256
```

`watch`/`proof` never run agents or approve patches. An aborted approval prompt
does nothing. A recorded approval without the second `APPLY ...` confirmation
leaves the original repository unchanged. CLI and HTTP use the same SQLite
mission/evidence store and candidate fingerprints. Run a **single mission worker**
at a time; don't run an active API mission and CLI mission on the same database
concurrently. Container checks never fall back to host execution. An interrupted
in-process write remains interrupted; use a fresh mission rather than blindly
replaying tool calls.

The browser UI offers **Review and save changes** after verification; approve
the exact candidate and click **Save approved changes to existing repository**
in the review panel. The status becomes `APPLIED` after the existing files are
updated. A mission stopped at `INTERRUPTED`, `BLOCKED` or failed verification has
no trusted patch to save; make a fresh follow-up and finish verification first.

## Run

From `backend/`, install `requirements.txt`, copy `.env.example` to `.env`, configure
the server-side gateway key, then run:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## M3 — Model adapter and Samurai vertical slice

M3's live exit check passed with Azure OpenAI Responses and `gpt-6-astra`.
See [M3_STATUS.md](M3_STATUS.md) for the tool trajectory and evidence path.

`app/agents/model_adapter.py` implements the Anthropic-compatible Messages API at
`ANTHROPIC_BASE_URL/messages`. The default base URL includes `/v1`. It validates
complete tool-use envelopes, tracks reported token usage, retries transient HTTP
and transport failures with capped jitter, and imposes per-request and total
deadlines. Upstream error bodies and credential-bearing transport messages are
never included in returned errors or application logs.

The same adapter supports Azure OpenAI's v1 Responses and Chat Completions APIs. To use an
existing Azure deployment, set these values in `backend/.env`:

```dotenv
DEVPILOT_MODEL_PROVIDER=azure_openai
AZURE_OPENAI_BASE_URL=https://YOUR-RESOURCE.openai.azure.com/openai/v1
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API=responses
AZURE_OPENAI_REASONING_EFFORT=low
```

The Azure deployment name is sent as `model`. The adapter translates tool
definitions, assistant function calls, and tool-result messages into Chat
Completions format and validates JSON-string tool arguments before execution.
Responses uses `max_output_tokens`, flat function definitions, and stateless
function-output messages with `store=false`. Opaque reasoning continuation items
are carried between model turns but excluded from public results and traces.
Use Responses for `gpt-6-astra`: its deployment rejects reasoning-enabled tools on
Chat Completions and also rejects the suggested `none` reasoning workaround.
`AZURE_OPENAI_API=chat_completions` supports compatible deployments using
`max_completion_tokens`. Both omit sampling parameters for reasoning-model
compatibility. `AZURE_OPENAI_REASONING_EFFORT` is optional; leave it empty to use
the deployment's default. `DEVPILOT_MODEL_PROVIDER=anthropic` selects the original protocol.
Health readiness and the smoke check use the selected provider's configuration.
The backend-local `.env` loads from either working directory; explicit process
environment variables take precedence. API keys are excluded from settings
serialization and representation.

`app/agents/samurai.py` exposes `SamuraiRunner.run(repository_id, request_text)`.
Connect a repository with `get_repository_service().connect_repository(path)`
first. Use `ModelAdapter` as an async context manager so its HTTP client is closed.
Each run gets a new mission workspace and an exclusive writer lease; passing an
existing mission ID fails instead of resetting or replaying its edits.

The runner gives the model six strictly validated tools: `list_files`,
`search_text` (literal), `read_file`, `apply_patch`, `read_diff`, and
`submit_candidate`. Existing files must be read before targeted edits; patches
require the current workspace fingerprint, unique target text, and a writer
lease. Tests/test configuration are protected. Repeated tool-use IDs return their
cached result instead of executing again. File reads, patch writes and diff
inspection supply the three developer tool categories required by the spec.

The baseline is captured alongside the disposable workspace. Successful handoff
requires read-back and diff inspection after the last edit of every changed file,
then freezes a separate candidate snapshot. The result is `CANDIDATE_READY`, not
mission verification or approval. Turn, tool-call, reported-token, context,
consecutive-error and elapsed-time limits stop runaway loops. Cancellation releases
the lease. These are in-process M3 controls, not a durable multi-worker scheduler.

### Reproducible real-model exit check

```powershell
python -m app.agents.smoke
```

This makes paid gateway calls using your configured model and key. It creates a
tiny synthetic repository, asks the real model to read and patch `greeting.py`,
requires read-back/diff/handoff, and deterministically checks the candidate source
bytes, fingerprint, changed-file list, and preservation of the original. It prints
the result and saves bounded JSON evidence under
`data/artifacts/<mission-id>/art-*_m3-smoke.json`. Exit code 0 means the source-level
M3 exit check passed; 1 means the run/check failed; 2 means no key was configured.

No generated repository code is executed by this smoke check. Docker is required
for repository tests/diagnostics; its absence is still reported by preflight and
the check gateway blocks execution. M3 read/edit/inspect can run without Docker.
Behavioral checks, multi-agent routing and durable mission/candidate integration
belong to subsequent milestones. The REST mission-creation route does not launch
Samurai automatically in this milestone.

### Deterministic regression suite

```powershell
python -m pytest tests/unit -q
```

M3 tests use `httpx.MockTransport` with scripted Messages API envelopes and real
workspace tools. They verify protocol handling, replay prevention, stale and
protected patch rejection, role/path restrictions, source isolation, budget stops,
exclusive leases, cancellation, and post-edit inspection requirements without
calling an external model.

## M4 — Durable guild coordination

This section describes the routing-only mode (`auto_repair: false`). Normal
authorizations now enable M5's bounded recovery, described below.

M4 adds the Shogun planner, Sentinel check runner, and Shadow Council reviewer,
with candidate-bound findings, persisted messages, and task dependencies. See
[M4_STATUS.md](M4_STATUS.md) for the regression evidence and live-run status.

### Prepare container checks

Start Docker Desktop's **Linux engine**, then run from `backend/`:

```powershell
docker build -f Dockerfile.checks -t devpilot-checks:py312 .
```

The default `DEVPILOT_DOCKER_IMAGE` is `devpilot-checks:py312`. This image includes
Python 3.12 and pytest. Repositories needing additional dependencies require a
prebuilt compatible image selected through that setting; the runtime never pulls
images or installs packages. Dependency installation occurs only during the
explicit image build. Repository checks use non-root UID/GID 1001, a read-only
root filesystem and candidate mount, no network, dropped capabilities, bounded
CPU/memory/processes, and bounded captured output. Timeout and cancellation stop
the Docker client and remove its uniquely named container. No host test fallback
is available.

### HTTP workflow

Run one backend worker (`python -m uvicorn app.main:app`). The controller is a
single-process scheduler; do not start multiple workers against the same database.

1. `POST /api/repositories/connect` with `{"path":"D:/projects/example"}`.
2. `POST /api/missions` with the repository ID, request text, and criteria.
3. `POST /api/missions/{id}/plan` starts a background operation and returns **202**.
   It captures the workspace and baseline, runs baseline checks, and lets Shogun
   inspect source and propose a validated DAG. Baseline code failures inform the
   plan; unavailable execution infrastructure stops the mission at `BLOCKED`.
4. Poll `GET /api/missions/{id}` until `READY_FOR_AUTHORIZATION`. Review its tasks
   and criteria, then call `POST /api/missions/{id}/authorize` with
   `{"scope_version":1,"auto_repair":false}` (use the returned mission version).
   This returns **202** and selects the M4 routing-only demonstration.
5. Samurai executes ready tasks in dependency order under a writer lease, freezing
   each handoff. Sentinel and Shadow Council then inspect the final frozen candidate
   concurrently on the frozen candidate. Source review is preliminary while
   checks run; material test/security/challenge findings trigger a second,
   evidence-informed review before routing. Neither agent writes the candidate.
6. Poll mission details for tasks, candidates, evidence, findings and messages.

The authorization is permission for disposable-workspace work, not approval to
apply a patch. Repeated starts and stale plan versions return **409**. Mission
creation itself does not start model calls. The backend stores repository context,
plans, candidate metadata, evidence, messages, and task state in SQLite. Candidate
file/diff endpoints restore metadata from that store after a restart. Interrupted
active operations become `INTERRUPTED`; their side effects are never replayed.

Additional endpoints:

- `GET /api/missions/{id}/candidates/{candidate_id}/diff`
- `GET /api/missions/{id}/candidates/{candidate_id}/file?path=app.py`
- `GET /api/missions/{id}/evidence/{evidence_id}` (bounded stdout/stderr included)
- `POST /api/missions/{id}/cancel` (stops the local operation and releases leases)

Candidate and evidence reads enforce mission ownership. Evidence writes reject
missing candidate references, mismatched fingerprints, and cross-candidate
citations transactionally. Configured backend API keys are redacted from guild
records and text artifacts.

### Where an M4 pass stops

- **Code/check or blocking review finding:** `REPAIRING`. Implementation tasks are
  conservatively reopened (the root becomes ready, dependent tasks remain pending),
  attempts increment, and structured findings with candidate/evidence references
  go to **both Shogun and Samurai**. Review/check tasks wait for a new candidate.
- **Missing infrastructure or timeout:** `BLOCKED`, with execution evidence and a
  blocker message; no blind code-repair round is started.
- **Checks/review complete with no blocking findings:** `VERIFYING`, awaiting the
  later independent verifier. Acceptance criteria are not marked passed by an agent.

Automatic replanning/repair and clarification resume are implemented in M5 below.
Independent acceptance verification, human approval/application are M6. SSE/frontend wiring is M7.
For a blocked/interrupted M4 demo, fix the environment and create a new mission;
M4 does not reset or implicitly resume an existing workspace.

### M4 verification commands

```powershell
python -m pytest tests/unit -q --junitxml=data/m4-regression.xml
python -m app.agents.guild_smoke
```

The unit suite uses scripted model responses, real filesystem/SQLite operations,
and controlled executor results. It proves routing and persistence without calling
a hosted model or pretending those results came from Docker.

The live smoke command uses the configured model and real restricted containers.
Its synthetic fixture deliberately retains a test expecting the old value while
asking Samurai to update the source, making a Sentinel failure/reopened task the
expected M4 demonstration outcome. Invoking it authorizes this synthetic pass.
It records JSON evidence under `data/artifacts/` and exits 0 only when the failure
is routed correctly and the original source remains unchanged. Without Docker it
records `BLOCKED` and exits 1 before model execution.

## M5 — Adaptive recovery and clarification

M5 consumes candidate-bound findings and revises the implementation DAG before
attempting repairs. Each accepted revision creates fresh task records, preserves
the old plan/task history, and produces a new frozen candidate for checks and
review. The approved criterion descriptions and check profiles cannot be added,
removed, or weakened by a repair plan. A repair proposal must cite every current
blocking finding, with no invented IDs.

### Default authorization behavior

```http
POST /api/missions/{id}/authorize
Content-Type: application/json

{"scope_version":1,"auto_repair":true}
```

`auto_repair` defaults to true in the application controller. False selects the
single-pass M4 behavior. Authorization covers only disposable work within the
approved criteria, subject to the mission budgets; it never approves applying
changes to the original repository.

After a code/check or high-severity review failure, Shogun receives the failed
candidate, exact findings, bounded check output, prior plan and clarification
answers. It proposes a revised DAG. Samurai then gets the repair task and finding
references. Sentinel reruns all approved profiles on the new candidate while
Shadow Council re-reviews it. A successful recovery stops at `VERIFYING` with
acceptance criteria still pending M6's independent verification.

Previous Sentinel findings receive new-candidate resolution evidence only when
the corresponding check passes. Previous review findings require an explicit
resolution in the new review; omitted resolutions remain blocking. A repair that
repeats an existing candidate fingerprint stops without replaying its checks.
Infrastructure failures/timeouts remain `BLOCKED`, rather than launching code edits.

`GET /api/missions/{id}` includes `plan_revision` and clarification records.
`scope_version` stays unchanged during in-scope repairs; `plan_revision` increases
when the implementation DAG changes. Durable plan history is stored in the guild
context, and `PLAN_REVISED`/repair/clarification events are recorded for later SSE use.

### User-facing agent activity

The same persisted mission event stream now includes `AGENT_ACTIVITY` records for
Shogun, Samurai, Sentinel and Shadow Council. Each event has a trusted source,
monotonic sequence number and bounded `display_payload` with `stage` (`intent`,
`outcome`, `failed`, `proposal` or `handoff`), `action` and a plain-language
`summary`. File paths are validated relative paths, never hardcoded example names.
Intent describes a proposed step; outcome is emitted after the tool completes.
Failed calls never produce a successful outcome. Sentinel check outcomes link
the frozen candidate and persisted evidence IDs; only the independent verifier
can report a verified acceptance decision. Review findings include severity and
evidence references. The stream excludes raw model thoughts, file contents,
diff bodies, command output and model credentials. SSE replay uses the same
durable events after reconnection; Dojo renders their summaries as an activity
timeline. Existing phase/status events remain available for compatibility.

### Clarification pause/resume

Shogun may call `request_clarification` during initial planning or repair planning.
The controller records the question, phase, scope version, candidate ID and
fingerprint, blocks unfinished tasks, and transitions to `AWAITING_CLARIFICATION`.
These are read-only planning checkpoints, never partially completed write operations.

Read the question from `GET /api/missions/{id}`, then submit:

```http
POST /api/missions/{id}/clarifications
Content-Type: application/json

{"question_id":"question-...","answer":"Use case-insensitive comparison."}
```

- **202:** the answer was stored and its background continuation started.
- **404:** the mission/question does not exist in this mission.
- **409:** the answer is duplicate, cancelled, stale, or its snapshot/workspace changed.
- **422:** the request is malformed or the trimmed answer is empty/too long.

Answer consumption and continuation ownership are transactional: concurrent
submissions cannot create two runs. Pauses survive backend restarts. Initial
planning resumes against the captured baseline without rerunning baseline checks,
then still waits for authorization. Repair planning resumes under the existing
authorization and reserved repair round. Answers and budgets carry forward.
Interrupted writes remain `INTERRUPTED`; this endpoint never resets or replays them.

### Shared budgets

Default mission limits:

| Budget | Default |
| --- | ---: |
| Repair rounds | 3 (hard maximum; `DEVPILOT_MAX_REPAIR_ROUNDS` can lower it) |
| Logical model turns | 25 |
| Tool calls, including checks and rejected calls | 50 |
| Reported input + output tokens | 160,000 |
| Active execution time | 600 seconds |
| Clarification questions | 3 |

The first reached limit stops the mission at `BUDGET_EXHAUSTED`. Three repair
rounds is a ceiling, not a guarantee that all three fit the other budgets.
Turns/tools are reserved durably before invocation; a failed model call still
uses its turn. Reported tokens are recorded before returned tool calls can run.
Provider HTTP retries retain their separate bounded adapter policy; token counts
reflect returned usage, not an exact provider billing ledger.

Active time accumulates across planning, authorization, repairs and resumes.
Time spent waiting for a user answer/authorization does not consume execution
time. A clarification resume does not replenish any budget or reserve an already
pending repair round twice. These limits are trusted `MissionBudgets` state;
the clarification payload cannot change them.

### M5 verification

```powershell
python -m pytest tests/unit -q --junitxml=data/m5-regression.xml
python -m app.agents.recovery_smoke
```

The deterministic suite includes seeded candidate failure → revised plan → new
candidate → passing re-test, with original source preservation and evidence-bound
finding resolution. It also tests the hard repair cap, failed-call accounting,
clarification/restart continuity, duplicate/stale answers, cancellation during a
repair write lease, no-progress stops, and rejection of weakened criteria.

The live smoke uses real model calls and restricted Docker checks. Its request
deliberately asks for an initial value of 2, then recovery to the test's required
value of 3. It only reports its M5 exit check passed if a repair round actually
occurred and the final run reached `VERIFYING`; a first-pass fix is not mislabeled
as evidence of adaptive recovery. Without Docker, it records a blocked attempt.
See [M5_STATUS.md](M5_STATUS.md) for current results and artifact paths.

## M6 — Verify, approve, apply

When a mission reaches `VERIFYING`, call `POST /api/missions/{id}/verify`.
The independent deterministic verifier evaluates the current frozen candidate's
structured check evidence, criteria, and blocking findings. For each behavioral
criterion, Shogun proposes one or more **existing pytest node IDs**, such as
`test_tasks.py::test_filter`, in the plan's `test_selectors`. Tests can support
several criteria. Mapping is visible in `GET /api/missions/{id}` before scope
authorization. Sentinel runs the entire suite **and** approved selected tests
on the frozen candidate; evidence stores criterion ID, selector, command,
candidate fingerprint, JSON report artifact/hash and versioned contract hash.
Missing, malformed, stale or skipped-only reports fail closed. A passing test
demonstrates its approved test, not a formal proof that natural-language
requirements are fully covered. Older plans without accepted mappings require
a new mission/plan to verify. Only a passing result enters
`VERIFIED_AWAITING_APPROVAL`; a failed check enters `FAILED_VERIFICATION`.

Review `GET /api/missions/{id}/candidates/{candidate_id}/diff`,
`GET /api/missions/{id}/report`, and `GET /api/missions/{id}/patch`. To record a
human decision, send `POST /api/missions/{id}/approve` with:

```json
{"candidate_id":"cand-...","candidate_fingerprint":"<64 hex characters>","decision":"APPROVED"}
```

An explicit `REJECTED` decision closes the mission without applying changes.
After approval, send `POST /api/missions/{id}/apply` with the candidate ID.
Application verifies the original repository's approved manifest/content and
the approved candidate snapshot before writing. Multi-file edits, new files and
deletions are supported. A durable journal stores all original and new file bytes
before the first mutation; each file is replaced atomically. If a write or database
finalization fails, rollback restores the original files. On backend startup,
`APPLYING` operations are inspected and rolled back before serving requests; if
journal integrity or external edits prevent safe rollback, the mission is blocked
and its journal retained for inspection. Multi-file visibility is **not globally
atomic to external readers** during the short apply window. Protected tests and
symlinked paths cannot be applied.
Conflicts, stale decisions, and duplicate attempts return HTTP 409. Verification
or approval alone never mutates the original repository. See
[M6_STATUS.md](M6_STATUS.md) for checks and known limits.

## M8 — Reproducible scenario evaluation

`python -m app.evaluation --mode controlled` exercises five prepared fixtures
using scripted model and source-oracle responses with real SQLite and workspace
operations. Synthetic checks are tagged and cannot pass independent verification.
`python -m app.evaluation --mode live` uses the configured model and restricted
Docker checks, blocks safely if Docker is unavailable, and never applies changes.
Both write separate per-run JSON evidence under `evaluation/results/`. See
[M8_STATUS.md](M8_STATUS.md) and [evaluation/README.md](../evaluation/README.md).

## Evidence-first improvements

The check image includes pinned `pytest-json-report` and Bandit, both run only
inside restricted containers. A bounded Python AST repository map supports
source/test discovery. The controller challenges eligible changed functions
with up to three isolated AST variants after checks pass; detection/survival is
recorded separately from code failure. `GET /api/missions/{id}/proof` exports
a bounded JSON/Markdown proof card, including causal finding-to-task links.
Without accepted tests Sentinel proposes separate acceptance test code for
human review **before authorization**. Accepted code runs only in disposable
verification views with contract-bound hashes; the developer cannot alter
it or weaken repository tests. See [INNOVATION_STATUS.md](INNOVATION_STATUS.md)
for current live evidence, limitations and attribution.
