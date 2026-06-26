function optionItems(items, selectedValue = "", valueOf = (item) => item.code, labelOf = (item) => item.name) {
  return (items || [])
    .map((item) => {
      const value = valueOf(item);
      const selected = value === selectedValue ? " selected" : "";
      return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(labelOf(item))}</option>`;
    })
    .join("");
}

function stringOptions(items, selectedValue = "") {
  return (items || [])
    .map((item) => `<option value="${escapeHtml(item)}"${item === selectedValue ? " selected" : ""}>${escapeHtml(item)}</option>`)
    .join("");
}

function assigneeName(user) {
  return user.display_name || user.email?.split("@")[0] || "";
}

function assigneeLabel(user) {
  const name = assigneeName(user);
  return name && name !== user.email ? `${name} · ${user.email}` : user.email;
}

function assigneeOptions(selectedValue = "") {
  return [
    `<option value="">手动负责人</option>`,
    ...(state.bootstrap?.assignees || []).map((user) => {
      const selected = user.id === selectedValue ? " selected" : "";
      return `<option value="${escapeHtml(user.id)}" data-name="${escapeHtml(assigneeName(user))}"${selected}>${escapeHtml(assigneeLabel(user))}</option>`;
    }),
  ].join("");
}

function bindAssigneeControls(container = document) {
  container.querySelectorAll("select[name='owner_user_id']").forEach((select) => {
    select.addEventListener("change", () => {
      const form = select.closest("form") || select.closest("article") || container;
      const ownerInput = form?.querySelector("input[name='owner_name']");
      if (!ownerInput) return;
      const selectedOption = select.selectedOptions[0];
      const selectedName = selectedOption?.dataset?.name || "";
      if (selectedName) {
        ownerInput.value = selectedName;
      }
    });
  });
}

function workbenchTaskStatusName(statusCode) {
  return (state.bootstrap?.workbench_task_statuses || []).find((item) => item.code === statusCode)?.name || statusCode || "";
}

function workbenchIssueStatusName(statusCode) {
  return (state.bootstrap?.workbench_issue_statuses || []).find((item) => item.code === statusCode)?.name || statusCode || "";
}

function workbenchSeverityName(severityCode) {
  return (state.bootstrap?.workbench_issue_severities || []).find((item) => item.code === severityCode)?.name || severityCode || "";
}

function workbenchIssueScopeName(scopeCode) {
  return (state.bootstrap?.workbench_issue_scopes || []).find((item) => item.code === scopeCode)?.name || scopeCode || "";
}

function workbenchAreaName(areaCode) {
  return (state.bootstrap?.workbench_areas || []).find((item) => item.code === areaCode)?.name || areaCode || "";
}

function workbenchDateValue(value) {
  return String(value || "").trim().slice(0, 10);
}

function requireDataset(button, key, label) {
  const value = button?.dataset?.[key] || "";
  if (value) return value;
  throw new Error(`${label}缺失，请刷新页面后重试`);
}

function workbenchRole() {
  if (state.auth.user) {
    const selected = $("#workbenchRoleSelect")?.value?.trim().toLowerCase();
    if (selected && userHasRole(selected)) return selected;
    return preferredWorkbenchRole();
  }
  const selected = $("#workbenchRoleSelect")?.value;
  if (selected) return selected.trim().toLowerCase();
  const urlRole = new URLSearchParams(window.location.search).get("role");
  return (urlRole || localStorage.getItem(WORKBENCH_ROLE_STORAGE_KEY) || "engineer").trim().toLowerCase();
}

function canReviewDeliverables() {
  return userHasRole("pm");
}

function renderTaskSelectOptions(tasks, selectedId = "") {
  return tasks
    .map((task) => `<option value="${escapeHtml(task.id)}"${task.id === selectedId ? " selected" : ""}>${escapeHtml(task.title)}</option>`)
    .join("");
}

function taskTitleById(tasks, taskId) {
  return tasks.find((task) => task.id === taskId)?.title || "";
}

function taskDone(task) {
  return ["confirmed", "completed", "cancelled"].includes(task.status);
}

function dueClass(dueDate) {
  if (!dueDate) return "neutral";
  if (dueDate < today()) return "danger";
  if (dueDate <= addDays(7)) return "warn";
  return "neutral";
}

function addDays(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function formDataFromContainer(container) {
  const data = {};
  container.querySelectorAll("[name]").forEach((input) => {
    if (input.disabled) return;
    if (input.type === "checkbox") {
      data[input.name] = input.checked ? "1" : "0";
    } else {
      data[input.name] = input.value;
    }
  });
  return data;
}

function openWorkbenchDialog(dialogId) {
  const dialog = $(dialogId);
  if (dialog?.showModal) {
    dialog.showModal();
  } else if (dialog) {
    dialog.setAttribute("open", "");
  }
}

function closeWorkbenchDialog(dialogId) {
  const dialog = $(dialogId);
  if (dialog?.close) {
    dialog.close();
  } else {
    dialog?.removeAttribute("open");
  }
}

function closeDialogOnBackdrop(dialog) {
  if (!dialog) return;
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.close();
    }
  });
}
