import test from "node:test";
import assert from "node:assert/strict";
import { addCriterion, classifyHealth, MAX_CRITERIA } from "../src/lib/mission-draft.ts";

test("criterion draft normalizes whitespace without changing the previous draft", () => {
  const original = ["A check runs"];
  const result = addCriterion(original, "  Reject   invalid\n status  ");
  assert.deepEqual(result.criteria, ["A check runs", "Reject invalid status"]);
  assert.deepEqual(original, ["A check runs"]);
  assert.equal(result.error, "");
});

test("empty, duplicate, oversized, and over-limit criteria cannot be added", () => {
  const original = ["Reject invalid status"];
  for (const input of ["  ", "reject INVALID status", "x".repeat(301)]) {
    const result = addCriterion(original, input);
    assert.strictEqual(result.criteria, original);
    assert.ok(result.error);
  }
  const full = Array.from({ length: MAX_CRITERIA }, (_, index) => `Criterion ${index}`);
  assert.match(addCriterion(full, "One more").error, /up to/);
});

test("health probe never equates an HTTP response or HTML fallback with readiness", () => {
  const response = { ok: true };
  assert.deepEqual(classifyHealth(response, "text/html", "<html>"), {
    state: "unavailable", label: "API unavailable", detail: "No compatible local API responded at /api/health.",
  });
  assert.equal(classifyHealth({ ok: false }, "application/json", {}).state, "unavailable");
  const valid = classifyHealth(response, "application/json; charset=utf-8", { status: "ok" });
  assert.equal(valid.state, "responding");
  assert.match(valid.detail, /still unverified/);
});
