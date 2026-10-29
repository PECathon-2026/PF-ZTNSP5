# DevPilot Orchestrator — Master Specification

> Project: DevPilot — The Mystic Mikado’s Autonomous AI Engineering Guild  
> Hackathon: PECATHON 2026 · PS-001  
> Purpose: Coordinate Planner, Developer, Tester, and Reviewer as a real evidence-driven engineering system.

## 1. Mission and non-negotiable design principles

The Orchestrator owns each run's lifecycle. It converts agent outputs and tool evidence into controlled state transitions, coordinates handoffs, manages retries and cancellation, and ensures that no agent can bypass candidate isolation or owner approval.

The four agents are specialized workers:
- Planner / Shogun
- Developer / Samurai
- Tester / Sentinel
- Reviewer / Shadow Council

The Orchestrator is control-plane infrastructure, not a fifth persona that merely chats. Its policy decisions must be deterministic wherever possible and enforced in backend code.

Non-negotiable principles:
1. Structured agent-to-agent communication and shared state are mandatory.
2. Every status claim must be supported by stored tool/model evidence.
3. Project code runs only in the restricted Linux container; never fall back to the host.
4. Only typed, allow-listed tool operations may be invoked.
5. The original repository remains unchanged until explicit owner approval and a controlled apply operation.
6. Approval is bound to one immutable candidate hash; any candidate change invalidates it.
7. Retry loops are bounded and must adapt to new evidence.
8. The approved Swytchcode model integration contract is authoritative. Do not invent provider IDs, model IDs, endpoints, or bypass it with direct HTTP/SDK calls.
9. The Orchestrator must not claim that a capability exists until the runtime/tooling proves it is available.

## 2. Proposed architecture

```text
User request
    |
    v
Run API / Orchestrator
    |---- Planner (read-only repository inspection)
    |       |---- plan + acceptance criteria
    |
    |---- Developer (candidate-only edits)
    |       |---- immutable candidate revision + diff
    |
    |---- Tester (independent checks in restricted container)
    |       |---- criterion-level results + execution evidence
    |
    |---- Reviewer (read-only diff/security review)
    |       |---- findings + owner-review recommendation
    |
    v
Deterministic verification and policy gates
    |
    v
Human approval bound to candidate hash
    |
    v
Controlled apply to original repository
```

The execution order can adapt to evidence. For example, a failed test returns the run to a bounded Developer repair cycle; an ambiguous requirement returns it to clarification; a missing sandbox blocks execution rather than triggering a host fallback.

## 3. Run state machine

Use a typed enum and a single state-transition function. No agent may set the run's state directly.

Suggested states:
- `queued`
- `initializing`
- `planning`
- `needs_clarification`
- `planned`
- `implementing`
- `candidate_ready`
- `testing`
- `repair_required`
- `reviewing`
- `owner_approval_pending`
- `approved`
- `applying`
- `completed`
- `blocked`
- `failed`
- `cancelled`

### Allowed transitions

| From | To | Trigger / guard |
|---|---|---|
| `queued` | `initializing` | Run accepted and resources allocated |
| `initializing` | `planning` | Repository and required adapters validated |
| `initializing` | `blocked` | Required repository/sandbox/model integration unavailable |
| `planning` | `needs_clarification` | Planner identifies material ambiguity |
| `planning` | `planned` | Valid plan with testable acceptance criteria |
| `needs_clarification` | `planning` | User provides clarification |
| `planned` | `implementing` | Plan schema valid and permissions granted |
| `implementing` | `candidate_ready` | Candidate edit completed and diff/hash recorded |
| `implementing` | `repair_required` | Tool or implementation failure with actionable evidence |
| `candidate_ready` | `testing` | Candidate revision pinned |
| `testing` | `reviewing` | Required criteria verified and no blocking test failure |
| `testing` | `repair_required` | Product-level test failure with reproducible evidence |
| `testing` | `blocked` | Required checks cannot run due to environment/tooling |
| `reviewing` | `owner_approval_pending` | No unresolved blocking findings and required verification complete |
| `reviewing` | `repair_required` | Reviewer identifies blocking issue |
| `repair_required` | `implementing` | Retry budget remains and repair task is actionable |
| `repair_required` | `planning` | New evidence invalidates the plan materially and replanning is allowed |
| `repair_required` | `blocked` | Retry budget exhausted or required capability unavailable |
| `owner_approval_pending` | `approved` | Owner approves exact candidate hash |
| `owner_approval_pending` | `cancelled` | Owner rejects/cancels candidate |
| `approved` | `applying` | Approval hash matches current candidate hash |
| `applying` | `completed` | Apply succeeds and post-apply integrity check passes |
| `applying` | `blocked` | Apply conflict or integrity check failure |
| Any non-terminal | `cancelled` | Authorized cancellation, with active work stopped safely |
| Any eligible non-terminal | `failed` | Unrecoverable internal error, recorded with evidence |

