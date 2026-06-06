function renderRiskDialog(issues, tasks) {
  const openIssueCount = issues.filter((issue) => ["open", "following"].includes(issue.status)).length;
  return `
    <dialog id="riskDialog" class="workbench-dialog risk-dialog">
      <div class="workbench-dialog-shell">
        <div class="workbench-dialog-header">
          <div>
            <h3>风险/异常</h3>
            <span class="subtext">${escapeHtml(openIssueCount)} 个打开 · ${escapeHtml(issues.length)} 条记录</span>
          </div>
          <button type="button" class="secondary slim-inline" data-action="close-risk-dialog">关闭</button>
        </div>
        ${renderIssuesPanel(issues, tasks)}
      </div>
    </dialog>
  `;
}

function renderIssuesPanel(issues, tasks) {
  const openIssueCount = issues.filter((issue) => ["open", "following"].includes(issue.status)).length;
  return `
    <section class="workbench-panel risk-window-panel">
      <div class="workbench-section-title">
        <h3>创建风险</h3>
        <span>${escapeHtml(openIssueCount)} 个打开</span>
      </div>
      <p class="panel-hint">产品/产线风险会在同一产品下所有设备显示；设备风险只影响当前项目；任务风险必须关联具体任务。</p>
      <form id="workbenchIssueForm" class="issue-create-form">
        <input name="title" placeholder="新增风险/问题" required />
        <select name="scope">
          ${optionItems(state.bootstrap?.workbench_issue_scopes || [], "equipment")}
        </select>
        <select name="task_id">
          <option value="">关联任务，仅任务级必填</option>
          ${renderTaskSelectOptions(tasks)}
        </select>
        <select name="issue_type">
          <option value="">类型</option>
          ${stringOptions(state.bootstrap?.workbench_issue_types || [])}
        </select>
        <select name="source">
          <option value="">来源</option>
          ${stringOptions(state.bootstrap?.workbench_issue_sources || [])}
        </select>
        <select name="severity">${optionItems(state.bootstrap?.workbench_issue_severities || [], "medium")}</select>
        <input name="owner_name" placeholder="负责人" value="${escapeHtml($("#workbenchOwnerInput").value.trim())}" />
        <input name="due_date" type="date" />
        <button type="submit" class="secondary compact-submit">+ 风险</button>
      </form>
      <div class="workbench-section-title risk-list-title">
        <h3>当前风险列表</h3>
        <span>${escapeHtml(issues.length)} 条</span>
      </div>
      <div class="issue-list">
        ${issues.length ? issues.map((issue) => renderIssueItem(issue, tasks)).join("") : `<div class="empty small-empty">暂无风险/问题</div>`}
      </div>
    </section>
  `;
}

