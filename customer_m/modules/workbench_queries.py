"""Workbench project, inbox, and detail queries."""

import sqlite3

from ..database import row_to_dict
from .workbench_due_dates import due_date_requests_for_project, list_due_date_requests
from .workbench_common import (
    DONE_STATUSES,
    _done_sql,
    _enrich_project_summary,
    _issue_filter,
    _project_area,
    _project_number,
    _project_row,
    _soon,
    _today,
)


def list_workbench_projects(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    filters = ["COALESCE(p.is_deleted, 0) = 0"]
    params: list[str] = []
    search = (query.get("search", [""])[0] or "").strip()
    area_filter = (query.get("area", [""])[0] or "").strip()
    owner = (query.get("owner", [""])[0] or "").strip()
    view = (query.get("view", [""])[0] or "all").strip()

    if search:
        like = f"%{search}%"
        filters.append(
            """
            (
              p.intake_no LIKE ?
              OR p.equipment_no LIKE ?
              OR p.equipment_name LIKE ?
              OR p.project_name LIKE ?
              OR c.name LIKE ?
              OR cg.name LIKE ?
              OR cs.name LIKE ?
              OR pg.name LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like])
    if owner:
        filters.append(
            """
            EXISTS (
              SELECT 1 FROM execution_tasks t
              WHERE t.project_id = p.id AND t.owner_name LIKE ?
            )
            """
        )
        params.append(f"%{owner}%")

    where = "WHERE " + " AND ".join(filters) if filters else ""
    rows = [
        _enrich_project_summary(conn, row_to_dict(row))
        for row in conn.execute(
            f"""
            SELECT p.id, p.intake_no, p.equipment_no, p.equipment_name, p.project_name,
              p.project_nature, p.status_code, s.name AS status_name, p.expected_delivery_date,
              p.project_folder_path, p.created_at, p.updated_at,
              c.name AS customer_name, cg.name AS customer_group_name,
              cs.name AS site_name, pg.name AS project_group_name, co.name AS contact_name
            FROM projects p
            JOIN customers c ON c.id = p.customer_id
            LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
            LEFT JOIN customer_sites cs ON cs.id = p.site_id
            LEFT JOIN project_groups pg ON pg.id = p.project_group_id
            LEFT JOIN contacts co ON co.id = p.contact_id
            JOIN project_statuses s ON s.code = p.status_code
            {where}
            ORDER BY p.created_at DESC
            LIMIT 300
            """,
            params,
        )
    ]

    if area_filter:
        rows = [project for project in rows if project["workbench_area"] == area_filter]
    if view == "inq":
        rows = [project for project in rows if project["workbench_area"] == "inq"]
    elif view == "wo":
        rows = [project for project in rows if project["workbench_area"] == "wo"]
    elif view == "closed":
        rows = [project for project in rows if project["workbench_area"] == "closed"]
    elif view == "blocked":
        rows = [project for project in rows if project.get("blocked_tasks", 0) or project.get("open_issues", 0)]
    elif view == "submitted":
        rows = [project for project in rows if project.get("submitted_tasks", 0)]
    elif view == "overdue":
        rows = [project for project in rows if project.get("overdue_tasks", 0)]
    elif view == "due_soon":
        rows = [
            project
            for project in rows
            if project.get("current_due_date") and _today() <= project["current_due_date"] <= _soon()
        ]
    elif view == "high_risk":
        rows = [project for project in rows if project.get("high_issues", 0)]

    rows.sort(
        key=lambda item: (
            0 if item.get("overdue_tasks") else 1,
            0 if item.get("blocked_tasks") else 1,
            item.get("current_due_date") or "9999-12-31",
            item.get("current_number") or "",
        )
    )
    kpis = {
        "total": len(rows),
        "blocked": sum(1 for project in rows if project.get("blocked_tasks") or project.get("open_issues")),
        "submitted": sum(1 for project in rows if project.get("submitted_tasks")),
        "overdue": sum(1 for project in rows if project.get("overdue_tasks")),
    }
    return {"projects": rows, "kpis": kpis}

def list_workbench_tasks(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    done_sql = _done_sql()
    filters = [f"t.status NOT IN ({done_sql})", "COALESCE(p.is_deleted, 0) = 0"]
    params: list[str] = []
    search = (query.get("search", [""])[0] or "").strip()
    owner = (query.get("owner", [""])[0] or "").strip()
    view = (query.get("view", [""])[0] or "all").strip()

    if owner:
        filters.append("t.owner_name LIKE ?")
        params.append(f"%{owner}%")
    if search:
        like = f"%{search}%"
        filters.append(
            """
            (
              t.title LIKE ?
              OR t.work_package LIKE ?
              OR t.owner_name LIKE ?
              OR p.intake_no LIKE ?
              OR p.equipment_no LIKE ?
              OR p.equipment_name LIKE ?
              OR p.project_name LIKE ?
              OR c.name LIKE ?
              OR cs.name LIKE ?
              OR pg.name LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like, like, like])
    if view == "overdue":
        filters.append("t.due_date < ?")
        params.append(_today())
    elif view == "due_soon":
        filters.append("t.due_date >= ? AND t.due_date <= ?")
        params.extend([_today(), _soon()])
    elif view == "blocked":
        filters.append("t.status IN ('blocked', 'waiting_info', 'rework')")
    elif view == "submitted":
        filters.append("t.status = 'submitted'")

    where = "WHERE " + " AND ".join(filters)
    rows = []
    for row in conn.execute(
        f"""
        SELECT
          t.*,
          p.intake_no,
          p.equipment_no,
          p.equipment_name,
          p.project_name,
          p.project_nature,
          p.status_code,
          p.expected_delivery_date,
          p.project_folder_path,
          p.created_at AS project_created_at,
          p.updated_at AS project_updated_at,
          c.name AS customer_name,
          cg.name AS customer_group_name,
          cs.name AS site_name,
          pg.name AS project_group_name,
          co.name AS contact_name
        FROM execution_tasks t
        JOIN projects p ON p.id = t.project_id
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
        LEFT JOIN customer_sites cs ON cs.id = p.site_id
        LEFT JOIN project_groups pg ON pg.id = p.project_group_id
        LEFT JOIN contacts co ON co.id = p.contact_id
        {where}
        ORDER BY
          CASE t.status
            WHEN 'blocked' THEN 0
            WHEN 'rework' THEN 1
            WHEN 'waiting_info' THEN 2
            WHEN 'submitted' THEN 3
            WHEN 'in_progress' THEN 4
            WHEN 'not_started' THEN 5
            ELSE 6
          END,
          COALESCE(t.due_date, '9999-12-31'),
          t.created_at
        LIMIT 500
        """,
        params,
    ):
        task = row_to_dict(row)
        project = _enrich_project_summary(
            conn,
            {
                "id": task["project_id"],
                "intake_no": task.get("intake_no"),
                "equipment_no": task.get("equipment_no"),
                "equipment_name": task.get("equipment_name"),
                "project_name": task.get("project_name"),
                "project_nature": task.get("project_nature"),
                "status_code": task.get("status_code"),
                "expected_delivery_date": task.get("expected_delivery_date"),
                "project_folder_path": task.get("project_folder_path"),
                "created_at": task.get("project_created_at"),
                "updated_at": task.get("project_updated_at"),
                "customer_name": task.get("customer_name"),
                "customer_group_name": task.get("customer_group_name"),
                "site_name": task.get("site_name"),
                "project_group_name": task.get("project_group_name"),
                "contact_name": task.get("contact_name"),
            },
        )
        task["current_number"] = project["current_number"]
        task["workbench_area"] = project["workbench_area"]
        task["project_open_issues"] = project.get("open_issues", 0)
        task["project_high_issues"] = project.get("high_issues", 0)
        rows.append(task)

    if view == "inq":
        rows = [task for task in rows if task["workbench_area"] == "inq"]
    elif view == "wo":
        rows = [task for task in rows if task["workbench_area"] == "wo"]
    elif view == "closed":
        rows = [task for task in rows if task["workbench_area"] == "closed"]
    elif view == "high_risk":
        rows = [task for task in rows if task.get("project_high_issues", 0)]

    kpis = {
        "total": len(rows),
        "blocked": sum(1 for task in rows if task.get("status") in {"blocked", "waiting_info", "rework"}),
        "submitted": sum(1 for task in rows if task.get("status") == "submitted"),
        "overdue": sum(
            1
            for task in rows
            if task.get("due_date") and task["due_date"] < _today() and task.get("status") not in DONE_STATUSES
        ),
    }
    return {"tasks": rows, "kpis": kpis}

def list_pending_deliverables(conn: sqlite3.Connection, query: dict[str, list[str]]) -> list[dict]:
    filters = ["d.status = 'submitted'", "COALESCE(p.is_deleted, 0) = 0"]
    params: list[str] = []
    search = (query.get("search", [""])[0] or "").strip()
    view = (query.get("view", [""])[0] or "all").strip()

    if view not in {"", "all", "submitted"}:
        return []
    if search:
        like = f"%{search}%"
        filters.append(
            """
            (
              pf.current_name LIKE ?
              OR t.title LIKE ?
              OR p.intake_no LIKE ?
              OR p.equipment_no LIKE ?
              OR p.equipment_name LIKE ?
              OR p.project_name LIKE ?
              OR c.name LIKE ?
              OR cs.name LIKE ?
              OR pg.name LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like, like])

    where = "WHERE " + " AND ".join(filters)
    rows = []
    for row in conn.execute(
        f"""
        SELECT
          d.*,
          t.title AS task_title,
          t.owner_name AS task_owner_name,
          pf.current_name AS file_name,
          pf.file_path,
          fc.name AS category_name,
          p.intake_no,
          p.equipment_no,
          p.equipment_name,
          p.project_name,
          p.project_nature,
          p.status_code,
          p.expected_delivery_date,
          p.project_folder_path,
          p.created_at AS project_created_at,
          p.updated_at AS project_updated_at,
          c.name AS customer_name,
          cg.name AS customer_group_name,
          cs.name AS site_name,
          pg.name AS project_group_name,
          co.name AS contact_name
        FROM task_deliverables d
        JOIN execution_tasks t ON t.id = d.task_id
        JOIN projects p ON p.id = d.project_id
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
        LEFT JOIN customer_sites cs ON cs.id = p.site_id
        LEFT JOIN project_groups pg ON pg.id = p.project_group_id
        LEFT JOIN contacts co ON co.id = p.contact_id
        LEFT JOIN project_files pf ON pf.id = d.file_id
        LEFT JOIN file_categories fc ON fc.code = pf.category_code
        {where}
        ORDER BY d.submitted_at DESC, d.created_at DESC
        LIMIT 300
        """,
        params,
    ):
        deliverable = row_to_dict(row)
        deliverable["current_number"] = _project_number(deliverable)
        deliverable["workbench_area"] = _project_area(deliverable)
        rows.append(deliverable)
    return rows

def list_workbench_inbox(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    role = (query.get("role", ["engineer"])[0] or "engineer").strip().lower()
    if role not in {"engineer", "pm"}:
        role = "engineer"

    owner = (query.get("owner", [""])[0] or "").strip()
    if role == "pm" and not owner:
        task_payload = {"tasks": [], "kpis": {"blocked": 0, "submitted": 0, "overdue": 0}}
    else:
        task_payload = list_workbench_tasks(conn, query)
    tasks = task_payload["tasks"]
    deliverables = list_pending_deliverables(conn, query) if role == "pm" else []
    due_date_requests = list_due_date_requests(conn, query) if role == "pm" else []
    kpis = {
        "total": len(tasks) + len(deliverables) + len(due_date_requests),
        "blocked": task_payload["kpis"].get("blocked", 0),
        "submitted": len(deliverables) + len(due_date_requests) if role == "pm" else task_payload["kpis"].get("submitted", 0),
        "overdue": task_payload["kpis"].get("overdue", 0),
    }
    return {
        "role": role,
        "tasks": tasks,
        "deliverables": deliverables,
        "due_date_requests": due_date_requests,
        "kpis": kpis,
    }

def _deliverables_for_project(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    return [
        row_to_dict(row)
        for row in conn.execute(
            """
            SELECT d.*, pf.current_name AS file_name, pf.file_path, fc.name AS category_name
            FROM task_deliverables d
            LEFT JOIN project_files pf ON pf.id = d.file_id
            LEFT JOIN file_categories fc ON fc.code = pf.category_code
            WHERE d.project_id = ?
            ORDER BY d.submitted_at DESC
            """,
            (project_id,),
        )
    ]

def get_workbench_project(conn: sqlite3.Connection, project_id: str) -> dict:
    project = _enrich_project_summary(conn, row_to_dict(_project_row(conn, project_id)))
    tasks = [
        row_to_dict(row)
        for row in conn.execute(
            """
            SELECT *
            FROM execution_tasks
            WHERE project_id = ?
            ORDER BY
              CASE status
                WHEN 'blocked' THEN 0
                WHEN 'submitted' THEN 1
                WHEN 'rework' THEN 2
                WHEN 'waiting_info' THEN 3
                WHEN 'in_progress' THEN 4
                WHEN 'not_started' THEN 5
                ELSE 6
              END,
              COALESCE(due_date, '9999-12-31'),
              created_at
            """,
            (project_id,),
        )
    ]
    deliverables = _deliverables_for_project(conn, project_id)
    by_task: dict[str, list[dict]] = {}
    for deliverable in deliverables:
        by_task.setdefault(deliverable["task_id"], []).append(deliverable)
    for task in tasks:
        task["deliverables"] = by_task.get(task["id"], [])
    due_date_requests = due_date_requests_for_project(conn, project_id)
    due_requests_by_task: dict[str, list[dict]] = {}
    for item in due_date_requests:
        due_requests_by_task.setdefault(item["task_id"], []).append(item)
    for task in tasks:
        task["due_date_requests"] = due_requests_by_task.get(task["id"], [])

    issue_where, issue_params = _issue_filter(project, "ei")
    issues = [
        row_to_dict(row)
        for row in conn.execute(
            f"""
            SELECT ei.*, source_project.equipment_name AS issue_project_name
            FROM execution_issues ei
            LEFT JOIN projects source_project ON source_project.id = ei.project_id
            WHERE {issue_where}
            ORDER BY
              CASE ei.scope WHEN 'product' THEN 0 WHEN 'equipment' THEN 1 ELSE 2 END,
              CASE ei.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
              CASE ei.status WHEN 'open' THEN 0 WHEN 'following' THEN 1 ELSE 2 END,
              COALESCE(ei.due_date, '9999-12-31'),
              ei.created_at DESC
            """,
            issue_params,
        )
    ]
    logs = [
        row_to_dict(row)
        for row in conn.execute(
            """
            SELECT *
            FROM execution_activity_logs
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT 80
            """,
            (project_id,),
        )
    ]
    return {
        "project": project,
        "tasks": tasks,
        "deliverables": deliverables,
        "due_date_requests": due_date_requests,
        "issues": issues,
        "logs": logs,
    }
