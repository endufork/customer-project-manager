const BOARD_KPI_DEFINITIONS = [
  { key: "active_projects", label: "进行中项目", view: "all" },
  { key: "due_soon_tasks", label: "本周到期", view: "due_soon" },
  { key: "overdue_tasks", label: "超期任务", view: "overdue" },
  { key: "blocked_projects", label: "阻塞项目", view: "blocked" },
  { key: "pending_confirmations", label: "待确认", view: "pending" },
  { key: "high_risk_projects", label: "高风险", view: "blocked" },
];

const BOARD_STATUS_CLASS = {
  overdue: "danger",
  blocked_risk: "danger",
  pending: "warn",
  rework: "warn",
  in_progress: "ok",
  pending_start: "neutral",
  inq: "neutral",
  closed: "muted",
};

const RISK_KPI_DEFINITIONS = [
  { key: "active", label: "打开风险", view: "active" },
  { key: "high", label: "高风险", view: "high" },
  { key: "overdue", label: "超期", view: "overdue" },
  { key: "due_soon", label: "本周到期", view: "due_soon" },
  { key: "resolved", label: "待PM确认", view: "resolved" },
];

function boardOwnerName() {
  return state.auth.user?.display_name || state.auth.user?.email?.split("@")[0] || $("#workbenchOwnerInput")?.value.trim() || "";
}

function boardQueryParams() {
  const params = new URLSearchParams();
  const search = $("#boardSearchInput").value.trim();
  const view = state.boardFilter || "all";
  if (search) params.set("search", search);
  if (view) params.set("view", view);
  if (view === "mine") params.set("owner", boardOwnerName());
  return params;
}

async function loadProjectBoard(selectProjectId = state.boardSelectedProjectId) {
  renderBoardMode();
  if (state.boardMode === "risks") {
    await loadRiskOverview();
    return;
  }
  updateBoardFilterButtons();
  const payload = await api(`/api/workbench/board?${boardQueryParams().toString()}`);
  state.boardPayload = payload;
  state.boardProjects = payload.projects || [];
  renderBoardKpis(payload.kpis || {});
  renderBoardProjectList(selectProjectId);
  const selectedExists = state.boardProjects.some((project) => project.id === selectProjectId);
  const selectedId = selectedExists ? selectProjectId : state.boardProjects[0]?.id || null;
  renderBoardSnapshot(selectedId);
}

function renderBoardMode() {
  const riskMode = state.boardMode === "risks";
  $("#boardProjectsModeButton").classList.toggle("active", !riskMode);
  $("#boardRisksModeButton").classList.toggle("active", riskMode);
  $("#boardKpis").hidden = riskMode;
  $("#riskKpis").hidden = !riskMode;
  $("#boardProjectToolbar").hidden = riskMode;
  $("#riskToolbar").hidden = !riskMode;
  $("#boardProjectLayout").hidden = riskMode;
  $("#riskOverviewLayout").hidden = !riskMode;
}

function updateBoardFilterButtons() {
  const filter = state.boardFilter || "all";
  document.querySelectorAll("[data-board-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.boardFilter === filter);
  });
}

function updateRiskFilterButtons() {
  const filter = state.boardRiskFilter || "active";
  document.querySelectorAll("[data-risk-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.riskFilter === filter);
  });
}

function renderBoardKpis(kpis = {}) {
  $("#boardKpis").innerHTML = BOARD_KPI_DEFINITIONS.map((item) => `
    <button type="button" class="board-kpi" data-board-kpi-view="${escapeHtml(item.view)}">
      <span>${escapeHtml(kpis[item.key] || 0)}</span>
      <small>${escapeHtml(item.label)}</small>
    </button>
  `).join("");
  $("#boardKpis").querySelectorAll("[data-board-kpi-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.boardFilter = button.dataset.boardKpiView || "all";
      loadProjectBoard().catch(console.error);
    });
  });
}

function riskQueryParams() {
  const params = new URLSearchParams();
  const search = $("#riskSearchInput").value.trim();
  const view = state.boardRiskFilter || "active";
  if (search) params.set("search", search);
  if (view) params.set("view", view);
  return params;
}

