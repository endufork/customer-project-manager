function optionItems(items, selectedValue = "", valueOf = (item) => item.code, labelOf = (item) => item.name) {
  return (items || [])
    .map((item) => {
      const value = valueOf(item);
      const selected = value === selectedValue ? " selected" : "";
      return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(labelOf(item))}</option>`;
    })
    .join("");
}

function stringOptions(items, selectedValue = "") {
  return (items || [])
    .map((item) => `<option value="${escapeHtml(item)}"${item === selectedValue ? " selected" : ""}>${escapeHtml(item)}</option>`)
    .join("");
}

function workbenchTaskStatusName(statusCode) {
  return (state.bootstrap?.workbench_task_statuses || []).find((item) => item.code === statusCode)?.name || statusCode || "";
}

function workbenchIssueStatusName(statusCode) {
  return (state.bootstrap?.workbench_issue_statuses || []).find((item) => item.code === statusCode)?.name || statusCode || "";
}

function workbenchSeverityName(severityCode) {
  return (state.bootstrap?.workbench_issue_severities || []).find((item) => item.code === severityCode)?.name || severityCode || "";
}

function workbenchIssueScopeName(scopeCode) {
  return (state.bootstrap?.workbench_issue_scopes || []).find((item) => item.code === scopeCode)?.name || scopeCode || "";
}

function workbenchAreaName(areaCode) {
  return (state.bootstrap?.workbench_areas || []).find((item) => item.code === areaCode)?.name || areaCode || "";
}

function workbenchRole() {
  const selected = $("#workbenchRoleSelect")?.value;
  if (selected) return selected.trim().toLowerCase();
  const urlRole = new URLSearchParams(window.location.search).get("role");
  return (urlRole || localStorage.getItem(WORKBENCH_ROLE_STORAGE_KEY) || "engineer").trim().toLowerCase();
}

function canReviewDeliverables() {
  return workbenchRole() === "pm";
}

function renderTaskSelectOptions(tasks, selectedId = "") {
  return tasks
    .map((task) => `<option value="${escapeHtml(task.id)}"${task.id === selectedId ? " selected" : ""}>${escapeHtml(task.title)}</option>`)
    .join("");
}

function taskTitleById(tasks, taskId) {
  return tasks.find((task) => task.id === taskId)?.title || "";
}

function taskDone(task) {
  return ["confirmed", "completed", "cancelled"].includes(task.status);
}

function dueClass(dueDate) {
  if (!dueDate) return "neutral";
  if (dueDate < today()) return "danger";
  if (dueDate <= addDays(7)) return "warn";
  return "neutral";
}

function addDays(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function formDataFromContainer(container) {
  const data = {};
  container.querySelectorAll("[name]").forEach((input) => {
    if (input.type === "checkbox") {
      data[input.name] = input.checked ? "1" : "0";
    } else {
      data[input.name] = input.value;
    }
  });
  return data;
}

function renderWorkbenchMode() {
  const isTaskMode = state.workbenchMode === "tasks";
  const role = workbenchRole();
  $("#workbenchView").classList.toggle("workbench-task-mode", isTaskMode);
  $("#workbenchProjectsModeButton").classList.toggle("active", !isTaskMode);
  $("#workbenchTasksModeButton").classList.toggle("active", isTaskMode);
  $("#workbenchKpiTotalLabel").textContent = isTaskMode ? "我的待办" : "执行项目";
  $("#workbenchKpiBlockedLabel").textContent = isTaskMode ? "阻塞/待资料" : "阻塞/风险";
  $("#workbenchKpiSubmittedLabel").textContent = isTaskMode && role === "pm" ? "待确认文件" : isTaskMode ? "已提交" : "待PM确认";
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
  if (owner) params.set("owner", owner);
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
  const owner = $("#workbenchOwnerInput").value.trim();
  const role = workbenchRole();
  if (role !== "pm" && !owner) {
    state.workbenchTasks = [];
    state.workbenchInbox = null;
    renderWorkbenchKpis({});
    renderMyTodoWorkspace({ tasks: [], deliverables: [], role }, { ownerRequired: true });
    return;
  }
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
    button.addEventListener("click", () => openWorkbenchProject(button.dataset.projectId).catch(console.error));
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
  const openIssueCount = issues.filter((issue) => ["open", "following"].includes(issue.status)).length;
  $("#workbenchWorkspace").innerHTML = `
    <div class="workbench-header">
      <div>
        <h3>${escapeHtml(project.current_number || project.intake_no)} · ${escapeHtml(project.equipment_name || project.project_name || "")}</h3>
        <p>${escapeHtml(project.customer_name || "")}${project.site_name ? ` · ${escapeHtml(project.site_name)}` : ""}${project.project_group_name ? ` · ${escapeHtml(project.project_group_name)}` : ""}</p>
      </div>
      <div class="workbench-header-actions">
        <button type="button" class="secondary" data-action="open-folder">打开资料夹</button>
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
          <button type="button" class="secondary workbench-entry-button" data-action="open-task-dialog">
            <span>新增任务</span>
            <small>${escapeHtml(tasks.filter((task) => !taskDone(task)).length)} 未完成</small>
          </button>
          <button type="button" class="secondary workbench-entry-button" data-action="open-risk-dialog">
            <span>风险/异常</span>
            <small>${escapeHtml(openIssueCount)} 打开</small>
          </button>
          <button type="button" class="secondary workbench-entry-button" data-action="open-log-drawer">
            <span>执行日志</span>
            <small>${escapeHtml(logs.length)} 条</small>
          </button>
        </div>
        ${renderTaskDialog(tasks)}
        ${renderRiskDialog(issues, tasks)}
        ${renderLogDrawer(logs)}
        <div class="workbench-section-title">
          <h3>任务</h3>
          <span>${escapeHtml(tasks.filter((task) => !taskDone(task)).length)} 个未完成</span>
        </div>
        <div class="workbench-task-list">
          ${tasks.length ? tasks.map((task) => renderWorkbenchTask(task)).join("") : `<div class="empty small-empty">暂无任务，先用模板或手动添加一个任务</div>`}
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
  const role = payload.role || workbenchRole();
  const owner = $("#workbenchOwnerInput").value.trim();
  if (options.ownerRequired) {
    $("#workbenchWorkspace").innerHTML = `
      <div class="workbench-header">
        <div>
          <h3>我的待办</h3>
          <p>先在顶部输入“我的名字/负责人”，系统会按负责人筛出未完成任务。</p>
        </div>
      </div>
      <div class="empty">请输入负责人后查看我的待办</div>
    `;
    return;
  }
  const overdueCount = tasks.filter((task) => dueClass(task.due_date || "") === "danger").length;
  const isPm = role === "pm";
  $("#workbenchWorkspace").innerHTML = `
    <div class="workbench-header">
      <div>
        <h3>我的待办 · ${isPm ? "PM" : "工程师"}${owner ? ` · ${escapeHtml(owner)}` : ""}</h3>
        <p>${isPm ? "优先处理待确认交付文件；填写负责人后，也会显示自己负责的未完成任务。" : "按 Due Date、阻塞和状态排序；需要提交文件的任务进入项目后上传交付物。"}</p>
      </div>
    </div>
    <div class="workbench-summary-grid">
      <div><span>${escapeHtml(isPm ? deliverables.length : tasks.length)}</span><small>${isPm ? "待确认文件" : "未完成任务"}</small></div>
      <div><span>${escapeHtml(overdueCount)}</span><small>已超期</small></div>
      <div><span>${escapeHtml(tasks.filter((task) => ["blocked", "waiting_info", "rework"].includes(task.status)).length)}</span><small>阻塞/待资料/返工</small></div>
      <div><span>${escapeHtml(isPm ? tasks.length : tasks.filter((task) => task.requires_deliverable).length)}</span><small>${isPm ? "我的任务" : "需要文件"}</small></div>
    </div>
    <section class="workbench-main my-task-surface">
      ${isPm ? renderInboxDeliverablesSection(deliverables) : ""}
      <div class="workbench-section-title">
        <h3>${isPm ? "我负责的任务" : "任务列表"}</h3>
        <span>${escapeHtml(tasks.length)} 个</span>
      </div>
      <div class="my-task-list">
        ${tasks.length ? tasks.map((task) => renderMyTaskCard(task)).join("") : `<div class="empty small-empty">${isPm && !owner ? "填写负责人后显示我负责的任务" : "暂无我的待办任务"}</div>`}
      </div>
    </section>
  `;
  bindMyTodoActions();
}

function renderInboxDeliverablesSection(deliverables) {
  return `
    <div class="workbench-section-title inbox-section-title">
      <h3>待确认文件</h3>
      <span>${escapeHtml(deliverables.length)} 个</span>
    </div>
    <div class="my-task-list inbox-deliverable-list">
      ${deliverables.length ? deliverables.map((item) => renderInboxDeliverableCard(item)).join("") : `<div class="empty small-empty">暂无待确认文件</div>`}
    </div>
  `;
}

function renderInboxDeliverableCard(item) {
  const projectName = item.equipment_name || item.project_name || "";
  const customerLine = [
    item.customer_name || "",
    item.site_name || "",
    item.project_group_name || "",
  ].filter(Boolean).join(" · ");
  const projectMeta = [
    item.current_number || item.intake_no || "",
    item.task_title || "",
    item.category_name || item.deliverable_type || "",
  ].filter(Boolean).join(" · ");
  return `
    <article class="my-task-card submitted" data-deliverable-id="${escapeHtml(item.id)}">
      <div class="my-task-main">
        <div>
          <strong>${escapeHtml(item.file_name || "交付文件")}</strong>
          <span class="subtext">${escapeHtml(projectMeta)}</span>
          <span class="subtext">${escapeHtml(customerLine)}${projectName ? ` · ${escapeHtml(projectName)}` : ""}</span>
        </div>
        <div class="my-task-status">
          <span class="task-status submitted">待确认</span>
          <span class="subtext">${escapeHtml(item.submitted_by || "提交人未填")}${item.submitted_at ? ` · ${escapeHtml(item.submitted_at)}` : ""}</span>
        </div>
      </div>
      <div class="my-task-foot">
        <span class="tag-row">
          ${item.version_note ? `<span class="tag">${escapeHtml(item.version_note)}</span>` : ""}
        </span>
        <span class="inline-actions">
          <button type="button" class="secondary slim-inline" data-action="open-inbox-project" data-project-id="${escapeHtml(item.project_id)}">打开项目</button>
          <button type="button" class="secondary slim-inline" data-action="confirm-inbox-deliverable" data-deliverable-id="${escapeHtml(item.id)}">确认</button>
          <button type="button" class="danger slim-inline" data-action="reject-inbox-deliverable" data-deliverable-id="${escapeHtml(item.id)}">驳回</button>
        </span>
      </div>
    </article>
  `;
}

function renderMyTaskCard(task) {
  const due = task.due_date || "未设置Due Date";
  const projectName = task.equipment_name || task.project_name || "";
  const customerLine = [
    task.customer_name || "",
    task.site_name || "",
    task.project_group_name || "",
  ].filter(Boolean).join(" · ");
  const projectMeta = [
    task.current_number || task.intake_no || "",
    workbenchAreaName(task.workbench_area),
    task.work_package || "未分组",
  ].filter(Boolean).join(" · ");
  return `
    <article class="my-task-card ${escapeHtml(task.status)}" data-task-id="${escapeHtml(task.id)}">
      <div class="my-task-main">
        <div>
          <strong>${escapeHtml(task.title)}</strong>
          <span class="subtext">${escapeHtml(projectMeta)}</span>
          <span class="subtext">${escapeHtml(customerLine)}${projectName ? ` · ${escapeHtml(projectName)}` : ""}</span>
        </div>
        <div class="my-task-status">
          <span class="task-status ${escapeHtml(task.status)}">${escapeHtml(workbenchTaskStatusName(task.status))}</span>
          <span class="${dueClass(task.due_date || "")}">${escapeHtml(due)}</span>
        </div>
      </div>
      <div class="my-task-foot">
        <span class="tag-row">
          ${task.requires_deliverable ? `<span class="tag">需要文件</span>` : ""}
          ${task.status === "submitted" ? `<span class="tag warn">待确认</span>` : ""}
          ${task.status === "blocked" ? `<span class="tag danger">阻塞</span>` : ""}
          ${task.status === "waiting_info" ? `<span class="tag warn">等待资料</span>` : ""}
        </span>
        <button type="button" class="secondary slim-inline" data-action="open-my-task-project" data-project-id="${escapeHtml(task.project_id)}">打开项目处理</button>
      </div>
      ${task.notes ? `<p class="my-task-note">${escapeHtml(task.notes)}</p>` : ""}
    </article>
  `;
}

function bindMyTodoActions() {
  $("#workbenchWorkspace").querySelectorAll("[data-action='open-my-task-project'], [data-action='open-inbox-project']").forEach((button) => {
    button.addEventListener("click", async () => {
      state.workbenchMode = "projects";
      await loadWorkbenchProjects(button.dataset.projectId);
    });
  });
  $("#workbenchWorkspace").querySelectorAll("[data-action='confirm-inbox-deliverable']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/api/workbench/deliverables/${encodeURIComponent(button.dataset.deliverableId)}`, {
          method: "PATCH",
          body: JSON.stringify({ status: "confirmed", confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM" }),
        });
        showToast("交付物已确认");
        await loadWorkbenchTasks();
      } catch (error) {
        showToast(error.message);
      }
    });
  });
  $("#workbenchWorkspace").querySelectorAll("[data-action='reject-inbox-deliverable']").forEach((button) => {
    button.addEventListener("click", async () => {
      const reason = prompt("请输入驳回原因");
      if (!reason) return;
      try {
        await api(`/api/workbench/deliverables/${encodeURIComponent(button.dataset.deliverableId)}`, {
          method: "PATCH",
          body: JSON.stringify({ status: "rejected", confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM", reject_reason: reason }),
        });
        showToast("交付物已驳回");
        await loadWorkbenchTasks();
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

function renderTaskDialog(tasks = []) {
  return `
    <dialog id="taskDialog" class="workbench-dialog task-dialog">
      <div class="workbench-dialog-shell">
        <div class="workbench-dialog-header">
          <div>
            <h3>新增任务</h3>
            <span class="subtext">先手动添加；模板任务可按需勾选</span>
          </div>
          <button type="button" class="secondary slim-inline" data-action="close-task-dialog">关闭</button>
        </div>
        <section class="workbench-panel task-window-panel">
          <div class="workbench-section-title">
            <h3>手动新增</h3>
          </div>
          ${renderTaskCreateForm()}
          <div class="workbench-section-title template-create-title">
            <h3>从模板选择添加</h3>
            <span>选择模板后显示条目</span>
          </div>
          <form id="templateTaskForm" class="template-task-form">
            <div class="template-picker-row">
              <label>
                模板
                <select id="taskTemplateSelect" name="template_code">
                  <option value="">选择任务模板</option>
                  ${Object.entries(WORKBENCH_TASK_TEMPLATES).map(([code, template]) => `<option value="${escapeHtml(code)}">${escapeHtml(template.name)}</option>`).join("")}
                </select>
              </label>
              <p id="taskTemplateNote" class="template-selected-note">先选择模板，再勾选要添加的任务。</p>
            </div>
            ${Object.keys(WORKBENCH_TASK_TEMPLATES).map((code) => renderTaskTemplateChecklist(code, tasks)).join("")}
            <div class="template-form-actions">
              <button type="button" class="secondary slim-inline" data-action="select-visible-template">全选当前模板</button>
              <button type="button" class="secondary slim-inline" data-action="clear-visible-template">清空</button>
              <button type="submit" class="secondary compact-submit">添加所选任务</button>
            </div>
          </form>
        </section>
      </div>
    </dialog>
  `;
}

function renderTaskTemplateChecklist(templateCode, tasks) {
  const template = WORKBENCH_TASK_TEMPLATES[templateCode];
  const existingTitles = new Set(tasks.map((task) => task.title));
  return `
    <div class="template-checklist" data-template-panel="${escapeHtml(templateCode)}" hidden>
      ${template.items.map((item, index) => {
        const exists = existingTitles.has(item.title);
        return `
          <div class="template-task-row${exists ? " disabled" : ""}">
            <input type="checkbox" data-template-code="${escapeHtml(templateCode)}" data-template-index="${escapeHtml(index)}"${exists ? " disabled" : " checked"} />
            <span class="template-task-main">
              <strong>${escapeHtml(item.title)}</strong>
              <small>${escapeHtml(item.work_package)}${item.requires_deliverable ? " · 需要文件" : ""}${exists ? " · 已存在" : ""}</small>
            </span>
            <label class="template-task-due">
              Due Date
              <input type="date" data-template-due value="${escapeHtml(addDays(item.offset_days))}"${exists ? " disabled" : ""} />
            </label>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderTaskCreateForm() {
  const owner = $("#workbenchOwnerInput").value.trim();
  return `
    <form id="workbenchTaskForm" class="workbench-create-form">
      <input name="title" placeholder="新增任务，例如 机械方案确认" required />
      <select name="work_package">
        <option value="">工作包</option>
        ${stringOptions(state.bootstrap?.workbench_work_packages || [])}
      </select>
      <input name="owner_name" placeholder="负责人" value="${escapeHtml(owner)}" />
      <input name="due_date" type="date" />
      <label class="checkline compact-check">
        <input name="requires_deliverable" type="checkbox" value="1" />
        需要文件
      </label>
      <button type="submit" class="secondary compact-submit">+ 任务</button>
    </form>
  `;
}

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

function renderWorkbenchTask(task) {
  const deliverables = task.deliverables || [];
  const owner = task.owner_name || "未指派";
  const due = task.due_date || "未设置Due Date";
  const workPackage = task.work_package || "未分组";
  return `
    <article class="workbench-task ${escapeHtml(task.status)}" data-task-id="${escapeHtml(task.id)}">
      <div class="task-readable">
        <div class="task-readable-main">
          <strong>${escapeHtml(task.title)}</strong>
          <span class="subtext">${escapeHtml(workPackage)} · ${escapeHtml(owner)} · <span class="${dueClass(task.due_date || "")}">${escapeHtml(due)}</span>${task.requires_deliverable ? " · 需要文件" : ""}</span>
        </div>
        <div class="task-actions">
          <span class="task-status ${escapeHtml(task.status)}">${escapeHtml(workbenchTaskStatusName(task.status))}</span>
          <button type="button" class="danger slim-inline" data-action="delete-task" data-task-id="${escapeHtml(task.id)}">删除</button>
        </div>
      </div>
      <details class="task-deliverable-panel">
        <summary>编辑任务 / 提交文件 ${deliverables.length ? `(${escapeHtml(deliverables.length)} 个文件)` : ""}</summary>
        <form class="workbench-task-form" data-task-id="${escapeHtml(task.id)}">
          <label>
            任务
            <input name="title" value="${escapeHtml(task.title)}" />
          </label>
          <label>
            工作包
            <select name="work_package">
              <option value="">工作包</option>
              ${stringOptions(state.bootstrap?.workbench_work_packages || [], task.work_package || "")}
            </select>
          </label>
          <label>
            负责人
            <input name="owner_name" value="${escapeHtml(task.owner_name || "")}" placeholder="负责人" />
          </label>
          <label>
            状态
            <select name="status">${optionItems(state.bootstrap?.workbench_task_statuses || [], task.status)}</select>
          </label>
          <label>
            Due Date
            <input name="due_date" type="date" value="${escapeHtml(task.due_date || "")}" />
          </label>
          <label class="checkline compact-check">
            <input name="requires_deliverable" type="checkbox" value="1"${task.requires_deliverable ? " checked" : ""} />
            需要文件
          </label>
          <label>
            备注/阻塞说明
            <input name="notes" value="${escapeHtml(task.notes || "")}" placeholder="备注/阻塞说明" />
          </label>
          <div class="task-actions">
            <button type="button" class="secondary slim-inline" data-action="save-task" data-task-id="${escapeHtml(task.id)}">保存任务</button>
          </div>
        </form>
        <form class="deliverable-upload-form" data-task-id="${escapeHtml(task.id)}">
          <input type="file" name="file" required />
          <select name="category_code">${optionItems(state.bootstrap?.file_categories || [], "solution", (item) => item.code, (item) => item.name)}</select>
          <input name="version_note" placeholder="版本说明，可选" />
          <input name="submitted_by" placeholder="提交人" value="${escapeHtml($("#workbenchOwnerInput").value.trim() || task.owner_name || "")}" />
          <button type="submit">提交文件</button>
        </form>
        <div class="deliverable-list">
          ${deliverables.length ? deliverables.map((item) => renderDeliverableItem(item)).join("") : `<div class="empty small-empty">暂无交付文件</div>`}
        </div>
      </details>
    </article>
  `;
}

function renderDeliverableItem(item) {
  const actions = canReviewDeliverables() && item.status === "submitted"
    ? `
      <button type="button" class="secondary slim-inline" data-action="confirm-deliverable" data-deliverable-id="${escapeHtml(item.id)}">确认</button>
      <button type="button" class="danger slim-inline" data-action="reject-deliverable" data-deliverable-id="${escapeHtml(item.id)}">驳回</button>
    `
    : "";
  return `
    <div class="deliverable-item">
      <div>
        <strong>${escapeHtml(item.file_name || "交付文件")}</strong>
        <span class="subtext">${escapeHtml(item.category_name || item.deliverable_type || "")}${item.version_note ? ` · ${escapeHtml(item.version_note)}` : ""}${item.submitted_by ? ` · ${escapeHtml(item.submitted_by)}` : ""}</span>
      </div>
      <div class="inline-actions">
        <span class="tag ${item.status === "rejected" ? "danger" : item.status === "submitted" ? "warn" : ""}">${escapeHtml(deliverableStatusName(item.status))}</span>
        ${actions}
      </div>
    </div>
  `;
}

function deliverableStatusName(statusCode) {
  return (state.bootstrap?.workbench_deliverable_statuses || []).find((item) => item.code === statusCode)?.name || statusCode || "";
}

function renderPendingDeliverables(items) {
  return `
    <section class="workbench-panel">
      <div class="workbench-section-title">
        <h3>待确认交付物</h3>
        <span>${escapeHtml(items.length)} 个</span>
      </div>
      <div class="deliverable-list">
        ${items.length ? items.map((item) => renderDeliverableItem(item)).join("") : `<div class="empty small-empty">暂无待确认文件</div>`}
      </div>
    </section>
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
          <button type="button" class="danger slim-inline" data-action="delete-issue" data-issue-id="${escapeHtml(issue.id)}">删除</button>
        </div>
      </div>
      <details class="issue-edit-panel">
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
      </details>
    </form>
  `;
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

function bindWorkbenchWorkspaceActions(projectId) {
  const workspace = $("#workbenchWorkspace");
  const taskForm = $("#workbenchTaskForm");
  if (taskForm) {
    taskForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      button.disabled = true;
      try {
        await api(`/api/workbench/projects/${encodeURIComponent(projectId)}/tasks`, {
          method: "POST",
          body: JSON.stringify(formToPayload(taskForm)),
        });
        showToast("任务已添加");
        await loadWorkbenchProjects(projectId);
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  }
  const issueForm = $("#workbenchIssueForm");
  if (issueForm) {
    issueForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      button.disabled = true;
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
        button.disabled = false;
      }
    });
  }
  const templateTaskForm = $("#templateTaskForm");
  if (templateTaskForm) {
    const templateSelect = $("#taskTemplateSelect");
    if (templateSelect) {
      templateSelect.addEventListener("change", () => {
        const selectedTemplate = WORKBENCH_TASK_TEMPLATES[templateSelect.value];
        templateTaskForm.querySelectorAll(".template-checklist").forEach((panel) => {
          panel.hidden = panel.dataset.templatePanel !== templateSelect.value;
        });
        const note = $("#taskTemplateNote");
        if (note) {
          note.textContent = selectedTemplate ? selectedTemplate.note : "先选择模板，再勾选要添加的任务。";
        }
      });
    }
    templateTaskForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      if (button) button.disabled = true;
      try {
        const activePanel = templateTaskForm.querySelector(".template-checklist:not([hidden])");
        if (!activePanel) {
          showToast("请先选择任务模板");
          return;
        }
        const checkedItems = Array.from(activePanel?.querySelectorAll("input[type='checkbox']:checked:not(:disabled)") || []);
        if (!checkedItems.length) {
          showToast("请选择要添加的模板任务");
          return;
        }
        let created = 0;
        for (const checkbox of checkedItems) {
          const template = WORKBENCH_TASK_TEMPLATES[checkbox.dataset.templateCode];
          const item = template?.items[Number(checkbox.dataset.templateIndex)];
          if (!item) continue;
          const row = checkbox.closest(".template-task-row");
          const dueDate = row?.querySelector("[data-template-due]")?.value || "";
          await api(`/api/workbench/projects/${encodeURIComponent(projectId)}/tasks`, {
            method: "POST",
            body: JSON.stringify({
              title: item.title,
              work_package: item.work_package,
              phase_code: item.phase_code,
              due_date: dueDate,
              requires_deliverable: item.requires_deliverable,
            }),
          });
          created += 1;
        }
        showToast(`已添加 ${created} 个模板任务`);
        await loadWorkbenchProjects(projectId);
      } catch (error) {
        showToast(error.message);
      } finally {
        if (button) button.disabled = false;
      }
    });
  }
  const riskDialog = workspace.querySelector("#riskDialog");
  if (riskDialog) {
    riskDialog.addEventListener("click", (event) => {
      if (event.target === riskDialog) {
        riskDialog.close();
      }
    });
  }
  const taskDialog = workspace.querySelector("#taskDialog");
  if (taskDialog) {
    taskDialog.addEventListener("click", (event) => {
      if (event.target === taskDialog) {
        taskDialog.close();
      }
    });
  }
  const logDrawer = workspace.querySelector("#logDrawer");
  if (logDrawer) {
    logDrawer.addEventListener("click", (event) => {
      if (event.target === logDrawer) {
        logDrawer.close();
      }
    });
  }
  workspace.querySelectorAll(".workbench-task-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await saveWorkbenchTask(form, projectId);
    });
  });
  workspace.querySelectorAll(".deliverable-upload-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      button.disabled = true;
      try {
        const formData = new FormData(form);
        await uploadApi(`/api/workbench/tasks/${encodeURIComponent(form.dataset.taskId)}/deliverables`, formData);
        showToast("文件已提交，等待PM确认");
        await loadWorkbenchProjects(projectId);
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });
  workspace.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      try {
        if (action === "open-folder") {
          await api(`/api/projects/${encodeURIComponent(projectId)}/open-folder`, { method: "POST", body: "{}" });
          showToast("已打开项目文件夹");
        }
        if (action === "open-library-detail") {
          await openDetail(projectId);
        }
        if (action === "open-task-dialog") {
          const dialog = $("#taskDialog");
          if (dialog?.showModal) {
            dialog.showModal();
          } else if (dialog) {
            dialog.setAttribute("open", "");
          }
        }
        if (action === "close-task-dialog") {
          const dialog = $("#taskDialog");
          if (dialog?.close) {
            dialog.close();
          } else {
            dialog?.removeAttribute("open");
          }
        }
        if (action === "select-visible-template") {
          $("#templateTaskForm")?.querySelectorAll(".template-checklist:not([hidden]) input[type='checkbox']:not(:disabled)").forEach((input) => {
            input.checked = true;
          });
        }
        if (action === "clear-visible-template") {
          $("#templateTaskForm")?.querySelectorAll(".template-checklist:not([hidden]) input[type='checkbox']").forEach((input) => {
            input.checked = false;
          });
        }
        if (action === "apply-template") {
          button.disabled = true;
          const result = await api(`/api/workbench/projects/${encodeURIComponent(projectId)}/templates`, {
            method: "POST",
            body: JSON.stringify({ template: button.dataset.template }),
          });
          showToast(`已生成 ${result.created} 个任务`);
          await loadWorkbenchProjects(projectId);
        }
        if (action === "open-risk-dialog") {
          const dialog = $("#riskDialog");
          if (dialog?.showModal) {
            dialog.showModal();
          } else if (dialog) {
            dialog.setAttribute("open", "");
          }
        }
        if (action === "close-risk-dialog") {
          const dialog = $("#riskDialog");
          if (dialog?.close) {
            dialog.close();
          } else {
            dialog?.removeAttribute("open");
          }
        }
        if (action === "open-log-drawer") {
          const drawer = $("#logDrawer");
          if (drawer?.showModal) {
            drawer.showModal();
          } else if (drawer) {
            drawer.setAttribute("open", "");
          }
        }
        if (action === "close-log-drawer") {
          const drawer = $("#logDrawer");
          if (drawer?.close) {
            drawer.close();
          } else {
            drawer?.removeAttribute("open");
          }
        }
        if (action === "save-task") {
          await saveWorkbenchTask(button.closest(".workbench-task-form"), projectId);
        }
        if (action === "delete-task") {
          if (!confirm("确定删除这个任务吗？")) return;
          await api(`/api/workbench/tasks/${encodeURIComponent(button.dataset.taskId)}`, { method: "DELETE", body: "{}" });
          showToast("任务已删除");
          await loadWorkbenchProjects(projectId);
        }
        if (action === "confirm-deliverable") {
          await api(`/api/workbench/deliverables/${encodeURIComponent(button.dataset.deliverableId)}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "confirmed", confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM" }),
          });
          showToast("交付物已确认");
          await loadWorkbenchProjects(projectId);
        }
        if (action === "reject-deliverable") {
          const reason = prompt("请输入驳回原因");
          if (!reason) return;
          await api(`/api/workbench/deliverables/${encodeURIComponent(button.dataset.deliverableId)}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "rejected", confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM", reject_reason: reason }),
          });
          showToast("交付物已驳回");
          await loadWorkbenchProjects(projectId);
        }
        if (action === "save-issue") {
          const form = button.closest(".issue-item");
          await api(`/api/workbench/issues/${encodeURIComponent(button.dataset.issueId)}`, {
            method: "PATCH",
            body: JSON.stringify(formDataFromContainer(form)),
          });
          showToast("风险/问题已保存");
          await loadWorkbenchProjects(projectId);
        }
        if (action === "delete-issue") {
          if (!confirm("确定删除这个风险/问题吗？")) return;
          await api(`/api/workbench/issues/${encodeURIComponent(button.dataset.issueId)}`, { method: "DELETE", body: "{}" });
          showToast("风险/问题已删除");
          await loadWorkbenchProjects(projectId);
        }
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });
}

async function saveWorkbenchTask(form, projectId) {
  const button = form.querySelector("[data-action='save-task']");
  if (button) button.disabled = true;
  try {
    await api(`/api/workbench/tasks/${encodeURIComponent(form.dataset.taskId)}`, {
      method: "PATCH",
      body: JSON.stringify(formDataFromContainer(form)),
    });
    showToast("任务已保存");
    await loadWorkbenchProjects(projectId);
  } catch (error) {
    showToast(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}
