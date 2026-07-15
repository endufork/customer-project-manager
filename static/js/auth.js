const AUTH_ROLE_LABELS = {
  admin: "Admin",
  pm: "PM",
  engineer: "工程师",
};

let globalScanPollingJobId = "";

function authRoles() {
  return state.auth.user?.roles || [];
}

function userHasRole(...roles) {
  const currentRoles = new Set(authRoles());
  return roles.some((role) => currentRoles.has(role));
}

function preferredWorkbenchRole() {
  if (userHasRole("pm") && userHasRole("engineer")) {
    const savedRole = localStorage.getItem(workbenchRoleStorageKey());
    if (["pm", "engineer"].includes(savedRole)) return savedRole;
    return "pm";
  }
  if (userHasRole("pm")) return "pm";
  return "engineer";
}

function workbenchRoleStorageKey() {
  const userKey = state.auth.user?.id || state.auth.user?.email || "anonymous";
  return `${WORKBENCH_ROLE_STORAGE_KEY}.${userKey}`;
}

function lastViewStorageKey() {
  const userKey = state.auth.user?.id || state.auth.user?.email || "anonymous";
  return `${LAST_VIEW_STORAGE_PREFIX}.${userKey}`;
}

function availableHomeViews() {
  const views = new Set(["board", "workbench"]);
  if (userHasRole("pm")) ["pmInbox", "library", "create"].forEach((view) => views.add(view));
  if (userHasRole("admin")) views.add("admin");
  return views;
}

function preferredHomeView() {
  if (userHasRole("pm") && userHasRole("engineer")) {
    const savedView = localStorage.getItem(lastViewStorageKey());
    return availableHomeViews().has(savedView) ? savedView : "pmInbox";
  }
  if (userHasRole("pm")) return "pmInbox";
  if (userHasRole("engineer")) return "workbench";
  if (userHasRole("admin")) return "admin";
  return "board";
}

function rememberHomeView(view) {
  if (!state.appReady || isWorkbenchFocusMode()) return;
  if (!(userHasRole("pm") && userHasRole("engineer"))) return;
  if (availableHomeViews().has(view)) localStorage.setItem(lastViewStorageKey(), view);
}

function showAuthView() {
  stopNotificationPolling();
  state.auth = { token: null, user: null };
  state.appReady = false;
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  document.body.classList.remove("authenticated", "app-initializing");
  document.querySelector("body > nav")?.removeAttribute("inert");
  document.querySelector("body > main")?.removeAttribute("inert");
  document.body.removeAttribute("aria-busy");
  $("#authView").hidden = false;
}

function setAppInitializing(isInitializing) {
  document.body.classList.toggle("app-initializing", isInitializing);
  document.body.toggleAttribute("aria-busy", isInitializing);
  document.querySelector("body > nav")?.toggleAttribute("inert", isInitializing);
  document.querySelector("body > main")?.toggleAttribute("inert", isInitializing);
}

function showAuthenticatedApp() {
  document.body.classList.add("authenticated");
  setAppInitializing(true);
  $("#authView").hidden = true;
  const user = state.auth.user;
  $("#authUserBadge").textContent = user.display_name || user.email.split("@")[0];
  const canManageProjects = userHasRole("pm");
  $("#navPmInboxButton").hidden = !canManageProjects;
  $("#navLibraryButton").hidden = !canManageProjects;
  $("#navCreateButton").hidden = !canManageProjects;
  $("#listCreateButton").hidden = !canManageProjects;
  $("#saveSettingsButton").disabled = !userHasRole("admin");
  $("#navAdminButton").hidden = !userHasRole("admin");
  const owner = user.display_name || user.email.split("@")[0];
  $("#workbenchOwnerInput").value = owner;
  $("#workbenchOwnerInput").readOnly = true;
  localStorage.setItem(WORKBENCH_OWNER_STORAGE_KEY, owner);
  $("#workbenchRoleSelect").value = preferredWorkbenchRole();
  $("#workbenchRoleSelect").disabled = !(userHasRole("pm") && userHasRole("engineer"));
  startNotificationPolling();
}

async function restoreAuthSession() {
  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  if (!token) {
    showAuthView();
    return false;
  }
  state.auth.token = token;
  try {
    const payload = await api("/api/auth/me");
    state.auth.user = payload.user;
    showAuthenticatedApp();
    return true;
  } catch (error) {
    showAuthView();
    return false;
  }
}

