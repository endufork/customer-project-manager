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

function renderBlockedIssueOptions(issues = [], task = {}) {
  const selectedIssue = issues.find((issue) => issue.task_id === task.id && ["open", "following"].includes(issue.status));
  const selectedId = selectedIssue?.id || "";
  const options = issues.filter((issue) => {
    if (!["open", "following"].includes(issue.status)) return false;
    if (issue.project_id !== task.project_id) return false;
    return !issue.task_id || issue.task_id === task.id;
  });
  if (!options.length) {
    return `<option value="">无可关联风险，阻塞时自动创建</option>`;
  }
  return `
    <option value="">不关联，阻塞时自动创建</option>
    ${options.map((issue) => {
      const scopeName = workbenchIssueScopeName(issue.scope || (issue.task_id ? "task" : "equipment"));
      return `<option value="${escapeHtml(issue.id)}"${issue.id === selectedId ? " selected" : ""}>${escapeHtml(issue.title)} · ${escapeHtml(scopeName)}</option>`;
    }).join("")}
  `;
}

function renderEditableTaskStatusOptions(selectedStatus) {
  const manualStatuses = new Set(["not_started", "in_progress", "waiting_info", "blocked", "rework", "cancelled"]);
  return optionItems(
    (state.bootstrap?.workbench_task_statuses || []).filter((item) => manualStatuses.has(item.code)),
    selectedStatus,
  );
}

function renderTaskStatusEditor(task) {
  const workflowStatuses = new Set(["submitted", "confirmed", "completed"]);
  if (workflowStatuses.has(task.status)) {
    return `
      <input value="${escapeHtml(workbenchTaskStatusName(task.status))}" disabled />
      <span class="field-note">流程状态由提交、确认、驳回按钮自动生成。</span>
    `;
  }
  return `<select name="status">${renderEditableTaskStatusOptions(task.status)}</select>`;
}

function renderWorkbenchTask(task, issues = []) {
  const deliverables = task.deliverables || [];
  const owner = task.owner_name || "未指派";
  const due = task.due_date || "未设置Due Date";
  const workPackage = task.work_package || "未分组";
  const pendingDueRequest = latestPendingDueDateRequest(task);
  const deleteButton = userHasRole("pm")
    ? `<button type="button" class="danger slim-inline" data-action="delete-task" data-task-id="${escapeHtml(task.id)}">删除</button>`
    : "";
  const dueDateButtonText = userHasRole("pm") ? "修改Due Date" : pendingDueRequest ? "查看改期" : "申请改期";
  const taskCompletionActions = !task.requires_deliverable && task.status === "submitted" && userHasRole("pm")
    ? `
      <button type="button" class="secondary slim-inline" data-action="confirm-task-completion" data-task-id="${escapeHtml(task.id)}" data-task-title="${escapeHtml(task.title)}">确认完成</button>
      <button type="button" class="danger slim-inline" data-action="reject-task-completion" data-task-id="${escapeHtml(task.id)}" data-task-title="${escapeHtml(task.title)}">驳回</button>
    `
    : "";
  return `
    <article class="workbench-task ${escapeHtml(task.status)}" data-task-id="${escapeHtml(task.id)}">
      <div class="task-readable">
        <div class="task-readable-main">
          <strong>${escapeHtml(task.title)}</strong>
          <span class="subtext">${escapeHtml(workPackage)} · ${escapeHtml(owner)} · <span class="${dueClass(task.due_date || "")}">${escapeHtml(due)}</span>${task.requires_deliverable ? " · 需要文件" : ""}</span>
        </div>
        <div class="task-actions">
          <span class="task-status ${escapeHtml(task.status)}">${escapeHtml(workbenchTaskStatusName(task.status))}</span>
          <button type="button" class="secondary slim-inline" data-action="open-due-date-dialog" data-task-id="${escapeHtml(task.id)}">${dueDateButtonText}</button>
          ${deleteButton}
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
            ${renderTaskStatusEditor(task)}
          </label>
          <label>
            Due Date
            <span class="inline-field-action">
              <input name="due_date_display" type="date" value="${escapeHtml(task.due_date || "")}" disabled />
              <button type="button" class="secondary slim-inline" data-action="open-due-date-dialog" data-task-id="${escapeHtml(task.id)}">修改</button>
            </span>
          </label>
          <label class="checkline compact-check">
            <input name="requires_deliverable" type="checkbox" value="1"${task.requires_deliverable ? " checked" : ""} />
            需要文件
          </label>
          <label>
            备注/阻塞说明
            <input name="notes" value="${escapeHtml(task.notes || "")}" placeholder="备注/阻塞说明" />
          </label>
          <label>
            关联阻塞风险
            <select name="linked_issue_id">
              ${renderBlockedIssueOptions(issues, task)}
            </select>
          </label>
          <div class="task-actions">
            <button type="button" class="secondary slim-inline" data-action="save-task" data-task-id="${escapeHtml(task.id)}">保存任务</button>
            ${taskCompletionActions}
          </div>
        </form>
        ${task.requires_deliverable ? renderDeliverableUploadForm(task) : renderTaskCompletionForm(task)}
        <div class="deliverable-list">
          ${deliverables.length ? deliverables.map((item) => renderDeliverableItem(item)).join("") : `<div class="empty small-empty">暂无交付文件</div>`}
        </div>
      </details>
      ${renderDueDateDialog(task)}
    </article>
  `;
}

