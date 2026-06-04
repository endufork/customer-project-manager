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

function bindTaskCreation(projectId) {
  const taskForm = $("#workbenchTaskForm");
  if (taskForm) {
    taskForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      if (button) button.disabled = true;
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
        if (button) button.disabled = false;
      }
    });
  }

  const templateTaskForm = $("#templateTaskForm");
  if (!templateTaskForm) return;
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

function bindTaskDialog(workspace) {
  closeDialogOnBackdrop(workspace.querySelector("#taskDialog"));
}

function bindTaskForms(projectId, workspace) {
  workspace.querySelectorAll(".workbench-task-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await saveWorkbenchTask(form, projectId);
    });
  });
}

async function handleTaskAction(action, button, projectId) {
  if (action === "open-task-dialog") {
    openWorkbenchDialog("#taskDialog");
    return true;
  }
  if (action === "close-task-dialog") {
    closeWorkbenchDialog("#taskDialog");
    return true;
  }
  if (action === "select-visible-template") {
    $("#templateTaskForm")?.querySelectorAll(".template-checklist:not([hidden]) input[type='checkbox']:not(:disabled)").forEach((input) => {
      input.checked = true;
    });
    return true;
  }
  if (action === "clear-visible-template") {
    $("#templateTaskForm")?.querySelectorAll(".template-checklist:not([hidden]) input[type='checkbox']").forEach((input) => {
      input.checked = false;
    });
    return true;
  }
  if (action === "apply-template") {
    button.disabled = true;
    const result = await api(`/api/workbench/projects/${encodeURIComponent(projectId)}/templates`, {
      method: "POST",
      body: JSON.stringify({ template: button.dataset.template }),
    });
    showToast(`已生成 ${result.created} 个任务`);
    await loadWorkbenchProjects(projectId);
    return true;
  }
  if (action === "save-task") {
    await saveWorkbenchTask(button.closest(".workbench-task-form"), projectId);
    return true;
  }
  if (action === "delete-task") {
    if (!confirm("确定删除这个任务吗？")) return true;
    await api(`/api/workbench/tasks/${encodeURIComponent(button.dataset.taskId)}`, { method: "DELETE", body: "{}" });
    showToast("任务已删除");
    await loadWorkbenchProjects(projectId);
    return true;
  }
  return false;
}
