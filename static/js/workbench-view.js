function renderWorkbenchMode() {
  const isTaskMode = state.workbenchMode === "tasks";
  const role = workbenchRole();
  $("#workbenchView").classList.toggle("workbench-task-mode", isTaskMode);
  $("#workbenchProjectsModeButton").classList.toggle("active", !isTaskMode);
  $("#workbenchTasksModeButton").classList.toggle("active", isTaskMode);
  $("#workbenchKpiTotalLabel").textContent = isTaskMode ? "我的待办" : "执行项目";
  $("#workbenchKpiBlockedLabel").textContent = isTaskMode ? "阻塞/待资料" : "阻塞/风险";
  $("#workbenchKpiSubmittedLabel").textContent = isTaskMode && role === "pm" ? "待处理审批" : isTaskMode ? "已提交" : "待PM确认";
}

async function loadWorkbench(selectProjectId = state.workbenchProjectId) {
  if (state.workbenchMode === "tasks") {
    await loadWorkbenchTasks();
    return;
  }
  await loadWorkbenchProjects(selectProjectId);
}

function workbenchQueryParams() {
  const params = new URLSearchParams();
  const search = $("#workbenchSearchInput").value.trim();
  const owner = $("#workbenchOwnerInput").value.trim();
  const role = workbenchRole();
  const view = $("#workbenchViewFilter").value;
  if (search) params.set("search", search);
  if (owner && state.workbenchMode === "tasks" && !state.auth.user) params.set("owner", owner);
  if (role) params.set("role", role);
  if (view) params.set("view", view);
  return params;
}

function renderWorkbenchKpis(kpis = {}) {
  $("#workbenchKpiTotal").textContent = kpis.total || 0;
  $("#workbenchKpiOverdue").textContent = kpis.overdue || 0;
  $("#workbenchKpiBlocked").textContent = kpis.blocked || 0;
  $("#workbenchKpiSubmitted").textContent = kpis.submitted || 0;
}

async function loadWorkbenchProjects(selectProjectId = state.workbenchProjectId) {
  renderWorkbenchMode();
  const params = workbenchQueryParams();
  const payload = await api(`/api/workbench/projects?${params.toString()}`);
  state.workbenchProjects = payload.projects || [];
  renderWorkbenchKpis(payload.kpis || {});
  const selectedExists = state.workbenchProjects.some((project) => project.id === selectProjectId);
  const selectedId = selectedExists ? selectProjectId : state.workbenchProjects[0]?.id;
  renderWorkbenchProjectList(selectedId);
  if (selectedId) {
    await openWorkbenchProject(selectedId);
  } else {
    state.workbenchProjectId = null;
    $("#workbenchWorkspace").innerHTML = `<div class="empty">暂无匹配的执行项目</div>`;
  }
}

async function loadWorkbenchTasks() {
  renderWorkbenchMode();
  state.workbenchProjectId = null;
  state.workbenchProjects = [];
  renderWorkbenchProjectList("");
  const role = workbenchRole();
  const params = workbenchQueryParams();
  const payload = await api(`/api/workbench/inbox?${params.toString()}`);
  state.workbenchTasks = payload.tasks || [];
  state.workbenchInbox = payload;
  renderWorkbenchKpis(payload.kpis || {});
  renderMyTodoWorkspace(payload);
}

