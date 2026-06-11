function renderRiskDialog(issues, tasks) {
  const openIssueCount = issues.filter((issue) => ["open", "following", "resolved"].includes(issue.status)).length;
  return `
    <dialog id="riskDialog" class="workbench-dialog risk-dialog">
      <div class="workbench-dialog-shell">
        <div class="workbench-dialog-header">
          <div>
            <h3>风险/异常</h3>
            <span class="subtext">${escapeHtml(openIssueCount)} 个未关闭 · ${escapeHtml(issues.length)} 条记录</span>
          </div>
          <button type="button" class="secondary slim-inline" data-action="close-risk-dialog">关闭</button>
        </div>
        ${renderIssuesPanel(issues, tasks)}
      </div>
    </dialog>
    ${renderIssueReviewDialog()}
  `;
}

function renderIssuesPanel(issues, tasks) {
  const activeIssues = issues.filter((issue) => ["open", "following"].includes(issue.status));
  const pendingReviews = issues.filter((issue) => issue.status === "resolved");
  const closedIssues = issues.filter((issue) => ["accepted", "closed"].includes(issue.status));
  return `
    <section class="workbench-panel risk-window-panel">
      <div class="workbench-section-title">
        <h3>创建风险</h3>
        <span>${escapeHtml(activeIssues.length + pendingReviews.length)} 个未关闭</span>
      </div>
      <p class="panel-hint">任务被标记阻塞时会自动生成任务级风险；这里主要用于新增产品/产线或设备级风险。</p>
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
        <h3>待处理风险</h3>
        <span>${escapeHtml(activeIssues.length)} 条</span>
      </div>
      <div class="issue-list">
        ${activeIssues.length ? activeIssues.map((issue) => renderIssueItem(issue, tasks)).join("") : `<div class="empty small-empty">暂无待处理风险</div>`}
      </div>
      <div class="workbench-section-title risk-list-title">
        <h3>待PM确认关闭</h3>
        <span>${escapeHtml(pendingReviews.length)} 条</span>
      </div>
      <div class="issue-list">
        ${pendingReviews.length ? pendingReviews.map((issue) => renderIssueItem(issue, tasks)).join("") : `<div class="empty small-empty">暂无待确认风险</div>`}
      </div>
      <div class="workbench-section-title risk-list-title">
        <h3>已关闭/已接受</h3>
        <span>${escapeHtml(closedIssues.length)} 条</span>
      </div>
      <div class="issue-list">
        ${closedIssues.length ? closedIssues.map((issue) => renderIssueItem(issue, tasks)).join("") : `<div class="empty small-empty">暂无关闭记录</div>`}
      </div>
    </section>
  `;
}

