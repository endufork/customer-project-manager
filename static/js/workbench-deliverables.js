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

function bindDeliverableUploads(projectId, workspace) {
  workspace.querySelectorAll(".deliverable-upload-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      if (button) button.disabled = true;
      try {
        const formData = new FormData(form);
        await uploadApi(`/api/workbench/tasks/${encodeURIComponent(form.dataset.taskId)}/deliverables`, formData);
        showToast("文件已提交，等待PM确认");
        await loadWorkbenchProjects(projectId);
      } catch (error) {
        showToast(error.message);
      } finally {
        if (button) button.disabled = false;
      }
    });
  });
}

async function handleDeliverableAction(action, button, reload) {
  if (!["confirm-deliverable", "reject-deliverable", "confirm-inbox-deliverable", "reject-inbox-deliverable"].includes(action)) {
    return false;
  }
  const status = action.startsWith("confirm") ? "confirmed" : "rejected";
  const body = { status, confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM" };
  if (status === "rejected") {
    const reason = prompt("请输入驳回原因");
    if (!reason) return true;
    body.reject_reason = reason;
  }
  await api(`/api/workbench/deliverables/${encodeURIComponent(button.dataset.deliverableId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  showToast(status === "confirmed" ? "交付物已确认" : "交付物已驳回");
  await reload();
  return true;
}
