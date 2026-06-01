"""Project record workflows."""

import sqlite3
from pathlib import Path

from ..config import EQUIPMENT_NO_RE, PROJECT_NATURES, SHARED_FOLDER_NAME
from ..database import row_to_dict
from ..utils import make_id, now_iso
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
from .scanner import scan_project_group_shared_folder


def validate_equipment_no(
    conn: sqlite3.Connection,
    equipment_no: str,
    exclude_project_id: str | None = None,
) -> str | None:
    value = equipment_no.strip()
    if not value:
        return None
    if not EQUIPMENT_NO_RE.fullmatch(value):
        raise ValueError("内部设备号只能包含英文字母、数字、横杠和下划线")
    if exclude_project_id:
        existing = conn.execute(
            "SELECT id FROM projects WHERE equipment_no = ? COLLATE NOCASE AND id <> ?",
            (value, exclude_project_id),
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT id FROM projects WHERE equipment_no = ? COLLATE NOCASE",
            (value,),
        ).fetchone()
    if existing:
        raise ValueError("内部设备号已存在")
    return value


def normalize_project_nature(value: str) -> str:
    nature = value.strip() or "新设备"
    if nature not in PROJECT_NATURES:
        raise ValueError("项目性质无效")
    return nature


def list_project_records(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    filters = []
    params: list[str] = []
    search = (query.get("search", [""])[0] or "").strip()
    status = (query.get("status", [""])[0] or "").strip()
    customer_id = (query.get("customer_id", [""])[0] or "").strip()
    group_id = (query.get("group_id", [""])[0] or "").strip()
    site_id = (query.get("site_id", [""])[0] or "").strip()
    needs_equipment = (query.get("needs_equipment", [""])[0] or "").strip()

    if search:
        like = f"%{search}%"
        filters.append(
            """
            (
              p.intake_no LIKE ?
              OR p.equipment_no LIKE ?
              OR p.equipment_name LIKE ?
              OR p.project_name LIKE ?
              OR p.project_nature LIKE ?
              OR p.related_legacy_no LIKE ?
              OR c.name LIKE ?
              OR cg.name LIKE ?
              OR cs.name LIKE ?
              OR pg.name LIKE ?
              OR co.name LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like, like, like, like])
    if status:
        filters.append("p.status_code = ?")
        params.append(status)
    if customer_id:
        filters.append("p.customer_id = ?")
        params.append(customer_id)
    if group_id:
        filters.append("p.customer_group_id = ?")
        params.append(group_id)
    if site_id:
        filters.append("p.site_id = ?")
        params.append(site_id)
    if needs_equipment == "1":
        filters.append("p.equipment_no IS NULL")

    where = "WHERE " + " AND ".join(filters) if filters else ""
    sql = f"""
        SELECT
          p.id, p.intake_no, p.equipment_no, p.equipment_name, p.project_name,
          p.project_nature, p.related_legacy_no,
          p.status_code, s.name AS status_name, p.currency_code,
          p.inquiry_date, p.expected_delivery_date, p.has_quote, p.has_po,
          p.has_3d_model, p.project_folder_path, p.created_at,
          cg.name AS customer_group_name, cs.name AS site_name, pg.name AS project_group_name, p.department,
          c.name AS customer_name, co.name AS contact_name,
          COUNT(f.id) AS file_count
        FROM projects p
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
        LEFT JOIN customer_sites cs ON cs.id = p.site_id
        LEFT JOIN project_groups pg ON pg.id = p.project_group_id
        LEFT JOIN contacts co ON co.id = p.contact_id
        JOIN project_statuses s ON s.code = p.status_code
        LEFT JOIN project_files f ON f.project_id = p.id
        {where}
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT 200
    """
    rows = [row_to_dict(row) for row in conn.execute(sql, params)]
    kpis = row_to_dict(
        conn.execute(
            """
            SELECT
              COUNT(*) AS total_projects,
              COALESCE(SUM(CASE WHEN equipment_no IS NULL THEN 1 ELSE 0 END), 0) AS no_equipment_no,
              COALESCE(SUM(CASE WHEN has_po = 1 THEN 1 ELSE 0 END), 0) AS with_po,
              COALESCE(SUM(CASE WHEN has_3d_model = 1 THEN 1 ELSE 0 END), 0) AS with_model
            FROM projects
            """
        ).fetchone()
    )
    return {"projects": rows, "kpis": kpis}


def get_project_detail_payload(conn: sqlite3.Connection, project_id: str) -> dict | None:
    project = row_to_dict(
        conn.execute(
            """
            SELECT p.*, c.name AS customer_name, co.name AS contact_name, s.name AS status_name
            , cg.name AS customer_group_name, cs.name AS site_name,
              pg.name AS project_group_name, pg.shared_folder_path AS shared_folder_path,
              po.name AS po_customer_name
            FROM projects p
            JOIN customers c ON c.id = p.customer_id
            LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
            LEFT JOIN customer_sites cs ON cs.id = p.site_id
            LEFT JOIN project_groups pg ON pg.id = p.project_group_id
            LEFT JOIN customers po ON po.id = p.po_customer_id
            LEFT JOIN contacts co ON co.id = p.contact_id
            JOIN project_statuses s ON s.code = p.status_code
            WHERE p.id = ?
            """,
            (project_id,),
        ).fetchone()
    )
    if project is None:
        return None

    files = [
        row_to_dict(row)
        for row in conn.execute(
            """
            SELECT f.*, fc.name AS category_name
            FROM project_files f
            JOIN file_categories fc ON fc.code = f.category_code
            WHERE f.project_id = ?
            ORDER BY fc.sort_order, f.original_name
            """,
            (project_id,),
        )
    ]
    shared_files = []
    if project.get("project_group_id"):
        shared_files = [
            row_to_dict(row)
            for row in conn.execute(
                """
                SELECT f.*, fc.name AS category_name
                FROM project_group_files f
                JOIN file_categories fc ON fc.code = f.category_code
                WHERE f.project_group_id = ?
                ORDER BY fc.sort_order, f.original_name
                """,
                (project["project_group_id"],),
            )
        ]
    events = [
        row_to_dict(row)
        for row in conn.execute(
            "SELECT * FROM project_events WHERE project_id = ? ORDER BY created_at DESC LIMIT 50",
            (project_id,),
        )
    ]
    return {"project": project, "files": files, "shared_files": shared_files, "events": events}


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


def _project_file_flags(conn: sqlite3.Connection, project_id: str) -> tuple[int, int, int]:
    has_quote = 1 if conn.execute(
        """
        SELECT 1 FROM project_files
        WHERE project_id = ? AND category_code IN ('customer_quote', 'internal_quote')
        LIMIT 1
        """,
        (project_id,),
    ).fetchone() else 0
    has_po = 1 if conn.execute(
        "SELECT 1 FROM project_files WHERE project_id = ? AND category_code = 'po' LIMIT 1",
        (project_id,),
    ).fetchone() else 0
    has_model = 1 if conn.execute(
        "SELECT 1 FROM project_files WHERE project_id = ? AND is_3d_model = 1 LIMIT 1",
        (project_id,),
    ).fetchone() else 0
    return has_quote, has_po, has_model


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


def get_project_folder_path(conn: sqlite3.Connection, project_id: str) -> str:
    row = conn.execute(
        "SELECT project_folder_path FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if row is None:
        raise ValueError("项目不存在")
    return row["project_folder_path"] or ""


def project_group_for_project(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT pg.id, pg.shared_folder_path
        FROM projects p
        JOIN project_groups pg ON pg.id = p.project_group_id
        WHERE p.id = ?
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        raise ValueError("该项目未关联客户产品/生产线")
    return row


def get_project_shared_folder_path(conn: sqlite3.Connection, project_id: str) -> str:
    group = project_group_for_project(conn, project_id)
    return group["shared_folder_path"] or ""


def scan_project_shared_folder(conn: sqlite3.Connection, project_id: str) -> dict:
    group = project_group_for_project(conn, project_id)
    result = scan_project_group_shared_folder(conn, group["id"])
    if result["new_files"]:
        create_event(conn, project_id, "shared_folder_scanned", f"扫描共享资料，新增 {result['new_files']} 个文件")
    return result
