const state = {
  bootstrap: null,
  projects: [],
  workbenchProjects: [],
  workbenchTasks: [],
  workbenchInbox: null,
  workbenchMode: "projects",
  workbenchProjectId: null,
  visibleColumns: [],
  sort: { key: "created_at", direction: "desc" },
  detailLastFocused: null,
};

const $ = (selector) => document.querySelector(selector);
const AUTO_CAPITALIZE_FIELDS = new Set([
  "customer_group_name",
  "customer_name",
  "site_name",
  "project_group_name",
  "department",
  "contact_name",
  "po_customer_name",
  "equipment_name",
  "project_name",
]);
const ACRONYMS = new Set(["abc", "dcps", "eolt", "fat", "mty", "npi", "po", "qa", "rfq", "sbd"]);
const COLUMN_STORAGE_KEY = "customerProject.visibleColumns.v1";
const WORKBENCH_OWNER_STORAGE_KEY = "customerProject.workbenchOwner.v1";
const WORKBENCH_ROLE_STORAGE_KEY = "customerProject.workbenchRole.v1";
const WORKBENCH_TASK_TEMPLATES = {
  inq: {
    name: "INQ前期支持",
    note: "方案、风险、报价前输入",
    items: [
      { title: "澄清客户需求", work_package: "前期方案", phase_code: "clarification", offset_days: 2, requires_deliverable: false },
      { title: "输出大致方案", work_package: "前期方案", phase_code: "rough_solution", offset_days: 3, requires_deliverable: true },
      { title: "评估技术风险", work_package: "前期方案", phase_code: "rough_solution", offset_days: 3, requires_deliverable: false },
      { title: "提供内部报价输入", work_package: "报价支持", phase_code: "quote_support", offset_days: 4, requires_deliverable: true },
      { title: "确认客户报价资料", work_package: "报价支持", phase_code: "quote_support", offset_days: 5, requires_deliverable: true },
    ],
  },
  wo: {
    name: "WO执行",
    note: "设计、BOM、采购、装配、调试",
    items: [
      { title: "细化方案确认", work_package: "项目管理", phase_code: "wo_kickoff", offset_days: 2, requires_deliverable: true },
      { title: "机械设计", work_package: "机械设计", phase_code: "detailed_design", offset_days: 7, requires_deliverable: true },
      { title: "电气设计", work_package: "电气设计", phase_code: "detailed_design", offset_days: 7, requires_deliverable: true },
      { title: "BOM输出与确认", work_package: "BOM/采购", phase_code: "bom_purchase", offset_days: 10, requires_deliverable: true },
      { title: "采购/来料跟进", work_package: "BOM/采购", phase_code: "bom_purchase", offset_days: 14, requires_deliverable: false },
      { title: "装配", work_package: "装配", phase_code: "assembly", offset_days: 18, requires_deliverable: false },
      { title: "接线", work_package: "接线", phase_code: "wiring_debug", offset_days: 20, requires_deliverable: false },
      { title: "调试", work_package: "调试", phase_code: "wiring_debug", offset_days: 23, requires_deliverable: true },
      { title: "验收资料", work_package: "验收", phase_code: "acceptance_delivery", offset_days: 26, requires_deliverable: true },
      { title: "发货资料", work_package: "发货", phase_code: "acceptance_delivery", offset_days: 28, requires_deliverable: true },
      { title: "项目关闭归档", work_package: "关闭归档", phase_code: "closed", offset_days: 30, requires_deliverable: false },
    ],
  },
};
const DEFAULT_PROJECT_COLUMNS = [
  "intake_no",
  "customer_name",
  "site_name",
  "project_group_name",
  "contact_name",
  "project_nature",
  "project_name",
  "status_name",
  "current_status_date",
  "markers",
];
const PROJECT_COLUMNS = [
  { key: "intake_no", label: "编号", sort: "current_number", render: projectIdentifierHtml },
  { key: "customer_group_name", label: "客户集团", sort: "customer_group_name", render: (project) => escapeHtml(project.customer_group_name || "") },
  { key: "customer_name", label: "法人主体", sort: "customer_name", render: (project) => escapeHtml(project.customer_name || "") },
  { key: "site_name", label: "工厂", sort: "site_name", render: (project) => escapeHtml(project.site_name || "") },
  { key: "project_group_name", label: "产品", sort: "project_group_name", render: (project) => escapeHtml(project.project_group_name || "") },
  { key: "department", label: "部门", sort: "department", render: (project) => escapeHtml(project.department || "") },
  { key: "contact_name", label: "联系人", sort: "contact_name", render: (project) => escapeHtml(project.contact_name || "") },
  { key: "project_nature", label: "性质", sort: "project_nature", render: (project) => escapeHtml(project.project_nature || "新设备") },
  { key: "project_name", label: "项目名", sort: "project_name", render: projectNameHtml },
  { key: "status_name", label: "状态", sort: "status_name", render: (project) => escapeHtml(project.status_name || "") },
  { key: "current_status_date", label: "日期", sort: "current_status_date", render: (project) => escapeHtml(statusDateValue(project)) },
  { key: "currency_code", label: "币种", sort: "currency_code", render: (project) => escapeHtml(project.currency_code || "") },
  { key: "file_count", label: "文件", sort: "file_count", render: (project) => escapeHtml(project.file_count || 0) },
  { key: "markers", label: "标记", sort: "markers", render: markersHtml },
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  const region = $("#toastRegion") || document.body;
  const node = document.createElement("div");
  node.className = "toast";
  node.setAttribute("role", "status");
  node.textContent = message;
  region.appendChild(node);
  setTimeout(() => node.remove(), 2600);
}

