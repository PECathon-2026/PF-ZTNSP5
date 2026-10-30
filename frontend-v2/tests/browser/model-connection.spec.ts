/** Input/validation fixtures only; no real keys or provider requests. */
import { expect, test } from "@playwright/test";

test("custom base URL and key must pass connection check; edits invalidate a stale result", async ({ page }) => {
  const probes: { api_key: string; base_url: string }[] = [];
  let finishProbe: (() => void) | undefined;
  await page.route("**/api/backend/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/backend", "");
    const json = (data: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    if (path === "/health") return json({ docker_available: true, model_configured: true, storage_ready: true });
    if (path === "/model-config") return json({ provider: "anthropic", model: "test-model", endpoint_configured: true });
    if (path === "/repositories/connect") return json({ repository_id: "repo-sample", name: "Sample", path: "D:/sample", preflight: { status: "READY", file_count: 2, warnings: [], blockers: [] } });
    if (path === "/model-config/validate") {
      const body = route.request().postDataJSON();
      probes.push(body);
      if (body.api_key === "wrong-test-key") return json({ detail: "Provider did not accept the API key, model or base URL; check its configuration." }, 400);
      await new Promise<void>(resolve => { finishProbe = resolve; });
      return json({ valid: true, provider: "anthropic", model: "test-model" });
    }
    return json({});
  });

  await page.goto("/missions/new");
  await page.getByLabel("01 / Repository").fill("D:/sample");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByLabel("02 / Your request").fill("Fix the helper");
  await page.getByLabel("Use my API key and base URL").check();
  const key = page.getByLabel("Your API key", { exact: true });
  const url = page.getByLabel(/Model base URL/);
  const create = page.getByRole("button", { name: "Create mission" });
  await key.fill("wrong-test-key");
  await url.fill("https://custom.example/v1");
  await page.getByRole("button", { name: "Test key and base URL" }).click();
  await expect(page.getByRole("alert")).toContainText("Provider did not accept");
  await expect(create).toBeDisabled();

  await key.fill("valid-test-key");
  await page.getByRole("button", { name: "Test key and base URL" }).click();
  await expect.poll(() => probes.length).toBe(2);
  await url.fill("https://changed.example/v1");
  finishProbe!();
  await expect(page.getByRole("button", { name: "Test key and base URL" })).toBeEnabled();
  await expect(create).toBeDisabled();

  await page.getByRole("button", { name: "Test key and base URL" }).click();
  await expect.poll(() => probes.length).toBe(3);
  finishProbe!();
  await expect(page.getByRole("status")).toContainText("connection verified");
  await expect(create).toBeEnabled();
  expect(probes.at(-1)).toEqual({ api_key: "valid-test-key", base_url: "https://changed.example/v1" });
  await key.fill("different-test-key");
  await expect(create).toBeDisabled();
});
