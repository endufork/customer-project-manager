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
  toastTimer: null,
  auth: { token: null, user: null },
  appReady: false,
};

const $ = (selector) => document.querySelector(selector);
const COLUMN_STORAGE_KEY = "customerProject.visibleColumns.v1";
const WORKBENCH_OWNER_STORAGE_KEY = "customerProject.workbenchOwner.v1";
const WORKBENCH_ROLE_STORAGE_KEY = "customerProject.workbenchRole.v1";
const AUTH_TOKEN_STORAGE_KEY = "customerProject.authToken.v1";

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
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.auth.token) {
    headers.Authorization = `Bearer ${state.auth.token}`;
  }
  const response = await fetch(path, {
    ...options,
    headers,
  });
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401 && typeof showAuthView === "function") {
      showAuthView();
    }
    throw new Error(payload.detail || payload.error || "请求失败");
  }
  return payload;
}

async function uploadApi(path, formData) {
  const headers = {};
  if (state.auth.token) {
    headers.Authorization = `Bearer ${state.auth.token}`;
  }
  const response = await fetch(path, {
    method: "POST",
    headers,
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401 && typeof showAuthView === "function") {
      showAuthView();
    }
    throw new Error(payload.detail || payload.error || "上传失败");
  }
  return payload;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}
