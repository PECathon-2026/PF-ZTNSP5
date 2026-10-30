/** Opt-in real-model/browser walkthrough, restricted to a newly generated demo repo. */
import { chromium } from "@playwright/test";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import { fingerprintFixture } from "./demo-integrity.mjs";

const origin = process.env.KAGE_TEST_BASE_URL || "http://127.0.0.1:3001";
const applyDemo = process.argv.includes("--approve-demo");
const temporaryRoot = join(tmpdir(), "opencode");
await mkdir(temporaryRoot, { recursive: true });
const repo = await mkdtemp(join(temporaryRoot, "kage-ui-live-"));
const output = resolve("test-results", `live-${Date.now()}`);
await mkdir(output, { recursive: true });
const source = '"""Small pagination utility for the isolated KAGE browser walkthrough."""\n\ndef paginate(items, page, size):\n    if page < 1 or size < 1:\n        raise ValueError("page and size must be positive")\n    start = (page - 1) * size\n    return items[start:start + size - 1]\n';
const tests = '"""Acceptance tests retained unchanged throughout the live walkthrough."""\nfrom pagination import paginate\n\ndef test_full_page():\n    assert paginate([10, 20, 30, 40, 50], 1, 2) == [10, 20]\n    assert paginate([10, 20, 30, 40, 50], 2, 2) == [30, 40]\n\ndef test_partial_page():\n    assert paginate([10, 20, 30, 40, 50], 3, 2) == [50]\n\ndef test_empty_input():\n    assert paginate([], 1, 2) == []\n\ndef test_invalid_page():\n    try:\n        paginate([1], 0, 1)\n    except ValueError:\n        return\n    raise AssertionError("invalid page must be rejected")\n';
await writeFile(join(repo, "pagination.py"), source);
// Include size-one pages: a real earlier run correctly flagged that missing boundary.
const completeTests = tests.replace('    assert paginate([10, 20, 30, 40, 50], 2, 2) == [30, 40]',
  '    assert paginate([10, 20, 30, 40, 50], 2, 2) == [30, 40]\n    assert paginate([10, 20, 30], 2, 1) == [20]');
