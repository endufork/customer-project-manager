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
  await expect(page.getByRole("heading", { name: "项目管理系统" })).toBeVisible();
  await page.locator("#loginEmailInput").fill(email);
  await page.getByRole("button", { name: "发送验证码" }).click();
  await expect(page.locator("#loginCodeInput")).not.toHaveValue("");
  await page.getByRole("button", { name: "登录" }).click();
}

test("project board opens, filters, shows snapshot, and links to workbench", async ({ page }) => {
  await login(page, `board.viewer.one.${process.env.CUSTOMER_PROJECT_E2E_RUN_ID}@jinxiangsz.com`);

  await expect(page.getByRole("heading", { name: "项目看板" })).toBeVisible();
  await expect(page.locator("#boardKpis .board-kpi")).toHaveCount(6);
  await expect(page.getByRole("button", { name: "需要处理" })).toBeVisible();

  await page.getByRole("button", { name: "需要处理" }).click();
  await expect(page.locator("[data-board-filter='attention']")).toHaveClass(/active/);
  await page.getByRole("button", { name: "全部" }).click();

  const firstProject = page.locator("[data-board-project-id]").first();
  if (await firstProject.count()) {
    await firstProject.click();
    await expect(page.locator("#boardSnapshot")).toContainText("当前责任人");
    await expect(page.locator("#boardSnapshot")).toContainText("待处理摘要");
    await expect(page.locator("#boardSnapshot")).not.toContainText("最近日志");
    await page.getByRole("button", { name: "进入项目执行" }).click();
    await expect(page.getByRole("heading", { name: "项目执行" })).toBeVisible();
  }
});

test("project board risk overview shows cross-project risks", async ({ page }) => {
  await login(page, `board.viewer.two.${process.env.CUSTOMER_PROJECT_E2E_RUN_ID}@jinxiangsz.com`);

  await page.getByRole("button", { name: "风险总览" }).click();
  await expect(page.locator("#riskOverviewLayout")).toBeVisible();
  await expect(page.locator("#riskKpis .board-kpi")).toHaveCount(5);
  await expect(page.getByRole("button", { name: "高风险" }).first()).toBeVisible();

  await page.locator("[data-risk-filter='high']").click();
  await expect(page.locator("[data-risk-filter='high']")).toHaveClass(/active/);

  const firstRisk = page.locator("[data-risk-id]").first();
  if (await firstRisk.count()) {
    await firstRisk.click();
    await expect(page.locator("#riskSnapshot")).toContainText("影响范围");
    await expect(page.locator("#riskSnapshot")).toContainText("处理说明");
    await page.getByRole("button", { name: "进入项目执行" }).click();
    await expect(page.getByRole("heading", { name: "项目执行" })).toBeVisible();
  }
});