Terminal states: `completed`, `blocked`, `failed`, `cancelled`. A `blocked` run may be resumable through an explicit resume operation; it must not silently continue.

Implement transition guards in Python, not only in prompts. Reject invalid transitions with a typed error and an audit event.

## 4. Shared contracts and Pydantic models

Create shared models once in the backend, then import them from all agent services. Do not let each agent define its own incompatible copy.

Recommended model families:

### `RunContext`
- `run_id: UUID`
- `repository_id: str`
- `candidate_id: UUID | None`
- `candidate_revision: int | None`
- `candidate_sha256: str | None`
- `user_request: str`
- `state: RunState`
- `attempt: int`
- `max_attempts: int`
- `deadline_at: datetime | None`
- `cancel_requested: bool`
- `created_at: datetime`
- `updated_at: datetime`

### `AcceptanceCriterion`
- `criterion_id: str`
- `description: str`
- `verification_method: str`
- `required: bool = True`
- `source_request_excerpt: str | None`

### `EvidenceRef`
- `evidence_id: UUID`
- `run_id: UUID`
- `candidate_id: UUID | None`
- `candidate_sha256: str | None`
- `kind: Literal["repository_read", "diff", "test_execution", "review_finding", "tool_event", "model_response", "approval", "apply_result"]`
- `uri_or_storage_key: str`
- `created_at: datetime`
- `metadata: dict[str, JSONValue]`

### `AgentMessage`
- `message_id: UUID`
- `run_id: UUID`
- `candidate_id: UUID | None`
- `candidate_sha256: str | None`
- `from_agent: Literal["orchestrator", "planner", "developer", "tester", "reviewer"]`
- `to_agent: Literal["orchestrator", "planner", "developer", "tester", "reviewer", "user"]`
- `message_type: Literal["task", "result", "finding", "question", "retry_request", "approval_gate", "stop"]`
- `status: Literal["success", "partial", "blocked", "failed", "needs_clarification"]`
- `summary: str`
- `payload: dict[str, JSONValue]`
- `evidence_refs: list[UUID]`
- `created_at: datetime`

### Other shared models
- `Candidate`: immutable revision metadata, parent revision, SHA-256, changed paths, diff evidence reference, creation timestamp.
- `TestExecution`: approved check ID, candidate hash, started/finished timestamps, exit status, timeout flag, output evidence refs.
- `ReviewFinding`: finding ID, candidate hash, severity, category, path/line reference, description, impact, recommended fix, blocking flag.
- `ApprovalRecord`: approval ID, owner identity/session reference, candidate ID, candidate SHA-256, decision, timestamp, expiry/nonce as appropriate.
- `RunEvent`: event ID, run ID, monotonic sequence number, event type, payload, timestamp.

Use strict validation, reject unexpected fields where appropriate, validate timestamps and IDs, and cap payload sizes. Define JSON-compatible value types centrally. Store schema versioning for persisted records if the product needs migrations.

## 5. Candidate and evidence integrity

Every candidate is an immutable snapshot or immutable patch artifact. A new edit creates a new revision with:
- candidate ID and parent candidate ID;
- monotonic revision number;
- SHA-256 of the exact reviewed/applicable artifact;
- changed paths;
- diff evidence reference;
- creator agent and timestamp.

Tester and Reviewer must explicitly echo the hash they evaluated. If the candidate changes during their work, their results become stale and cannot satisfy a gate.

Evidence records must preserve:
- exact approved check identifier (not arbitrary shell text);
- execution environment/container identity;
- start/end time and exit status;
- bounded stdout/stderr references;
- candidate hash;
- tool name and structured arguments, with secrets redacted;
- whether the evidence was produced by a real tool execution or a mocked test fixture.

Never mark mocked evidence as real run evidence. Use content-addressed storage or integrity hashes where practical.

## 6. Orchestration algorithm

