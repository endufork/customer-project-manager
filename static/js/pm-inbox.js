const PM_INBOX_TYPE_META = {
  all: { label: "全部", kpi: "total" },
  deliverable: { label: "待确认文件", kpi: "deliverables" },
  completion: { label: "完成说明", kpi: "completions" },
  due_date: { label: "改期申请", kpi: "due_date_requests" },
  risk_review: { label: "风险关闭", kpi: "risk_reviews" },
};

function pmInboxQueryParams() {
  const params = new URLSearchParams();
  const search = $("#pmInboxSearchInput")?.value.trim() || "";
  if (search) params.set("search", search);
  params.set("view", "submitted");
  return params;
}

async function loadPmInbox(selectKey = state.pmInboxSelectedKey) {
  if (!userHasRole("pm")) {
    $("#pmInboxList").innerHTML = `<div class="empty">当前账号没有PM权限</div>`;
    $("#pmInboxPanel").innerHTML = `<div class="empty">请使用PM或Admin账号登录</div>`;
    return;
  }
  const payload = await api(`/api/workbench/pm-inbox?${pmInboxQueryParams().toString()}`);
  state.pmInboxPayload = payload;
  state.pmInboxItems = payload.items || [];
  renderPmInboxKpis(payload.kpis || {});
  updatePmInboxFilters();

  const visibleItems = filteredPmInboxItems();
  const selectedExists = visibleItems.some((item) => item.key === selectKey);
  state.pmInboxSelectedKey = selectedExists ? selectKey : visibleItems[0]?.key || null;
  renderPmInboxList();
  renderPmInboxPanel();
}

function filteredPmInboxItems() {
  if (state.pmInboxFilter === "all") return state.pmInboxItems;
  return state.pmInboxItems.filter((item) => item.type === state.pmInboxFilter);
}

function renderPmInboxKpis(kpis = {}) {
  $("#pmInboxKpis").innerHTML = Object.entries(PM_INBOX_TYPE_META).map(([type, meta]) => {
    const active = state.pmInboxFilter === type ? " active" : "";
    return `
      <button type="button" class="pm-inbox-kpi${active}" data-pm-inbox-filter="${escapeHtml(type)}">
        <span>${escapeHtml(kpis[meta.kpi] || 0)}</span>
        <small>${escapeHtml(meta.label)}</small>
      </button>
    `;
  }).join("");
  $("#pmInboxKpis").querySelectorAll("[data-pm-inbox-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      state.pmInboxFilter = button.dataset.pmInboxFilter || "all";
      loadPmInbox().catch(console.error);
    });
  });
}

function updatePmInboxFilters() {
  document.querySelectorAll("[data-pm-inbox-filter]").forEach((button) => {
    button.classList.toggle("active", (button.dataset.pmInboxFilter || "all") === state.pmInboxFilter);
  });
}

function renderPmInboxList() {
  const items = filteredPmInboxItems();
  const list = $("#pmInboxList");
  if (!items.length) {
    list.innerHTML = `<div class="empty small-empty">暂无${escapeHtml(PM_INBOX_TYPE_META[state.pmInboxFilter]?.label || "待处理事项")}</div>`;
    return;
  }
  list.innerHTML = items.map((item) => {
    const active = item.key === state.pmInboxSelectedKey ? " active" : "";
    const typeClass = item.type === "risk_review" ? "danger" : item.type === "due_date" ? "warn" : "neutral";
    return `
      <button type="button" class="pm-inbox-row${active}" data-item-key="${escapeHtml(item.key)}">
        <span>
          <strong>${escapeHtml(item.project_number || "未编号")}</strong>
          <small>${escapeHtml(item.customer_line || "")}</small>
        </span>
        <span>
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(item.project_title || "")}${item.task_title ? ` · ${escapeHtml(item.task_title)}` : ""}</small>
        </span>
        <span>
          <span class="tag ${typeClass}">${escapeHtml(item.type_label)}</span>
          <small>${escapeHtml(item.owner_name || item.submitted_by || "未填")}</small>
        </span>
        <span>
          <small>${escapeHtml(item.submitted_at || "")}</small>
        </span>
      </button>
    `;
  }).join("");
  list.querySelectorAll("[data-item-key]").forEach((button) => {
    button.addEventListener("click", () => {
      state.pmInboxSelectedKey = button.dataset.itemKey;
      renderPmInboxList();
      renderPmInboxPanel();
    });
  });
}

