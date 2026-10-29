# DevPilot Shared Contracts and Evidence Model

> Companion to `Orchestrator_Master_Spec.md` and the four agent specs. This document defines the shared contracts to implement once and reuse across all services.

## 1. Contract ownership

Shared Pydantic models belong in one common backend package. Agent modules may define agent-specific payload models, but must import shared primitives rather than redefining run IDs, candidate hashes, evidence references, message envelopes, or event metadata.

Before implementation, inspect the repository and reuse compatible existing models. This document is normative for behavior, while exact module paths should follow the existing project.

## 2. Common types

Use strict types and explicit enums. Suggested types:

- `RunState`: queued, initializing, planning, needs_clarification, planned, implementing, candidate_ready, testing, repair_required, reviewing, owner_approval_pending, approved, applying, completed, blocked, failed, cancelled.
- `AgentName`: orchestrator, planner, developer, tester, reviewer.
- `AgentStatus`: success, partial, blocked, failed, needs_clarification.
- `EvidenceKind`: repository_read, diff, test_execution, review_finding, tool_event, model_response, approval, apply_result.
- `Severity`: critical, high, medium, low, info.
- `NextAction`: continue, retry, clarify, test, review, owner_approval, apply, stop.
- `JSONValue`: recursively JSON-compatible scalar/list/dict type, with size/depth limits enforced by validators or the persistence layer.

## 3. Shared model contracts

### RunContext
Required run identity and current execution context. Include run ID, repository ID, user request, state, current candidate ID/hash/revision, attempt and max-attempt counts, deadline, cancellation state, timestamps, and schema version.

### AcceptanceCriterion
Criterion ID, clear observable description, verification method, required flag, source-request excerpt, and status when used in a result. A required criterion cannot be considered passed without evidence.

### EvidenceRef
Evidence ID, run ID, optional candidate ID/hash, kind, storage key or URI, creation time, metadata, and a flag distinguishing actual runtime evidence from mocked fixture evidence. Mocked fixture evidence is valid in unit tests but cannot satisfy production run gates.

### AgentMessage
Message ID, run ID, optional candidate identity, sender, recipient, message type, status, concise summary, typed or validated payload, evidence references, timestamp, schema version, and correlation/causation IDs when useful.

### Candidate
Candidate ID, run ID, parent candidate ID, revision number, SHA-256 of exact artifact/diff, changed paths, diff evidence reference, created timestamp, and creator. Candidate records are immutable.

### TestExecution
Execution ID, run ID, candidate ID/hash, approved check ID, environment/container identity, start/end times, exit status, timeout status, bounded output evidence references, and execution provenance.

### TestCriterionResult
Criterion ID, status (`pass`, `fail`, `blocked`, `not_tested`), expected behavior, observed behavior, evidence references, and concise notes.

### ReviewFinding
Finding ID, run ID, candidate ID/hash, severity, category, path and line/diff reference where available, description, impact, recommendation, blocking flag, and evidence references.

### ApprovalRecord
Approval ID, run ID, candidate ID/hash, authorized owner/session reference, decision, approved scope, timestamp, expiry, nonce/replay protection metadata, and consumption status. Never store raw authentication secrets.

### RunEvent
Event ID, run ID, monotonically increasing per-run sequence number, event type, timestamp, schema version, candidate identity if applicable, and JSON-compatible data payload.

## 4. Validation invariants

1. Candidate hash is a normalized SHA-256 hex digest.
2. Candidate revisions increase monotonically within a run.
3. Candidate, evidence, test, review, approval, and event references must belong to the same run unless an explicit cross-run reference is supported.
4. Tester and Reviewer results must identify the exact candidate hash they evaluated.
5. Approval hash must equal the current candidate hash at apply time.
6. A changed candidate invalidates prior candidate-specific test/review readiness and pending approval.
7. `pass` requires actual successful evidence; `blocked` is never equivalent to `pass`.
8. Mocked fixture output cannot satisfy production gates.
9. Unknown enum values and unexpected fields should be rejected for security-sensitive payloads.
10. Output and payload sizes must be bounded to prevent memory/log exhaustion.
11. Timestamps must be timezone-aware.
12. Secrets must never be included in model payloads, event payloads, or evidence metadata.
13. State transitions must be checked by the Orchestrator's state-machine service, not accepted from an agent's output.
14. Event sequence IDs must be unique and monotonic per run.

## 5. Persistence expectations

Persist run state, candidates, agent messages, evidence, test executions, review findings, approval records, and run events. Use SQLite transactions for state transition plus audit event where practical. Store large stdout/stderr/diff artifacts in bounded artifact storage and keep integrity hashes and references in SQLite rather than unbounded blobs when appropriate.

Avoid coupling Pydantic models directly to SQLite row objects; use explicit mapping/repository functions. Add schema migrations or a documented schema version strategy.

## 6. Minimum tests

- Valid and invalid enum/value validation.
- Malformed candidate hash rejection.
- Naive timestamp rejection.
- Oversized payload rejection.
- Cross-run evidence/candidate mismatch rejection.
- Stale Tester/Reviewer result rejection after candidate changes.
- Mocked evidence rejected by production readiness gate.
- Approval mismatch, replay, expiry, and reuse rejection.
- Non-monotonic event sequence rejection.
- Invalid state transition rejected.
