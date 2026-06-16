function isWorkbenchFocusMode() {
  return new URLSearchParams(window.location.search).get("view") === "workbench";
}

function initialWorkbenchProjectId() {
  return new URLSearchParams(window.location.search).get("project") || null;
}

function openWorkbenchWindow(projectId = "") {
  const params = new URLSearchParams({ view: "workbench" });
  if (projectId) params.set("project", projectId);
  const popup = window.open(
    `/?${params.toString()}`,
    "customerProjectWorkbench",
    "width=1480,height=920,menubar=no,toolbar=no,location=no,status=no",
  );
  if (popup) {
    popup.focus();
    return true;
  }
  return false;
}

function switchView(view, refresh = true) {
  const isBoard = view === "board";
  const isPmInbox = view === "pmInbox";
  const isCreate = view === "create";
  const isWorkbench = view === "workbench";
  const isLibrary = view === "library";
  const isAdmin = view === "admin";
  $("#boardView").hidden = !isBoard;
  $("#pmInboxView").hidden = !isPmInbox;
  $("#entryView").hidden = !isCreate;
  $("#libraryView").hidden = !isLibrary;
  $("#workbenchView").hidden = !isWorkbench;
  $("#adminView").hidden = !isAdmin;
  $("#navBoardButton").classList.toggle("active", isBoard);
  $("#navPmInboxButton").classList.toggle("active", isPmInbox);
  $("#navCreateButton").classList.toggle("active", isCreate);
  $("#navLibraryButton").classList.toggle("active", isLibrary);
  $("#navWorkbenchButton").classList.toggle("active", isWorkbench);
  $("#navAdminButton").classList.toggle("active", isAdmin);
  if (isWorkbench) {
    closeDetailPane({ restoreFocus: false });
  }
  if (isBoard && refresh) {
    loadProjectBoard().catch(console.error);
  }
  if (isPmInbox && refresh) {
    loadPmInbox().catch(console.error);
  }
  if (isLibrary && refresh) {
    loadProjects().catch(console.error);
  }
  if (isWorkbench && refresh) {
    loadWorkbench().catch(console.error);
  }
  if (isAdmin && refresh) {
    loadUsers().catch(console.error);
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