function selectedPmInboxItem() {
  return state.pmInboxItems.find((item) => item.key === state.pmInboxSelectedKey) || null;
}

function renderPmInboxPanel() {
  const item = selectedPmInboxItem();
  const panel = $("#pmInboxPanel");
  if (!item) {
    panel.innerHTML = `<div class="empty">请选择一条待处理事项</div>`;
    return;
  }
  panel.innerHTML = `
    <div class="pm-inbox-panel-head">
      <div>
        <span class="tag ${item.type === "risk_review" ? "danger" : item.type === "due_date" ? "warn" : "neutral"}">${escapeHtml(item.type_label)}</span>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.project_number || "未编号")} · ${escapeHtml(item.project_title || "")}</p>
      </div>
      <button type="button" class="secondary slim-inline" data-action="open-pm-inbox-project" data-project-id="${escapeHtml(item.project_id)}">打开项目执行</button>
    </div>
    <dl class="pm-inbox-detail-grid">
      <dt>客户/工厂/产品</dt><dd>${escapeHtml(item.customer_line || "未填写")}</dd>
      <dt>任务</dt><dd>${escapeHtml(item.task_title || item.raw?.title || "未关联任务")}</dd>
      <dt>负责人/提交人</dt><dd>${escapeHtml(item.owner_name || item.submitted_by || "未填写")}</dd>
      <dt>提交时间</dt><dd>${escapeHtml(item.submitted_at || "未记录")}</dd>
      <dt>说明</dt><dd>${escapeHtml(item.summary || "无")}</dd>
    </dl>
    ${renderPmInboxActionForm(item)}
  `;
  bindPmInboxPanelActions(panel, item);
}

function renderPmInboxActionForm(item) {
  if (item.type === "deliverable") {
    return `
      <form class="pm-inbox-action-form" data-action-kind="deliverable">
        <input name="target_id" type="hidden" value="${escapeHtml(item.id)}" />
        <div class="deliverable-flow-strip" aria-label="交付物传递路径">
          <span>工程师上传</span>
          <span>归档资料库</span>
          <span>PM确认</span>
          <span>关闭/返工</span>
        </div>
        <label>
          驳回原因
          <textarea name="reject_reason" rows="3" placeholder="仅驳回时填写，例如文件版本不对、资料不完整"></textarea>
        </label>
        <div class="form-actions right">
          <button type="submit" class="danger slim-inline" data-review-status="rejected">驳回文件</button>
          <button type="submit" class="secondary compact-submit" data-review-status="confirmed">确认文件</button>
        </div>
      </form>
    `;
  }
  if (item.type === "completion") {
    return `
      <form class="pm-inbox-action-form" data-action-kind="completion">
        <input name="target_id" type="hidden" value="${escapeHtml(item.id)}" />
        <label>
          驳回原因
          <textarea name="reject_reason" rows="3" placeholder="仅驳回时填写，例如说明不完整、任务实际未完成"></textarea>
        </label>
        <div class="form-actions right">
          <button type="submit" class="danger slim-inline" data-review-status="rejected">驳回说明</button>
          <button type="submit" class="secondary compact-submit" data-review-status="confirmed">确认完成</button>
        </div>
      </form>
    `;
  }
  if (item.type === "due_date") {
    return `
      <form class="pm-inbox-action-form" data-action-kind="due_date">
        <input name="target_id" type="hidden" value="${escapeHtml(item.id)}" />
        <label>
          审批意见
          <textarea name="review_note" rows="3" placeholder="驳回必须填写；批准可填写同步说明"></textarea>
        </label>
        <div class="form-actions right">
          <button type="submit" class="danger slim-inline" data-review-status="rejected">驳回改期</button>
          <button type="submit" class="secondary compact-submit" data-review-status="approved">批准改期</button>
        </div>
      </form>
    `;
  }
  if (item.type === "risk_review") {
    const hasTask = Boolean(item.task_id);
    return `
      <form class="pm-inbox-action-form" data-action-kind="risk_review">
        <input name="target_id" type="hidden" value="${escapeHtml(item.id)}" />
        <label>
          PM处理意见
          <textarea name="review_note" rows="3" placeholder="退回必须填写；关闭或接受可填写确认说明"></textarea>
        </label>
        ${hasTask ? `
          <label>
            关联任务下一状态
            <select name="task_next_status">
              <option value="in_progress">恢复进行中</option>
              <option value="waiting_info">仍等待资料</option>
              <option value="rework">需要返工</option>
              <option value="not_started">回到未开始</option>
            </select>
          </label>
        ` : ""}
        <div class="form-actions right">
          <button type="submit" class="danger slim-inline" data-review-status="following">退回跟进</button>
          <button type="submit" class="secondary slim-inline" data-review-status="accepted">接受风险</button>
          <button type="submit" class="secondary compact-submit" data-review-status="closed">确认关闭</button>
        </div>
      </form>
    `;
  }
  return `<div class="empty small-empty">暂不支持该类型处理</div>`;
}

