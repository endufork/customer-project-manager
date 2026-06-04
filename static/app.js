function formToPayload(form) {
  normalizeTextInputs(form);
  const data = new FormData(form);
  return Object.fromEntries(data.entries());
}

async function createProject(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = event.submitter;
  button.disabled = true;
  $("#formStatus").textContent = "正在创建...";
  try {
    const payload = formToPayload(form);
    const result = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast(`项目已创建：INQ ${result.intake_no}`);
    form.reset();
    bindStatusDateControl(form, true);
    await loadBootstrap();
    await loadProjects();
    switchView("library", false);
    await openDetail(result.id);
    $("#formStatus").textContent = "一条项目对应一台设备/夹具/具体工程对象；能归属客户产品时，优先填写客户产品/生产线";
  } catch (error) {
    $("#formStatus").textContent = error.message;
    showToast(error.message);
  } finally {
    button.disabled = false;
  }
}

async function saveSettings() {
  const projectRootPath = $("#projectRootPath").value.trim();
  await api("/api/settings", {
    method: "PATCH",
    body: JSON.stringify({ project_root_path: projectRootPath }),
  });
  showToast("配置已保存");
  await loadBootstrap();
}

function bindEvents() {
  const debouncedLoadProjects = debounce(() => loadProjects().catch(console.error), 300);
  bindAuthEvents();
  $("#projectForm").addEventListener("submit", createProject);
  document.addEventListener("focusout", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement && AUTO_CAPITALIZE_FIELDS.has(target.name)) {
      target.value = smartCapitalize(target.value.trim());
    }
  });
  document.addEventListener("keydown", (event) => {
    const deleteDialog = $("#deleteProjectDialog");
    const columnPicker = document.querySelector(".column-picker");
    if (event.key === "Escape" && columnPicker?.open) {
      columnPicker.open = false;
      return;
    }
    if (event.key === "Escape" && !$("#detailPane").hidden && !deleteDialog?.open) {
      closeDetailPane();
    }
  });
  document.addEventListener("click", (event) => {
    const columnPicker = document.querySelector(".column-picker");
    if (!columnPicker?.open) return;
    if (event.target instanceof Element && columnPicker.contains(event.target)) return;
    columnPicker.open = false;
  });
  $("#projectTableHead").addEventListener("click", (event) => {
    const th = event.target instanceof Element ? event.target.closest("th[data-sort]") : null;
    if (!th) return;
    const key = th.dataset.sort;
    if (state.sort.key === key) {
      state.sort.direction = state.sort.direction === "asc" ? "desc" : "asc";
    } else {
      state.sort = { key, direction: "asc" };
    }
    renderProjects();
  });
  $("#columnOptions").addEventListener("change", (event) => {
    if (event.target.name !== "project_column") return;
    const checked = Array.from($("#columnOptions").querySelectorAll("input:checked")).map((input) => input.value);
    if (!checked.length) {
      event.target.checked = true;
      showToast("至少保留一列");
      return;
    }
    state.visibleColumns = checked;
    saveVisibleColumns();
    renderProjects();
  });
  $("#resetColumnsButton").addEventListener("click", () => {
    state.visibleColumns = [...DEFAULT_PROJECT_COLUMNS];
    saveVisibleColumns();
    renderColumnPicker();
    renderProjects();
  });
  $("#navLibraryButton").addEventListener("click", () => switchView("library"));
  $("#navCreateButton").addEventListener("click", () => switchView("create"));
  $("#navWorkbenchButton").addEventListener("click", () => {
    if (isWorkbenchFocusMode() || !openWorkbenchWindow()) {
      switchView("workbench");
    }
  });
  $("#listCreateButton").addEventListener("click", () => switchView("create"));
  $("#backToLibraryButton").addEventListener("click", () => switchView("library"));
  $("#refreshButton").addEventListener("click", loadProjects);
  $("#workbenchRefreshButton").addEventListener("click", () => loadWorkbench().catch(console.error));
  $("#workbenchProjectsModeButton").addEventListener("click", () => {
    state.workbenchMode = "projects";
    loadWorkbench().catch(console.error);
  });
  $("#workbenchTasksModeButton").addEventListener("click", () => {
    state.workbenchMode = "tasks";
    loadWorkbench().catch(console.error);
  });
  $("#saveSettingsButton").addEventListener("click", saveSettings);
  $("#searchInput").addEventListener("input", debouncedLoadProjects);
  $("#filterGroup").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterSite").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterStatus").addEventListener("change", () => loadProjects().catch(console.error));
  $("#filterNeedsEquipment").addEventListener("change", () => loadProjects().catch(console.error));
  $("#workbenchSearchInput").addEventListener("input", debounce(() => loadWorkbench().catch(console.error), 300));
  $("#workbenchOwnerInput").addEventListener("input", debounce(() => {
    localStorage.setItem(WORKBENCH_OWNER_STORAGE_KEY, $("#workbenchOwnerInput").value.trim());
    loadWorkbench().catch(console.error);
  }, 300));
  $("#workbenchRoleSelect").addEventListener("change", () => {
    if ($("#workbenchRoleSelect").disabled) return;
    localStorage.setItem(WORKBENCH_ROLE_STORAGE_KEY, $("#workbenchRoleSelect").value);
    loadWorkbench().catch(console.error);
  });
  $("#workbenchViewFilter").addEventListener("change", () => loadWorkbench().catch(console.error));
  $("#closeDetailButton").addEventListener("click", () => {
    closeDetailPane();
  });
  $("#detailBackdrop").addEventListener("click", () => {
    closeDetailPane();
  });
}

async function startAuthenticatedApp() {
  await loadBootstrap();
  if (isWorkbenchFocusMode()) {
    switchView("workbench", false);
    await loadWorkbench(initialWorkbenchProjectId());
  } else if (!$("#adminView").hidden) {
    await loadUsers();
  } else {
    await loadProjects();
  }
  state.appReady = true;
}

async function boot() {
  state.visibleColumns = loadVisibleColumns();
  $("#workbenchOwnerInput").value = localStorage.getItem(WORKBENCH_OWNER_STORAGE_KEY) || "";
  const initialRole = new URLSearchParams(window.location.search).get("role") || localStorage.getItem(WORKBENCH_ROLE_STORAGE_KEY) || "engineer";
  $("#workbenchRoleSelect").value = initialRole === "pm" ? "pm" : "engineer";
  if (isWorkbenchFocusMode()) {
    document.body.classList.add("workbench-focus");
  }
  renderColumnPicker();
  bindEvents();
  const authenticated = await restoreAuthSession();
  if (!authenticated) return;
  await startAuthenticatedApp();
}

boot().catch((error) => {
  showToast(error.message);
  console.error(error);
});