function debounce(callback, delay = 300) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), delay);
  };
}

function closeDetailPane({ restoreFocus = true } = {}) {
  const pane = $("#detailPane");
  const backdrop = $("#detailBackdrop");
  pane.hidden = true;
  if (backdrop) backdrop.hidden = true;
  pane.setAttribute("aria-modal", "false");
  if (restoreFocus && state.detailLastFocused instanceof HTMLElement && document.contains(state.detailLastFocused)) {
    state.detailLastFocused.focus();
  }
}

function showDetailPane() {
  const pane = $("#detailPane");
  const backdrop = $("#detailBackdrop");
  state.detailLastFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  if (backdrop) backdrop.hidden = false;
  pane.hidden = false;
  pane.setAttribute("aria-modal", "true");
  pane.focus();
}

function confirmProjectDeletion() {
  const dialog = $("#deleteProjectDialog");
  if (!dialog || typeof dialog.showModal !== "function") {
    const keepFiles = confirm("是否保留项目资料文件夹？\n\n确定：保留资料，只删除系统记录。\n取消：不保留资料，继续确认删除项目文件夹。");
    if (keepFiles) return Promise.resolve({ confirmed: true, deleteFiles: false });
    const deleteFiles = confirm("你选择不保留资料。确认永久删除这个项目文件夹吗？");
    return Promise.resolve({ confirmed: deleteFiles, deleteFiles });
  }

  return new Promise((resolve) => {
    let result = { confirmed: false, deleteFiles: false };
    const cancelButton = $("#deleteCancelButton");
    const keepButton = $("#deleteKeepFilesButton");
    const deleteButton = $("#deleteWithFilesButton");
    const cleanup = () => {
      cancelButton.removeEventListener("click", onCancel);
      keepButton.removeEventListener("click", onKeep);
      deleteButton.removeEventListener("click", onDelete);
      dialog.removeEventListener("close", onClose);
      dialog.removeEventListener("cancel", onCancel);
    };
    const closeWith = (nextResult) => {
      result = nextResult;
      if (dialog.open) dialog.close();
    };
    const onCancel = (event) => {
      event?.preventDefault();
      closeWith({ confirmed: false, deleteFiles: false });
    };
    const onKeep = () => {
      closeWith({ confirmed: true, deleteFiles: false });
    };
    const onDelete = () => {
      closeWith({ confirmed: true, deleteFiles: true });
    };
    const onClose = () => {
      cleanup();
      resolve(result);
    };
    cancelButton.addEventListener("click", onCancel);
    keepButton.addEventListener("click", onKeep);
    deleteButton.addEventListener("click", onDelete);
    dialog.addEventListener("cancel", onCancel);
    dialog.addEventListener("close", onClose);
    dialog.showModal();
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "请求失败");
  }
  return payload;
}

function isWorkbenchFocusMode() {
  return new URLSearchParams(window.location.search).get("view") === "workbench";
}

function initialWorkbenchProjectId() {
  return new URLSearchParams(window.location.search).get("project") || null;
}

function openWorkbenchWindow(projectId = "") {
  const params = new URLSearchParams({ view: "workbench" });
  if (projectId) params.set("project", projectId);
  const popup = window.open(
    `/?${params.toString()}`,
    "customerProjectWorkbench",
    "width=1480,height=920,menubar=no,toolbar=no,location=no,status=no",
  );
  if (popup) {
    popup.focus();
    return true;
  }
  return false;
}

async function uploadApi(path, formData) {
  const response = await fetch(path, {
    method: "POST",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "上传失败");
  }
  return payload;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function smartCapitalize(value) {
  return String(value || "").replace(/\b([A-Za-z][A-Za-z0-9-]*)\b/g, (word) => {
    const lower = word.toLowerCase();
    if (ACRONYMS.has(lower)) return word.toUpperCase();
    return word.charAt(0).toUpperCase() + word.slice(1);
  });
}

function normalizeTextInputs(form) {
  AUTO_CAPITALIZE_FIELDS.forEach((name) => {
    const input = form.elements[name];
    if (input && typeof input.value === "string") {
      input.value = smartCapitalize(input.value.trim());
    }
  });
}

function loadVisibleColumns() {
  try {
    const saved = JSON.parse(localStorage.getItem(COLUMN_STORAGE_KEY) || "[]");
    const validKeys = new Set(PROJECT_COLUMNS.map((column) => column.key));
    const visible = Array.isArray(saved) ? saved.filter((key) => validKeys.has(key)) : [];
    if (visible.length) return visible;
  } catch (error) {
    console.warn("Column preference ignored", error);
  }
  return [...DEFAULT_PROJECT_COLUMNS];
}

function saveVisibleColumns() {
  localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(state.visibleColumns));
}