1. Create run, validate request size and permissions, persist initial state.
2. Verify repository is available, candidate workspace can be isolated, required container runtime is usable, and approved model adapter is configured. If a required dependency is unavailable, mark `blocked` with concrete evidence.
3. Invoke Planner with read-only tools and persist its structured output.
4. Validate plan and acceptance criteria. If materially ambiguous, transition to `needs_clarification` and wait for the user's answer.
5. Create isolated candidate from the source repository; record its baseline fingerprint.
6. Invoke Developer with a bounded task brief and candidate-only edit permissions.
7. Validate the diff and create an immutable candidate revision.
8. Invoke Tester against the pinned candidate; persist actual check execution records.
9. If required tests fail, produce a targeted repair task with criterion IDs, expected/observed behavior, output references, and suspected cause. Increment the retry counter and route back to Developer if budget remains.
10. Invoke Reviewer against the exact candidate hash and test evidence.
11. If blocking review findings exist, route a structured repair task to Developer. After edits, re-run affected tests and review the new hash.
12. Run deterministic policy gates independent of model judgement.
13. If gates pass, transition to `owner_approval_pending`. Present the diff summary, exact candidate hash, test report, review findings, and explicit apply scope to the owner.
14. Accept approval only for the exact current candidate hash and within the approval validity policy. Reject stale, replayed, expired, or mismatched approvals.
15. Apply through a controlled patch mechanism with pre-apply baseline integrity check. Never use a blind overwrite.
16. Verify post-apply integrity and report completion only after successful apply verification.
17. Persist all transitions, agent messages, tool executions, evidence references, and final status.

The exact order may be adapted when the project master plan specifies a different sequence, but safety gates must not be weakened.

## 7. Deterministic verification gates

Model recommendations are not sufficient. Implement code-level gates for:
- valid plan and required acceptance criteria;
- candidate path confinement and permitted changed-file scope;
- candidate hash consistency across Developer, Tester, Reviewer, and approval;
- required test status and real execution evidence;
- no unresolved blocking review findings;
- retry count below configured maximum;
- no active cancellation request;
- owner approval matching the current hash;
- source repository baseline unchanged before apply;
- successful post-apply integrity check.

A required criterion that is untested or blocked must not silently count as passing. Policy may permit a user-approved exception, but it must be explicit and auditable rather than inferred by an agent.

## 8. Retry, recovery, and stopping policy

Use configurable bounded attempts (for example, a small default such as 2–3 repair cycles; final value should be set in configuration and tests). Every retry record must contain:
- failed criterion/finding IDs;
- candidate hash that failed;
- evidence references;
- classification: product defect, tool failure, environment failure, ambiguous requirement, or transient failure;
- suspected cause with confidence;
- proposed corrective action;
- remaining budget.

Retry only if there is a plausible new action supported by evidence. Do not repeat the same request unchanged after the same failure. Tool/environment failures should be retried only when transient and policy allows. If sandbox or model integration is unavailable, stop as `blocked`. If a user decision is needed, transition to `needs_clarification`. Cancellation must propagate to running tasks and prevent apply.

## 9. FastAPI, async tasks, SQLite, and SSE

Align with existing backend layout and current spec. Suggested responsibility boundaries:
- `orchestrator/service.py`: run lifecycle and coordination policy.
- `orchestrator/state_machine.py`: allowed transitions and guards.
- `schemas/`: shared Pydantic contracts.
- `repositories/`: SQLite persistence for runs, candidates, messages, evidence, events, approvals.
- `agents/`: Planner, Developer, Tester, Reviewer adapters/services.
- `tools/`: repository, diff, and approved check-runner interfaces.
- `api/`: run creation/status/cancel/resume, approval, and controlled apply endpoints.
- `events/`: SSE publishing, event IDs, replay/reconnect, and state snapshots.

Treat this as a suggested layout only; reconcile with the actual repository before creating or moving files.

Use async task management appropriate to the existing stack; avoid untracked background tasks. Persist events before publishing where feasible. SSE should include `id`, `event`, and serialized `data`, use monotonic per-run sequence IDs, and support `Last-Event-ID` replay or a state snapshot on reconnect. Do not leak secrets or unbounded tool output in event streams.

Potential API surface, subject to existing conventions:
- `POST /runs`
- `GET /runs/{run_id}`
- `POST /runs/{run_id}/cancel`
- `POST /runs/{run_id}/resume`
- `GET /runs/{run_id}/events`
- `GET /runs/{run_id}/diff`
- `POST /runs/{run_id}/approval`
- `POST /runs/{run_id}/apply`

Do not add duplicate endpoints if the repository already has equivalent routes. Approval and apply routes require authorization and candidate-hash checks.

## 10. Security threat model and controls

Threats include malicious or malformed user prompts, prompt injection in repository files, unsafe path inputs, model-generated tool misuse, repository symlink escape, resource exhaustion, candidate tampering, stale test results, forged/replayed approvals, secret leakage, and apply-time source changes.

Controls:
- Treat repository content as untrusted data, never as instructions to change system policy.
- Enforce tool authorization in backend code on every call.
- Resolve and validate paths inside a fixed workspace; reject traversal and symlink escapes.
- Use fixed approved command IDs mapped to argument schemas; no free-form shell command field.
- Execute code only in a restricted container with bounded CPU, memory, time, filesystem, and network permissions.
- If container isolation cannot be established, block execution; no host fallback.
- Redact secrets and cap logs/output.
- Use unguessable run/approval IDs and authorization checks.
- Bind approval to candidate hash, scope, and run; enforce expiry/nonce/replay protection.
- Check source baseline before applying; fail safely on concurrent changes.
- Keep audit records for state transitions and privileged operations.
- Do not treat model-generated assertions as evidence.

