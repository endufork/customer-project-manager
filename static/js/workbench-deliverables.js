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
          <button type="button" class="secondary slim-inline" data-action="confirm-inbox-deliverable" data-deliverable-id="${escapeHtml(item.id)}" data-file-name="${escapeHtml(item.file_name || "交付文件")}" data-task-title="${escapeHtml(item.task_title || "")}">确认</button>
          <button type="button" class="danger slim-inline" data-action="reject-inbox-deliverable" data-deliverable-id="${escapeHtml(item.id)}" data-file-name="${escapeHtml(item.file_name || "交付文件")}" data-task-title="${escapeHtml(item.task_title || "")}">驳回</button>
        </span>
      </div>
    </article>
  `;
}

function renderDeliverableItem(item) {
  const actions = canReviewDeliverables() && item.status === "submitted"
    ? `
      <button type="button" class="secondary slim-inline" data-action="confirm-deliverable" data-deliverable-id="${escapeHtml(item.id)}" data-file-name="${escapeHtml(item.file_name || "交付文件")}" data-task-title="${escapeHtml(item.task_title || "")}">确认</button>
      <button type="button" class="danger slim-inline" data-action="reject-deliverable" data-deliverable-id="${escapeHtml(item.id)}" data-file-name="${escapeHtml(item.file_name || "交付文件")}" data-task-title="${escapeHtml(item.task_title || "")}">驳回</button>
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

function renderDeliverableReviewDialog() {
  return `
    <dialog id="deliverableReviewDialog" class="workbench-dialog deliverable-review-dialog">
      <div class="workbench-dialog-shell">
        <div class="workbench-dialog-header">
          <div>
            <h3 id="deliverableReviewTitle">确认交付物</h3>
            <span id="deliverableReviewMeta" class="subtext">确认后任务会关闭；驳回后任务会进入返工。</span>
          </div>
          <button type="button" class="secondary slim-inline" data-action="close-deliverable-review">关闭</button>
        </div>
        <form id="deliverableReviewForm" class="workbench-panel deliverable-review-form">
          <input name="deliverable_id" type="hidden" />
          <input name="status" type="hidden" />
          <div class="deliverable-flow-strip" aria-label="交付物传递路径">
            <span>工程师上传</span>
            <span>归档资料库</span>
            <span>PM确认</span>
            <span>关闭/返工</span>
          </div>
          <p id="deliverableReviewHint" class="deliverable-review-hint">确认后，该任务会从未完成列表移出。</p>
          <label id="deliverableRejectReasonLabel" hidden>
            驳回原因
            <textarea name="reject_reason" rows="3" placeholder="例如文件版本不对、资料不完整、需要补充说明"></textarea>
          </label>
          <div class="form-actions right">
            <button type="button" class="secondary slim-inline" data-action="close-deliverable-review">取消</button>
            <button id="deliverableReviewSubmitButton" type="submit" class="secondary compact-submit">确认</button>
          </div>
        </form>
      </div>
    </dialog>
  `;
}

function openDeliverableReviewDialog(button, status) {
  const dialog = $("#deliverableReviewDialog");
  const form = $("#deliverableReviewForm");
  if (!dialog || !form) return false;
  const isReject = status === "rejected";
  form.reset();
  form.elements.deliverable_id.value = button.dataset.deliverableId || "";
  form.elements.status.value = status;
  $("#deliverableReviewTitle").textContent = isReject ? "驳回交付物" : "确认交付物";
  const fileName = button.dataset.fileName || "交付文件";
  const taskTitle = button.dataset.taskTitle || "任务";
  $("#deliverableReviewMeta").textContent = `${fileName} · ${taskTitle}`;
  $("#deliverableReviewHint").textContent = isReject
    ? "驳回后任务会进入返工，并把原因写入任务备注和执行日志。"
    : "确认后任务会关闭，并从待确认文件中移出。";
  $("#deliverableRejectReasonLabel").hidden = !isReject;
  form.elements.reject_reason.required = isReject;
  $("#deliverableReviewSubmitButton").textContent = isReject ? "确认驳回" : "确认通过";
  $("#deliverableReviewSubmitButton").classList.toggle("danger", isReject);
  openWorkbenchDialog("#deliverableReviewDialog");
  return true;
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

function bindDeliverableReviewDialog(workspace, reload) {
  const dialog = workspace.querySelector("#deliverableReviewDialog");
  closeDialogOnBackdrop(dialog);
  workspace.querySelectorAll("[data-action='close-deliverable-review']").forEach((button) => {
    button.addEventListener("click", () => closeWorkbenchDialog("#deliverableReviewDialog"));
  });
  const form = workspace.querySelector("#deliverableReviewForm");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    if (button) button.disabled = true;
    try {
      const status = form.elements.status.value;
      const body = { status, confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM" };
      if (status === "rejected") {
        const reason = form.elements.reject_reason.value.trim();
        if (!reason) {
          showToast("驳回交付物需要填写原因");
          return;
        }
        body.reject_reason = reason;
      }
      await api(`/api/workbench/deliverables/${encodeURIComponent(form.elements.deliverable_id.value)}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      closeWorkbenchDialog("#deliverableReviewDialog");
      showToast(status === "confirmed" ? "交付物已确认，任务已关闭" : "交付物已驳回，任务已进入返工");
      await reload();
    } catch (error) {
      showToast(error.message);
    } finally {
      if (button) button.disabled = false;
    }
  });
}

async function handleDeliverableAction(action, button, reload) {
  if (!["confirm-deliverable", "reject-deliverable", "confirm-inbox-deliverable", "reject-inbox-deliverable"].includes(action)) {
    return false;
  }
  const status = action.startsWith("confirm") ? "confirmed" : "rejected";
  openDeliverableReviewDialog(button, status);
  return true;
}