function visibleProjectColumns() {
  const visible = state.visibleColumns.length ? state.visibleColumns : DEFAULT_PROJECT_COLUMNS;
  const visibleSet = new Set(visible);
  return PROJECT_COLUMNS.filter((column) => visibleSet.has(column.key));
}

function renderColumnPicker() {
  const options = $("#columnOptions");
  if (!options) return;
  const visibleSet = new Set(state.visibleColumns.length ? state.visibleColumns : DEFAULT_PROJECT_COLUMNS);
  options.innerHTML = PROJECT_COLUMNS.map(
    (column) => `
      <label class="column-option">
        <input type="checkbox" name="project_column" value="${escapeHtml(column.key)}"${visibleSet.has(column.key) ? " checked" : ""} />
        ${escapeHtml(column.label)}
      </label>
    `,
  ).join("");
}

function switchView(view, refresh = true) {
  const isCreate = view === "create";
  const isWorkbench = view === "workbench";
  const isLibrary = view === "library";
  $("#entryView").hidden = !isCreate;
  $("#libraryView").hidden = !isLibrary;
  $("#workbenchView").hidden = !isWorkbench;
  $("#navCreateButton").classList.toggle("active", isCreate);
  $("#navLibraryButton").classList.toggle("active", isLibrary);
  $("#navWorkbenchButton").classList.toggle("active", isWorkbench);
  if (isWorkbench) {
    closeDetailPane({ restoreFocus: false });
  }
  if (isLibrary && refresh) {
    loadProjects().catch(console.error);
  }
  if (isWorkbench && refresh) {
    loadWorkbench().catch(console.error);
  }
}

async function loadBootstrap() {
  state.bootstrap = await api("/api/bootstrap");
  $("#projectRootPath").value = state.bootstrap.settings.project_root_path || "";

  const statusOptions = state.bootstrap.statuses
    .map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`)
    .join("");
  $("#statusSelect").innerHTML = statusOptions;
  $("#filterStatus").innerHTML =
    `<option value="">全部状态</option>` + statusOptions;

  $("#currencySelect").innerHTML = state.bootstrap.currencies
    .map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.code)} · ${escapeHtml(item.name)}</option>`)
    .join("");
  $("#projectNatureSelect").innerHTML = projectNatureOptions("新设备");

  $("#customerGroupOptions").innerHTML = state.bootstrap.customer_groups
    .map((item) => `<option value="${escapeHtml(item.name)}"></option>`)
    .join("");
  $("#customerOptions").innerHTML = state.bootstrap.customers
    .map((item) => `<option value="${escapeHtml(item.name)}"></option>`)
    .join("");
  $("#siteOptions").innerHTML = state.bootstrap.sites
    .map((item) => `<option value="${escapeHtml(item.name)}"></option>`)
    .join("");
  $("#projectGroupOptions").innerHTML = state.bootstrap.project_groups
    .map((item) => `<option value="${escapeHtml(item.name)}"></option>`)
    .join("");
  $("#contactOptions").innerHTML = state.bootstrap.contacts
    .map((item) => `<option value="${escapeHtml(item.name)}"></option>`)
    .join("");
  $("#filterGroup").innerHTML =
    `<option value="">全部集团</option>` +
    state.bootstrap.customer_groups
      .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`)
      .join("");
  $("#filterSite").innerHTML =
    `<option value="">全部工厂/站点</option>` +
    state.bootstrap.sites
      .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`)
      .join("");

  bindStatusDateControl($("#projectForm"), true);
}

async function loadProjects() {
  const params = new URLSearchParams();
  const search = $("#searchInput").value.trim();
  const status = $("#filterStatus").value;
  const group = $("#filterGroup").value;
  const site = $("#filterSite").value;
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (group) params.set("group_id", group);
  if (site) params.set("site_id", site);
  if ($("#filterNeedsEquipment").checked) params.set("needs_equipment", "1");
  const payload = await api(`/api/projects?${params.toString()}`);
  state.projects = payload.projects;
  renderKpis(payload.kpis || {});
  renderProjects();
}

function renderKpis(kpis) {
  $("#kpiTotal").textContent = kpis.total_projects || 0;
  $("#kpiNoEquipment").textContent = kpis.no_equipment_no || 0;
  $("#kpiPo").textContent = kpis.with_po || 0;
  $("#kpiModel").textContent = kpis.with_model || 0;
}