async function requestLoginCode() {
  const email = $("#loginEmailInput").value.trim();
  $("#requestCodeButton").disabled = true;
  $("#authStatus").textContent = "正在发送验证码...";
  try {
    const payload = await api("/api/auth/request-code", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    if (payload.dev_code) {
      $("#loginCodeInput").value = payload.dev_code;
      $("#authStatus").textContent = `测试验证码：${payload.dev_code}`;
    } else {
      $("#authStatus").textContent = payload.message || "验证码已发送";
    }
  } catch (error) {
    $("#authStatus").textContent = error.message;
    showToast(error.message);
  } finally {
    $("#requestCodeButton").disabled = false;
  }
}

async function loginWithCode(event) {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  $("#authStatus").textContent = "正在登录...";
  try {
    const payload = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: $("#loginEmailInput").value.trim(),
        code: $("#loginCodeInput").value.trim(),
      }),
    });
    state.auth.token = payload.token;
    state.auth.user = payload.user;
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, payload.token);
    showAuthenticatedApp();
    await startAuthenticatedApp();
    showToast("已登录");
  } catch (error) {
    $("#authStatus").textContent = error.message;
    showToast(error.message);
  } finally {
    button.disabled = false;
  }
}

async function logout() {
  try {
    await api("/api/auth/logout", { method: "POST", body: "{}" });
  } catch (error) {
    console.error(error);
  }
  showAuthView();
}

function bindAuthEvents() {
  $("#requestCodeButton").addEventListener("click", () => requestLoginCode().catch(console.error));
  $("#loginForm").addEventListener("submit", loginWithCode);
  $("#logoutButton").addEventListener("click", () => logout().catch(console.error));
  $("#navAdminButton").addEventListener("click", () => switchView("admin"));
  $("#refreshUsersButton").addEventListener("click", () => loadUsers().catch(console.error));
  $("#globalScanButton").addEventListener("click", () => runGlobalScan().catch(console.error));
  $("#userSearchInput").addEventListener("input", debounce(() => loadUsers().catch(console.error), 300));
}

async function loadUsers() {
  if (!userHasRole("admin")) return;
  const search = $("#userSearchInput").value.trim();
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  const payload = await api(`/api/users?${params.toString()}`);
  renderUsers(payload.users || []);
  await loadLatestGlobalScanStatus();
}

function renderUsers(users) {
  $("#userList").innerHTML = users.length
    ? `
      <div class="user-list-head">
        <span>账号</span>
        <span>姓名</span>
        <span>状态</span>
        <span>角色</span>
        <span>保存</span>
        <span>删除</span>
      </div>
      ${users.map((user) => renderUserCard(user)).join("")}
    `
    : `<div class="empty">暂无用户</div>`;
  $("#userList").querySelectorAll(".user-card").forEach((card) => {
    card.querySelector("[data-action='save-user']").addEventListener("click", () => saveUser(card).catch(console.error));
    card.querySelector("[data-action='delete-user']").addEventListener("click", () => deleteUser(card).catch(console.error));
  });
}

function renderUserCard(user) {
  const roles = new Set(user.roles || []);
  return `
    <article class="user-card" data-user-id="${escapeHtml(user.id)}">
      <div class="user-identity">
        <strong>${escapeHtml(user.email)}</strong>
        <small>最后登录：${escapeHtml(user.last_login_at || "未登录")}</small>
      </div>
      <input name="display_name" value="${escapeHtml(user.display_name || "")}" placeholder="姓名" />
      <select name="status">
        <option value="pending"${user.status === "pending" ? " selected" : ""}>待分配</option>
        <option value="enabled"${user.status === "enabled" ? " selected" : ""}>启用</option>
        <option value="disabled"${user.status === "disabled" ? " selected" : ""}>停用</option>
      </select>
      <div class="role-checks" aria-label="用户角色">
        ${Object.entries(AUTH_ROLE_LABELS).map(([role, label]) => `
          <label class="role-check">
            <input type="checkbox" name="roles" value="${escapeHtml(role)}"${roles.has(role) ? " checked" : ""} />
            <span class="role-box" aria-hidden="true"></span>
            <span class="role-label">${escapeHtml(label)}</span>
          </label>
        `).join("")}
      </div>
      <div class="user-card-actions">
        <button type="button" class="secondary slim-inline" data-action="save-user">保存</button>
      </div>
      <div class="user-card-actions">
        <button type="button" class="danger slim-inline" data-action="delete-user">删除</button>
      </div>
    </article>
  `;
}