function renderWorkbenchProjectList(selectedId = state.workbenchProjectId) {
  const list = $("#workbenchProjectList");
  if (!state.workbenchProjects.length) {
    list.innerHTML = `<div class="empty small-empty">暂无项目</div>`;
    return;
  }
  list.innerHTML = state.workbenchProjects
    .map((project) => {
      const active = project.id === selectedId ? " active" : "";
      const due = project.current_due_date || project.expected_delivery_date || "";
      const tags = [
        project.overdue_tasks ? `<span class="tag danger">超期 ${escapeHtml(project.overdue_tasks)}</span>` : "",
        project.blocked_tasks ? `<span class="tag warn">阻塞 ${escapeHtml(project.blocked_tasks)}</span>` : "",
        project.submitted_tasks ? `<span class="tag">待确认 ${escapeHtml(project.submitted_tasks)}</span>` : "",
        project.high_issues ? `<span class="tag danger">高风险</span>` : "",
      ].join(" ");
      return `
        <button type="button" class="workbench-project-card${active}" data-project-id="${escapeHtml(project.id)}">
          <span class="workbench-card-top">
            <strong>${escapeHtml(project.current_number || project.intake_no)}</strong>
            <small>${escapeHtml(workbenchAreaName(project.workbench_area))}</small>
          </span>
          <span class="workbench-project-title">${escapeHtml(project.equipment_name || project.project_name || "")}</span>
          <small>${escapeHtml(project.customer_name || "")}${project.site_name ? ` · ${escapeHtml(project.site_name)}` : ""}</small>
          <span class="workbench-card-foot">
            <small class="${dueClass(due)}">${escapeHtml(due || "未设置Due Date")}</small>
            <small>${escapeHtml(project.task_done || 0)}/${escapeHtml(project.task_total || 0)} 任务</small>
          </span>
          <span class="tag-row">${tags}</span>
        </button>
      `;
    })
    .join("");
  list.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", () => {
      try {
        openWorkbenchProject(requireDataset(button, "projectId", "项目ID")).catch(console.error);
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

async function openWorkbenchProject(projectId) {
  state.workbenchProjectId = projectId;
  renderWorkbenchProjectList(projectId);
  const payload = await api(`/api/workbench/projects/${encodeURIComponent(projectId)}`);
  renderWorkbenchWorkspace(payload);
}

function renderWorkbenchWorkspace(payload) {
  const { project, tasks = [], deliverables = [], issues = [], logs = [] } = payload;
  const pendingDeliverables = deliverables.filter((item) => item.status === "submitted");
  const showPmDeliverables = canReviewDeliverables();
  const canManageTasks = userHasRole("pm");
  const openIssueCount = issues.filter((issue) => ["open", "following", "resolved"].includes(issue.status)).length;
  $("#workbenchWorkspace").innerHTML = `
    <div class="workbench-header">
      <div>
        <h3>${escapeHtml(project.current_number || project.intake_no)} · ${escapeHtml(project.equipment_name || project.project_name || "")}</h3>
        <p>${escapeHtml(project.customer_name || "")}${project.site_name ? ` · ${escapeHtml(project.site_name)}` : ""}${project.project_group_name ? ` · ${escapeHtml(project.project_group_name)}` : ""}</p>
      </div>
      <div class="workbench-header-actions">
        <button type="button" class="secondary" data-action="copy-path" data-path="${escapeHtml(project.project_folder_path || "")}">复制资料路径</button>
        <button type="button" class="secondary" data-action="open-library-detail">资料库详情</button>
      </div>
    </div>
    <div class="workbench-summary-grid">
      <div><span>${escapeHtml(project.task_done || 0)}/${escapeHtml(project.task_total || 0)}</span><small>任务进度</small></div>
      <div><span>${escapeHtml(project.current_due_date || "未设")}</span><small>最近Due Date</small></div>
      ${showPmDeliverables ? `<div><span>${escapeHtml(project.submitted_tasks || 0)}</span><small>待确认交付物</small></div>` : ""}
      <div><span>${escapeHtml(project.open_issues || 0)}</span><small>打开风险/问题</small></div>
    </div>
    <div class="workbench-columns${showPmDeliverables ? "" : " single"}">
      <section class="workbench-main">
        <div class="workbench-action-row">
          ${canManageTasks ? `<button type="button" class="secondary workbench-entry-button" data-action="open-task-dialog">
            <span>新增任务</span>
            <small>${escapeHtml(tasks.filter((task) => !taskDone(task)).length)} 未完成</small>
          </button>` : ""}
          <button type="button" class="secondary workbench-entry-button" data-action="open-risk-dialog">
            <span>风险/异常</span>
            <small>${escapeHtml(openIssueCount)} 打开</small>
          </button>
          <button type="button" class="secondary workbench-entry-button" data-action="open-log-drawer">
            <span>执行日志</span>
            <small>${escapeHtml(logs.length)} 条</small>
          </button>
        </div>
        ${canManageTasks ? renderTaskDialog(tasks) : ""}
        ${renderRiskDialog(issues, tasks)}
        ${renderLogDrawer(logs)}
        ${renderDeliverableReviewDialog()}
        ${renderTaskCompletionReviewDialog()}
        <div class="workbench-section-title">
          <h3>任务</h3>
          <span>${escapeHtml(tasks.filter((task) => !taskDone(task)).length)} 个未完成</span>
        </div>
        <div class="workbench-task-list">
          ${tasks.length ? tasks.map((task) => renderWorkbenchTask(task, issues)).join("") : `<div class="empty small-empty">暂无任务，先用模板或手动添加一个任务</div>`}
        </div>
      </section>
      ${showPmDeliverables ? `<aside class="workbench-side">
        ${showPmDeliverables ? renderPendingDeliverables(pendingDeliverables) : ""}
      </aside>` : ""}
    </div>
  `;
  bindWorkbenchWorkspaceActions(project.id);
}

function renderMyTodoWorkspace(payload = {}, options = {}) {
  const tasks = payload.tasks || [];
  const deliverables = payload.deliverables || [];
  const taskCompletions = payload.task_completions || [];
  const dueDateRequests = payload.due_date_requests || [];
  const riskReviews = payload.risk_reviews || [];
  const role = payload.role || workbenchRole();
  const owner = $("#workbenchOwnerInput").value.trim();
  const overdueCount = tasks.filter((task) => dueClass(task.due_date || "") === "danger").length;
  const isPm = role === "pm";
  $("#workbenchWorkspace").innerHTML = `
    <div class="workbench-header">
      <div>
        <h3>我的待办 · ${isPm ? "PM" : "工程师"}${owner ? ` · ${escapeHtml(owner)}` : ""}</h3>
        <p>${isPm ? "优先处理待确认文件、改期申请和自己负责的任务。" : "按登录账号筛选；旧任务会兼容负责人姓名匹配。"}</p>
      </div>
    </div>
    <div class="workbench-summary-grid">
      <div><span>${escapeHtml(isPm ? deliverables.length + taskCompletions.length + dueDateRequests.length + riskReviews.length : tasks.length)}</span><small>${isPm ? "待处理审批" : "未完成任务"}</small></div>
      <div><span>${escapeHtml(overdueCount)}</span><small>已超期</small></div>
      <div><span>${escapeHtml(tasks.filter((task) => ["blocked", "waiting_info", "rework"].includes(task.status)).length)}</span><small>阻塞/待资料/返工</small></div>
      <div><span>${escapeHtml(isPm ? tasks.length : tasks.filter((task) => task.requires_deliverable).length)}</span><small>${isPm ? "我的任务" : "需要文件"}</small></div>
    </div>
    <section class="workbench-main my-task-surface">
      ${renderDeliverableReviewDialog()}
      ${renderTaskCompletionReviewDialog()}
      ${isPm ? renderIssueReviewDialog() : ""}
      ${isPm ? renderInboxDeliverablesSection(deliverables) : ""}
      ${isPm ? renderInboxTaskCompletionsSection(taskCompletions) : ""}
      ${isPm ? renderInboxDueDateSection(dueDateRequests) : ""}
      ${isPm ? renderInboxRiskReviewsSection(riskReviews) : ""}
      <div class="workbench-section-title">
        <h3>${isPm ? "我负责的任务" : "任务列表"}</h3>
        <span>${escapeHtml(tasks.length)} 个</span>
      </div>
      <div class="my-task-list">
        ${tasks.length ? tasks.map((task) => renderMyTaskCard(task)).join("") : `<div class="empty small-empty">暂无我的待办任务</div>`}
      </div>
    </section>
  `;
  bindMyTodoActions();
}

function renderLogDrawer(logs) {
  return `
    <dialog id="logDrawer" class="log-drawer">
      <div class="log-drawer-shell">
        <div class="log-drawer-header">
          <div>
            <h3>执行日志</h3>
            <span class="subtext">${escapeHtml(logs.length)} 条</span>
          </div>
          <button type="button" class="secondary slim-inline" data-action="close-log-drawer">关闭</button>
        </div>
      <div class="log-list">
        ${logs.length ? logs.slice(0, 12).map((log) => `
          <div class="log-item">
            <strong>${escapeHtml(log.title)}</strong>
            <span class="subtext">${escapeHtml(log.created_at)}${log.detail ? ` · ${escapeHtml(log.detail)}` : ""}</span>
          </div>
        `).join("") : `<div class="empty small-empty">暂无日志</div>`}
      </div>
      </div>
    </dialog>
  `;
}

function bindMyTodoActions() {
  bindDeliverableReviewDialog($("#workbenchWorkspace"), () => loadWorkbenchTasks());
  bindTaskCompletionReviewDialog($("#workbenchWorkspace"), () => loadWorkbenchTasks());
  bindRiskDialog($("#workbenchWorkspace"));
  $("#workbenchWorkspace").querySelectorAll("[data-action='open-my-task-project'], [data-action='open-inbox-project']").forEach((button) => {
    button.addEventListener("click", async () => {
      state.workbenchMode = "projects";
      await loadWorkbenchProjects(requireDataset(button, "projectId", "项目ID"));
    });
  });
  $("#workbenchWorkspace").querySelectorAll("[data-action='confirm-inbox-deliverable'], [data-action='reject-inbox-deliverable']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await handleDeliverableAction(button.dataset.action, button, () => loadWorkbenchTasks());
      } catch (error) {
        showToast(error.message);
      }
    });
  });
  $("#workbenchWorkspace").querySelectorAll("[data-action='confirm-inbox-task-completion'], [data-action='reject-inbox-task-completion']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const status = button.dataset.action.startsWith("confirm") ? "confirmed" : "rejected";
        requireDataset(button, "taskId", "任务ID");
        openTaskCompletionReviewDialog(button, status);
      } catch (error) {
        showToast(error.message);
      }
    });
  });
  $("#workbenchWorkspace").querySelectorAll("[data-action='approve-due-date-request'], [data-action='reject-due-date-request']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await handleDueDateAction(button.dataset.action, button, button.dataset.projectId || state.workbenchProjectId);
      } catch (error) {
        showToast(error.message);
      }
    });
  });
  $("#workbenchWorkspace").querySelectorAll("[data-action='close-inbox-issue'], [data-action='accept-inbox-issue'], [data-action='reopen-inbox-issue']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await handleIssueAction(button.dataset.action, button, button.dataset.projectId || state.workbenchProjectId);
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

function bindLogDrawer(workspace) {
  closeDialogOnBackdrop(workspace.querySelector("#logDrawer"));
}

async function handleWorkbenchShellAction(action, projectId, button) {
  if (action === "copy-path") {
    const path = button?.dataset.path || "";
    if (!path) throw new Error("当前项目未配置可复制的网络路径");
    await navigator.clipboard.writeText(path);
    showToast("资料路径已复制，请粘贴到资源管理器地址栏");
    return true;
  }
  if (action === "open-library-detail") {
    if (!projectId) throw new Error("项目ID缺失，请刷新页面后重试");
    await openDetail(projectId);
    return true;
  }
  if (action === "open-log-drawer") {
    openWorkbenchDialog("#logDrawer");
    return true;
  }
  if (action === "close-log-drawer") {
    closeWorkbenchDialog("#logDrawer");
    return true;
  }
  return false;
}

function bindWorkbenchWorkspaceActions(projectId) {
  const workspace = $("#workbenchWorkspace");
  bindTaskCreation(projectId);
  bindRiskCreation(projectId);
  bindTaskDialog(workspace);
  bindDueDateDialogs(workspace);
  bindRiskDialog(workspace);
  bindLogDrawer(workspace);
  bindTaskForms(projectId, workspace);
  bindTaskCompletionForms(projectId, workspace);
  bindDueDateForms(projectId, workspace);
  bindDeliverableUploads(projectId, workspace);
  bindDeliverableReviewDialog(workspace, () => loadWorkbenchProjects(projectId));
  bindTaskCompletionReviewDialog(workspace, (result = {}) => loadWorkbenchProjects(result.project_id || projectId));

  workspace.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      try {
        if (await handleWorkbenchShellAction(action, projectId, button)) return;
        if (await handleTaskAction(action, button, projectId)) return;
        if (await handleDueDateAction(action, button, projectId)) return;
        if (await handleDeliverableAction(action, button, () => loadWorkbenchProjects(projectId))) return;
        if (await handleIssueAction(action, button, projectId)) return;
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });
}
