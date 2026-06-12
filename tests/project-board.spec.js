const { test, expect } = require("@playwright/test");

async function login(page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "项目管理系统" })).toBeVisible();
  await page.locator("#loginEmailInput").fill("board.viewer@jinxiangsz.com");
  await page.getByRole("button", { name: "发送验证码" }).click();
  await expect(page.locator("#loginCodeInput")).not.toHaveValue("");
  await page.getByRole("button", { name: "登录" }).click();
}

test("project board opens, filters, shows snapshot, and links to workbench", async ({ page }) => {
  await login(page);

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
    await expect(page.locator("#boardSnapshot")).toContainText("最近日志");
    await page.getByRole("button", { name: "进入项目执行" }).click();
    await expect(page.getByRole("heading", { name: "项目执行" })).toBeVisible();
  }
});
