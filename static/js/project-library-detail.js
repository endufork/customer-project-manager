async function openDetail(projectId) {
  const payload = await api(`/api/projects/${encodeURIComponent(projectId)}`);
  const { project, files, shared_files: sharedFiles = [], events } = payload;
  const sharedButtons = project.project_group_id
    ? `
      <button type="button" class="secondary" data-action="copy-path" data-path="${escapeHtml(project.shared_folder_path || "")}" data-path-label="共享资料路径">复制共享路径</button>
    `
    : "";
  const sharedScanButton = project.project_group_id
    ? `<button type="button" class="secondary" data-action="scan-shared-folder" data-id="${escapeHtml(project.id)}">扫描共享资料</button>`
    : "";
  $("#detailContent").innerHTML = `
    <div class="detail-actions">
      <button type="button" data-action="copy-path" data-path="${escapeHtml(project.project_folder_path || "")}" data-path-label="项目路径">复制项目路径</button>
      <button type="button" class="secondary" data-action="open-workbench" data-id="${escapeHtml(project.id)}">打开项目执行</button>
      ${sharedButtons}
    </div>
    <div class="scan-toolbar">
      <div>
        <strong>文件扫描</strong>
        <span>把资料放入对应文件夹后，在这里更新文件索引和文件标记。</span>
      </div>
      <div class="scan-buttons">
        <button type="button" data-action="scan-all-folders" data-id="${escapeHtml(project.id)}">一键扫描</button>
        <button type="button" data-action="scan-folder" data-id="${escapeHtml(project.id)}">扫描项目文件</button>
        ${sharedScanButton}
      </div>
    </div>
    <dl class="detail-grid">
      <dt>当前编号</dt><dd>${escapeHtml(projectCurrentNumber(project))}</dd>
      <dt>编号阶段</dt><dd>${escapeHtml(projectNumberStage(project))}</dd>
      <dt>项目性质</dt><dd>${escapeHtml(project.project_nature || "新设备")}</dd>
      <dt>关联原项目/原WO号</dt><dd>${escapeHtml(project.related_legacy_no || "未填写")}</dd>
      <dt>客户集团</dt><dd>${escapeHtml(project.customer_group_name || "未填写")}</dd>
      <dt>客户公司/法人主体</dt><dd>${escapeHtml(project.customer_name)}</dd>
      <dt>工厂/站点</dt><dd>${escapeHtml(project.site_name || "未填写")}</dd>
      <dt>客户产品/生产线</dt><dd>${escapeHtml(project.project_group_name || "未关联")}</dd>
      <dt>共享资料目录</dt><dd>${escapeHtml(project.shared_folder_path || "无")}</dd>
      <dt>部门/业务单元</dt><dd>${escapeHtml(project.department || "未填写")}</dd>
      <dt>项目来源角色</dt><dd>${escapeHtml(project.origin_role || "未填写")}</dd>
      <dt>PO/采购主体</dt><dd>${escapeHtml(project.po_customer_name || project.customer_name)}</dd>
      <dt>联系人</dt><dd>${escapeHtml(project.contact_name || "未填写")}</dd>
      <dt>项目/设备/夹具</dt><dd>${escapeHtml(project.equipment_name)}</dd>
      <dt>状态</dt><dd>${escapeHtml(project.status_name)}</dd>
      <dt>状态日期</dt><dd>${escapeHtml(project.status_date_label || "状态日期")}：${escapeHtml(statusDateValue(project) || "未填写")}</dd>
      <dt>询价日期</dt><dd>${escapeHtml(project.inquiry_date || "未填写")}</dd>
      <dt>预计交期</dt><dd>${escapeHtml(project.expected_delivery_date || "未填写")}</dd>
      <dt>币种</dt><dd>${escapeHtml(project.currency_code)}</dd>
      <dt>项目目录</dt><dd>${escapeHtml(project.project_folder_path || "")}</dd>
      <dt>备注</dt><dd>${escapeHtml(project.notes || "")}</dd>
    </dl>
    <details class="edit-block">
      <summary>编辑基础信息</summary>
      <form id="detailEditForm" class="project-form compact-form">
        <input type="hidden" name="inquiry_date" value="${escapeHtml(project.inquiry_date || "")}" />
        <input type="hidden" name="quote_date" value="${escapeHtml(project.quote_date || "")}" />
        <input type="hidden" name="po_date" value="${escapeHtml(project.po_date || "")}" />
        <input type="hidden" name="actual_ship_date" value="${escapeHtml(project.actual_ship_date || "")}" />
        <input type="hidden" name="project_name" value="${escapeHtml(project.project_name || "")}" />
        <div class="grid two">
          <label>
            客户集团
            <input name="customer_group_name" list="customerGroupOptions" value="${escapeHtml(project.customer_group_name || "")}" />
          </label>
          <label>
            客户公司/法人主体 *
            <input name="customer_name" list="customerOptions" value="${escapeHtml(project.customer_name || "")}" required />
          </label>
        </div>
        <div class="grid three">
          <label>
            工厂/站点
            <input name="site_name" list="siteOptions" value="${escapeHtml(project.site_name || "")}" />
          </label>
          <label>
            客户产品/生产线
            <input name="project_group_name" list="projectGroupOptions" value="${escapeHtml(project.project_group_name || "")}" />
          </label>
          <label>
            部门/业务单元
            <input name="department" list="departmentOptions" value="${escapeHtml(project.department || "")}" />
          </label>
          <label>
            项目来源角色
            <select name="origin_role">${roleOptions(project.origin_role)}</select>
          </label>
        </div>
        <div class="grid two">
          <label>
            联系人
            <input name="contact_name" list="contactOptions" value="${escapeHtml(project.contact_name || "")}" />
          </label>
          <label>
            PO/采购主体
            <input name="po_customer_name" list="customerOptions" value="${escapeHtml(project.po_customer_name || project.customer_name || "")}" />
          </label>
        </div>
        <div class="grid two">
          <label>
            项目/设备/夹具名称 *
            <input name="equipment_name" list="equipmentNameOptions" value="${escapeHtml(project.equipment_name || "")}" required />
          </label>
          <label>
            项目性质
            <select name="project_nature">${projectNatureOptions(project.project_nature)}</select>
          </label>
        </div>
        <div class="grid two">
          <label>
            关联原项目/原WO号
            <input name="related_legacy_no" list="legacyNumberOptions" value="${escapeHtml(project.related_legacy_no || "")}" />
          </label>
          <label>
            WO号/内部设备号
            <input name="equipment_no" list="equipmentNoOptions" value="${escapeHtml(project.equipment_no || "")}" />
          </label>
        </div>
        <div class="grid three">
          <label>
            状态
            <select name="status_code">${selectOptions(state.bootstrap.statuses, project.status_code)}</select>
          </label>
          <label>
            币种
            <select name="currency_code">${selectOptions(state.bootstrap.currencies, project.currency_code, (item) => `${item.code} · ${item.name}`)}</select>
          </label>
          <label>
            <span data-status-date-label>${escapeHtml(project.status_date_label || "状态日期")}</span>
            <input name="status_date" type="date" value="${escapeHtml(statusDateValue(project))}" />
          </label>
        </div>
        <label>
          预计交期
          <input name="expected_delivery_date" type="date" value="${escapeHtml(project.expected_delivery_date || "")}" />
        </label>
        <label>
          备注
          <textarea name="notes" rows="3">${escapeHtml(project.notes || "")}</textarea>
        </label>
        <div class="actions">
          <button type="submit">保存修改</button>
          <button type="button" class="danger" data-action="delete-project" data-id="${escapeHtml(project.id)}">删除项目记录</button>
        </div>
      </form>
    </details>
    <h3>共享资料</h3>
    <div class="file-list">
      ${
        project.project_group_id
          ? sharedFiles.length
            ? sharedFiles
                .map(
                  (file) => `
                    <div class="file-item">
                      <strong>${escapeHtml(file.current_name)}</strong>
                    </div>
                  `,
                )
                .join("")
            : `<div class="empty">暂无共享文件。把共用资料放入 00_共享资料 后点击“扫描共享资料”。</div>`
          : `<div class="empty">未关联客户产品/生产线，当前项目没有共享资料层。</div>`
      }
    </div>
    <h3>文件</h3>
    <div class="file-list">
      ${
        files.length
          ? files
              .map(
                (file) => `
                  <div class="file-item">
                    <strong>${escapeHtml(file.current_name)}</strong>
                  </div>
                `,
              )
              .join("")
          : `<div class="empty">暂无文件</div>`
      }
    </div>
    <h3>时间线</h3>
    <div class="file-list">
      ${
        events.length
          ? events
              .map(
                (event) => `
                  <div class="file-item">
                    <strong>${escapeHtml(event.title)}</strong>
                    <div class="subtext">${escapeHtml(event.created_at)} · ${escapeHtml(event.detail || "")}</div>
                  </div>
                `,
              )
              .join("")
          : `<div class="empty">暂无事件</div>`
      }
    </div>
  `;
  if (!userHasRole("pm")) {
    $("#detailContent").querySelector(".edit-block")?.setAttribute("hidden", "");
    $("#detailContent").querySelector(".scan-toolbar")?.setAttribute("hidden", "");
  }
  if (!userHasRole("admin")) {
    $("#detailContent").querySelector("[data-action='delete-project']")?.setAttribute("hidden", "");
  }
  bindDetailActions(project);
  showDetailPane();
}