function renderDeliverableUploadForm(task) {
  return `
    <form class="deliverable-upload-form" data-task-id="${escapeHtml(task.id)}">
      <input type="file" name="file" required />
      <select name="category_code">${optionItems(state.bootstrap?.file_categories || [], "solution", (item) => item.code, (item) => item.name)}</select>
      <input name="version_note" placeholder="版本说明，可选" />
      <input name="submitted_by" placeholder="提交人" value="${escapeHtml($("#workbenchOwnerInput").value.trim() || task.owner_name || "")}" />
      <button type="submit">提交文件</button>
    </form>
  `;
}

function renderTaskCompletionForm(task) {
  if (taskDone(task)) {
    return `<div class="empty small-empty">任务已关闭</div>`;
  }
  if (task.status === "submitted") {
    return `<div class="empty small-empty">完成说明已提交，等待 PM 确认。</div>`;
  }
  const submitText = userHasRole("pm") ? "提交并确认" : "提交完成说明";
  return `
    <form class="task-completion-form" data-task-id="${escapeHtml(task.id)}" data-project-id="${escapeHtml(task.project_id || "")}">
      <textarea name="completion_note" rows="2" placeholder="填写完成说明，例如 已完成客户资料确认并同步给PM" required></textarea>
      <input name="submitted_by" placeholder="提交人" value="${escapeHtml($("#workbenchOwnerInput").value.trim() || task.owner_name || "")}" />
      <button type="submit" class="secondary compact-submit">${submitText}</button>
    </form>
  `;
}

function renderTaskCompletionReviewDialog() {
  return `
    <dialog id="taskCompletionReviewDialog" class="workbench-dialog deliverable-review-dialog">
      <div class="workbench-dialog-shell">
        <div class="workbench-dialog-header">
          <div>
            <h3 id="taskCompletionReviewTitle">确认完成说明</h3>
            <span id="taskCompletionReviewMeta" class="subtext">确认后任务关闭；驳回后任务进入返工。</span>
          </div>
          <button type="button" class="secondary slim-inline" data-action="close-task-completion-review">关闭</button>
        </div>
        <form id="taskCompletionReviewForm" class="workbench-panel deliverable-review-form">
          <input name="task_id" type="hidden" />
          <input name="status" type="hidden" />
          <p id="taskCompletionReviewHint" class="deliverable-review-hint">该操作只处理已提交的完成说明。确认后任务关闭，驳回后任务回到需返工。</p>
          <label id="taskCompletionRejectReasonLabel" hidden>
            驳回原因
            <textarea name="reject_reason" rows="3" placeholder="例如说明不完整、需要补充客户确认、任务实际未完成"></textarea>
          </label>
          <div class="form-actions right">
            <button type="button" class="secondary slim-inline" data-action="close-task-completion-review">取消</button>
            <button id="taskCompletionReviewSubmitButton" type="submit" class="secondary compact-submit">确认</button>
          </div>
        </form>
      </div>
    </dialog>
  `;
}

