function latestPendingDueDateRequest(task) {
  return (task.due_date_requests || []).find((item) => item.status === "pending");
}

function dueDateStatusName(status) {
  if (status === "pending") return "待审批";
  if (status === "approved") return "已批准";
  if (status === "rejected") return "已驳回";
  return status || "";
}

function renderDueDateDialog(task) {
  const requests = task.due_date_requests || [];
  const pending = latestPendingDueDateRequest(task);
  const isPm = userHasRole("pm");
  const canCreate = isPm || !pending;
  const title = isPm ? "修改Due Date" : "申请改期";
  const submitText = isPm ? "确认修改" : "提交申请";
  const dialogId = `dueDateDialog-${task.id}`;
  return `
    <dialog id="${escapeHtml(dialogId)}" class="workbench-dialog due-date-dialog">
      <div class="workbench-dialog-shell">
        <div class="workbench-dialog-header">
          <div>
            <h3>${title}</h3>
            <span class="subtext">${escapeHtml(task.title)} · 当前 ${escapeHtml(task.due_date || "未设置")}</span>
          </div>
          <button type="button" class="secondary slim-inline" data-action="close-due-date-dialog" data-dialog-id="${escapeHtml(dialogId)}">关闭</button>
        </div>
        <section class="workbench-panel due-date-window-panel">
          ${pending ? renderDueDateRequestSummary(pending, { isPm, compact: false }) : ""}
          ${canCreate ? `
            <form class="due-date-request-form" data-task-id="${escapeHtml(task.id)}">
              <label>
                新 Due Date
                <input name="proposed_due_date" type="date" value="${escapeHtml(task.due_date || "")}" required />
              </label>
              <label>
                修改理由
                <textarea name="reason" rows="3" placeholder="必须填写，例如客户资料延迟、物料延期、范围变化" required></textarea>
              </label>
              <label>
                影响说明
                <input name="impact_note" placeholder="可选，例如影响调试/发货/其他任务" />
              </label>
              <div class="form-actions right">
                <button type="submit" class="secondary compact-submit">${submitText}</button>
              </div>
            </form>
          ` : `<div class="empty small-empty">该任务已有待审批改期申请，PM处理后才能再次申请。</div>`}
          ${requests.length ? `
            <div class="due-date-history">
              <div class="workbench-section-title">
                <h3>改期记录</h3>
                <span>${escapeHtml(requests.length)} 条</span>
              </div>
              ${requests.slice(0, 5).map((item) => renderDueDateRequestSummary(item, { isPm, compact: true })).join("")}
            </div>
          ` : ""}
        </section>
      </div>
    </dialog>
  `;
}

function renderDueDateRequestSummary(item, options = {}) {
  const isPm = options.isPm ?? userHasRole("pm");
  const compact = Boolean(options.compact);
  const statusClass = item.status === "pending" ? "warn" : item.status === "rejected" ? "danger" : "";
  const actions = isPm && item.status === "pending"
    ? `
      <span class="inline-actions">
        <button type="button" class="secondary slim-inline" data-action="approve-due-date-request" data-request-id="${escapeHtml(item.id)}" data-project-id="${escapeHtml(item.project_id || "")}">批准</button>
        <button type="button" class="danger slim-inline" data-action="reject-due-date-request" data-request-id="${escapeHtml(item.id)}" data-project-id="${escapeHtml(item.project_id || "")}">驳回</button>
      </span>
    `
    : "";
  return `
    <div class="due-date-request-card${compact ? " compact" : ""}">
      <div>
        <strong>${escapeHtml(item.old_due_date || "未设置")} -> ${escapeHtml(item.proposed_due_date || "")}</strong>
        <span class="subtext">${escapeHtml(item.requested_by || "申请人未填")}${item.requested_at ? ` · ${escapeHtml(item.requested_at)}` : ""}</span>
        <span class="subtext">${escapeHtml(item.reason || "")}${item.impact_note ? ` · 影响：${escapeHtml(item.impact_note)}` : ""}</span>
        ${item.review_note ? `<span class="subtext">审批意见：${escapeHtml(item.review_note)}</span>` : ""}
      </div>
      <div class="due-date-request-status">
        <span class="tag ${statusClass}">${escapeHtml(dueDateStatusName(item.status))}</span>
        ${actions}
      </div>
    </div>
  `;
}

