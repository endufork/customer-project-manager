const { test, expect } = require("@playwright/test");
const { execFileSync } = require("child_process");


function ensureE2eUser(email, roles) {
  execFileSync(
    "powershell",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/ensure-e2e-user.ps1", "-Email", email, "-Roles", roles],
    { stdio: "inherit" },
  );
}


async function login(page, email, roles) {
  ensureE2eUser(email, roles);
  await page.goto("/");
  await page.locator("#loginEmailInput").fill(email);
  await page.getByRole("button", { name: "发送验证码" }).click();
  await expect(page.locator("#loginCodeInput")).not.toHaveValue("");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.locator("body")).toHaveClass(/authenticated/);
}


test("role-based home opens engineer tasks, PM inbox, and remembers multi-role page", async ({ page }) => {
  const runId = process.env.CUSTOMER_PROJECT_E2E_RUN_ID;

  await login(page, `home.engineer.${runId}@jinxiangsz.com`, "engineer");
  await expect(page.locator("#workbenchView")).toBeVisible();
  await expect(page.locator("#workbenchTasksModeButton")).toHaveClass(/active/);
  await page.getByRole("button", { name: "退出" }).click();

  await login(page, `home.pm.${runId}@jinxiangsz.com`, "pm");
  await expect(page.locator("#pmInboxView")).toBeVisible();
  await page.getByRole("button", { name: "退出" }).click();

  await login(page, `home.multi.${runId}@jinxiangsz.com`, "pm,engineer");
  await expect(page.locator("#pmInboxView")).toBeVisible();
  await page.getByRole("button", { name: "项目库", exact: true }).click();
  await expect(page.locator("#libraryView")).toBeVisible();
  await page.reload();
  await expect(page.locator("#libraryView")).toBeVisible();
});