function bindDetailActions(project) {
  const projectId = project.id;
  const editForm = $("#detailEditForm");
  if (editForm) {
    bindStatusDateControl(editForm);
    editForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      button.disabled = true;
      try {
        const previousEquipmentNo = (project.equipment_no || "").trim();
        const payload = formToPayload(editForm);
        const nextEquipmentNo = (payload.equipment_no || "").trim();
        await api(`/api/projects/${encodeURIComponent(projectId)}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        if (nextEquipmentNo && nextEquipmentNo !== previousEquipmentNo) {
          const shouldRename = confirm(`已填写 WO号 ${nextEquipmentNo}，是否将项目文件夹重命名为 WO号？`);
          if (shouldRename) {
            const result = await api(`/api/projects/${encodeURIComponent(projectId)}/rename-folder`, {
              method: "POST",
              body: "{}",
            });
            showToast(result.renamed ? "项目已更新，文件夹已重命名为WO号" : result.message || "项目已更新");
          } else {
            showToast("项目已更新，文件夹名称保留不变");
          }
        } else {
          showToast("项目已更新");
        }
        await loadBootstrap();
        await loadProjects();
        await openDetail(projectId);
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  }
  $("#detailContent").querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      try {
        if (action === "scan-folder") {
          button.disabled = true;
          const result = await api(`/api/projects/${encodeURIComponent(projectId)}/scan`, { method: "POST", body: "{}" });
          showToast(`扫描完成：新增 ${result.new_files} 个，更新 ${result.updated_files || 0} 个，移除 ${result.removed_files || 0} 个文件记录`);
          await loadProjects();
          await openDetail(projectId);
        }
        if (action === "scan-all-folders") {
          button.disabled = true;
          const result = await api(`/api/projects/${encodeURIComponent(projectId)}/scan-all`, { method: "POST", body: "{}" });
          const projectResult = result.project || {};
          const sharedResult = result.shared || {};
          const sharedText = sharedResult.skipped
            ? sharedResult.reason || "未扫描共享资料"
            : `共享新增 ${sharedResult.new_files || 0} 个，更新 ${sharedResult.updated_files || 0} 个，移除 ${sharedResult.removed_files || 0} 个`;
          showToast(`一键扫描完成：项目新增 ${projectResult.new_files || 0} 个，更新 ${projectResult.updated_files || 0} 个，移除 ${projectResult.removed_files || 0} 个；${sharedText}`);
          await loadProjects();
          await openDetail(projectId);
        }
        if (action === "scan-shared-folder") {
          button.disabled = true;
          const result = await api(`/api/projects/${encodeURIComponent(projectId)}/scan-shared`, { method: "POST", body: "{}" });
          showToast(`共享资料扫描完成：新增 ${result.new_files} 个，更新 ${result.updated_files || 0} 个，移除 ${result.removed_files || 0} 个文件记录`);
          await openDetail(projectId);
        }
        if (action === "copy-path") {
          const path = button.dataset.path || "";
          if (!path) throw new Error("当前项目未配置可复制的网络路径");
          await navigator.clipboard.writeText(path);
          showToast(`${button.dataset.pathLabel || "路径"}已复制，请粘贴到资源管理器地址栏`);
        }
        if (action === "delete-project") {
          const decision = await confirmProjectDeletion();
          if (!decision.confirmed) return;
          const result = await api(`/api/projects/${encodeURIComponent(projectId)}`, {
            method: "DELETE",
            body: JSON.stringify({ delete_files: decision.deleteFiles }),
          });
          showToast(result.folder_archived ? "项目记录已删除，资料已移入回收站" : "项目记录已删除，资料已保留");
          closeDetailPane({ restoreFocus: false });
          await loadBootstrap();
          await loadProjects();
        }
        if (action === "open-workbench") {
          closeDetailPane({ restoreFocus: false });
          if (isWorkbenchFocusMode() || !openWorkbenchWindow(projectId)) {
            switchView("workbench", false);
            await loadWorkbenchProjects(projectId);
          }
        }
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });
}
