import { test } from "node:test";
import assert from "node:assert/strict";
import { agentStatus, approvalState, graphLinks, mergeEvents, verifierStatus } from "../src/lib/mission.ts";
import type { Detail, MissionEvent } from "../src/lib/types.ts";

const event = (sequence: number, mission_id = "m") => ({ sequence, mission_id, event_type: "AGENT_ACTIVITY", source: "SAMURAI", display_payload: {} } as MissionEvent);
test("replay is deduplicated, ordered and isolated from other missions", () => {
  assert.deepEqual(mergeEvents([event(2), event(1)], [event(2), event(3), event(8, "other")], "m").map(e => e.sequence), [1, 2, 3]);
});
test("approval cannot be reused for a historical or different fingerprint candidate", () => {
  const detail = { mission: { active_candidate_id: "c", status: "VERIFIED_AWAITING_APPROVAL" }, candidates: [{ id: "c", state: "APPROVED", content_fingerprint: "new" }], approvals: [{ candidate_id: "c", candidate_fingerprint: "old", decision: "APPROVED" }] } as Detail;
  assert.equal(approvalState(detail, "c").canApply, false);
  detail.approvals[0].candidate_fingerprint = "new";
  assert.equal(approvalState(detail, "c").canApply, true);
  detail.mission.active_candidate_id = "other";
  assert.equal(approvalState(detail, "c").canApply, false);
});
test("queued RUNNING review task does not animate before recorded activity", () => {
  const detail = { mission: { status: "CHECKING" }, tasks: [{ owner_agent: "SHADOW_COUNCIL", status: "RUNNING" }] } as Detail;
  assert.equal(agentStatus("SHADOW_COUNCIL", detail, []), "idle");
  assert.equal(agentStatus("SHADOW_COUNCIL", detail, [{ ...event(1), source: "SHADOW_COUNCIL", display_payload: { stage: "intent" } }]), "working");
  detail.mission.status = "BLOCKED";
  assert.equal(agentStatus("SHADOW_COUNCIL", detail, [{ ...event(1), source: "SHADOW_COUNCIL", display_payload: { stage: "intent" } }]), "idle");
});
test("graph edges require real messages and preserve repair feedback", () => {
  const detail = { messages: [] } as unknown as Detail;
  assert.deepEqual(graphLinks(detail), []);
  detail.messages = [
    { sender: "SENTINEL", recipient: "SAMURAI", type: "FINDING" },
    { sender: "SENTINEL", recipient: "SAMURAI", type: "FINDING" },
    { sender: "USER", recipient: "CONTROLLER", type: "HANDOFF" },
  ] as Detail["messages"];
  const links = graphLinks(detail);
  assert.equal(links.length, 1);
  assert.deepEqual([links[0].source, links[0].target, links[0].count], ["SENTINEL", "SAMURAI", 2]);
});

test("candidate-filtered connections keep only their own message IDs", () => {
  const detail = { messages: [
    { id: "old", sender: "SENTINEL", recipient: "SAMURAI", type: "FINDING", candidate_id: "c1" },
    { id: "new", sender: "SENTINEL", recipient: "SAMURAI", type: "FINDING", candidate_id: "c2" },
  ] } as Detail;
  assert.deepEqual(graphLinks(detail, "c2")[0].messageIds, ["new"]);
  assert.equal(graphLinks(detail)[0].count, 2);
  assert.deepEqual(graphLinks(detail, "missing"), []);
});

test("clarification and independent verifier state follow the current mission and candidate", () => {
  const detail = { mission: { id: "m", active_candidate_id: "c", status: "AWAITING_CLARIFICATION" } } as Detail;
  assert.equal(agentStatus("SHOGUN", detail, []), "waiting for you");
  detail.mission.status = "VERIFYING";
  const started = { ...event(5), candidate_id: "c", source: "VERIFIER", event_type: "VERIFIER_STARTED" };
  assert.equal(verifierStatus(detail, []), "ready");
  assert.equal(verifierStatus(detail, [started]), "running");
  assert.equal(verifierStatus(detail, [{ ...started, candidate_id: "old" }]), "ready");
  assert.equal(verifierStatus(detail, [{ ...started, mission_id: "other" }]), "ready");
  assert.equal(verifierStatus(detail, [started, { ...started, sequence: 6, event_type: "VERIFIER_ERROR" }]), "stopped without a verdict");
  assert.equal(verifierStatus(detail, [started, { ...started, sequence: 6, event_type: "VERIFICATION_FAILED" }]), "failed");
  detail.mission.status = "VERIFIED_AWAITING_APPROVAL";
  assert.equal(verifierStatus(detail, []), "passed");
});