async function loadRiskOverview(selectRiskId = state.boardSelectedRiskId) {
  updateRiskFilterButtons();
  const payload = await api(`/api/workbench/risks?${riskQueryParams().toString()}`);
  state.boardRiskPayload = payload;
  state.boardRisks = payload.risks || [];
  renderRiskKpis(payload.kpis || {});
  const selectedExists = state.boardRisks.some((risk) => risk.id === selectRiskId);
  const selectedId = selectedExists ? selectRiskId : state.boardRisks[0]?.id || null;
  renderRiskOverviewList(selectedId);
  renderRiskSnapshot(selectedId);
}

function renderRiskKpis(kpis = {}) {
  $("#riskKpis").innerHTML = RISK_KPI_DEFINITIONS.map((item) => `
    <button type="button" class="board-kpi" data-risk-kpi-view="${escapeHtml(item.view)}">
      <span>${escapeHtml(kpis[item.key] || 0)}</span>
      <small>${escapeHtml(item.label)}</small>
    </button>
  `).join("");
  $("#riskKpis").querySelectorAll("[data-risk-kpi-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.boardRiskFilter = button.dataset.riskKpiView || "active";
      loadRiskOverview().catch(console.error);
    });
  });
}

function renderRiskOverviewList(selectedId = state.boardSelectedRiskId) {
  const list = $("#riskOverviewList");
  if (!state.boardRisks.length) {
    list.innerHTML = `<div class="empty">暂无匹配风险</div>`;
    return;
  }
  list.innerHTML = state.boardRisks.map((risk) => renderRiskRow(risk, selectedId)).join("");
  list.querySelectorAll("[data-risk-id]").forEach((button) => {
    button.addEventListener("click", () => {
      renderRiskSnapshot(button.dataset.riskId);
    });
  });
}

function renderRiskRow(risk, selectedId) {
  const active = risk.id === selectedId ? " active" : "";
  const statusClass = riskStatusClass(risk);
  const due = risk.due_date || "";
  const context = [
    risk.customer_name || "",
    risk.site_name || "",
    risk.project_group_name || "",
  ].filter(Boolean).join(" · ");
  return `
    <button type="button" class="risk-row${active}" data-risk-id="${escapeHtml(risk.id)}">
      <span class="risk-row-project">
        <strong>${escapeHtml(risk.current_number || "")}</strong>
        <small>${escapeHtml(risk.equipment_name || risk.project_name || "")}</small>
      </span>
      <span class="risk-row-title">
        <strong>${escapeHtml(risk.title || "")}</strong>
        <small>${escapeHtml(context || "未填写客户/产品信息")}</small>
      </span>
      <span class="risk-row-scope">
        <span class="tag neutral">${escapeHtml(risk.scope_label || "")}</span>
        <small>${escapeHtml(risk.task_title || risk.issue_type || "")}</small>
      </span>
      <span class="risk-row-owner">
        <strong>${escapeHtml(risk.owner_name || "未指定")}</strong>
        <small>责任人</small>
      </span>
      <span class="risk-row-due">
        <strong class="${dueClass(due)}">${escapeHtml(due || "未设")}</strong>
        <small>Due Date</small>
      </span>
      <span class="risk-row-state">
        <span class="status-pill ${statusClass}">${escapeHtml(risk.status_label || "")}</span>
        <small>${escapeHtml(risk.severity_label || "")}风险</small>
      </span>
    </button>
  `;
}

function riskStatusClass(risk) {
  if (risk.is_overdue || risk.severity === "high") return "danger";
  if (risk.status === "resolved" || risk.is_due_soon) return "warn";
  if (["accepted", "closed"].includes(risk.status)) return "muted";
  return "neutral";
}

