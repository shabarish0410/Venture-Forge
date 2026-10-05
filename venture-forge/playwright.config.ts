import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/browser",
  workers: 1,
  timeout: 60000,
  outputDir: ".local/browser-results",
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3001",
    browserName: "chromium",
    channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
    viewport: { width: 1440, height: 1080 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `${process.platform === "win32" ? ".venv\\Scripts\\python.exe" : "python"} scripts/browser_test_server.py`,
      url: "http://127.0.0.1:8011/api/v1/health",
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: "npm exec --workspace @venture-forge/web -- next dev --hostname 127.0.0.1 --port 3001",
      env: { FORGE_API_URL: "http://127.0.0.1:8011", FORGE_DIST_DIR: ".next-test" },
      url: "http://127.0.0.1:3001",
      reuseExistingServer: false,
      timeout: 90000,
    },
  ],
});
