import test from "node:test";
import assert from "node:assert/strict";
import { activeCandidate, approvedCandidate, checkedCandidate, eventSummary, sequenceUpdate } from "../src/lib/backend.ts";

function detail() {
  return { mission: { active_candidate_id: "v2" }, candidates: [{ id: "v1", content_fingerprint: "old" }, { id: "v2", content_fingerprint: "new" }],
    approvals: [{ candidate_id: "v1", candidate_fingerprint: "old", decision: "APPROVED" }],
    evidence: [{ candidate_id: "v1", fingerprint: "old", exit_code: 0, metadata: { check_profile: "python_pytest", execution_status: "SUCCEEDED" } }] };
}

test("old candidate evidence and approval never display as current", () => {
  const state = detail();
  assert.equal(activeCandidate(state)?.id, "v2");
  assert.equal(checkedCandidate(state), false);
  assert.equal(approvedCandidate(state), false);
  state.evidence.push({ candidate_id: "v2", fingerprint: "stale", exit_code: 0, metadata: { check_profile: "python_pytest", execution_status: "SUCCEEDED" } });
  assert.equal(checkedCandidate(state), false);
  state.evidence[1].fingerprint = "new";
  assert.equal(checkedCandidate(state), true);
  state.approvals.push({ candidate_id: "v2", candidate_fingerprint: "stale", decision: "APPROVED" });
  assert.equal(approvedCandidate(state), false);
  state.approvals[1].candidate_fingerprint = "new";
  assert.equal(approvedCandidate(state), true);
});

test("SSE cursor rejects replay and detects gaps", () => {
  assert.equal(sequenceUpdate(3, 3), "duplicate");
  assert.equal(sequenceUpdate(3, 2), "duplicate");
  assert.equal(sequenceUpdate(3, 4), "next");
  assert.equal(sequenceUpdate(3, 7), "gap");
  assert.equal(sequenceUpdate(0, Number.NaN), "duplicate");
});

test("activity timeline shows persisted summary and falls back for legacy events", () => {
  const event = { event_type: "AGENT_ACTIVITY", display_payload: { summary: "Samurai read `routes.py` to inspect conventions." } };
  assert.equal(eventSummary(event), "Samurai read `routes.py` to inspect conventions.");
  assert.equal(eventSummary({ event_type: "PLAN_READY", display_payload: {} }), "PLAN_READY");
  assert.equal(eventSummary({ event_type: "AGENT_ACTIVITY", display_payload: { summary: 9 } }), "AGENT_ACTIVITY");
});