function sortableValue(project, key) {
  if (key === "file_count") return Number(project.file_count || 0);
  if (key === "current_number") return projectCurrentNumber(project);
  if (key === "project_name") return [project.equipment_name || "", project.project_name || ""].join(" ");
  if (key === "current_status_date") return statusDateValue(project);
  if (key === "markers") {
    return [project.has_po ? "PO" : "", project.has_3d_model ? "模型" : "", !project.equipment_no ? "待补WO号" : ""].join(" ");
  }
  return String(project[key] ?? "").toLocaleLowerCase("zh-CN");
}

function sortedProjects() {
  const { key, direction } = state.sort;
  const factor = direction === "asc" ? 1 : -1;
  return [...state.projects].sort((a, b) => {
    const left = sortableValue(a, key);
    const right = sortableValue(b, key);
    if (typeof left === "number" && typeof right === "number") return (left - right) * factor;
    return String(left).localeCompare(String(right), "zh-CN", { numeric: true }) * factor;
  });
}

function updateSortHeaders() {
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    const active = th.dataset.sort === state.sort.key;
    th.classList.toggle("sorted", active);
    th.setAttribute("aria-sort", active ? (state.sort.direction === "asc" ? "ascending" : "descending") : "none");
    const arrow = active ? (state.sort.direction === "asc" ? " ↑" : " ↓") : "";
    th.querySelector(".sort-indicator").textContent = arrow;
  });
}

function renderTableHead(columns) {
  $("#projectTableHead").innerHTML = columns
    .map(
      (column) => `
        <th data-sort="${escapeHtml(column.sort || column.key)}">
          ${escapeHtml(column.label)}<span class="sort-indicator"></span>
        </th>
      `,
    )
    .join("");
  updateSortHeaders();
}

function projectIdentifierHtml(project) {
  const phase = project.equipment_no ? "WO工程执行" : "前期支持 · 待开WO";
  return `<div class="identifier"><span>${escapeHtml(projectCurrentNumber(project))}</span><small class="subtext">${phase}</small></div>`;
}

function projectCurrentNumber(project) {
  return project.equipment_no || project.intake_no || "";
}

function projectNumberStage(project) {
  return project.equipment_no ? "WO工程执行" : "INQ前期支持";
}

function projectNameHtml(project) {
  const related = project.related_legacy_no
    ? `<div class="subtext">关联 ${escapeHtml(project.related_legacy_no)}</div>`
    : "";
  return `${escapeHtml(project.equipment_name)}<div class="subtext">${escapeHtml(project.project_name || "")}</div>${related}`;
}

function markersHtml(project) {
  const markers = [
    project.has_po ? `<span class="tag">PO</span>` : "",
    project.has_3d_model ? `<span class="tag">模型</span>` : "",
    project.project_nature && project.project_nature !== "新设备" ? `<span class="tag neutral">${escapeHtml(project.project_nature)}</span>` : "",
    !project.equipment_no ? `<span class="tag warn">待补WO号</span>` : "",
  ].join(" ");
  return markers || `<span class="tag neutral">普通</span>`;
}

function renderProjects(projects = sortedProjects()) {
  const tbody = $("#projectRows");
  const columns = visibleProjectColumns();
  renderTableHead(columns);
  if (!projects.length) {
    tbody.innerHTML = `<tr><td colspan="${columns.length || 1}" class="empty">暂无项目</td></tr>`;
    return;
  }
  tbody.innerHTML = projects
    .map((project) => {
      return `
        <tr class="project-row" data-id="${escapeHtml(project.id)}" tabindex="0">
          ${columns.map((column) => `<td data-column="${escapeHtml(column.key)}">${column.render(project)}</td>`).join("")}
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll(".project-row").forEach((row) => {
    row.addEventListener("click", () => openDetail(row.dataset.id));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDetail(row.dataset.id);
      }
    });
  });
}

function selectOptions(items, selectedValue, label = (item) => item.name) {
  return items
    .map((item) => {
      const selected = item.code === selectedValue || item.id === selectedValue ? " selected" : "";
      const value = item.code || item.id || "";
      return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(label(item))}</option>`;
    })
    .join("");
}

function roleOptions(selectedValue) {
  const roles = ["", "工程师", "项目经理", "采购", "维护", "NPI", "其他"];
  return roles
    .map((role) => {
      const selected = role === (selectedValue || "") ? " selected" : "";
      return `<option value="${escapeHtml(role)}"${selected}>${escapeHtml(role || "未选择")}</option>`;
    })
    .join("");
}

function projectNatureOptions(selectedValue) {
  const natures = state.bootstrap?.project_natures || ["新设备", "老设备改造", "夹具/治具", "备件/耗材", "售后/服务", "纯方案/报价", "其他"];
  return natures
    .map((nature) => {
      const selected = nature === (selectedValue || "新设备") ? " selected" : "";
      return `<option value="${escapeHtml(nature)}"${selected}>${escapeHtml(nature)}</option>`;
    })
    .join("");
}