function renderIssueItem(issue, tasks) {
  const linkedTask = taskTitleById(tasks, issue.task_id);
  const scope = issue.scope || (issue.task_id ? "task" : "equipment");
  const scopeName = workbenchIssueScopeName(scope);
  const canManageIssue = userHasRole("pm");
  const linkText = scope === "task"
    ? `任务：${linkedTask || "未关联"}`
    : scope === "product"
      ? "影响产品/产线"
      : `设备：${issue.issue_project_name || "当前设备"}`;
  const due = issue.due_date || "未设置Due Date";
  return `
    <form class="issue-item ${escapeHtml(issue.severity || "")}" data-issue-id="${escapeHtml(issue.id)}">
      <div class="issue-readable">
        <div class="issue-readable-main">
          <strong>${escapeHtml(issue.title)}</strong>
          <span class="subtext">${escapeHtml(scopeName)} · ${escapeHtml(issue.issue_type || "未分类")} · ${escapeHtml(issue.source || "来源未填")} · ${escapeHtml(issue.owner_name || "未指派")} · <span class="${dueClass(issue.due_date || "")}">${escapeHtml(due)}</span></span>
          <span class="subtext">${escapeHtml(linkText)}</span>
        </div>
        <div class="task-actions">
          <span class="tag ${issue.severity === "high" ? "danger" : issue.severity === "medium" ? "warn" : "neutral"}">${escapeHtml(workbenchSeverityName(issue.severity))} · ${escapeHtml(workbenchIssueStatusName(issue.status))}</span>
          ${canManageIssue ? `<button type="button" class="danger slim-inline" data-action="delete-issue" data-issue-id="${escapeHtml(issue.id)}">删除</button>` : ""}
        </div>
      </div>
      ${canManageIssue ? `<details class="issue-edit-panel">
        <summary>编辑风险 / 处理记录</summary>
        <div class="issue-edit-grid">
          <input name="title" value="${escapeHtml(issue.title)}" />
          <select name="scope">${optionItems(state.bootstrap?.workbench_issue_scopes || [], scope)}</select>
          <select name="task_id">
            <option value="">关联任务，仅任务级必填</option>
            ${renderTaskSelectOptions(tasks, issue.task_id || "")}
          </select>
          <select name="issue_type">
            <option value="">类型</option>
            ${stringOptions(state.bootstrap?.workbench_issue_types || [], issue.issue_type || "")}
          </select>
          <select name="source">
            <option value="">来源</option>
            ${stringOptions(state.bootstrap?.workbench_issue_sources || [], issue.source || "")}
          </select>
          <select name="severity">${optionItems(state.bootstrap?.workbench_issue_severities || [], issue.severity)}</select>
          <select name="status">${optionItems(state.bootstrap?.workbench_issue_statuses || [], issue.status)}</select>
          <input name="owner_name" value="${escapeHtml(issue.owner_name || "")}" placeholder="负责人" />
          <input name="due_date" type="date" value="${escapeHtml(issue.due_date || "")}" />
          <input name="resolution" value="${escapeHtml(issue.resolution || "")}" placeholder="处理记录" />
          <div class="task-actions">
            <button type="button" class="secondary slim-inline" data-action="save-issue" data-issue-id="${escapeHtml(issue.id)}">保存</button>
          </div>
        </div>
      </details>` : ""}
    </form>
  `;
}

function bindRiskCreation(projectId) {
  const issueForm = $("#workbenchIssueForm");
  if (!issueForm) return;
  issueForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    if (button) button.disabled = true;
    try {
      await api(`/api/workbench/projects/${encodeURIComponent(projectId)}/issues`, {
        method: "POST",
        body: JSON.stringify(formToPayload(issueForm)),
      });
      showToast("风险/问题已添加");
      await loadWorkbenchProjects(projectId);
    } catch (error) {
      showToast(error.message);
    } finally {
      if (button) button.disabled = false;
    }
  });
}

function bindRiskDialog(workspace) {
  closeDialogOnBackdrop(workspace.querySelector("#riskDialog"));
}

async function handleIssueAction(action, button, projectId) {
  if (action === "open-risk-dialog") {
    openWorkbenchDialog("#riskDialog");
    return true;
  }
  if (action === "close-risk-dialog") {
    closeWorkbenchDialog("#riskDialog");
    return true;
  }
  if (action === "save-issue") {
    const form = button.closest(".issue-item");
    const issueId = requireDataset(button, "issueId", "风险ID");
    await api(`/api/workbench/issues/${encodeURIComponent(issueId)}`, {
      method: "PATCH",
      body: JSON.stringify(formDataFromContainer(form)),
    });
    showToast("风险/问题已保存");
    await loadWorkbenchProjects(projectId);
    return true;
  }
  if (action === "delete-issue") {
    if (!confirm("确定删除这个风险/问题吗？")) return true;
    const issueId = requireDataset(button, "issueId", "风险ID");
    await api(`/api/workbench/issues/${encodeURIComponent(issueId)}`, { method: "DELETE", body: "{}" });
    showToast("风险/问题已删除");
    await loadWorkbenchProjects(projectId);
    return true;
  }
  return false;
}
