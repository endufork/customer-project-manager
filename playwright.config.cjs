const { defineConfig, devices } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const RUN_ID = process.env.CUSTOMER_PROJECT_E2E_RUN_ID;
const TEST_ROOT = process.env.CUSTOMER_PROJECT_TEST_ROOT;
const PORT = process.env.CUSTOMER_PROJECT_PORT;
if (!RUN_ID || !TEST_ROOT || !PORT || process.env.CUSTOMER_PROJECT_ENV !== "test") {
  throw new Error("Run Playwright through npm run test:e2e so every worker shares one isolated test environment.");
}
const BASE_URL = `http://127.0.0.1:${PORT}`;

fs.mkdirSync(path.join(TEST_ROOT, "data"), { recursive: true });
fs.mkdirSync(path.join(TEST_ROOT, "projects"), { recursive: true });
fs.mkdirSync(path.join(TEST_ROOT, "logs"), { recursive: true });

Object.assign(process.env, {
  CUSTOMER_PROJECT_ENV: "test",
  CUSTOMER_PROJECT_PORT: PORT,
  CUSTOMER_PROJECT_DATA_DIR: process.env.CUSTOMER_PROJECT_DATA_DIR || path.join(TEST_ROOT, "data"),
  CUSTOMER_PROJECT_DB_PATH: process.env.CUSTOMER_PROJECT_DB_PATH || path.join(TEST_ROOT, "data", "customer_projects.db"),
  CUSTOMER_PROJECT_LOG_DIR: process.env.CUSTOMER_PROJECT_LOG_DIR || path.join(TEST_ROOT, "logs"),
});

module.exports = defineConfig({
  testDir: "./tests",
  timeout: 30 * 1000,
  expect: {
    timeout: 5 * 1000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: {
    command: "powershell -NoProfile -ExecutionPolicy Bypass -File tools/start-test-server.ps1",
    url: BASE_URL,
    reuseExistingServer: false,
    timeout: 30 * 1000,
  },
  projects: [
    {
      name: "chrome",
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
  ],
});
