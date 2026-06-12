const { test, expect } = require("@playwright/test");

test("workbench action windows open from the task action row", async ({ page }) => {
  await page.goto("/?view=workbench");
  await expect(page.getByRole("heading", { name: "项目管理系统" })).toBeVisible();
  await page.locator("#loginEmailInput").fill("rongkai@jinxiangsz.com");
  await page.getByRole("button", { name: "发送验证码" }).click();
  await expect(page.locator("#authStatus")).toContainText(/验证码/);
  await expect(page.locator("#loginCodeInput")).not.toHaveValue("");
  await page.getByRole("button", { name: "登录" }).click();

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
  const riskScopeSelect = dialog.locator("#workbenchIssueForm select[name='scope']");
  await expect(riskScopeSelect).toBeVisible();
  await expect(riskScopeSelect).toContainText("产品/产线");
  await expect(riskScopeSelect).toContainText("当前设备");
  await expect(riskScopeSelect).toContainText("具体任务");
  await expect(dialog.getByRole("heading", { name: "待处理风险" })).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "待PM确认关闭" })).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "已关闭/已接受" })).toBeVisible();

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

  const dueDateButton = page.getByRole("button", { name: /修改Due Date|申请改期|查看改期/ }).first();
  if (await dueDateButton.count()) {
    await expect(dueDateButton).toBeVisible();
    await dueDateButton.click();
    const dueDateDialog = page.locator(".due-date-dialog:visible");
    await expect(dueDateDialog).toBeVisible();
    await expect(dueDateDialog.getByRole("heading", { name: /修改Due Date|申请改期/ })).toBeVisible();
    await expect(dueDateDialog.locator("textarea[name='reason']")).toBeVisible();
    await dueDateDialog.getByRole("button", { name: "关闭" }).click();
    await expect(dueDateDialog).not.toBeVisible();
  }

  await page.getByRole("button", { name: "我的待办" }).click();
  await expect(page.locator("#workbenchKpiTotalLabel")).toHaveText("我的待办");
  await expect(page.locator("#workbenchView")).toHaveClass(/workbench-task-mode/);
  await expect(page.locator("#workbenchRoleSelect")).toBeDisabled();
  await expect(page.locator("#workbenchWorkspace")).toContainText("待确认文件");
  await expect(page.locator("#workbenchKpiSubmittedLabel")).toHaveText("待处理审批");
  await expect(page.locator("#workbenchWorkspace")).toContainText("待审批改期");

  await page.goto("/");
  await page.getByRole("button", { name: "PM待处理" }).click();
  await expect(page.getByRole("heading", { name: "PM待处理" })).toBeVisible();
  await expect(page.locator("#pmInboxKpis")).toContainText("全部");
  await expect(page.locator("#pmInboxKpis")).toContainText("改期申请");
  await expect(page.locator("#pmInboxList")).toBeVisible();
  await expect(page.locator("#pmInboxPanel")).toBeVisible();
  await page.getByRole("button", { name: "项目执行" }).click();

  const inboxConfirmDeliverable = page.locator("[data-action='confirm-inbox-deliverable']").first();
  if (await inboxConfirmDeliverable.count()) {
    await inboxConfirmDeliverable.click();
    const reviewDialog = page.locator("#deliverableReviewDialog");
    await expect(reviewDialog).toBeVisible();
    await expect(reviewDialog.getByRole("heading", { name: "确认交付物" })).toBeVisible();
    await expect(reviewDialog).toContainText("工程师上传");
    await expect(reviewDialog).toContainText("归档资料库");
    await expect(reviewDialog).toContainText("PM确认");
    await expect(reviewDialog).toContainText("关闭/返工");
    await expect(reviewDialog).toContainText("确认后任务会关闭");
    await reviewDialog.getByRole("button", { name: "关闭" }).click();
    await expect(reviewDialog).not.toBeVisible();
  }

  const inboxRejectDeliverable = page.locator("[data-action='reject-inbox-deliverable']").first();
  if (await inboxRejectDeliverable.count()) {
    await inboxRejectDeliverable.click();
    const reviewDialog = page.locator("#deliverableReviewDialog");
    await expect(reviewDialog).toBeVisible();
    await expect(reviewDialog.getByRole("heading", { name: "驳回交付物" })).toBeVisible();
    await expect(reviewDialog.locator("textarea[name='reject_reason']")).toBeVisible();
    await expect(reviewDialog.locator("textarea[name='reject_reason']")).toBeRequired();
    await reviewDialog.getByRole("button", { name: "关闭" }).click();
    await expect(reviewDialog).not.toBeVisible();
  }
});
