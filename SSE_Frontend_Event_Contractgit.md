# DevPilot SSE and Frontend Event Contract

> Defines the event stream consumed by the DevPilot dashboard. Align with the current backend/frontend before implementing new endpoints or event names.

## 1. Envelope

Every event uses one versioned envelope:

```json
{
  "event_id": "uuid",
  "run_id": "uuid",
  "sequence": 12,
  "event_type": "agent.started",
  "timestamp": "2026-10-29T12:00:00Z",
  "schema_version": 1,
  "candidate_id": "uuid-or-null",
  "candidate_sha256": "sha256-or-null",
  "data": {}
}
```

The above is illustrative. IDs and timestamps must be validated. Event payloads must not contain secrets or unbounded raw output.

## 2. Event types

- `run.state_changed`: old state, new state, reason/evidence references.
- `agent.started`: agent name, attempt number, task/correlation ID.
- `agent.message`: structured handoff metadata and a safe summary.
- `tool.started`: approved tool ID, safe argument summary.
- `tool.completed`: tool ID, status, exit status if applicable, duration, evidence refs.
- `candidate.created`: candidate ID, revision, hash, changed paths.
- `test.started`: candidate hash and approved check IDs.
- `test.completed`: candidate hash, criterion statuses, execution evidence refs.
- `review.finding`: candidate hash, severity, category, safe finding summary, evidence ref.
- `retry.scheduled`: reason, failed criterion/finding IDs, attempt/max attempts.
- `approval.required`: candidate hash, diff summary, required owner action.
- `approval.recorded`: decision and candidate hash, without authentication secrets.
- `apply.started`: candidate hash and approved apply scope.
- `apply.completed`: result and integrity-check evidence.
- `run.blocked`, `run.failed`, `run.cancelled`: terminal/paused reason and evidence references.

## 3. SSE delivery requirements

- Send standard SSE `id`, `event`, and `data` fields.
- `id` must correspond to a persisted monotonic sequence/event identifier.
- Persist an event before publishing it where feasible to avoid lost updates.
- Support `Last-Event-ID` replay. If the requested cursor is no longer available, send a state snapshot or instruct the client to fetch `GET /runs/{run_id}`.
- The client must deduplicate events and detect sequence gaps.
- Reconnect with bounded backoff and cancellation-aware cleanup.
- Do not create one untracked task per connection; manage connection/task lifetimes.
- Heartbeats may be used to keep intermediaries from closing idle streams.
- SSE is read-only telemetry, never proof of owner identity or authorization.
- Enforce authorization for both stream connection and snapshot/replay endpoints.
- Redact secrets and truncate tool output; fetch large artifacts via authorized evidence references.

## 4. Frontend behavior

- Render run state and agent activity from server events.
- On reconnect, reconcile from the canonical run snapshot and then resume the stream.
- Show distinct states for `blocked`, `failed`, `cancelled`, `needs_clarification`, and successful completion.
- Never display “tests passed” unless required test evidence is present for the current candidate hash.
- Never display “approved” unless a valid owner approval record matches the current candidate hash.
- If candidate hash changes, mark previous test/review badges stale until refreshed evidence arrives.
- Show retry count and why the retry occurred.
- Make approval UI display the exact candidate hash and diff summary that will be applied.