function renderInboxDueDateSection(requests) {
  return `
    <div class="workbench-section-title inbox-section-title">
      <h3>待审批改期</h3>
      <span>${escapeHtml(requests.length)} 个</span>
    </div>
    <div class="my-task-list inbox-due-date-list">
      ${requests.length ? requests.map((item) => renderInboxDueDateCard(item)).join("") : `<div class="empty small-empty">暂无待审批改期</div>`}
    </div>
  `;
}

function renderInboxDueDateCard(item) {
  const projectName = item.equipment_name || item.project_name || "";
  const customerLine = [
    item.customer_name || "",
    item.site_name || "",
    item.project_group_name || "",
  ].filter(Boolean).join(" · ");
  const projectMeta = [
    item.current_number || item.intake_no || "",
    item.task_title || "",
    item.task_owner_name || "",
  ].filter(Boolean).join(" · ");
  return `
    <article class="my-task-card due-date-review-card" data-request-id="${escapeHtml(item.id)}">
      <div class="my-task-main">
        <div>
          <strong>${escapeHtml(item.old_due_date || "未设置")} -> ${escapeHtml(item.proposed_due_date)}</strong>
          <span class="subtext">${escapeHtml(projectMeta)}</span>
          <span class="subtext">${escapeHtml(customerLine)}${projectName ? ` · ${escapeHtml(projectName)}` : ""}</span>
          <span class="subtext">${escapeHtml(item.reason || "")}${item.impact_note ? ` · 影响：${escapeHtml(item.impact_note)}` : ""}</span>
        </div>
        <div class="my-task-status">
          <span class="task-status waiting_info">待审批</span>
          <span class="subtext">${escapeHtml(item.requested_by || "申请人未填")}</span>
        </div>
      </div>
      <div class="my-task-foot">
        <span class="tag-row">
          <span class="tag warn">Due Date</span>
        </span>
        <span class="inline-actions">
          <button type="button" class="secondary slim-inline" data-action="open-inbox-project" data-project-id="${escapeHtml(item.project_id)}">打开项目</button>
          <button type="button" class="secondary slim-inline" data-action="approve-due-date-request" data-request-id="${escapeHtml(item.id)}" data-project-id="${escapeHtml(item.project_id)}">批准</button>
          <button type="button" class="danger slim-inline" data-action="reject-due-date-request" data-request-id="${escapeHtml(item.id)}" data-project-id="${escapeHtml(item.project_id)}">驳回</button>
        </span>
      </div>
    </article>
  `;
}

function bindDueDateDialogs(workspace) {
  workspace.querySelectorAll(".due-date-dialog").forEach((dialog) => closeDialogOnBackdrop(dialog));
}

function bindDueDateForms(projectId, workspace) {
  workspace.querySelectorAll(".due-date-request-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      if (button) button.disabled = true;
      try {
        const payload = formToPayload(form);
        payload.direct = userHasRole("pm");
        await api(`/api/workbench/tasks/${encodeURIComponent(form.dataset.taskId)}/due-date-requests`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        showToast(userHasRole("pm") ? "Due Date已修改" : "改期申请已提交");
        await loadWorkbenchProjects(projectId);
      } catch (error) {
        showToast(error.message);
      } finally {
        if (button) button.disabled = false;
      }
    });
  });
}

async function reviewDueDateRequest(button, status, reload) {
  const body = { status };
  if (status === "rejected") {
    const reason = prompt("请输入驳回原因");
    if (!reason) return;
    body.review_note = reason;
  }
  await api(`/api/workbench/due-date-requests/${encodeURIComponent(button.dataset.requestId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  showToast(status === "approved" ? "改期已批准" : "改期已驳回");
  await reload();
}

async function handleDueDateAction(action, button, projectId) {
  if (action === "open-due-date-dialog") {
    openWorkbenchDialog(`#dueDateDialog-${button.dataset.taskId}`);
    return true;
  }
  if (action === "close-due-date-dialog") {
    closeWorkbenchDialog(`#${button.dataset.dialogId}`);
    return true;
  }
  if (action === "approve-due-date-request") {
    await reviewDueDateRequest(button, "approved", () => state.workbenchMode === "tasks" ? loadWorkbenchTasks() : loadWorkbenchProjects(projectId));
    return true;
  }
  if (action === "reject-due-date-request") {
    await reviewDueDateRequest(button, "rejected", () => state.workbenchMode === "tasks" ? loadWorkbenchTasks() : loadWorkbenchProjects(projectId));
    return true;
  }
  return false;
}