async function saveUser(card) {
  const roles = Array.from(card.querySelectorAll("input[name='roles']:checked")).map((input) => input.value);
  const payload = {
    display_name: card.querySelector("[name='display_name']").value.trim(),
    status: card.querySelector("[name='status']").value,
    roles,
  };
  await api(`/api/users/${encodeURIComponent(card.dataset.userId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  showToast("用户已保存");
  await loadBootstrap();
  await loadUsers();
}

async function deleteUser(card) {
  const email = card.querySelector(".user-identity strong")?.textContent || "该用户";
  if (!confirm(`确定删除用户 ${email} 吗？\n\n删除后该用户不能登录，历史任务会保留负责人姓名但解除账号绑定。`)) {
    return;
  }
  await api(`/api/users/${encodeURIComponent(card.dataset.userId)}`, {
    method: "DELETE",
    body: "{}",
  });
  showToast("用户已删除");
  await loadBootstrap();
  await loadUsers();
}

function globalScanIsActive(job) {
  return ["pending", "running"].includes(job?.status);
}

function renderGlobalScanStatus(job) {
  const button = $("#globalScanButton");
  const status = $("#globalScanStatus");
  if (!job) {
    button.disabled = false;
    status.textContent = "全局扫描只更新文件索引，不移动或删除物理文件。";
    return;
  }
  button.disabled = globalScanIsActive(job);
  const result = job.result || {};
  const project = result.project || {};
  const shared = result.shared || {};
  if (globalScanIsActive(job)) {
    status.textContent =
      `后台扫描 ${job.progress_percent || 0}%：项目 ${job.processed_projects || 0}/${job.total_projects || 0}，` +
      `共享资料 ${job.processed_shared_groups || 0}/${job.total_shared_groups || 0}；` +
      `已新增 ${Number(project.new_files || 0) + Number(shared.new_files || 0)} 个文件索引。`;
    return;
  }
  if (job.status === "failed") {
    status.textContent = `后台扫描失败：${job.error || "未知错误"}`;
    return;
  }
  status.textContent =
    `扫描完成：项目 ${result.scanned_projects || 0} 个，共享资料 ${result.scanned_shared_groups || 0} 个；` +
    `项目新增 ${project.new_files || 0}、更新 ${project.updated_files || 0}、移除索引 ${project.removed_files || 0}；` +
    `共享新增 ${shared.new_files || 0}、更新 ${shared.updated_files || 0}、移除索引 ${shared.removed_files || 0}；` +
    `失败范围 ${result.failed_scopes || 0} 个。`;
}

function waitForGlobalScanPoll() {
  return new Promise((resolve) => window.setTimeout(resolve, 1000));
}

async function pollGlobalScan(jobId) {
  if (!jobId || globalScanPollingJobId === jobId) return;
  globalScanPollingJobId = jobId;
  try {
    while (globalScanPollingJobId === jobId) {
      const job = await api(`/api/system/global-scan/${encodeURIComponent(jobId)}`);
      renderGlobalScanStatus(job);
      if (!globalScanIsActive(job)) {
        if (job.status === "completed") {
          showToast("全局扫描完成");
          await loadBootstrap();
        } else {
          showToast(job.error || "全局扫描失败");
        }
        break;
      }
      await waitForGlobalScanPoll();
    }
  } catch (error) {
    $("#globalScanStatus").textContent = error.message;
    showToast(error.message);
  } finally {
    if (globalScanPollingJobId === jobId) globalScanPollingJobId = "";
    $("#globalScanButton").disabled = false;
  }
}

async function loadLatestGlobalScanStatus() {
  const payload = await api("/api/system/global-scan");
  const job = payload.job || null;
  renderGlobalScanStatus(job);
  if (globalScanIsActive(job)) pollGlobalScan(job.id).catch(console.error);
}

async function runGlobalScan() {
  const button = $("#globalScanButton");
  button.disabled = true;
  $("#globalScanStatus").textContent = "正在创建后台扫描任务。";
  try {
    const job = await api("/api/system/global-scan", { method: "POST", body: "{}" });
    renderGlobalScanStatus(job);
    if (!job.created) showToast("已有全局扫描任务正在运行");
    await pollGlobalScan(job.id);
  } catch (error) {
    $("#globalScanStatus").textContent = error.message;
    showToast(error.message);
    button.disabled = false;
  }
}