function bindPmInboxPanelActions(panel, item) {
  panel.querySelector("[data-action='open-pm-inbox-project']")?.addEventListener("click", async (event) => {
    const projectId = event.currentTarget.dataset.projectId || "";
    if (!projectId) return;
    switchView("workbench", false);
    state.workbenchMode = "projects";
    await loadWorkbenchProjects(projectId);
  });
  const form = panel.querySelector(".pm-inbox-action-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    if (!button) return;
    button.disabled = true;
    try {
      await submitPmInboxAction(item, form, button.dataset.reviewStatus || "");
      await loadPmInbox();
    } catch (error) {
      showToast(error.message);
    } finally {
      button.disabled = false;
    }
  });
}

async function submitPmInboxAction(item, form, status) {
  const targetId = form.elements.target_id.value;
  if (!targetId) throw new Error("待处理事项ID缺失，请刷新页面后重试");
  if (item.type === "deliverable") {
    const body = { status, confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM" };
    if (status === "rejected") {
      body.reject_reason = form.elements.reject_reason.value.trim();
      if (!body.reject_reason) throw new Error("驳回文件需要填写原因");
    }
    await api(`/api/workbench/deliverables/${encodeURIComponent(targetId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    showToast(status === "confirmed" ? "交付文件已确认" : "交付文件已驳回");
    return;
  }
  if (item.type === "completion") {
    const body = { status, confirmed_by: $("#workbenchOwnerInput").value.trim() || "PM" };
    if (status === "rejected") {
      body.reject_reason = form.elements.reject_reason.value.trim();
      if (!body.reject_reason) throw new Error("驳回完成说明需要填写原因");
    }
    await api(`/api/workbench/tasks/${encodeURIComponent(targetId)}/completion`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    showToast(status === "confirmed" ? "任务已确认完成" : "完成说明已驳回");
    return;
  }
  if (item.type === "due_date") {
    const body = { status };
    const reviewNote = form.elements.review_note.value.trim();
    if (reviewNote) body.review_note = reviewNote;
    if (status === "rejected" && !reviewNote) throw new Error("驳回改期需要填写原因");
    await api(`/api/workbench/due-date-requests/${encodeURIComponent(targetId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    showToast(status === "approved" ? "改期已批准" : "改期已驳回");
    return;
  }
  if (item.type === "risk_review") {
    const body = { status };
    const reviewNote = form.elements.review_note.value.trim();
    if (reviewNote) body.review_note = reviewNote;
    if (status === "following" && !reviewNote) throw new Error("退回风险需要填写原因");
    if (form.elements.task_next_status && status !== "following") {
      body.task_next_status = form.elements.task_next_status.value;
    }
    await api(`/api/workbench/issues/${encodeURIComponent(targetId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    showToast(status === "following" ? "风险已退回继续跟进" : "风险已处理");
  }
}
