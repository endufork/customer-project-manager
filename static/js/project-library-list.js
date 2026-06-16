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
  { key: "workbench_summary", label: "执行", sort: "workbench_summary", render: workbenchSummaryHtml },
  { key: "currency_code", label: "币种", sort: "currency_code", render: (project) => escapeHtml(project.currency_code || "") },
  { key: "file_count", label: "文件", sort: "file_count", render: (project) => escapeHtml(project.file_count || 0) },
  { key: "markers", label: "标记", sort: "markers", render: markersHtml },
];

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
  if (key === "workbench_summary") {
    return [
      Number(project.overdue_tasks || 0),
      Number(project.blocked_tasks || 0),
      Number(project.high_issues || 0),
      Number(project.submitted_tasks || 0),
      project.current_due_date || "",
      project.next_action || "",
    ].join(" ");
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
