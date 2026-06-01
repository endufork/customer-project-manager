"""Project write workflows and command handlers."""

import sqlite3
from pathlib import Path

from ..config import SHARED_FOLDER_NAME
from .customers import (
    get_or_create_contact,
    get_or_create_customer,
    get_or_create_customer_group,
    get_or_create_site,
)
from .file_import import import_source_path
from .folders import (
    delete_project_folder_if_requested,
    ensure_standard_dirs,
    get_or_create_project_group,
    move_project_folder_if_needed,
    project_folder_for,
    project_group_folder_for,
    project_parent_folder_for,
)
from .lifecycle import create_default_project_todos, create_event, generate_intake_no
from .project_queries import _project_file_flags, project_group_for_project
from .project_rules import normalize_project_nature, validate_equipment_no
from .scanner import scan_project_group_shared_folder
from ..utils import make_id, now_iso

def _project_input(data: dict, default_status: str = "inquiry") -> dict:
    return {
        "customer_group_name": (data.get("customer_group_name") or "").strip(),
        "customer_name": (data.get("customer_name") or "").strip(),
        "customer_id": (data.get("customer_id") or "").strip(),
        "site_name": (data.get("site_name") or "").strip(),
        "site_id": (data.get("site_id") or "").strip(),
        "project_group_name": (data.get("project_group_name") or "").strip(),
        "department": (data.get("department") or "").strip(),
        "contact_name": (data.get("contact_name") or "").strip(),
        "contact_id": (data.get("contact_id") or "").strip(),
        "contact_role": (data.get("contact_role") or "").strip(),
        "origin_role": (data.get("origin_role") or "").strip(),
        "po_customer_name": (data.get("po_customer_name") or "").strip(),
        "equipment_name": (data.get("equipment_name") or "").strip(),
        "project_name": (data.get("project_name") or "").strip(),
        "project_nature": normalize_project_nature(data.get("project_nature") or ""),
        "related_legacy_no": (data.get("related_legacy_no") or "").strip(),
        "status_code": (data.get("status_code") or default_status).strip(),
        "currency_code": (data.get("currency_code") or "CNY").strip().upper(),
        "equipment_no_raw": (data.get("equipment_no") or "").strip(),
        "source_path": (data.get("source_path") or "").strip(),
        "inquiry_date": (data.get("inquiry_date") or "").strip() or None,
        "expected_delivery_date": (data.get("expected_delivery_date") or "").strip() or None,
        "quote_due_date": (data.get("quote_due_date") or "").strip(),
        "notes": (data.get("notes") or "").strip() or None,
    }

def _validate_project_input(conn: sqlite3.Connection, payload: dict) -> None:
    if not payload["equipment_name"]:
        raise ValueError("项目/设备/夹具名称不能为空")
    if not conn.execute("SELECT code FROM project_statuses WHERE code = ?", (payload["status_code"],)).fetchone():
        raise ValueError("项目状态无效")
    if not conn.execute("SELECT code FROM currencies WHERE code = ?", (payload["currency_code"],)).fetchone():
        raise ValueError("币种无效")

def _lookup_name(conn: sqlite3.Connection, table: str, record_id: str | None) -> str:
    if not record_id:
        return ""
    row = conn.execute(f"SELECT name FROM {table} WHERE id = ?", (record_id,)).fetchone()
    return row["name"] if row else ""

