# Mission recovery and budget extension

Recovery is explicit. Startup still marks interrupted work as interrupted and
does not replay tool calls. These endpoints let the user inspect a stopped
mission and authorize a bounded continuation of the same mission.

Restart the backend after updating to register the new routes.

## Endpoints

### `GET /api/missions/{id}/recovery`

Returns `stage`, `can_continue`, `can_extend_budget`, `checkpoint_token`, actual
budget usage/remaining, structural and budget blockers, a bounded partial diff,
and the checkpoint candidate. This is read-only.

The token binds the decision to mission state, plan/context, tasks, criteria,
candidates, findings and the actual workspace fingerprint. Inspect again after
any state change or budget extension. It is a stale-state guard, not login/auth.

### `GET /api/missions/{id}/recovery/file?checkpoint_token=...&path=...`

Reads an included unverified workspace file for human inspection before recovery.
Both the checkpoint and path are validated. Deleted files are reported explicitly.
This avoids confusing the last frozen candidate with newer partial edits.

### `POST /api/missions/{id}/budget-extension`

```json
{
  "checkpoint_token": "<from recovery inspection>",
  "limits": {
    "max_model_turns": 80,
    "max_tool_calls": 150,
    "max_tokens": 480000,
    "max_time_seconds": 1200
  }
}
```

Send complete new total ceilings. At least one must increase; none can decrease.
All usage counters, clarification count and repair rounds remain unchanged. The
schema rejects usage-counter inputs and out-of-range values. This operation does
not start a worker or invoke a model. The returned inspection contains a new token.

Absolute mission ceilings remain 100 turns, 500 tools, 1,000,000 reported tokens
and 3,600 active seconds. The repair cap remains three and is not extensible.
Before/after limits are retained in context and the `BUDGET_EXTENDED` audit event.

### `POST /api/missions/{id}/continue`

```json
{
  "checkpoint_token": "<fresh token after any extension>",
  "accept_partial_edits": true
}
```

Returns 202 and the mission snapshot after claiming the continuation. The flag is
required only when there are unverified partial edits. It authorizes their use as
a recovery checkpoint, not application to the original repository.

The SQLite claim and writer lease reject duplicate/stale requests. Source and
snapshot validation is repeated before snapshot capture. An original repository
that changed, protected test changes, symlinks/junctions, missing snapshots, an
active worker, prior approval, or pending application journal block recovery.

## Recovery stages

- **Planning:** retain original files and clarification answers; capture a fresh
  baseline record, rerun baseline checks and replan without resetting the workspace.
  The new plan still needs user authorization. Superseded plan/task history remains.
- **Development:** retain completed tasks and source changes. Capture partial work
  as `UNVERIFIED_RECOVERY`. A fresh bounded developer loop receives inherited
  changed paths. It cannot hand off until it reads back and inspects those changes,
  even if it needs no additional edit. Old write calls are never replayed.
- **Checks/review:** create a fresh candidate record and fresh check/review tasks.
  Prior evidence remains historical; it is not reused to certify the new record.
  This also avoids ambiguous duplicate report sets on one candidate.
- **Repair planning:** resume the existing evidence-driven repair checkpoint.
  Already-reserved rounds are not charged twice; a fourth repair is still refused.

New developer attempts retain the local 20-turn/50-tool/300-second bounds within
the remaining global allowance. Context is reconstructed from saved tasks,
clarifications and candidate evidence, rather than resending the old transcript.

Independent verification and a new explicit candidate decision are still required
before application. No existing approval may authorize a recovered candidate.

## Existing-state actions

Clarification, plan authorization, verification and approved application continue
to use their existing endpoints. Applied, rejected and cancelled missions require
a new follow-up. Missions without a complete durable baseline cannot be recovered.
Workspace edits appearing after a final developer handoff are rejected rather than
silently replacing that handoff. Recovery is not a mechanism to change criteria or
approved acceptance tests; that scope change still needs a fresh mission.

For missions using their own API key, re-enter the key after a stop/restart before
continuing. Recovery uses the same per-mission credential path and never falls back
to the server key. Keys are never added to checkpoint tokens, counters or history.

## Frontend

Mission History exposes the appropriate Continue/Review/Answer action. The mission
workspace shows a recovery panel, partial-file inspection, explicit budget
extension and a separate Continue action. Recoverable stopped missions retain an
event stream so the UI follows a resumed worker. Starting a fresh mission remains
available when continuation is blocked.

## Verification

```powershell
python -m pytest tests/unit/test_mission_recovery.py -q
```

The suite uses temporary SQLite/files and scripted model/check responses. It covers
partial-edit acknowledgment, inherited-change inspection, no original modification,
counter preservation, stale/duplicate requests, restart continuity, changed files,
protected tests, read-only inspection, approval rejection, repair cap and own-key
requirements. Controlled check results cannot pass independent verification.