function statusDateLabel(statusCode) {
  return state.bootstrap?.status_date_labels?.[statusCode] || "状态日期";
}

function statusDateValue(project) {
  return project.current_status_date || project.status_date || "";
}

function bindStatusDateControl(form, fillWhenEmpty = false) {
  const statusSelect = form.elements.status_code;
  const dateInput = form.elements.status_date;
  const label = form.querySelector("[data-status-date-label]");
  if (!statusSelect || !dateInput || !label) return;
  const refresh = () => {
    label.textContent = statusDateLabel(statusSelect.value);
    if (fillWhenEmpty && !dateInput.value) {
      dateInput.value = today();
    }
  };
  if (!statusSelect.dataset.statusDateBound) {
    statusSelect.addEventListener("change", refresh);
    statusSelect.dataset.statusDateBound = "1";
  }
  refresh();
}

async function openDetail(projectId) {
  const payload = await api(`/api/projects/${encodeURIComponent(projectId)}`);
  const { project, files, shared_files: sharedFiles = [], events } = payload;
  const sharedButtons = project.project_group_id
    ? `
      <button type="button" class="secondary" data-action="open-shared-folder" data-id="${escapeHtml(project.id)}">打开共享资料</button>
    `
    : "";
  const sharedScanButton = project.project_group_id
    ? `<button type="button" class="secondary" data-action="scan-shared-folder" data-id="${escapeHtml(project.id)}">扫描共享资料</button>`
    : "";
  $("#detailContent").innerHTML = `
    <div class="detail-actions">
      <button type="button" data-action="open-folder" data-id="${escapeHtml(project.id)}">打开项目文件夹</button>
      <button type="button" class="secondary" data-action="open-workbench" data-id="${escapeHtml(project.id)}">打开项目执行</button>
      <button type="button" class="secondary" data-action="copy-path" data-path="${escapeHtml(project.project_folder_path || "")}">复制路径</button>
      ${sharedButtons}
    </div>
    <div class="scan-toolbar">
      <div>
        <strong>文件扫描</strong>
        <span>把资料放入对应文件夹后，在这里更新文件索引和文件标记。</span>
      </div>
      <div class="scan-buttons">
        <button type="button" data-action="scan-folder" data-id="${escapeHtml(project.id)}">扫描项目文件</button>
        ${sharedScanButton}
      </div>
    </div>
    <dl class="detail-grid">
      <dt>当前编号</dt><dd>${escapeHtml(projectCurrentNumber(project))}</dd>
      <dt>编号阶段</dt><dd>${escapeHtml(projectNumberStage(project))}</dd>
      <dt>项目性质</dt><dd>${escapeHtml(project.project_nature || "新设备")}</dd>
      <dt>关联原项目/原WO号</dt><dd>${escapeHtml(project.related_legacy_no || "未填写")}</dd>
      <dt>客户集团</dt><dd>${escapeHtml(project.customer_group_name || "未填写")}</dd>
      <dt>客户公司/法人主体</dt><dd>${escapeHtml(project.customer_name)}</dd>
      <dt>工厂/站点</dt><dd>${escapeHtml(project.site_name || "未填写")}</dd>
      <dt>客户产品/生产线</dt><dd>${escapeHtml(project.project_group_name || "未关联")}</dd>
      <dt>共享资料目录</dt><dd>${escapeHtml(project.shared_folder_path || "无")}</dd>
      <dt>部门/业务单元</dt><dd>${escapeHtml(project.department || "未填写")}</dd>
      <dt>项目来源角色</dt><dd>${escapeHtml(project.origin_role || "未填写")}</dd>
      <dt>PO/采购主体</dt><dd>${escapeHtml(project.po_customer_name || project.customer_name)}</dd>
      <dt>联系人</dt><dd>${escapeHtml(project.contact_name || "未填写")}</dd>
      <dt>项目/设备/夹具</dt><dd>${escapeHtml(project.equipment_name)}</dd>
      <dt>状态</dt><dd>${escapeHtml(project.status_name)}</dd>
      <dt>状态日期</dt><dd>${escapeHtml(project.status_date_label || "状态日期")}：${escapeHtml(statusDateValue(project) || "未填写")}</dd>
      <dt>询价日期</dt><dd>${escapeHtml(project.inquiry_date || "未填写")}</dd>
      <dt>预计交期</dt><dd>${escapeHtml(project.expected_delivery_date || "未填写")}</dd>
      <dt>币种</dt><dd>${escapeHtml(project.currency_code)}</dd>
      <dt>项目目录</dt><dd>${escapeHtml(project.project_folder_path || "")}</dd>
      <dt>备注</dt><dd>${escapeHtml(project.notes || "")}</dd>
    </dl>
    <details class="edit-block">
      <summary>编辑基础信息</summary>
      <form id="detailEditForm" class="project-form compact-form">
        <input type="hidden" name="inquiry_date" value="${escapeHtml(project.inquiry_date || "")}" />
        <input type="hidden" name="quote_date" value="${escapeHtml(project.quote_date || "")}" />
        <input type="hidden" name="po_date" value="${escapeHtml(project.po_date || "")}" />
        <input type="hidden" name="actual_ship_date" value="${escapeHtml(project.actual_ship_date || "")}" />
        <div class="grid two">
          <label>
            客户集团
            <input name="customer_group_name" list="customerGroupOptions" value="${escapeHtml(project.customer_group_name || "")}" />
          </label>
          <label>
            客户公司/法人主体 *
            <input name="customer_name" list="customerOptions" value="${escapeHtml(project.customer_name || "")}" required />
          </label>
        </div>
        <div class="grid three">
          <label>
            工厂/站点
            <input name="site_name" list="siteOptions" value="${escapeHtml(project.site_name || "")}" />
          </label>
          <label>
            客户产品/生产线
            <input name="project_group_name" list="projectGroupOptions" value="${escapeHtml(project.project_group_name || "")}" />
          </label>
          <label>
            部门/业务单元
            <input name="department" value="${escapeHtml(project.department || "")}" />
          </label>
          <label>
            项目来源角色
            <select name="origin_role">${roleOptions(project.origin_role)}</select>
          </label>
        </div>
        <div class="grid two">
          <label>
            联系人
            <input name="contact_name" list="contactOptions" value="${escapeHtml(project.contact_name || "")}" />
          </label>
          <label>
            PO/采购主体
            <input name="po_customer_name" list="customerOptions" value="${escapeHtml(project.po_customer_name || project.customer_name || "")}" />
          </label>
        </div>
        <div class="grid two">
          <label>
            项目/设备/夹具名称 *
            <input name="equipment_name" value="${escapeHtml(project.equipment_name || "")}" required />
          </label>
          <label>
            项目性质
            <select name="project_nature">${projectNatureOptions(project.project_nature)}</select>
          </label>
        </div>
        <div class="grid two">
          <label>
            关联原项目/原WO号
            <input name="related_legacy_no" value="${escapeHtml(project.related_legacy_no || "")}" />
          </label>
          <label>
            WO号/内部设备号
            <input name="equipment_no" value="${escapeHtml(project.equipment_no || "")}" />
          </label>
        </div>
        <div class="grid three">
          <label>
            状态
            <select name="status_code">${selectOptions(state.bootstrap.statuses, project.status_code)}</select>
          </label>
          <label>
            币种
            <select name="currency_code">${selectOptions(state.bootstrap.currencies, project.currency_code, (item) => `${item.code} · ${item.name}`)}</select>
          </label>
          <label>
            <span data-status-date-label>${escapeHtml(project.status_date_label || "状态日期")}</span>
            <input name="status_date" type="date" value="${escapeHtml(statusDateValue(project))}" />
          </label>
        </div>
        <div class="grid two">
          <label>
            预计交期
            <input name="expected_delivery_date" type="date" value="${escapeHtml(project.expected_delivery_date || "")}" />
          </label>
          <label>
            项目名称
            <input name="project_name" value="${escapeHtml(project.project_name || "")}" />
          </label>
        </div>
        <label>
          备注
          <textarea name="notes" rows="3">${escapeHtml(project.notes || "")}</textarea>
        </label>
        <div class="actions">
          <button type="submit">保存修改</button>
          <button type="button" class="danger" data-action="delete-project" data-id="${escapeHtml(project.id)}">删除项目记录</button>
        </div>
      </form>
    </details>
    <h3>共享资料</h3>
    <div class="file-list">
      ${
        project.project_group_id
          ? sharedFiles.length
            ? sharedFiles
                .map(
                  (file) => `
                    <div class="file-item">
                      <strong>${escapeHtml(file.current_name)}</strong>
                    </div>
                  `,
                )
                .join("")
            : `<div class="empty">暂无共享文件。把共用资料放入 00_共享资料 后点击“扫描共享资料”。</div>`
          : `<div class="empty">未关联客户产品/生产线，当前项目没有共享资料层。</div>`
      }
    </div>
    <h3>文件</h3>
    <div class="file-list">
      ${
        files.length
          ? files
              .map(
                (file) => `
                  <div class="file-item">
                    <strong>${escapeHtml(file.current_name)}</strong>
                  </div>
                `,
              )
              .join("")
          : `<div class="empty">暂无文件</div>`
      }
    </div>
    <h3>时间线</h3>
    <div class="file-list">
      ${
        events.length
          ? events
              .map(
                (event) => `
                  <div class="file-item">
                    <strong>${escapeHtml(event.title)}</strong>
                    <div class="subtext">${escapeHtml(event.created_at)} · ${escapeHtml(event.detail || "")}</div>
                  </div>
                `,
              )
              .join("")
          : `<div class="empty">暂无事件</div>`
      }
    </div>
  `;
  bindDetailActions(project);
  showDetailPane();
}