def _resolve_customer_context(conn: sqlite3.Connection, payload: dict) -> dict:
    group_id = get_or_create_customer_group(conn, payload["customer_group_name"])
    customer_id = get_or_create_customer(conn, payload["customer_id"], payload["customer_name"], group_id)
    customer = conn.execute("SELECT name, group_id FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if group_id is None:
        group_id = customer["group_id"]
    site_id = get_or_create_site(conn, customer_id, payload["site_id"], payload["site_name"])
    contact_id = get_or_create_contact(
        conn,
        customer_id,
        site_id,
        payload["contact_id"],
        payload["contact_name"],
        payload["contact_role"],
        payload["department"],
    )
    po_customer_id = (
        get_or_create_customer(conn, "", payload["po_customer_name"], group_id)
        if payload["po_customer_name"]
        else customer_id
    )
    group_name = _lookup_name(conn, "customer_groups", group_id)
    site_name = _lookup_name(conn, "customer_sites", site_id)
    contact_name = _lookup_name(conn, "contacts", contact_id)
    return {
        "group_id": group_id,
        "group_name": group_name,
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "site_id": site_id,
        "site_name": site_name,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "po_customer_id": po_customer_id,
    }

def _ensure_project_group(conn: sqlite3.Connection, payload: dict, context: dict) -> str | None:
    project_group_name = payload["project_group_name"]
    if not project_group_name:
        return None
    project_group_folder = project_group_folder_for(
        conn,
        context["group_name"],
        context["customer_name"],
        context["site_name"],
        project_group_name,
    )
    shared_folder = project_group_folder / SHARED_FOLDER_NAME
    shared_folder.mkdir(parents=True, exist_ok=True)
    return get_or_create_project_group(
        conn,
        project_group_name,
        context["group_id"],
        context["customer_id"],
        context["site_id"],
        shared_folder,
    )

def create_project_record(conn: sqlite3.Connection, data: dict) -> dict:
    payload = _project_input(data)
    _validate_project_input(conn, payload)

    equipment_no = validate_equipment_no(conn, payload["equipment_no_raw"])
    context = _resolve_customer_context(conn, payload)
    project_group_id = _ensure_project_group(conn, payload, context)
    intake_no = generate_intake_no(conn)
    project_id = make_id()
    project_folder = project_folder_for(
        conn,
        context["group_name"],
        context["customer_name"],
        context["site_name"],
        payload["project_group_name"],
        context["contact_name"],
        payload["equipment_name"],
        intake_no,
        equipment_no,
    )
    ensure_standard_dirs(project_folder, conn)
    conn.execute(
        """
        INSERT INTO projects (
          id, intake_no, equipment_no, source_type, customer_id, contact_id,
          project_group_id, customer_group_id, site_id, department, origin_role, po_customer_id,
          project_name, equipment_name, project_nature, related_legacy_no, status_code, currency_code,
          inquiry_date, expected_delivery_date, project_folder_path,
          original_source_path, has_quote, has_po, has_3d_model,
          is_historical, is_data_complete, is_archived, notes, created_at, updated_at
        )
        VALUES (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            project_id,
            intake_no,
            equipment_no,
            "new",
            context["customer_id"],
            context["contact_id"],
            project_group_id,
            context["group_id"],
            context["site_id"],
            payload["department"] or None,
            payload["origin_role"] or None,
            context["po_customer_id"],
            payload["project_name"] or None,
            payload["equipment_name"],
            payload["project_nature"],
            payload["related_legacy_no"] or None,
            payload["status_code"],
            payload["currency_code"],
            payload["inquiry_date"],
            payload["expected_delivery_date"],
            str(project_folder),
            payload["source_path"] or None,
            0,
            0,
            0,
            0,
            0,
            0,
            payload["notes"],
            now_iso(),
            now_iso(),
        ),
    )
    create_event(conn, project_id, "project_created", "创建新项目", intake_no)
    imported_count, has_model = import_source_path(conn, project_id, project_folder, payload["source_path"])
    has_quote, has_po, indexed_has_model = _project_file_flags(conn, project_id)
    conn.execute(
        """
        UPDATE projects
        SET has_quote = ?, has_po = ?, has_3d_model = ?, updated_at = ?
        WHERE id = ?
        """,
        (has_quote, has_po, 1 if has_model or indexed_has_model else 0, now_iso(), project_id),
    )
    if imported_count:
        create_event(conn, project_id, "file_imported", f"导入 {imported_count} 个文件", payload["source_path"])
    create_default_project_todos(
        conn,
        project_id,
        equipment_no,
        payload["inquiry_date"],
        payload["quote_due_date"],
    )
    return {"id": project_id, "intake_no": intake_no, "project_folder_path": str(project_folder)}

def update_project_record(conn: sqlite3.Connection, project_id: str, data: dict) -> dict:
    payload = _project_input(data)
    _validate_project_input(conn, payload)
    existing = conn.execute("SELECT id, project_folder_path, intake_no FROM projects WHERE id = ?", (project_id,)).fetchone()
    if existing is None:
        raise ValueError("项目不存在")

    equipment_no = validate_equipment_no(conn, payload["equipment_no_raw"], project_id)
    context = _resolve_customer_context(conn, payload)
    target_parent = project_parent_folder_for(
        conn,
        context["group_name"],
        context["customer_name"],
        context["site_name"],
        payload["project_group_name"],
    )
    current_leaf = Path(existing["project_folder_path"]).name if existing["project_folder_path"] else ""
    if current_leaf:
        target_project_folder = target_parent / current_leaf
    else:
        target_project_folder = project_folder_for(
            conn,
            context["group_name"],
            context["customer_name"],
            context["site_name"],
            payload["project_group_name"],
            context["contact_name"],
            payload["equipment_name"],
            existing["intake_no"] or "",
            equipment_no,
        )

    project_group_id = None
    if payload["project_group_name"]:
        shared_folder = target_parent / SHARED_FOLDER_NAME
        shared_folder.mkdir(parents=True, exist_ok=True)
        project_group_id = get_or_create_project_group(
            conn,
            payload["project_group_name"],
            context["group_id"],
            context["customer_id"],
            context["site_id"],
            shared_folder,
        )
    move_project_folder_if_needed(conn, project_id, target_project_folder)

    conn.execute(
        """
        UPDATE projects
        SET equipment_no = ?,
            project_group_id = ?,
            customer_group_id = ?,
            customer_id = ?,
            site_id = ?,
            department = ?,
            origin_role = ?,
            po_customer_id = ?,
            contact_id = ?,
            project_name = ?,
            equipment_name = ?,
            project_nature = ?,
            related_legacy_no = ?,
            status_code = ?,
            currency_code = ?,
            inquiry_date = ?,
            expected_delivery_date = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            equipment_no,
            project_group_id,
            context["group_id"],
            context["customer_id"],
            context["site_id"],
            payload["department"] or None,
            payload["origin_role"] or None,
            context["po_customer_id"],
            context["contact_id"],
            payload["project_name"] or None,
            payload["equipment_name"],
            payload["project_nature"],
            payload["related_legacy_no"] or None,
            payload["status_code"],
            payload["currency_code"],
            payload["inquiry_date"],
            payload["expected_delivery_date"],
            payload["notes"],
            now_iso(),
            project_id,
        ),
    )
    create_event(conn, project_id, "project_updated", "修改项目基础信息")
    return {"id": project_id, "updated": True}

def delete_project_record(conn: sqlite3.Connection, project_id: str, delete_files: bool) -> dict:
    folder_deleted = False
    project = conn.execute(
        "SELECT project_folder_path FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if project is None:
        raise ValueError("项目不存在")
    folder_path = project["project_folder_path"]
    if delete_files:
        folder_deleted = delete_project_folder_if_requested(conn, folder_path)
    conn.execute("DELETE FROM file_search WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return {
        "deleted": True,
        "folder_deleted": folder_deleted,
        "project_folder_path": folder_path,
    }

def scan_project_shared_folder(conn: sqlite3.Connection, project_id: str) -> dict:
    group = project_group_for_project(conn, project_id)
    result = scan_project_group_shared_folder(conn, group["id"])
    if result["new_files"]:
        create_event(conn, project_id, "shared_folder_scanned", f"扫描共享资料，新增 {result['new_files']} 个文件")
    return result
