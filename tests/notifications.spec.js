const { test, expect } = require("@playwright/test");
const { execFileSync } = require("child_process");


function ensureE2eUser(email) {
  execFileSync(
    "powershell",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/ensure-e2e-user.ps1", "-Email", email, "-Roles", "pm,engineer"],
    { stdio: "inherit" },
  );
}


async function login(page, email) {
  ensureE2eUser(email);
  await page.goto("/");
  await page.locator("#loginEmailInput").fill(email);
  await page.getByRole("button", { name: "发送验证码" }).click();
  await expect(page.locator("#loginCodeInput")).not.toHaveValue("");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.locator("body")).toHaveClass(/authenticated/);
}


test("notification dialog shows unread workflow items and marks them read", async ({ page }) => {
  const email = `notification.ui.${process.env.CUSTOMER_PROJECT_E2E_RUN_ID}@jinxiangsz.com`;
  await login(page, email);
  const token = await page.evaluate(() => localStorage.getItem("customerProject.authToken.v1"));
  const auth = { Authorization: `Bearer ${token}` };
  const me = await page.request.get("/api/auth/me", { headers: auth });
  const user = (await me.json()).user;
  const projectResponse = await page.request.post("/api/projects", {
    headers: auth,
    data: {
      customer_name: "Notification UI Customer",
      site_name: "Suzhou",
      equipment_name: "Notification UI Fixture",
      project_name: "Notification UI Verification",
      project_nature: "夹具/治具",
      status_code: "inquiry",
      currency_code: "CNY",
      inquiry_date: "2026-07-15",
    },
  });
  expect(projectResponse.status()).toBe(201);
  const projectId = (await projectResponse.json()).id;
  const taskResponse = await page.request.post(`/api/workbench/projects/${projectId}/tasks`, {
    headers: auth,
    data: { title: "UI notification task", owner_user_id: user.id, requires_deliverable: 0 },
  });
  expect(taskResponse.status()).toBe(201);

  await page.getByRole("button", { name: /^通知/ }).click();
  await expect(page.getByRole("heading", { name: "系统通知" })).toBeVisible();
  await expect(page.locator("#notificationUnreadBadge")).toHaveText("1");
  await expect(page.locator("#notificationList")).toContainText("UI notification task");
  await page.getByRole("button", { name: "标记已读" }).click();
  await expect(page.locator("#notificationUnreadBadge")).toBeHidden();
  await page.getByRole("button", { name: "打开项目执行" }).click();
  await expect(page.locator("#workbenchView")).toBeVisible();
  await expect(page.locator("#workbenchWorkspace")).toContainText("UI notification task");
});