## 11. SSE event contract

Each event should include:
- `event_id` / monotonically increasing sequence;
- `run_id`;
- `candidate_id` and hash when relevant;
- `event_type`;
- `timestamp`;
- schema-versioned `data`.

Suggested event types:
- `run.state_changed`
- `agent.started`
- `agent.message`
- `tool.started`
- `tool.completed`
- `candidate.created`
- `test.started`
- `test.completed`
- `review.finding`
- `retry.scheduled`
- `approval.required`
- `approval.recorded`
- `apply.started`
- `apply.completed`
- `run.blocked`
- `run.failed`
- `run.cancelled`

The frontend should render events as they arrive, handle duplicate/out-of-order events by sequence ID, reconnect using the last event ID, and fetch a fresh run snapshot after reconnect. SSE is an observation channel, not an authorization channel.

## 12. Required evaluation suite

Implement integration scenarios with isolated fixture repositories and real tool evidence wherever the required runtime is available:

1. **Feature implementation:** request a bounded feature; confirm criteria, diff, tests, review, and approval gate.
2. **Seeded bug:** include a known bug; verify diagnosis is grounded in repository evidence and fix resolves it.
3. **Test-driven recovery:** deliberately make first candidate fail a check; verify the retry uses failure evidence and creates a new candidate hash.
4. **Security review:** seed a risky change; ensure Reviewer reports evidence-backed findings and blocks owner review where appropriate.
5. **Unexpected conditions:** unavailable container, timeout, malformed model output, missing file, cancellation, concurrent source modification, and SSE reconnect.
6. **Approval integrity:** test stale hash, mismatched hash, replayed approval, expired approval, and changed candidate after approval.
7. **Evidence integrity:** ensure fabricated or mocked output cannot be accepted as real execution evidence.

Metrics:
- acceptance-criteria pass rate;
- successful completion rate;
- median and p95 run duration;
- average repair cycles;
- tool failure and blocked-run rates;
- reviewer blocking-finding detection rate on seeded cases;
- stale-evidence rejection rate;
- approval/apply integrity test pass rate.

Report sample size and fixture details. Do not present fabricated benchmark numbers or claim performance superiority without measurements.

## 13. Definition of done

- [ ] Shared schemas are implemented once and imported by all agents.
- [ ] State transitions are validated in backend code.
- [ ] Agent handoffs and tool calls are persisted and traceable.
- [ ] Candidate revisions are immutable and hash-bound.
- [ ] Tester and Reviewer evidence matches the current candidate.
- [ ] Retry/clarification/stop decisions are bounded and evidence-driven.
- [ ] Restricted container is verified; no host fallback exists.
- [ ] Model access uses only the approved Swytchcode integration.
- [ ] Human approval is required and bound to exact candidate hash.
- [ ] Apply verifies source baseline and post-apply integrity.
- [ ] SSE supports replay/reconnect and state recovery.
- [ ] Required evaluation scenarios have actual recorded results.
- [ ] Documentation clearly distinguishes implemented capabilities from planned capabilities.

## 14. Antigravity implementation prompt

Implement the DevPilot Orchestrator according to this specification and the repository's `DEVPILOT_MASTER_PLAN.md` and backend master spec.

Before editing:
1. Inspect the actual repository tree, current API, schemas, model integration, repository tools, check runner, persistence, and frontend event expectations.
2. Confirm which capabilities exist and which are missing. Do not invent Swytchcode APIs/provider IDs or claim container isolation without verifying the runtime.
3. Propose a minimal implementation sequence and list files expected to change.

Then implement in small milestones:
1. shared Pydantic contracts and state machine;
2. persistence for run state, messages, candidates, evidence, and events;
3. orchestration service with bounded task lifecycle and cancellation;
4. evidence-backed retry routing;
5. deterministic verification gates and candidate-bound approval/apply;
6. SSE event contract and reconnect behavior;
7. integration tests for required scenarios.

Use the existing project architecture rather than blindly creating the suggested layout. Preserve working behavior, do not overwrite unrelated work, and do not run project code outside the restricted Linux container. Use the approved Swytchcode integration only. Never fabricate test results. After each milestone, run approved checks and report actual commands/check IDs, exit statuses, changed files, remaining gaps, and the next step. If a required dependency is unavailable, mark the relevant functionality blocked and explain why instead of creating a fake implementation.
