"""Project read models and lookup queries."""

import sqlite3

from ..config import STATUS_DATE_FIELD_BY_STATUS, STATUS_DATE_LABELS
from ..database import row_to_dict


def status_date_label(status_code: str) -> str:
    return STATUS_DATE_LABELS.get(status_code, "状态日期")


def current_status_date(project: dict) -> str:
    status_code = project.get("status_code") or ""
    mapped_field = STATUS_DATE_FIELD_BY_STATUS.get(status_code)
    if project.get("status_date"):
        return project["status_date"]
    if mapped_field and project.get(mapped_field):
        return project[mapped_field]
    return ""


def enrich_project_status_date(project: dict) -> dict:
    project["status_date_label"] = status_date_label(project.get("status_code") or "")
    project["current_status_date"] = current_status_date(project)
    return project


def list_project_records(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    filters = ["COALESCE(p.is_deleted, 0) = 0"]
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
          p.status_code, s.name AS status_name, p.status_date, p.currency_code,
          p.inquiry_date, p.quote_date, p.po_date, p.expected_delivery_date,
          p.actual_ship_date, p.has_quote, p.has_po,
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
    rows = [enrich_project_status_date(row_to_dict(row)) for row in conn.execute(sql, params)]
    kpis = row_to_dict(
        conn.execute(
            """
            SELECT
              COUNT(*) AS total_projects,
              COALESCE(SUM(CASE WHEN equipment_no IS NULL THEN 1 ELSE 0 END), 0) AS no_equipment_no,
              COALESCE(SUM(CASE WHEN has_po = 1 THEN 1 ELSE 0 END), 0) AS with_po,
              COALESCE(SUM(CASE WHEN has_3d_model = 1 THEN 1 ELSE 0 END), 0) AS with_model
            FROM projects
            WHERE COALESCE(is_deleted, 0) = 0
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
            WHERE p.id = ? AND COALESCE(p.is_deleted, 0) = 0
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
            SELECT f.*, fc.name AS category_name, fc.default_folder AS category_folder
            FROM project_files f
            JOIN file_categories fc ON fc.code = f.category_code
            WHERE f.project_id = ?
            ORDER BY fc.default_folder, f.file_path, f.original_name
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
                SELECT f.*, fc.name AS category_name, fc.default_folder AS category_folder
                FROM project_group_files f
                JOIN file_categories fc ON fc.code = f.category_code
                WHERE f.project_group_id = ?
                ORDER BY fc.default_folder, f.file_path, f.original_name
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
    return {"project": enrich_project_status_date(project), "files": files, "shared_files": shared_files, "events": events}

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

def get_project_folder_path(conn: sqlite3.Connection, project_id: str) -> str:
    row = conn.execute(
        "SELECT project_folder_path FROM projects WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
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
        WHERE p.id = ? AND COALESCE(p.is_deleted, 0) = 0
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        raise ValueError("该项目未关联客户产品/生产线")
    return row

def get_project_shared_folder_path(conn: sqlite3.Connection, project_id: str) -> str:
    group = project_group_for_project(conn, project_id)
    return group["shared_folder_path"] or ""
