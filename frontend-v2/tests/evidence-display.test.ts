import { test } from "node:test";
import assert from "node:assert/strict";
import { evidenceDisplay } from "../src/lib/evidence-display.ts";
import type { Evidence } from "../src/lib/types.ts";

test("zero exit without a structured report is not labelled tests passed", () => {
  const item = { kind: "TEST", exit_code: 0, metadata: { check_profile: "python_pytest" } } as Evidence;
  assert.equal(evidenceDisplay(item).result, "Exit 0");
});

test("actual report counts and controlled provenance remain visible", () => {
  const item = { kind: "TEST", exit_code: 0, criterion_id: "c", metadata: {
    check_profile: "python_pytest", controlled_evaluation: true, test_selector: "test_app.py::test_value",
    report: { summary: { passed: 4, failed: 0, skipped: 1 } },
  } } as unknown as Evidence;
  assert.deepEqual(evidenceDisplay(item), { title: "Acceptance check", result: "4 passed · 1 skipped", controlled: true, selector: "test_app.py::test_value" });
});
