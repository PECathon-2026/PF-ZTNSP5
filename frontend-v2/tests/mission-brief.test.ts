import { test } from "node:test";
import assert from "node:assert/strict";
import { missionBrief, shortMissionTitle } from "../src/lib/mission-brief.ts";

test("follow-up context stays complete without becoming the page heading", () => {
  const text = "Follow-up to miss-2c43d44a. Begin from the current original repository; prior unfinished edits are not inherited. Original request: Explain this repo and build a habit tracker.\nPrior user clarifications (re-evaluate against the repository):\n- Question: CLI or web? Answer: CLI\n- Question: Include the status bug fix? Answer: Yes\nNew user instructions:\n- Save daily history";
  const brief = missionBrief(text);
  assert.equal(brief.title, "Explain this repo and build a habit tracker.");
  assert.equal(brief.parentMissionId, "miss-2c43d44a");
  assert.deepEqual(brief.exchanges, [{ question: "CLI or web?", answer: "CLI" }, { question: "Include the status bug fix?", answer: "Yes" }]);
  assert.equal(brief.instructions, "- Save daily history");
  assert.equal(brief.fullText, text);
});

test("plain requests are not parsed as generated follow-up context", () => {
  const text = "Fix the parser for Original request: and New user instructions: markers";
  assert.equal(missionBrief(text).originalRequest, text);
  assert.equal(missionBrief(text).parentMissionId, null);
});

test("long and unbroken titles are bounded without discarding the complete request", () => {
  const request = "Explain the repository and its implementation. ".repeat(200);
  assert.ok(missionBrief(request).title.length <= 100);
  assert.equal(missionBrief(request).fullText, request);
  assert.ok(shortMissionTitle("x".repeat(10000)).length <= 100);
});
