function showToast(message) {
  const region = $("#toastRegion") || document.body;
  if (state.toastTimer) {
    clearTimeout(state.toastTimer);
    state.toastTimer = null;
  }
  region.querySelectorAll(".toast").forEach((item) => item.remove());
  const node = document.createElement("div");
  node.className = "toast";
  node.setAttribute("role", "status");
  node.textContent = message;
  region.appendChild(node);
  state.toastTimer = setTimeout(() => {
    node.remove();
    state.toastTimer = null;
  }, 2200);
}

function closeDetailPane({ restoreFocus = true } = {}) {
  const pane = $("#detailPane");
  const backdrop = $("#detailBackdrop");
  pane.hidden = true;
  if (backdrop) backdrop.hidden = true;
  pane.setAttribute("aria-modal", "false");
  if (restoreFocus && state.detailLastFocused instanceof HTMLElement && document.contains(state.detailLastFocused)) {
    state.detailLastFocused.focus();
  }
}

function showDetailPane() {
  const pane = $("#detailPane");
  const backdrop = $("#detailBackdrop");
  state.detailLastFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  if (backdrop) backdrop.hidden = false;
  pane.hidden = false;
  pane.setAttribute("aria-modal", "true");
  pane.focus();
}

function confirmProjectDeletion() {
  const dialog = $("#deleteProjectDialog");
  if (!dialog || typeof dialog.showModal !== "function") {
    const keepFiles = confirm("是否保留项目资料文件夹？\n\n确定：保留资料，只删除系统记录。\n取消：将资料移入系统回收站。");
    if (keepFiles) return Promise.resolve({ confirmed: true, deleteFiles: false });
    const deleteFiles = confirm("你选择不保留资料。确认将项目文件夹移入 _RecycleBin_ 回收站吗？");
    return Promise.resolve({ confirmed: deleteFiles, deleteFiles });
  }

  return new Promise((resolve) => {
    let result = { confirmed: false, deleteFiles: false };
    const cancelButton = $("#deleteCancelButton");
    const keepButton = $("#deleteKeepFilesButton");
    const deleteButton = $("#deleteWithFilesButton");
    const cleanup = () => {
      cancelButton.removeEventListener("click", onCancel);
      keepButton.removeEventListener("click", onKeep);
      deleteButton.removeEventListener("click", onDelete);
      dialog.removeEventListener("close", onClose);
      dialog.removeEventListener("cancel", onCancel);
    };
    const closeWith = (nextResult) => {
      result = nextResult;
      if (dialog.open) dialog.close();
    };
    const onCancel = (event) => {
      event?.preventDefault();
      closeWith({ confirmed: false, deleteFiles: false });
    };
    const onKeep = () => {
      closeWith({ confirmed: true, deleteFiles: false });
    };
    const onDelete = () => {
      closeWith({ confirmed: true, deleteFiles: true });
    };
    const onClose = () => {
      cleanup();
      resolve(result);
    };
    cancelButton.addEventListener("click", onCancel);
    keepButton.addEventListener("click", onKeep);
    deleteButton.addEventListener("click", onDelete);
    dialog.addEventListener("cancel", onCancel);
    dialog.addEventListener("close", onClose);
    dialog.showModal();
  });
}
