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


test("LAN folder actions copy client paths without calling server Explorer endpoints", async ({ page, context }) => {
  const email = `lan.path.${process.env.CUSTOMER_PROJECT_E2E_RUN_ID}@jinxiangsz.com`;
  await login(page, email);
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(page.url()).origin });

  const token = await page.evaluate(() => localStorage.getItem("customerProject.authToken.v1"));
  const response = await page.request.post("/api/projects", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      customer_name: "LAN Path Customer",
      site_name: "Suzhou",
      project_group_name: "LAN Path Line",
      equipment_name: "LAN Path Fixture",
      project_name: "LAN Path Verification",
      project_nature: "夹具/治具",
      status_code: "inquiry",
      currency_code: "CNY",
      inquiry_date: "2026-07-15",
    },
  });
  expect(response.status()).toBe(201);
  const projectId = (await response.json()).id;
  const forbiddenRequests = [];
  page.on("request", (request) => {
    if (/open-(shared-)?folder/.test(request.url())) forbiddenRequests.push(request.url());
  });

  await page.getByRole("button", { name: "项目库", exact: true }).click();
  await page.locator(`.project-row[data-id="${projectId}"]`).click();
  const projectCopyButton = page.getByRole("button", { name: "复制项目路径" });
  await expect(projectCopyButton).toBeVisible();
  await expect(page.getByRole("button", { name: "复制共享路径" })).toBeVisible();
  await expect(page.getByRole("button", { name: "打开项目文件夹" })).toHaveCount(0);

  const expectedProjectPath = await projectCopyButton.getAttribute("data-path");
  await projectCopyButton.click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(expectedProjectPath);
  await expect(page.getByRole("status")).toContainText("粘贴到资源管理器地址栏");

  await page.goto(`/?view=workbench&project=${encodeURIComponent(projectId)}`);
  const workbenchCopyButton = page.getByRole("button", { name: "复制资料路径" });
  await expect(workbenchCopyButton).toBeVisible();
  await workbenchCopyButton.click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(expectedProjectPath);
  expect(forbiddenRequests).toEqual([]);
});