function openTaskCompletionReviewDialog(button, status) {
  const dialog = $("#taskCompletionReviewDialog");
  const form = $("#taskCompletionReviewForm");
  if (!dialog || !form) return false;
  const taskId = button.dataset.taskId || "";
  if (!taskId) {
    showToast("任务ID缺失，请刷新页面后重试");
    return true;
  }
  const isReject = status === "rejected";
  form.reset();
  dialog.dataset.taskId = taskId;
  dialog.dataset.status = status;
  form.dataset.taskId = taskId;
  form.elements.task_id.value = taskId;
  form.elements.status.value = status;
  $("#taskCompletionReviewTitle").textContent = isReject ? "驳回完成说明" : "确认任务完成";
  $("#taskCompletionReviewMeta").textContent = button.dataset.taskTitle || "任务完成说明";
  $("#taskCompletionReviewHint").textContent = isReject
    ? "驳回后任务会进入需返工，并把原因写入任务备注和执行日志。"
    : "确认后任务会关闭，并从待确认完成说明中移出。";
  $("#taskCompletionRejectReasonLabel").hidden = !isReject;
  form.elements.reject_reason.required = isReject;
  $("#taskCompletionReviewSubmitButton").textContent = isReject ? "确认驳回" : "确认通过";
  $("#taskCompletionReviewSubmitButton").classList.toggle("danger", isReject);
  openWorkbenchDialog("#taskCompletionReviewDialog");
  return true;
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

function bindTaskCompletionForms(projectId, workspace) {
  workspace.querySelectorAll(".task-completion-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      if (button) button.disabled = true;
      try {
        const payload = formDataFromContainer(form);
        if (userHasRole("pm")) {
          payload.direct_confirm = true;
        }
        const result = await api(`/api/workbench/tasks/${encodeURIComponent(form.dataset.taskId)}/completion`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        showToast(userHasRole("pm") ? "任务已提交并确认关闭" : "完成说明已提交，等待PM确认");
        const reloadProjectId = result.project_id || form.dataset.projectId || projectId || state.workbenchProjectId;
        if (reloadProjectId) {
          await loadWorkbenchProjects(reloadProjectId);
        } else {
          await loadWorkbench();
        }
      } catch (error) {
        showToast(error.message);
      } finally {
        if (button) button.disabled = false;
      }
    });
  });
}

function bindTaskCompletionReviewDialog(workspace, reload) {
  const dialog = workspace.querySelector("#taskCompletionReviewDialog");
  closeDialogOnBackdrop(dialog);
  workspace.querySelectorAll("[data-action='close-task-completion-review']").forEach((button) => {
    button.addEventListener("click", () => closeWorkbenchDialog("#taskCompletionReviewDialog"));
  });
  const form = workspace.querySelector("#taskCompletionReviewForm");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const button = event.submitter;
    if (button) button.disabled = true;
    try {
      const status = form.elements.status.value;
      const taskId = form.dataset.taskId || form.elements.task_id.value || workspace.querySelector("#taskCompletionReviewDialog")?.dataset.taskId || "";
      if (!taskId) {
        showToast("任务ID缺失，请刷新页面后重试");
        return;
      }
      const body = { status, confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM" };
      if (status === "rejected") {
        const reason = form.elements.reject_reason.value.trim();
        if (!reason) {
          showToast("驳回完成说明需要填写原因");
          return;
        }
        body.reject_reason = reason;
      }
      const result = await api(`/api/workbench/tasks/${encodeURIComponent(taskId)}/completion`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      closeWorkbenchDialog("#taskCompletionReviewDialog");
      showToast(status === "confirmed" ? "任务已确认关闭" : "任务已驳回，进入返工");
      await reload(result);
    } catch (error) {
      showToast(error.message);
    } finally {
      if (button) button.disabled = false;
    }
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
  if (action === "confirm-task-completion") {
    openTaskCompletionReviewDialog(button, "confirmed");
    return true;
  }
  if (action === "reject-task-completion") {
    openTaskCompletionReviewDialog(button, "rejected");
    return true;
  }
  return false;
}
