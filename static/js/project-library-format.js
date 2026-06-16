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

function workbenchSummaryHtml(project) {
  const taskTotal = Number(project.task_total || 0);
  const tags = [];
  if (taskTotal) {
    tags.push(`<span class="tag neutral">${escapeHtml(project.task_done || 0)}/${escapeHtml(taskTotal)}</span>`);
  }
  if (project.overdue_tasks) {
    tags.push(`<span class="tag danger">超期 ${escapeHtml(project.overdue_tasks)}</span>`);
  }
  if (project.blocked_tasks) {
    tags.push(`<span class="tag warn">阻塞 ${escapeHtml(project.blocked_tasks)}</span>`);
  }
  if (project.submitted_tasks) {
    tags.push(`<span class="tag">待确认 ${escapeHtml(project.submitted_tasks)}</span>`);
  }
  if (project.high_issues) {
    tags.push(`<span class="tag danger">高风险</span>`);
  }
  const next = project.next_action
    ? `<div class="subtext">${escapeHtml(project.next_action)}${project.current_due_date ? ` · ${escapeHtml(project.current_due_date)}` : ""}</div>`
    : "";
  return tags.length ? `<div class="summary-tags">${tags.join(" ")}</div>${next}` : `<span class="tag neutral">未生成任务</span>`;
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
