const { test, expect } = require("@playwright/test");

test("workbench action windows open from the task action row", async ({ page }) => {
  await page.goto("/?view=workbench");

  await expect(page.getByRole("heading", { name: "项目执行" })).toBeVisible();
  await expect(page.locator("#workbenchWorkspace")).toContainText(/任务|暂无匹配的执行项目/);

  const taskButton = page.getByRole("button", { name: /新增任务/ });
  await expect(taskButton).toBeVisible();
  await taskButton.click();

  const taskDialog = page.locator("#taskDialog");
  await expect(taskDialog).toBeVisible();
  await expect(taskDialog.getByRole("heading", { name: "新增任务" })).toBeVisible();
  await expect(taskDialog.getByRole("heading", { name: "手动新增" })).toBeVisible();
  await expect(taskDialog.getByRole("heading", { name: "从模板选择添加" })).toBeVisible();
  await expect(taskDialog.locator(".template-checklist:not([hidden])")).toHaveCount(0);
  await taskDialog.locator("#taskTemplateSelect").selectOption("inq");
  await expect(taskDialog.getByText("澄清客户需求")).toBeVisible();
  const firstTemplateCheckbox = taskDialog.locator(".template-checklist:not([hidden]) input[type='checkbox']").first();
  const checkboxBox = await firstTemplateCheckbox.boundingBox();
  expect(checkboxBox.width).toBeLessThanOrEqual(20);
  expect(checkboxBox.height).toBeLessThanOrEqual(20);
  const firstTemplateDueDate = taskDialog.locator(".template-checklist:not([hidden]) input[type='date']").first();
  await expect(firstTemplateDueDate).toBeVisible();
  await firstTemplateDueDate.fill("2026-06-20");
  await expect(firstTemplateDueDate).toHaveValue("2026-06-20");
  await taskDialog.locator("#taskTemplateSelect").selectOption("wo");
  const visibleTemplateItems = taskDialog.locator(".template-checklist:not([hidden]) .template-task-row");
  await expect(visibleTemplateItems.filter({ hasText: "机械设计" })).toBeVisible();
  await taskDialog.getByRole("button", { name: "关闭" }).click();
  await expect(taskDialog).not.toBeVisible();

  const riskButton = page.getByRole("button", { name: /风险\/异常/ });
  await expect(riskButton).toBeVisible();
  await riskButton.click();

  const dialog = page.locator("#riskDialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "风险/异常" })).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "创建风险" })).toBeVisible();
  await expect(dialog.locator("select[name='scope']")).toBeVisible();
  await expect(dialog.locator("select[name='scope']")).toContainText("产品/产线");
  await expect(dialog.locator("select[name='scope']")).toContainText("当前设备");
  await expect(dialog.locator("select[name='scope']")).toContainText("具体任务");
  await expect(dialog.getByRole("heading", { name: "当前风险列表" })).toBeVisible();

  await dialog.getByRole("button", { name: "关闭" }).click();
  await expect(dialog).not.toBeVisible();

  const logButton = page.getByRole("button", { name: /执行日志/ });
  await expect(logButton).toBeVisible();
  await logButton.click();

  const logDrawer = page.locator("#logDrawer");
  await expect(logDrawer).toBeVisible();
  await expect(logDrawer.getByRole("heading", { name: "执行日志" })).toBeVisible();
  await logDrawer.getByRole("button", { name: "关闭" }).click();
  await expect(logDrawer).not.toBeVisible();

  await page.getByRole("button", { name: "我的任务" }).click();
  await expect(page.locator("#workbenchWorkspace")).toContainText("请输入负责人后查看我的任务");
  await expect(page.locator("#workbenchKpiTotalLabel")).toHaveText("我的任务");
  await expect(page.locator("#workbenchView")).toHaveClass(/workbench-task-mode/);
});