function bindDetailActions(project) {
  const projectId = project.id;
  const editForm = $("#detailEditForm");
  if (editForm) {
    bindStatusDateControl(editForm);
    editForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      button.disabled = true;
      try {
        const previousEquipmentNo = (project.equipment_no || "").trim();
        const payload = formToPayload(editForm);
        const nextEquipmentNo = (payload.equipment_no || "").trim();
        await api(`/api/projects/${encodeURIComponent(projectId)}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        if (nextEquipmentNo && nextEquipmentNo !== previousEquipmentNo) {
          const shouldRename = confirm(`已填写 WO号 ${nextEquipmentNo}，是否将项目文件夹重命名为 WO号？`);
          if (shouldRename) {
            const result = await api(`/api/projects/${encodeURIComponent(projectId)}/rename-folder`, {
              method: "POST",
              body: "{}",
            });
            showToast(result.renamed ? "项目已更新，文件夹已重命名为WO号" : result.message || "项目已更新");
          } else {
            showToast("项目已更新，文件夹名称保留不变");
          }
        } else {
          showToast("项目已更新");
        }
        await loadBootstrap();
        await loadProjects();
        await openDetail(projectId);
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  }
  $("#detailContent").querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      try {
        if (action === "open-folder") {
          await api(`/api/projects/${encodeURIComponent(projectId)}/open-folder`, { method: "POST", body: "{}" });
          showToast("已打开项目文件夹");
        }
        if (action === "scan-folder") {
          button.disabled = true;
          const result = await api(`/api/projects/${encodeURIComponent(projectId)}/scan`, { method: "POST", body: "{}" });
          showToast(`扫描完成：新增 ${result.new_files} 个文件`);
          await loadProjects();
          await openDetail(projectId);
        }
        if (action === "open-shared-folder") {
          await api(`/api/projects/${encodeURIComponent(projectId)}/open-shared-folder`, { method: "POST", body: "{}" });
          showToast("已打开共享资料文件夹");
        }
        if (action === "scan-shared-folder") {
          button.disabled = true;
          const result = await api(`/api/projects/${encodeURIComponent(projectId)}/scan-shared`, { method: "POST", body: "{}" });
          showToast(`共享资料扫描完成：新增 ${result.new_files} 个文件`);
          await openDetail(projectId);
        }
        if (action === "copy-path") {
          await navigator.clipboard.writeText(button.dataset.path || "");
          showToast("项目路径已复制");
        }
        if (action === "delete-project") {
          const decision = await confirmProjectDeletion();
          if (!decision.confirmed) return;
          const result = await api(`/api/projects/${encodeURIComponent(projectId)}`, {
            method: "DELETE",
            body: JSON.stringify({ delete_files: decision.deleteFiles }),
          });
          showToast(result.folder_deleted ? "项目记录和资料文件夹已删除" : "项目记录已删除，资料已保留");
          closeDetailPane({ restoreFocus: false });
          await loadBootstrap();
          await loadProjects();
        }
        if (action === "open-workbench") {
          closeDetailPane({ restoreFocus: false });
          if (isWorkbenchFocusMode() || !openWorkbenchWindow(projectId)) {
            switchView("workbench", false);
            await loadWorkbenchProjects(projectId);
          }
        }
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });
}

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

function formToPayload(form) {
  normalizeTextInputs(form);
  const data = new FormData(form);
  return Object.fromEntries(data.entries());
}

async function createProject(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = event.submitter;
  button.disabled = true;
  $("#formStatus").textContent = "正在创建...";
  try {
    const payload = formToPayload(form);
    const result = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast(`项目已创建：INQ ${result.intake_no}`);
    form.reset();
    bindStatusDateControl(form, true);
    await loadBootstrap();
    await loadProjects();
    switchView("library", false);
    await openDetail(result.id);
    $("#formStatus").textContent = "一条项目对应一台设备/夹具/具体工程对象；能归属客户产品时，优先填写客户产品/生产线";
  } catch (error) {
    $("#formStatus").textContent = error.message;
    showToast(error.message);
  } finally {
    button.disabled = false;
  }
}

async function saveSettings() {
  const projectRootPath = $("#projectRootPath").value.trim();
  await api("/api/settings", {
    method: "PATCH",
    body: JSON.stringify({ project_root_path: projectRootPath }),
  });
  showToast("配置已保存");
  await loadBootstrap();
}

function bindEvents() {
  const debouncedLoadProjects = debounce(() => loadProjects().catch(console.error), 300);
  $("#projectForm").addEventListener("submit", createProject);
  document.addEventListener("focusout", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement && AUTO_CAPITALIZE_FIELDS.has(target.name)) {
      target.value = smartCapitalize(target.value.trim());
    }
  });
  document.addEventListener("keydown", (event) => {
    const deleteDialog = $("#deleteProjectDialog");
    const columnPicker = document.querySelector(".column-picker");
    if (event.key === "Escape" && columnPicker?.open) {
      columnPicker.open = false;
      return;
    }
    if (event.key === "Escape" && !$("#detailPane").hidden && !deleteDialog?.open) {
      closeDetailPane();
    }
  });
  document.addEventListener("click", (event) => {
    const columnPicker = document.querySelector(".column-picker");
    if (!columnPicker?.open) return;
    if (event.target instanceof Element && columnPicker.contains(event.target)) return;
    columnPicker.open = false;
  });
  $("#projectTableHead").addEventListener("click", (event) => {
    const th = event.target instanceof Element ? event.target.closest("th[data-sort]") : null;
    if (!th) return;
    const key = th.dataset.sort;
    if (state.sort.key === key) {
      state.sort.direction = state.sort.direction === "asc" ? "desc" : "asc";
    } else {
      state.sort = { key, direction: "asc" };
    }
    renderProjects();
  });
  $("#columnOptions").addEventListener("change", (event) => {
    if (event.target.name !== "project_column") return;
    const checked = Array.from($("#columnOptions").querySelectorAll("input:checked")).map((input) => input.value);
    if (!checked.length) {
      event.target.checked = true;
      showToast("至少保留一列");
      return;
    }
    state.visibleColumns = checked;
    saveVisibleColumns();
    renderProjects();
  });
  $("#resetColumnsButton").addEventListener("click", () => {
    state.visibleColumns = [...DEFAULT_PROJECT_COLUMNS];
    saveVisibleColumns();
    renderColumnPicker();
    renderProjects();
  });
  $("#navLibraryButton").addEventListener("click", () => switchView("library"));
  $("#navCreateButton").addEventListener("click", () => switchView("create"));
  $("#navWorkbenchButton").addEventListener("click", () => {
    if (isWorkbenchFocusMode() || !openWorkbenchWindow()) {
      switchView("workbench");
    }
  });
  $("#listCreateButton").addEventListener("click", () => switchView("create"));
  $("#backToLibraryButton").addEventListener("click", () => switchView("library"));
  $("#refreshButton").addEventListener("click", loadProjects);
  $("#workbenchRefreshButton").addEventListener("click", () => loadWorkbench().catch(console.error));
  $("#workbenchProjectsModeButton").addEventListener("click", () => {
    state.workbenchMode = "projects";
    loadWorkbench().catch(console.error);
  });
  $("#workbenchTasksModeButton").addEventListener("click", () => {
    state.workbenchMode = "tasks";
    loadWorkbench().catch(console.error);
  });
  $("#saveSettingsButton").addEventListener("click", saveSettings);
  $("#searchInput").addEventListener("input", debouncedLoadProjects);
  $("#filterGroup").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterSite").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterStatus").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterNeedsEquipment").addEventListener("change", () => loadProjects().catch(console.error));
  $("#workbenchSearchInput").addEventListener("input", debounce(() => loadWorkbench().catch(console.error), 300));
  $("#workbenchOwnerInput").addEventListener("input", debounce(() => {
    localStorage.setItem(WORKBENCH_OWNER_STORAGE_KEY, $("#workbenchOwnerInput").value.trim());
    loadWorkbench().catch(console.error);
  }, 300));
  $("#workbenchRoleSelect").addEventListener("change", () => {
    localStorage.setItem(WORKBENCH_ROLE_STORAGE_KEY, $("#workbenchRoleSelect").value);
    loadWorkbench().catch(console.error);
  });
  $("#workbenchViewFilter").addEventListener("change", () => loadWorkbench().catch(console.error));
  $("#closeDetailButton").addEventListener("click", () => {
    closeDetailPane();
  });
  $("#detailBackdrop").addEventListener("click", () => {
    closeDetailPane();
  });
}

async function boot() {
  state.visibleColumns = loadVisibleColumns();
  $("#workbenchOwnerInput").value = localStorage.getItem(WORKBENCH_OWNER_STORAGE_KEY) || "";
  const initialRole = new URLSearchParams(window.location.search).get("role") || localStorage.getItem(WORKBENCH_ROLE_STORAGE_KEY) || "engineer";
  $("#workbenchRoleSelect").value = initialRole === "pm" ? "pm" : "engineer";
  if (isWorkbenchFocusMode()) {
    document.body.classList.add("workbench-focus");
  }
  renderColumnPicker();
  bindEvents();
  await loadBootstrap();
  if (isWorkbenchFocusMode()) {
    switchView("workbench", false);
    await loadWorkbench(initialWorkbenchProjectId());
  } else {
    await loadProjects();
  }
}

boot().catch((error) => {
  showToast(error.message);
  console.error(error);
});