function renderRiskSnapshot(riskId) {
  state.boardSelectedRiskId = riskId || null;
  renderRiskOverviewList(riskId);
  const risk = state.boardRisks.find((item) => item.id === riskId);
  if (!risk) {
    $("#riskSnapshot").innerHTML = `<div class="empty">请选择一个风险查看摘要</div>`;
    return;
  }
  $("#riskSnapshot").innerHTML = `
    <div class="board-snapshot-head">
      <div>
        <h3>${escapeHtml(risk.current_number || "")}</h3>
        <p>${escapeHtml(risk.title || "")}</p>
      </div>
      <span class="status-pill ${riskStatusClass(risk)}">${escapeHtml(risk.status_label || "")}</span>
    </div>
    <dl class="board-snapshot-grid">
      <dt>客户/工厂</dt>
      <dd>${escapeHtml(risk.customer_name || "")}${risk.site_name ? ` · ${escapeHtml(risk.site_name)}` : ""}</dd>
      <dt>产品/产线</dt>
      <dd>${escapeHtml(risk.project_group_name || "未关联")}</dd>
      <dt>项目/设备</dt>
      <dd>${escapeHtml(risk.equipment_name || risk.project_name || "")}</dd>
      <dt>影响范围</dt>
      <dd>${escapeHtml(risk.scope_label || "")}</dd>
      <dt>关联任务</dt>
      <dd>${escapeHtml(risk.task_title || "未关联具体任务")}</dd>
      <dt>严重度</dt>
      <dd>${escapeHtml(risk.severity_label || "")}</dd>
      <dt>责任人</dt>
      <dd>${escapeHtml(risk.owner_name || "未指定")}</dd>
      <dt>Due Date</dt>
      <dd class="${dueClass(risk.due_date || "")}">${escapeHtml(risk.due_date || "未设置")}</dd>
    </dl>
    <section class="board-snapshot-section">
      <h4>处理说明</h4>
      <p class="risk-resolution-text">${escapeHtml(risk.resolution || "暂无处理说明")}</p>
    </section>
    <div class="board-snapshot-actions">
      <button type="button" data-risk-action="open-workbench-project" data-project-id="${escapeHtml(risk.project_id)}">进入项目执行</button>
    </div>
  `;
  bindRiskSnapshotActions();
}

