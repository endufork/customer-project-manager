function renderNotificationBadge(unreadCount) {
  const badge = $("#notificationUnreadBadge");
  const count = Number(unreadCount || 0);
  badge.textContent = count > 99 ? "99+" : String(count);
  badge.hidden = count === 0;
  $("#notificationButton").setAttribute("aria-label", count ? `通知，${count} 条未读` : "通知，无未读");
}


function notificationTime(value) {
  return value ? String(value).replace("T", " ").slice(0, 16) : "";
}


function renderNotifications(payload) {
  const items = payload.notifications || [];
  renderNotificationBadge(payload.unread_count || 0);
  $("#notificationReadAllButton").disabled = !(payload.unread_count > 0);
  $("#notificationList").innerHTML = items.length
    ? items.map((item) => `
      <article class="notification-item${item.status === "unread" ? " unread" : ""}" data-notification-id="${escapeHtml(item.id)}">
        <div class="notification-copy">
          <div class="notification-title-row">
            <strong>${escapeHtml(item.title)}</strong>
            ${item.status === "unread" ? '<span class="tag">未读</span>' : ""}
          </div>
          ${item.body ? `<p>${escapeHtml(item.body)}</p>` : ""}
          <small>${escapeHtml(notificationTime(item.created_at))}</small>
        </div>
        <div class="notification-item-actions">
          ${item.related_type === "project" && item.related_id ? `<button type="button" class="secondary slim-inline" data-notification-action="open-project" data-project-id="${escapeHtml(item.related_id)}">打开项目执行</button>` : ""}
          ${item.status === "unread" ? '<button type="button" class="secondary slim-inline" data-notification-action="read">标记已读</button>' : ""}
        </div>
      </article>
    `).join("")
    : '<div class="empty">暂无系统通知</div>';

  $("#notificationList").querySelectorAll("[data-notification-action]").forEach((button) => {
    button.addEventListener("click", () => handleNotificationAction(button).catch((error) => showToast(error.message)));
  });
}


async function loadNotifications(limit = 30) {
  if (!state.auth.token) return;
  const payload = await api(`/api/notifications?limit=${encodeURIComponent(limit)}`);
  renderNotifications(payload);
}


async function refreshNotificationCount() {
  if (!state.auth.token) return;
  const payload = await api("/api/notifications?limit=1");
  renderNotificationBadge(payload.unread_count || 0);
}


async function handleNotificationAction(button) {
  const item = button.closest("[data-notification-id]");
  const notificationId = item?.dataset.notificationId;
  if (button.dataset.notificationAction === "read" && notificationId) {
    await api(`/api/notifications/${encodeURIComponent(notificationId)}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "read" }),
    });
    await loadNotifications();
    return;
  }
  if (button.dataset.notificationAction === "open-project") {
    if (notificationId && item.classList.contains("unread")) {
      await api(`/api/notifications/${encodeURIComponent(notificationId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "read" }),
      });
    }
    $("#notificationDialog").close();
    state.workbenchMode = "projects";
    switchView("workbench", false);
    await loadWorkbenchProjects(button.dataset.projectId);
    await refreshNotificationCount();
  }
}


function stopNotificationPolling() {
  if (state.notificationPollTimer) {
    window.clearInterval(state.notificationPollTimer);
    state.notificationPollTimer = null;
  }
  const badge = $("#notificationUnreadBadge");
  if (badge) badge.hidden = true;
}


function startNotificationPolling() {
  stopNotificationPolling();
  refreshNotificationCount().catch(console.error);
  state.notificationPollTimer = window.setInterval(() => refreshNotificationCount().catch(console.error), 30000);
}


function bindNotificationEvents() {
  $("#notificationButton").addEventListener("click", async () => {
    await loadNotifications();
    $("#notificationDialog").showModal();
  });
  $("#notificationCloseButton").addEventListener("click", () => $("#notificationDialog").close());
  $("#notificationReadAllButton").addEventListener("click", async () => {
    await api("/api/notifications/read-all", {
      method: "POST",
      body: JSON.stringify({ status: "read" }),
    });
    await loadNotifications();
  });
  closeDialogOnBackdrop($("#notificationDialog"));
}
