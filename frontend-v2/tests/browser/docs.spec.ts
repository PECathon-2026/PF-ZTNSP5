import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("docs work without a backend, search content, and navigate to anchored sections", async ({ page }) => {
  await page.route("**/api/backend/**", route => route.abort());
  await page.goto("/docs");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Keep the final word.");
  const search = page.getByRole("searchbox", { name: "Find an answer" });
  await search.fill("Docker unavailable");
  await expect(page.locator("#troubleshooting")).toBeVisible();
  await page.getByText("Docker unavailable / baseline checks blocked", { exact: true }).click();
  await expect(page.locator("#troubleshooting details[open]")).toContainText("no host-execution fallback");
  await search.fill("nothing-matches-this-phrase");
  await expect(page.getByRole("heading", { name: "No matching section." })).toBeVisible();
  await page.getByRole("button", { name: "Show all documentation" }).click();
  await page.getByRole("navigation", { name: "Documentation sections" }).getByRole("link", { name: "License & credits" }).click();
  await expect(page).toHaveURL(/#license$/);
  await expect(page.locator("#license")).toBeInViewport();
  await page.goto("/docs");
  await page.screenshot({ path: test.info().outputPath("docs-desktop.png"), fullPage: false });
});

test("setup commands copy and license download matches the actual repository license", async ({ page, context, request }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/docs#quick-start");
  await page.getByRole("button", { name: "Copy 3 / Frontend terminal · from the project root", exact: true }).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain("npm run dev");
  const response = await request.get("/license");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-disposition"]).toContain("attachment");
  const rootLicense = await readFile(new URL("../../../LICENSE", import.meta.url), "utf8");
  expect((await response.text()).replace(/\r\n/g, "\n").trim()).toBe(rootLicense.replace(/\r\n/g, "\n").trim());
});

test("mobile docs remain readable with keyboard navigation and no page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/docs");
  await expect(page.getByRole("searchbox", { name: "Find an answer" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.getByRole("searchbox", { name: "Find an answer" }).focus();
  await page.keyboard.type("API key");
  await expect(page.locator("#api-keys")).toBeVisible();
  await page.getByRole("button", { name: "Clear documentation search" }).click();
  await page.screenshot({ path: test.info().outputPath("docs-mobile.png"), fullPage: false });
});
