const { defineConfig, devices } = require("@playwright/test");

const PORT = process.env.CUSTOMER_PROJECT_PORT || "8765";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PORT}`;

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
    reuseExistingServer: true,
    timeout: 30 * 1000,
  },
  projects: [
    {
      name: "chrome",
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
  ],
});