function bindRiskSnapshotActions() {
  $("#riskSnapshot").querySelectorAll("[data-risk-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        if (button.dataset.riskAction === "open-workbench-project") {
          switchView("workbench", false);
          await loadWorkbenchProjects(button.dataset.projectId);
        }
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

function renderBoardProjectList(selectedId = state.boardSelectedProjectId) {
  const list = $("#boardProjectList");
  if (!state.boardProjects.length) {
    list.innerHTML = `<div class="empty">暂无匹配项目</div>`;
    return;
  }
  const groups = state.boardPayload?.groups || [];
  list.innerHTML = groups
    .map((group) => {
      const projects = state.boardProjects.filter((project) => project.board_group === group.key);
      if (!projects.length) return "";
      return `
        <section class="board-group">
          <div class="board-group-head">
            <h3>${escapeHtml(group.label)}</h3>
            <span>${escapeHtml(projects.length)} 项</span>
          </div>
          <div class="board-group-list">
            ${projects.map((project) => renderBoardProjectRow(project, selectedId)).join("")}
          </div>
        </section>
      `;
    })
    .join("");
  list.querySelectorAll("[data-board-project-id]").forEach((button) => {
    button.addEventListener("click", () => {
      renderBoardSnapshot(button.dataset.boardProjectId);
    });
  });
}

function renderBoardProjectRow(project, selectedId) {
  const active = project.id === selectedId ? " active" : "";
  const due = project.current_due_date || project.expected_delivery_date || "";
  const statusClass = BOARD_STATUS_CLASS[project.board_status] || "neutral";
  const progress = project.task_total ? `${project.task_done || 0}/${project.task_total}` : "未建任务";
  const flags = (project.board_flags || []).map((flag) => `<span class="tag ${boardFlagClass(flag)}">${escapeHtml(flag)}</span>`).join("");
  return `
    <button type="button" class="board-project-row${active}" data-board-project-id="${escapeHtml(project.id)}">
      <span class="board-row-number">
        <strong>${escapeHtml(project.current_number || project.intake_no || "")}</strong>
        <small>${escapeHtml(workbenchAreaName(project.workbench_area))}</small>
      </span>
      <span class="board-row-main">
        <strong>${escapeHtml(project.equipment_name || project.project_name || "")}</strong>
        <small>${escapeHtml(project.customer_name || "")}${project.site_name ? ` · ${escapeHtml(project.site_name)}` : ""}${project.project_group_name ? ` · ${escapeHtml(project.project_group_name)}` : ""}</small>
      </span>
      <span class="board-row-stage">
        <span class="status-pill ${statusClass}">${escapeHtml(project.board_status_label)}</span>
        <small>${escapeHtml(project.status_name || "")}</small>
      </span>
      <span class="board-row-owner">
        <strong>${escapeHtml(project.current_owner || "未指定")}</strong>
        <small>责任人</small>
      </span>
      <span class="board-row-next">
        <strong>${escapeHtml(project.next_action || "未设置下一步")}</strong>
        <small>${escapeHtml(progress)} 任务</small>
      </span>
      <span class="board-row-due">
        <strong class="${dueClass(due)}">${escapeHtml(due || "未设")}</strong>
        <small>Due Date</small>
      </span>
      <span class="board-row-flags">${flags || `<span class="tag neutral">正常</span>`}</span>
    </button>
  `;
}

function boardFlagClass(flag) {
  if (["超期", "高风险"].includes(flag)) return "danger";
  if (["阻塞", "返工", "待WO"].includes(flag)) return "warn";
  if (flag === "待确认") return "";
  return "neutral";
}

function renderBoardSnapshot(projectId) {
  state.boardSelectedProjectId = projectId || null;
  renderBoardProjectList(projectId);
  const project = state.boardProjects.find((item) => item.id === projectId);
  if (!project) {
    $("#boardSnapshot").innerHTML = `<div class="empty">请选择一个项目查看快照</div>`;
    return;
  }
  const canOpenLibrary = userHasRole("pm");
  const pendingRows = [
    ["交付文件", project.pending_deliverables],
    ["完成说明", project.pending_completions],
    ["改期申请", project.pending_due_date_requests],
    ["风险关闭", project.pending_risk_reviews],
  ];
  $("#boardSnapshot").innerHTML = `
    <div class="board-snapshot-head">
      <div>
        <h3>${escapeHtml(project.current_number || project.intake_no || "")}</h3>
        <p>${escapeHtml(project.equipment_name || project.project_name || "")}</p>
      </div>
      <span class="status-pill ${BOARD_STATUS_CLASS[project.board_status] || "neutral"}">${escapeHtml(project.board_status_label)}</span>
    </div>
    <dl class="board-snapshot-grid">
      <dt>客户/工厂</dt>
      <dd>${escapeHtml(project.customer_name || "")}${project.site_name ? ` · ${escapeHtml(project.site_name)}` : ""}</dd>
      <dt>产品/产线</dt>
      <dd>${escapeHtml(project.project_group_name || "未关联")}</dd>
      <dt>当前阶段</dt>
      <dd>${escapeHtml(project.status_name || workbenchAreaName(project.workbench_area))}</dd>
      <dt>当前责任人</dt>
      <dd>${escapeHtml(project.current_owner || "未指定")}</dd>
      <dt>下一步动作</dt>
      <dd>${escapeHtml(project.next_action || "未设置")}</dd>
      <dt>Due Date</dt>
      <dd class="${dueClass(project.current_due_date || project.expected_delivery_date || "")}">${escapeHtml(project.current_due_date || project.expected_delivery_date || "未设置")}</dd>
    </dl>
    <div class="board-snapshot-metrics">
      <div><span>${escapeHtml(project.task_done || 0)}/${escapeHtml(project.task_total || 0)}</span><small>任务</small></div>
      <div><span>${escapeHtml(project.open_issues || 0)}</span><small>打开风险</small></div>
      <div><span>${escapeHtml(project.pending_total || 0)}</span><small>待确认</small></div>
    </div>
    <section class="board-snapshot-section">
      <h4>待处理摘要</h4>
      <div class="board-pending-list">
        ${pendingRows.map(([label, count]) => `
          <span class="${count ? "active" : ""}">${escapeHtml(label)} <strong>${escapeHtml(count || 0)}</strong></span>
        `).join("")}
      </div>
    </section>
    <div class="board-snapshot-actions">
      <button type="button" data-board-action="open-workbench" data-project-id="${escapeHtml(project.id)}">进入项目执行</button>
      ${canOpenLibrary ? `<button type="button" class="secondary" data-board-action="open-library" data-project-id="${escapeHtml(project.id)}">资料库详情</button>` : ""}
    </div>
  `;
  bindBoardSnapshotActions();
}

function bindBoardSnapshotActions() {
  $("#boardSnapshot").querySelectorAll("[data-board-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const projectId = button.dataset.projectId;
      try {
        if (button.dataset.boardAction === "open-workbench") {
          switchView("workbench", false);
          await loadWorkbenchProjects(projectId);
        }
        if (button.dataset.boardAction === "open-library") {
          await openDetail(projectId);
        }
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}
