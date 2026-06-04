const state = {
  bootstrap: null,
  projects: [],
  workbenchProjects: [],
  workbenchTasks: [],
  workbenchInbox: null,
  workbenchMode: "projects",
  workbenchProjectId: null,
  visibleColumns: [],
  sort: { key: "created_at", direction: "desc" },
  detailLastFocused: null,
};

const $ = (selector) => document.querySelector(selector);
const COLUMN_STORAGE_KEY = "customerProject.visibleColumns.v1";
const WORKBENCH_OWNER_STORAGE_KEY = "customerProject.workbenchOwner.v1";
const WORKBENCH_ROLE_STORAGE_KEY = "customerProject.workbenchRole.v1";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function debounce(callback, delay = 300) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), delay);
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "请求失败");
  }
  return payload;
}

async function uploadApi(path, formData) {
  const response = await fetch(path, {
    method: "POST",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "上传失败");
  }
  return payload;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}
