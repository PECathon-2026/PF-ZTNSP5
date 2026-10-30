/** Browser integration fixtures are synthetic, never evidence of a model run. */
import { expect, test, type Page } from "@playwright/test";

const hash = "a".repeat(64);
function fixture(id = "miss-current", status = "RUNNING") {
  return {
    mission: { id, repository_id: "repo-sample", request_text: id === "miss-current" ? "Reject negative amounts" : "Add empty-input handling", status, created_at: id === "miss-current" ? "2026-10-30T10:00:00Z" : "2026-10-29T10:00:00Z", scope_version: 1, active_candidate_id: "cand-one", failure_reason: null, budgets: { repair_rounds_used: 1, max_repair_rounds: 3, tool_calls_used: 8, max_tool_calls: 50, model_turns_used: 5, max_model_turns: 25 } },
    tasks: [{ id: "task-one", title: "Validate the amount", description: "Reject negatives and retain valid behavior", owner_agent: "SAMURAI", status: "RUNNING", attempt: 2, dependencies: [], candidate_id: "cand-one", evidence_ids: ["ev-one"], result_summary: "Inspected candidate" }],
    criteria: [{ id: "criterion-one", description: "Negative amounts are rejected", status: "PASS", evidence_ids: ["ev-one"], verification_method: "test_profile:python_pytest|test_ledger.py::test_negative" }],
    candidates: [{ id: "cand-one", state: "FROZEN", content_fingerprint: hash, changed_files: ["ledger.py"], parent_candidate_id: null }],
    evidence: [{ id: "ev-one", candidate_id: "cand-one", fingerprint: hash, source: "SENTINEL", kind: "TEST", command: ["python", "-m", "pytest"], exit_code: 0, duration_ms: 220, criterion_id: "criterion-one", metadata: { check_profile: "python_pytest" } }],
    findings: [], messages: [{ id: "msg-one", sender: "SENTINEL", recipient: "SAMURAI", type: "FINDING", summary: "Negative amount failed", candidate_id: "cand-one", evidence_ids: ["ev-one"], payload: {} }],
    repository_files: ["ledger.py", "test_ledger.py"], clarifications: [], approvals: [] as { candidate_id: string; candidate_fingerprint: string; decision: string }[], plan_revision: 2,
  };
}
async function backend(page: Page, status = "RUNNING", requestText?: string) {
  const current = fixture("miss-current", status);
  if (requestText) current.mission.request_text = requestText;
  const previous = fixture("miss-past", "APPLIED");
  const mutations: { action: string; body: Record<string, unknown> }[] = [];
  let checkpoint = "b".repeat(64);
  function recovery() {
    return { can_continue: true, can_extend_budget: true, stage: "development", checkpoint_token: checkpoint,
      partial_edits: true, changed_files: ["ledger.py"], partial_files: ["ledger.py"], diff: "+raise ValueError('negative')", diff_truncated: false,
      blockers: [], budget_blockers: [], budgets: { max_tokens: 160000, max_time_seconds: 600, ...current.mission.budgets },
      checkpoint_candidate_id: "cand-one", new_agent_turn_limit: 20 };
  }
  await page.route("**/api/backend/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/backend", "");
    const record = path.includes("miss-past") ? previous : current;
    const json = (data: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    if (path.endsWith("/recovery")) return json(recovery());
    if (path.endsWith("/recovery/file")) return json({ content: "raise ValueError('negative')\n" });
    if (path === "/health") return json({ docker_available: true, model_configured: true, storage_ready: true });
    if (path === "/repositories/connect") return json({ repository_id: "repo-sample", name: "Sample repo", path: "D:/sample", preflight: { status: "READY", file_count: 2, warnings: [], blockers: [] } });
    if (path === "/missions") {
      if (request.method() === "POST") {
        const body = request.postDataJSON();
        mutations.push({ action: "create", body });
        Object.assign(current.mission.budgets, body.limits);
        return json(current);
      }
      return json([current.mission, previous.mission]);
    }
    if (path.endsWith("/history")) return json({ events: [{ sequence: 1, mission_id: record.mission.id, source: "SAMURAI", event_type: "AGENT_ACTIVITY", task_id: "task-one", candidate_id: "cand-one", created_at: "2026-10-30T10:02:00Z", evidence_ids: [], display_payload: { stage: "intent", action: "read_file", relative_path: "ledger.py", summary: "Samurai is reading ledger.py" } }], next_cursor: 1, has_more: false, repository_name: "Sample repo" });
    if (path.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: ": heartbeat\n\n" });
    if (path.endsWith("/diff")) return json({ files: [{ file_path: "ledger.py", change_type: "MODIFIED" }], unified_diff: "--- a/ledger.py\n+++ b/ledger.py\n@@ -1 +1 @@\n-return value\n+return max(value, 0)\n" });
    if (path.endsWith("/file")) return json({ content: path.includes("/baseline/") ? "def debit(value):\n    return value\n" : "def debit(value):\n    if value < 0:\n        raise ValueError('negative')\n    return value\n" });
    if (path.includes("/evidence/")) return json({ ...record.evidence[0], stdout: "1 passed (synthetic browser fixture)", stderr: "" });
    if (request.method() === "POST") {
      const action = path.split("/").at(-1)!;
      const body = request.postDataJSON();
      mutations.push({ action, body });
      if (action === "budget-extension") {
        Object.assign(current.mission.budgets, body.limits);
        checkpoint = "c".repeat(64);
        return json(recovery());
      }
      if (action === "continue") current.mission.status = "RUNNING";
      if (action === "approve") { current.approvals = [body]; current.candidates[0].state = body.decision; }
      if (action === "apply") { current.mission.status = "APPLIED"; current.candidates[0].state = "APPLIED"; }
      return json(current);
    }
    return json(record);
  });
  return mutations;
}

