const { test, expect } = require("@playwright/test");
const { execFileSync } = require("child_process");

test("admin starts a background global scan and sees persisted progress", async ({ page }) => {
  const email = `scan.admin.${process.env.CUSTOMER_PROJECT_E2E_RUN_ID}@jinxiangsz.com`;
  execFileSync(
    "powershell",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/ensure-e2e-user.ps1", "-Email", email, "-Roles", "admin,pm"],
    { stdio: "inherit" },
  );
  await page.goto("/");
  await page.locator("#loginEmailInput").fill(email);
  await page.getByRole("button", { name: "发送验证码" }).click();
  await expect(page.locator("#loginCodeInput")).not.toHaveValue("");
  await page.getByRole("button", { name: "登录" }).click();

  await page.locator("#navAdminButton").click();
  const scanButton = page.locator("#globalScanButton");
  const scanStatus = page.locator("#globalScanStatus");
  await expect(scanButton).toBeVisible();
  await scanButton.click();

  await expect(scanStatus).toContainText("扫描完成", { timeout: 15_000 });
  await expect(scanButton).toBeEnabled();
  await page.reload();
  await page.locator("#navAdminButton").click();
  await expect(scanStatus).toContainText("扫描完成");
});