await writeFile(join(repo, "test_pagination.py"), completeTests);
const digest = value => createHash("sha256").update(value).digest("hex");
const report = { started_at: new Date().toISOString(), repository: repo, original_hash: digest(source), mode: "real_model_real_docker_real_browser", automation_approval_on_generated_fixture_only: applyDemo, checkpoints: [], browser_errors: [] };
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", error => report.browser_errors.push(error.message));
let missionId;
async function checkpoint(name, detail) {
  report.checkpoints.push({ name, at: new Date().toISOString(), status: detail?.mission?.status });
  console.log(name, detail?.mission?.status || "");
  await writeFile(join(output, "report.json"), JSON.stringify(report, null, 2));
}
async function snapshot() {
  const response = await page.request.get(`${origin}/api/backend/missions/${missionId}`);
  if (!response.ok()) throw new Error(`Mission read failed: ${response.status()}`);
  return response.json();
}
async function waitForMission(states, milliseconds = 480000) {
  const end = Date.now() + milliseconds;
  while (Date.now() < end) {
    const detail = await snapshot();
    if (states.includes(detail.mission.status)) return detail;
    if (["BLOCKED", "BUDGET_EXHAUSTED", "INTERRUPTED", "FAILED_VERIFICATION", "AWAITING_CLARIFICATION"].includes(detail.mission.status)) {
      report.failure_detail = { status: detail.mission.status, reason: detail.mission.failure_reason, questions: detail.clarifications, budgets: detail.mission.budgets };
      throw new Error(`Mission stopped at ${detail.mission.status}: ${detail.mission.failure_reason || "human input required"}`);
    }
    await page.waitForTimeout(1500);
  }
  throw new Error("Live walkthrough exceeded its bounded wait");
}
try {
  await page.goto(`${origin}/missions/new`);
  await page.getByText("Docker ready", { exact: true }).waitFor({ timeout: 30000 });
  await page.getByLabel("01 / Repository").fill(repo);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByLabel("02 / Your request").fill("Fix the off-by-one slicing bug in paginate so full pages contain the requested number of items. Preserve partial pages, empty input, and existing invalid-page validation. Keep tests unchanged; make only the necessary source change.");
  await page.getByLabel("03 / Acceptance criteria").fill("Full pages contain the requested number of items.\nThe final partial page remains correct.\nEmpty input returns an empty page.\nInvalid page numbers still raise ValueError.");
  await page.getByLabel("04 / Mission budget").selectOption("extended");
  await page.getByRole("button", { name: "Create mission", exact: true }).click();
  await page.waitForURL(/\/missions\/miss-[a-zA-Z0-9-]+\/workspace/, { timeout: 30000 });
  missionId = new URL(page.url()).pathname.split("/")[2];
  report.mission_id = missionId;
  console.log("MISSION", missionId, "REPO", repo, "REPORT", output);
  await checkpoint("created", await snapshot());
  await page.getByRole("button", { name: "Start planning", exact: true }).click();
  let detail = await waitForMission(["READY_FOR_AUTHORIZATION"]);
  await checkpoint("plan_ready", detail);
  if (detail.acceptance_test_proposal && !detail.acceptance_test_proposal.accepted) {
    throw new Error("Unexpected proposed tests require human review; fixture already has acceptance tests");
  }
  await page.getByRole("button", { name: "Authorize workspace work", exact: true }).click({ timeout: 30000 });
  await page.getByRole("link", { name: "Agent graph", exact: true }).click();
  detail = await waitForMission(["VERIFYING"]);
  await page.screenshot({ path: join(output, "graph.png"), fullPage: true });
  await checkpoint("checks_and_review_completed", detail);
  await page.getByRole("button", { name: /^(Run independent verifier|Verify candidate)$/ }).click({ timeout: 30000 });
  detail = await waitForMission(["VERIFIED_AWAITING_APPROVAL"], 30000);
  await checkpoint("verified", detail);
  await page.getByRole("link", { name: "Review & apply", exact: true }).click();
  await page.getByRole("button", { name: "Approve this candidate", exact: true }).waitFor({ timeout: 30000 });
  await page.screenshot({ path: join(output, "review-before-approval.png"), fullPage: true });
  report.original_preserved_before_approval = (await readFile(join(repo, "pagination.py"), "utf8")) === source;
  if (!report.original_preserved_before_approval) throw new Error("Original changed before approval");
  const candidate = detail.candidates.find(c => c.id === detail.mission.active_candidate_id);
  report.candidate_id = candidate.id;
  report.fingerprint = candidate.content_fingerprint;
  report.criteria = detail.criteria;
  report.budgets = detail.mission.budgets;
  if (applyDemo) {
    // This script has no --repo argument and can only apply to the fixture it created.
    await page.getByLabel("I reviewed this diff, its criteria and supporting evidence.").check();
    await page.getByRole("button", { name: "Approve this candidate", exact: true }).click();
    await page.getByLabel("Apply this approved candidate to the original repository.").waitFor({ timeout: 30000 });
    report.original_preserved_after_approval = (await readFile(join(repo, "pagination.py"), "utf8")) === source;
    if (!report.original_preserved_after_approval) throw new Error("Approval alone changed the original");
    await checkpoint("approved_generated_fixture_only", await snapshot());
    await page.getByLabel("Apply this approved candidate to the original repository.").check();
    await page.getByRole("button", { name: "Apply approved changes", exact: true }).click();
    detail = await waitForMission(["APPLIED"], 30000);
    const applied = await readFile(join(repo, "pagination.py"), "utf8");
    const frozenResponse = await page.request.get(`${origin}/api/backend/missions/${missionId}/candidates/${candidate.id}/file?path=pagination.py`);
    if (!frozenResponse.ok()) throw new Error("Cannot inspect approved frozen source");
    const frozen = await frozenResponse.json();
    // File-read API normalizes CRLF; compare raw directory fingerprints for integrity.
    report.applied_fingerprint = await fingerprintFixture(repo);
    report.applied_bytes_match_candidate = report.applied_fingerprint === candidate.content_fingerprint;
    report.applied_text_matches_view = applied.replaceAll("\r\n", "\n") === frozen.content;
    report.tests_preserved = (await readFile(join(repo, "test_pagination.py"), "utf8")) === completeTests;
    if (!report.applied_bytes_match_candidate || !report.tests_preserved || applied === source) throw new Error("Applied fixture integrity check failed");
    await checkpoint("applied_and_integrity_checked", detail);
    await page.screenshot({ path: join(output, "applied.png"), fullPage: true });
  }
  const proof = await page.request.get(`${origin}/api/backend/missions/${missionId}/proof`);
  await writeFile(join(output, "proof.json"), JSON.stringify(await proof.json(), null, 2));
  report.final_status = detail.mission.status;
  report.success = report.browser_errors.length === 0;
  if (!report.success) throw new Error("Browser errors were recorded");
} catch (error) {
  report.success = false;
  report.error = error.message;
  await page.screenshot({ path: join(output, "failure.png"), fullPage: true }).catch(() => {});
  console.error(error.message);
  process.exitCode = 1;
} finally {
  report.finished_at = new Date().toISOString();
  await writeFile(join(output, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ success: report.success, mission_id: missionId, final_status: report.final_status, output }));
  await browser.close();
}