test("landing and mobile setup remain usable without horizontal overflow", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await backend(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Great code. A little shadow work." })).toBeVisible();
  await page.screenshot({ path: "test-results/landing-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/missions/new");
  await page.getByLabel("01 / Repository").fill("D:/sample");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByLabel("02 / Your request").fill("Reject negative amounts");
  await expect(page.getByRole("button", { name: "Create mission" })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});

test("IDE displays code and agent history remains separate across missions", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", error => browserErrors.push(error.message));
  const actions = await backend(page);
  await page.goto("/missions/miss-current/workspace");
  await expect(page.getByRole("heading", { name: "Reject negative amounts", exact: true })).toBeVisible();
  await expect(page.locator(".monaco-diff-editor")).toBeVisible();
  await page.getByLabel("Candidate revision").selectOption("cand-one");
  await expect(page.getByRole("link", { name: "Agent graph", exact: true })).toHaveAttribute("href", /candidate=cand-one/);
  await page.screenshot({ path: "test-results/workspace-desktop.png", fullPage: true });
  await page.getByRole("button", { name: /Samurai.*Developer/ }).click();
  await page.getByRole("button", { name: "This mission", exact: true }).click();
  await expect(page.locator(".agent-drawer").getByText("Validate the amount", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Previous missions", exact: true }).click();
  await page.getByRole("button", { name: /Add empty-input handling/ }).click();
  await expect(page.getByRole("link", { name: "Open historical graph" })).toHaveAttribute("href", /miss-past\/graph\?returnTo=miss-current/);
  await expect(page.locator(".tool-chips").getByText("read_file", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Open historical graph" }).click();
  await expect(page.getByRole("link", { name: "Return to active mission" })).toBeVisible();
  await expect(page.locator(".react-flow__node-agent")).toHaveCount(4);
  await page.screenshot({ path: "test-results/graph-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: "test-results/graph-mobile.png", fullPage: true });
  expect(actions).toHaveLength(0);
  expect(browserErrors).toEqual([]);
});

test("live activity replay deduplicates events and ignores another mission", async ({ page }) => {
  await backend(page);
  await page.addInitScript(() => {
    class TestSource extends EventTarget {
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor() {
        super();
        (window as unknown as { emitTestEvent: (data: unknown) => void }).emitTestEvent = data => this.dispatchEvent(new MessageEvent("mission", { data: JSON.stringify(data) }));
        setTimeout(() => this.onopen?.(), 10);
      }
      close() {}
    }
    Object.defineProperty(window, "EventSource", { value: TestSource });
  });
  await page.goto("/missions/miss-current/workspace");
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  await expect(page.locator(".connection.live")).toBeVisible();
  await page.evaluate(() => {
    const emit = (window as unknown as { emitTestEvent: (data: unknown) => void }).emitTestEvent;
    const event = { sequence: 2, mission_id: "miss-current", source: "SAMURAI", event_type: "AGENT_ACTIVITY", display_payload: { stage: "outcome", action: "read_diff", summary: "Inspected the new candidate diff" } };
    emit(event); emit(event);
    emit({ ...event, sequence: 3, mission_id: "miss-other", display_payload: { summary: "OTHER MISSION DATA" } });
  });
  await expect(page.getByText("Inspected the new candidate diff", { exact: true })).toHaveCount(1);
  await expect(page.getByText("OTHER MISSION DATA")).toHaveCount(0);
});

test("approval binds the fingerprint and application requires a second explicit action", async ({ page }) => {
  const actions = await backend(page, "VERIFIED_AWAITING_APPROVAL");
  await page.goto("/missions/miss-current/review");
  const approve = page.getByRole("button", { name: "Approve this candidate" });
  await expect(approve).toBeDisabled();
  await page.getByLabel("I reviewed this diff, its criteria and supporting evidence.").check();
  await approve.click();
  await expect(page.getByText("Approval recorded. The original has not been changed by approval alone.")).toBeVisible();
  expect(actions).toEqual([{ action: "approve", body: { candidate_id: "cand-one", candidate_fingerprint: hash, decision: "APPROVED" } }]);
  const apply = page.getByRole("button", { name: "Apply approved changes" });
  await expect(apply).toBeDisabled();
  await page.getByLabel("Apply this approved candidate to the original repository.").check();
  await apply.click();
  await expect(page.getByText("The backend recorded successful application.")).toBeVisible();
  expect(actions.at(-1)).toEqual({ action: "apply", body: { candidate_id: "cand-one" } });
});

test("failed backend requests are visible instead of populated with demo results", async ({ page }) => {
  await page.route("**/api/backend/**", route => route.fulfill({ status: 502, contentType: "application/json", body: JSON.stringify({ detail: "Backend unavailable." }) }));
  await page.goto("/missions/miss-missing/workspace");
  await expect(page.locator(".error-banner[role=alert]")).toContainText("Backend unavailable");
  await expect(page.getByRole("heading", { name: "Unable to load mission" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve this candidate" })).toHaveCount(0);
});

test("exhausted mission prepares a fresh explicitly selected extended budget without resuming", async ({ page }) => {
  const actions = await backend(page, "BUDGET_EXHAUSTED");
  await page.goto("/missions/miss-current/workspace");
  await page.getByRole("link", { name: "Prepare a new mission with extended budget" }).click();
  await expect(page.getByLabel("04 / Mission budget")).toHaveValue("extended");
  await expect(page.getByLabel("02 / Your request")).toHaveValue("Reject negative amounts");
  expect(actions).toHaveLength(0);
  await page.getByLabel("01 / Repository").fill("D:/sample");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByRole("button", { name: "Create mission", exact: true }).click();
  await expect(page).toHaveURL(/miss-current\/workspace/);
  expect(actions).toHaveLength(1);
  expect(actions[0].action).toBe("create");
  expect(actions[0].body.limits).toEqual({ max_model_turns: 60, max_tool_calls: 100, max_tokens: 320000, max_time_seconds: 900 });
});

test("graph handoffs expose recorded messages and evidence", async ({ page }) => {
  await backend(page);
  await page.goto("/missions/miss-current/graph");
  await page.getByRole("button", { name: "1 connections", exact: true }).click();
  await page.locator(".connection-list button").click();
  await expect(page.locator(".message-record")).toContainText("Negative amount failed");
  await page.getByLabel("Graph connection scope").selectOption("candidate");
  await page.locator(".connection-list button").click();
  await page.locator(".message-record").getByRole("button", { name: "Inspect evidence" }).click();
  await expect(page.getByRole("dialog")).toContainText("1 passed (synthetic browser fixture)");
  await page.getByRole("button", { name: "Close evidence" }).click();
  await page.screenshot({ path: "test-results/graph-handoff.png", fullPage: true });
});

test("file tabs close cleanly and line links focus the candidate", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await backend(page);
  await page.goto("/missions/miss-current/workspace?file=ledger.py&line=3");
  await expect(page.locator(".code-toolbar .mono")).toHaveText("ledger.py:3");
  await expect(page.locator(".monaco-diff-editor")).toBeVisible();
  await page.locator(".file-panel").getByRole("button", { name: "test_ledger.py", exact: true }).click();
  await expect(page.getByRole("button", { name: "Close ledger.py", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Close test_ledger.py", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close test_ledger.py", exact: true }).click();
  await expect(page.locator(".code-toolbar .mono")).toHaveText("ledger.py");
  await page.getByRole("button", { name: "Close ledger.py", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your canvas is ready" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("same-mission recovery extends ceilings then separately accepts partial edits and continues", async ({ page }) => {
  const actions = await backend(page, "BUDGET_EXHAUSTED");
  await page.goto("/missions/miss-current/workspace");
  const panel = page.getByRole("region", { name: "Mission recovery" });
  const continueButton = panel.getByRole("button", { name: "Continue developer work", exact: true });
  await expect(continueButton).toBeDisabled();
  await panel.getByRole("button", { name: "Inspect ledger.py", exact: true }).click();
  await expect(panel.getByText("Unverified workspace / ledger.py", { exact: true })).toBeVisible();
  await panel.getByText("Extend this mission’s budget", { exact: true }).click();
  await panel.getByRole("button", { name: "Suggest bounded extra allowance" }).click();
  await panel.getByRole("button", { name: "Confirm budget extension" }).click();
  await expect(panel.getByRole("status")).toContainText("Usage is preserved");
  expect(actions).toHaveLength(1);
  expect(actions[0].action).toBe("budget-extension");
  await panel.getByLabel("I inspected these unverified edits and authorize a fresh bounded developer attempt.").check();
  await continueButton.click();
  await expect(page.locator(".mission-title-actions .badge")).toContainText("running");
  expect(actions[1]).toEqual({ action: "continue", body: { checkpoint_token: "c".repeat(64), accept_partial_edits: true } });
  expect(actions.some(a => a.action === "approve" || a.action === "apply")).toBe(false);
});

test("long follow-up briefs stay out of the header and remain fully inspectable", async ({ page }) => {
  const request = "Follow-up to miss-2c43d44a. Begin from the original repository. Original request: Build a terminal habit tracker.\nPrior user clarifications (re-evaluate against the repository):\n- Question: " + "Repository details and possible improvements. ".repeat(80) + "Answer: Use a simple terminal app.\nNew user instructions:\nSave history locally.";
  await backend(page, "RUNNING", request);
  await page.goto("/missions/miss-current/workspace");
  await expect(page.getByRole("heading", { name: "Build a terminal habit tracker.", exact: true })).toBeVisible();
  const header = await page.locator(".mission-titlebar").boundingBox();
  expect(header!.height).toBeLessThan(180);
  await expect(page.getByRole("dialog", { name: "Mission brief" })).not.toBeVisible();
  await expect(page.locator(".monaco-diff-editor")).toBeVisible();
  await page.screenshot({ path: "test-results/compact-mission-header.png", fullPage: true });
  await page.getByRole("button", { name: /Mission brief/ }).click();
  const brief = page.getByRole("dialog", { name: "Mission brief" });
  await expect(brief).toBeVisible();
  await brief.locator(".brief-exchange summary").click();
  await expect(brief.locator(".brief-answer")).toHaveText("Use a simple terminal app.");
  await brief.getByRole("button", { name: "Original text", exact: true }).click();
  expect(await brief.locator(".brief-full-text").textContent()).toBe(request);
  await page.keyboard.press("Escape");
  await expect(brief).not.toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