function renderIssueItem(issue, tasks) {
  const linkedTask = taskTitleById(tasks, issue.task_id);
  const scope = issue.scope || (issue.task_id ? "task" : "equipment");
  const scopeName = workbenchIssueScopeName(scope);
  const canManageIssue = userHasRole("pm");
  const canResolveIssue = userHasRole("engineer", "pm") && ["open", "following"].includes(issue.status);
  const canReviewIssue = userHasRole("pm") && issue.status === "resolved";
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
          ${canResolveIssue ? `<button type="button" class="secondary slim-inline" data-action="resolve-issue" data-issue-id="${escapeHtml(issue.id)}" data-issue-title="${escapeHtml(issue.title)}" data-task-id="${escapeHtml(issue.task_id || "")}">提交解决</button>` : ""}
          ${canReviewIssue ? `
            <button type="button" class="secondary slim-inline" data-action="close-issue" data-issue-id="${escapeHtml(issue.id)}" data-issue-title="${escapeHtml(issue.title)}" data-task-id="${escapeHtml(issue.task_id || "")}">确认关闭</button>
            <button type="button" class="secondary slim-inline" data-action="accept-issue" data-issue-id="${escapeHtml(issue.id)}" data-issue-title="${escapeHtml(issue.title)}" data-task-id="${escapeHtml(issue.task_id || "")}">接受风险</button>
            <button type="button" class="danger slim-inline" data-action="reopen-issue" data-issue-id="${escapeHtml(issue.id)}" data-issue-title="${escapeHtml(issue.title)}" data-task-id="${escapeHtml(issue.task_id || "")}">退回跟进</button>
          ` : ""}
          ${canManageIssue ? `<button type="button" class="danger slim-inline" data-action="delete-issue" data-issue-id="${escapeHtml(issue.id)}">删除</button>` : ""}
        </div>
      </div>
      ${canManageIssue ? `<details class="issue-edit-panel">
        <summary>编辑基础信息</summary>
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

function renderInboxRiskReviewsSection(issues) {
  return `
    <div class="workbench-section-title inbox-section-title">
      <h3>待确认风险关闭</h3>
      <span>${escapeHtml(issues.length)} 个</span>
    </div>
    <div class="my-task-list inbox-deliverable-list">
      ${issues.length ? issues.map((issue) => renderInboxRiskReviewCard(issue)).join("") : `<div class="empty small-empty">暂无待确认风险</div>`}
    </div>
  `;
}

function renderInboxRiskReviewCard(issue) {
  const projectName = issue.equipment_name || issue.project_name || "";
  const customerLine = [
    issue.customer_name || "",
    issue.site_name || "",
    issue.project_group_name || "",
  ].filter(Boolean).join(" · ");
  const projectMeta = [
    issue.current_number || issue.intake_no || "",
    workbenchIssueScopeName(issue.scope || (issue.task_id ? "task" : "equipment")),
    issue.task_title || "",
  ].filter(Boolean).join(" · ");
  return `
    <article class="my-task-card submitted" data-issue-id="${escapeHtml(issue.id)}">
      <div class="my-task-main">
        <div>
          <strong>${escapeHtml(issue.title || "风险待确认")}</strong>
          <span class="subtext">${escapeHtml(projectMeta)}</span>
          <span class="subtext">${escapeHtml(customerLine)}${projectName ? ` · ${escapeHtml(projectName)}` : ""}</span>
        </div>
        <div class="my-task-status">
          <span class="tag ${issue.severity === "high" ? "danger" : issue.severity === "medium" ? "warn" : "neutral"}">${escapeHtml(workbenchSeverityName(issue.severity))}</span>
          <span class="task-status submitted">待PM确认</span>
        </div>
      </div>
      ${issue.resolution ? `<p class="my-task-note">${escapeHtml(issue.resolution)}</p>` : ""}
      <div class="my-task-foot">
        <span class="inline-actions">
          <button type="button" class="secondary slim-inline" data-action="open-inbox-project" data-project-id="${escapeHtml(issue.project_id)}">打开项目</button>
          <button type="button" class="secondary slim-inline" data-action="close-inbox-issue" data-issue-id="${escapeHtml(issue.id)}" data-issue-title="${escapeHtml(issue.title || "风险待确认")}" data-task-id="${escapeHtml(issue.task_id || "")}">确认关闭</button>
          <button type="button" class="secondary slim-inline" data-action="accept-inbox-issue" data-issue-id="${escapeHtml(issue.id)}" data-issue-title="${escapeHtml(issue.title || "风险待确认")}" data-task-id="${escapeHtml(issue.task_id || "")}">接受风险</button>
          <button type="button" class="danger slim-inline" data-action="reopen-inbox-issue" data-issue-id="${escapeHtml(issue.id)}" data-issue-title="${escapeHtml(issue.title || "风险待确认")}" data-task-id="${escapeHtml(issue.task_id || "")}">退回</button>
        </span>
      </div>
    </article>
  `;
}

function renderIssueReviewDialog() {
  return `
    <dialog id="issueReviewDialog" class="workbench-dialog issue-review-dialog">
      <div class="workbench-dialog-shell">
        <div class="workbench-dialog-header">
          <div>
            <h3 id="issueReviewTitle">处理风险</h3>
            <span id="issueReviewMeta" class="subtext">风险关闭后会同步任务状态。</span>
          </div>
          <button type="button" class="secondary slim-inline" data-action="close-issue-review">关闭</button>
        </div>
        <form id="issueReviewForm" class="workbench-panel deliverable-review-form">
          <input name="issue_id" type="hidden" />
          <input name="status" type="hidden" />
          <p id="issueReviewHint" class="deliverable-review-hint">提交解决说明后，PM会在我的待办里确认关闭或退回继续跟进。</p>
          <label id="issueResolutionLabel">
            解决/处理说明
            <textarea name="resolution" rows="3" placeholder="例如客户已补充3D数据，已完成验证；或物料延期已协调新到货日期"></textarea>
          </label>
          <label id="issueReviewNoteLabel" hidden>
            PM处理意见
            <textarea name="review_note" rows="3" placeholder="例如确认关闭、接受残余风险、说明还需要继续跟进的原因"></textarea>
          </label>
          <label id="issueTaskNextStatusLabel" hidden>
            关联任务下一状态
            <select name="task_next_status">
              <option value="in_progress">恢复进行中</option>
              <option value="waiting_info">仍等待资料</option>
              <option value="rework">需要返工</option>
              <option value="not_started">回到未开始</option>
            </select>
          </label>
          <div class="form-actions right">
            <button type="button" class="secondary slim-inline" data-action="close-issue-review">取消</button>
            <button id="issueReviewSubmitButton" type="submit" class="secondary compact-submit">提交</button>
          </div>
        </form>
      </div>
    </dialog>
  `;
}

function openIssueReviewDialog(button, status) {
  const dialog = $("#issueReviewDialog");
  const form = $("#issueReviewForm");
  if (!dialog || !form) return false;
  const issueId = requireDataset(button, "issueId", "风险ID");
  const issueTitle = button.dataset.issueTitle || "风险";
  const hasTask = Boolean(button.dataset.taskId);
  const isResolve = status === "resolved";
  const isReopen = status === "following";
  form.reset();
  form.dataset.issueId = issueId;
  form.elements.issue_id.value = issueId;
  form.elements.status.value = status;
  $("#issueReviewTitle").textContent = isResolve ? "提交风险解决" : isReopen ? "退回继续跟进" : status === "accepted" ? "接受残余风险" : "确认关闭风险";
  $("#issueReviewMeta").textContent = issueTitle;
  $("#issueReviewHint").textContent = isResolve
    ? "提交后风险进入PM待确认；如果关联了阻塞任务，任务仍保持阻塞，直到PM处理。"
    : isReopen
      ? "退回后风险继续跟进；如果有关联任务，任务会保持或回到阻塞。"
      : "确认后风险关闭；如果有关联阻塞任务，需要选择任务恢复到哪个状态。";
  $("#issueResolutionLabel").hidden = !isResolve;
  form.elements.resolution.required = isResolve;
  $("#issueReviewNoteLabel").hidden = isResolve;
  form.elements.review_note.required = isReopen;
  $("#issueTaskNextStatusLabel").hidden = isResolve || isReopen || !hasTask;
  $("#issueReviewSubmitButton").textContent = isResolve ? "提交解决" : isReopen ? "退回跟进" : status === "accepted" ? "接受风险" : "确认关闭";
  $("#issueReviewSubmitButton").classList.toggle("danger", isReopen);
  openWorkbenchDialog("#issueReviewDialog");
  return true;
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
  closeDialogOnBackdrop(workspace.querySelector("#issueReviewDialog"));
  workspace.querySelectorAll("[data-action='close-issue-review']").forEach((button) => {
    button.addEventListener("click", () => closeWorkbenchDialog("#issueReviewDialog"));
  });
  const form = workspace.querySelector("#issueReviewForm");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    if (button) button.disabled = true;
    try {
      const issueId = form.dataset.issueId || form.elements.issue_id.value || "";
      if (!issueId) throw new Error("风险ID缺失，请刷新页面后重试");
      const status = form.elements.status.value;
      const body = { status };
      if (status === "resolved") {
        const resolution = form.elements.resolution.value.trim();
        if (!resolution) {
          showToast("提交风险解决需要填写说明");
          return;
        }
        body.resolution = resolution;
      } else {
        body.review_note = form.elements.review_note.value.trim();
        if (form.elements.task_next_status && !$("#issueTaskNextStatusLabel").hidden) {
          body.task_next_status = form.elements.task_next_status.value;
        }
      }
      const result = await api(`/api/workbench/issues/${encodeURIComponent(issueId)}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      closeWorkbenchDialog("#issueReviewDialog");
      showToast(status === "resolved" ? "风险解决已提交，等待PM确认" : status === "following" ? "风险已退回继续跟进" : "风险已处理");
      if (state.workbenchMode === "tasks") {
        await loadWorkbenchTasks();
      } else {
        await loadWorkbenchProjects(result.project_id || state.workbenchProjectId);
      }
    } catch (error) {
      showToast(error.message);
    } finally {
      if (button) button.disabled = false;
    }
  });
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
  if (action === "resolve-issue") {
    openIssueReviewDialog(button, "resolved");
    return true;
  }
  if (action === "close-issue") {
    openIssueReviewDialog(button, "closed");
    return true;
  }
  if (action === "close-inbox-issue") {
    openIssueReviewDialog(button, "closed");
    return true;
  }
  if (action === "accept-issue") {
    openIssueReviewDialog(button, "accepted");
    return true;
  }
  if (action === "accept-inbox-issue") {
    openIssueReviewDialog(button, "accepted");
    return true;
  }
  if (action === "reopen-issue") {
    openIssueReviewDialog(button, "following");
    return true;
  }
  if (action === "reopen-inbox-issue") {
    openIssueReviewDialog(button, "following");
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
