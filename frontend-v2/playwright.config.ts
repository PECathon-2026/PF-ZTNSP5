import { defineConfig } from "@playwright/test";

const existingServer = process.env.KAGE_TEST_BASE_URL;

export default defineConfig({
  testDir: "./tests/browser",
  outputDir: "test-results/browser",
  timeout: 45000,
  fullyParallel: false,
  workers: 1,
  use: { baseURL: existingServer || "http://127.0.0.1:3101", channel: "chrome", viewport: { width: 1440, height: 1000 }, screenshot: "only-on-failure", trace: "retain-on-failure" },
  webServer: existingServer ? undefined : { command: "npx next dev --hostname 127.0.0.1 --port 3101", url: "http://127.0.0.1:3101", reuseExistingServer: !process.env.CI, timeout: 120000 },
});
