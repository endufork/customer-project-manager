const state = {
  bootstrap: null,
  projects: [],
  sort: { key: "created_at", direction: "desc" },
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 2600);
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

function switchView(view, refresh = true) {
  const isCreate = view === "create";
  $("#entryView").hidden = !isCreate;
  $("#libraryView").hidden = isCreate;
  $("#navCreateButton").classList.toggle("active", isCreate);
  $("#navLibraryButton").classList.toggle("active", !isCreate);
  if (!isCreate && refresh) {
    loadProjects().catch(console.error);
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
  if (key === "markers") {
    return [project.has_po ? "PO" : "", project.has_3d_model ? "模型" : "", !project.equipment_no ? "待补内部设备号" : ""].join(" ");
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

function renderProjects(projects = sortedProjects()) {
  const tbody = $("#projectRows");
  updateSortHeaders();
  if (!projects.length) {
    tbody.innerHTML = `<tr><td colspan="14" class="empty">暂无项目</td></tr>`;
    return;
  }
  tbody.innerHTML = projects
    .map((project) => {
      const equipment = project.equipment_no
        ? `<small>设备号 ${escapeHtml(project.equipment_no)}</small>`
        : `<small class="subtext">待补内部设备号</small>`;
      const related = project.related_legacy_no
        ? `<div class="subtext">关联 ${escapeHtml(project.related_legacy_no)}</div>`
        : "";
      const markers = [
        project.has_po ? `<span class="tag">PO</span>` : "",
        project.has_3d_model ? `<span class="tag">模型</span>` : "",
        project.project_nature && project.project_nature !== "新设备" ? `<span class="tag neutral">${escapeHtml(project.project_nature)}</span>` : "",
        !project.equipment_no ? `<span class="tag warn">待补内部设备号</span>` : "",
      ].join(" ");
      return `
        <tr class="project-row" data-id="${escapeHtml(project.id)}">
          <td><div class="identifier">${escapeHtml(project.intake_no)}${equipment}</div></td>
          <td>${escapeHtml(project.customer_group_name || "")}</td>
          <td>${escapeHtml(project.customer_name || "")}</td>
          <td>${escapeHtml(project.site_name || "")}</td>
          <td>${escapeHtml(project.project_group_name || "")}</td>
          <td>${escapeHtml(project.department || "")}</td>
          <td>${escapeHtml(project.contact_name || "")}</td>
          <td>${escapeHtml(project.project_nature || "新设备")}</td>
          <td>${escapeHtml(project.equipment_name)}<div class="subtext">${escapeHtml(project.project_name || "")}</div>${related}</td>
          <td>${escapeHtml(project.status_name)}<div class="subtext">${escapeHtml(project.status_date_label || "状态日期")}</div></td>
          <td>${escapeHtml(statusDateValue(project))}</td>
          <td>${escapeHtml(project.currency_code)}</td>
          <td>${project.file_count || 0}</td>
          <td>${markers || `<span class="tag neutral">普通</span>`}</td>
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll(".project-row").forEach((row) => {
    row.addEventListener("click", () => openDetail(row.dataset.id));
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
      <dt>临时项目号</dt><dd>${escapeHtml(project.intake_no)}</dd>
      <dt>内部设备号</dt><dd>${escapeHtml(project.equipment_no || "待补充")}</dd>
      <dt>项目性质</dt><dd>${escapeHtml(project.project_nature || "新设备")}</dd>
      <dt>关联原项目/原设备号</dt><dd>${escapeHtml(project.related_legacy_no || "未填写")}</dd>
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
            关联原项目/原设备号
            <input name="related_legacy_no" value="${escapeHtml(project.related_legacy_no || "")}" />
          </label>
          <label>
            内部设备号
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
                      <div class="subtext">${escapeHtml(file.category_name)} · ${escapeHtml(file.extension || "")} · ${escapeHtml(file.file_path)}</div>
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
                    <div class="subtext">${escapeHtml(file.category_name)} · ${escapeHtml(file.extension || "")} · ${escapeHtml(file.file_path)}</div>
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
  bindDetailActions(project.id);
  $("#detailPane").hidden = false;
}

function bindDetailActions(projectId) {
  const editForm = $("#detailEditForm");
  if (editForm) {
    bindStatusDateControl(editForm);
    editForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      button.disabled = true;
      try {
        await api(`/api/projects/${encodeURIComponent(projectId)}`, {
          method: "PATCH",
          body: JSON.stringify(formToPayload(editForm)),
        });
        showToast("项目已更新");
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
          const ok = confirm("确定删除这个项目记录吗？");
          if (!ok) return;
          const keepFiles = confirm("是否保留项目资料文件夹？\n\n确定：保留资料，只删除系统记录。\n取消：不保留资料，继续确认删除项目文件夹。");
          let deleteFiles = false;
          if (!keepFiles) {
            deleteFiles = confirm("你选择不保留资料。确认永久删除这个项目文件夹吗？");
            if (!deleteFiles) return;
          }
          const result = await api(`/api/projects/${encodeURIComponent(projectId)}`, {
            method: "DELETE",
            body: JSON.stringify({ delete_files: deleteFiles }),
          });
          showToast(result.folder_deleted ? "项目记录和资料文件夹已删除" : "项目记录已删除，资料已保留");
          $("#detailPane").hidden = true;
          await loadBootstrap();
          await loadProjects();
        }
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });
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
    showToast(`项目已创建：${result.intake_no}`);
    form.reset();
    bindStatusDateControl(form, true);
    await loadBootstrap();
    await loadProjects();
    switchView("library", false);
    await openDetail(result.id);
    $("#formStatus").textContent = "能归属客户产品时，优先填写客户产品/生产线";
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
  $("#projectForm").addEventListener("submit", createProject);
  document.addEventListener("focusout", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement && AUTO_CAPITALIZE_FIELDS.has(target.name)) {
      target.value = smartCapitalize(target.value.trim());
    }
  });
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (state.sort.key === key) {
        state.sort.direction = state.sort.direction === "asc" ? "desc" : "asc";
      } else {
        state.sort = { key, direction: "asc" };
      }
      renderProjects();
    });
  });
  $("#navLibraryButton").addEventListener("click", () => switchView("library"));
  $("#navCreateButton").addEventListener("click", () => switchView("create"));
  $("#listCreateButton").addEventListener("click", () => switchView("create"));
  $("#backToLibraryButton").addEventListener("click", () => switchView("library"));
  $("#refreshButton").addEventListener("click", loadProjects);
  $("#saveSettingsButton").addEventListener("click", saveSettings);
  $("#searchInput").addEventListener("input", () => loadProjects().catch(console.error));
  $("#filterGroup").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterSite").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterStatus").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterNeedsEquipment").addEventListener("change", () => loadProjects().catch(console.error));
  $("#closeDetailButton").addEventListener("click", () => {
    $("#detailPane").hidden = true;
  });
}

async function boot() {
  bindEvents();
  await loadBootstrap();
  await loadProjects();
}

boot().catch((error) => {
  showToast(error.message);
  console.error(error);
});
