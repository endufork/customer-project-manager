"""Execution workbench workflows."""

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from ..config import (
    MODEL_EXTENSIONS,
    WORKBENCH_DONE_TASK_STATUSES,
    WORKBENCH_ISSUE_SCOPES,
    WORKBENCH_ISSUE_SEVERITIES,
    WORKBENCH_ISSUE_STATUSES,
    WORKBENCH_TASK_STATUSES,
    WORKBENCH_WORK_PACKAGES,
)
from ..database import row_to_dict
from ..utils import make_id, now_iso, sanitize_path_part
from .lifecycle import create_event
from .parsers import extract_text
from .scanner import sha256_file


TASK_STATUS_CODES = {item["code"] for item in WORKBENCH_TASK_STATUSES}
ISSUE_STATUS_CODES = {item["code"] for item in WORKBENCH_ISSUE_STATUSES}
ISSUE_SEVERITY_CODES = {item["code"] for item in WORKBENCH_ISSUE_SEVERITIES}
ISSUE_SCOPE_CODES = {item["code"] for item in WORKBENCH_ISSUE_SCOPES}
DONE_STATUSES = tuple(WORKBENCH_DONE_TASK_STATUSES)
DEFAULT_TASK_STATUS = "not_started"
DEFAULT_ISSUE_STATUS = "open"
DEFAULT_ISSUE_SCOPE = "equipment"


STATUS_TO_PHASE = {
    "inquiry": "inq_intake",
    "no_equipment_no": "inq_intake",
    "clarification": "clarification",
    "solution_design": "rough_solution",
    "cost_review": "quote_support",
    "internal_quote": "quote_support",
    "quoted": "waiting_feedback",
    "waiting_feedback": "waiting_feedback",
    "po_received": "wo_kickoff",
    "purchasing": "bom_purchase",
    "manufacturing": "assembly",
    "acceptance": "wiring_debug",
    "shipped": "acceptance_delivery",
    "completed": "closed",
    "lost_closed": "closed",
    "historical_entry": "closed",
}


TEMPLATES = {
    "inq": [
        ("澄清客户需求", "前期方案", "clarification", 2, 0),
        ("输出大致方案", "前期方案", "rough_solution", 3, 1),
        ("评估技术风险", "前期方案", "rough_solution", 3, 0),
        ("提供内部报价输入", "报价支持", "quote_support", 4, 1),
        ("确认客户报价资料", "报价支持", "quote_support", 5, 1),
    ],
    "wo": [
        ("细化方案确认", "项目管理", "wo_kickoff", 2, 1),
        ("机械设计", "机械设计", "detailed_design", 7, 1),
        ("电气设计", "电气设计", "detailed_design", 7, 1),
        ("BOM输出与确认", "BOM/采购", "bom_purchase", 10, 1),
        ("采购/来料跟进", "BOM/采购", "bom_purchase", 14, 0),
        ("装配", "装配", "assembly", 18, 0),
        ("接线", "接线", "wiring_debug", 20, 0),
        ("调试", "调试", "wiring_debug", 23, 1),
        ("验收资料", "验收", "acceptance_delivery", 26, 1),
        ("发货资料", "发货", "acceptance_delivery", 28, 1),
        ("项目关闭归档", "关闭归档", "closed", 30, 0),
    ],
}


def _project_row(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT p.*, c.name AS customer_name, co.name AS contact_name, s.name AS status_name,
          cg.name AS customer_group_name, cs.name AS site_name, pg.name AS project_group_name,
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
    if row is None:
        raise ValueError("项目不存在")
    return row


def _project_area(project: dict) -> str:
    if project.get("status_code") in {"completed", "lost_closed", "historical_entry"}:
        return "closed"
    if project.get("equipment_no"):
        return "wo"
    return "inq"


def _project_number(project: dict) -> str:
    return project.get("equipment_no") or project.get("intake_no") or ""


def _clean_task_status(value: str | None) -> str:
    status = (value or DEFAULT_TASK_STATUS).strip()
    if status not in TASK_STATUS_CODES:
        raise ValueError("任务状态无效")
    return status


def _clean_issue_status(value: str | None) -> str:
    status = (value or DEFAULT_ISSUE_STATUS).strip()
    if status not in ISSUE_STATUS_CODES:
        raise ValueError("问题状态无效")
    return status


def _clean_issue_severity(value: str | None) -> str:
    severity = (value or "medium").strip()
    if severity not in ISSUE_SEVERITY_CODES:
        raise ValueError("问题严重度无效")
    return severity


def _clean_issue_scope(value: str | None, task_id: str | None = None) -> str:
    scope = (value or ("task" if task_id else DEFAULT_ISSUE_SCOPE)).strip()
    if scope not in ISSUE_SCOPE_CODES:
        raise ValueError("风险影响范围无效")
    return scope


def _clean_work_package(value: str | None) -> str | None:
    work_package = (value or "").strip()
    if not work_package:
        return None
    if work_package not in WORKBENCH_WORK_PACKAGES:
        raise ValueError("工作包无效")
    return work_package


def _bool_value(value) -> int:
    if value in (1, "1", True, "true", "on", "yes"):
        return 1
    return 0


def _nullable_text(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _date_or_none(value) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("日期格式应为 YYYY-MM-DD") from exc
    return text


def _done_sql() -> str:
    return ",".join(f"'{status}'" for status in DONE_STATUSES)


def _today() -> str:
    return date.today().isoformat()


def _soon() -> str:
    return (date.today() + timedelta(days=7)).isoformat()


def record_activity(
    conn: sqlite3.Connection,
    project_id: str,
    activity_type: str,
    title: str,
    detail: str | None = None,
    task_id: str | None = None,
    issue_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO execution_activity_logs (
          id, project_id, task_id, issue_id, activity_type, title, detail, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (make_id(), project_id, task_id, issue_id, activity_type, title, detail, now_iso()),
    )


def _task_stats(conn: sqlite3.Connection, project_id: str) -> dict:
    done_sql = _done_sql()
    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS task_total,
          COALESCE(SUM(CASE WHEN status IN ({done_sql}) THEN 1 ELSE 0 END), 0) AS task_done,
          COALESCE(SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END), 0) AS blocked_tasks,
          COALESCE(SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END), 0) AS submitted_tasks,
          COALESCE(SUM(CASE WHEN due_date < ? AND status NOT IN ({done_sql}) THEN 1 ELSE 0 END), 0) AS overdue_tasks,
          MIN(CASE WHEN status NOT IN ({done_sql}) THEN due_date ELSE NULL END) AS current_due_date
        FROM execution_tasks
        WHERE project_id = ?
        """,
        (_today(), project_id),
    ).fetchone()
    return row_to_dict(row) or {}


def _issue_filter(project: dict, alias: str = "execution_issues") -> tuple[str, list[str]]:
    project_group_id = project.get("project_group_id")
    project_id = project["id"]
    if project_group_id:
        return (
            f"""
            (
              ({alias}.scope = 'product' AND EXISTS (
                SELECT 1 FROM projects issue_project
                WHERE issue_project.id = {alias}.project_id
                  AND issue_project.project_group_id = ?
              ))
              OR ({alias}.project_id = ? AND {alias}.scope <> 'product')
            )
            """,
            [project_group_id, project_id],
        )
    return (f"{alias}.project_id = ?", [project_id])


def _issue_stats(conn: sqlite3.Connection, project: dict) -> dict:
    issue_where, issue_params = _issue_filter(project)
    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS issue_total,
          COALESCE(SUM(CASE WHEN status IN ('open', 'following') THEN 1 ELSE 0 END), 0) AS open_issues,
          COALESCE(SUM(CASE WHEN severity = 'high' AND status IN ('open', 'following') THEN 1 ELSE 0 END), 0) AS high_issues
        FROM execution_issues
        WHERE {issue_where}
        """,
        issue_params,
    ).fetchone()
    return row_to_dict(row) or {}


def _current_task(conn: sqlite3.Connection, project_id: str) -> dict | None:
    done_sql = _done_sql()
    row = conn.execute(
        f"""
        SELECT *
        FROM execution_tasks
        WHERE project_id = ? AND status NOT IN ({done_sql})
        ORDER BY
          CASE status
            WHEN 'blocked' THEN 0
            WHEN 'submitted' THEN 1
            WHEN 'rework' THEN 2
            WHEN 'waiting_info' THEN 3
            WHEN 'in_progress' THEN 4
            ELSE 5
          END,
          COALESCE(due_date, '9999-12-31'),
          created_at
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    return row_to_dict(row)


def _last_activity_at(conn: sqlite3.Connection, project_id: str) -> str:
    row = conn.execute(
        """
        SELECT MAX(created_at) AS last_activity_at
        FROM execution_activity_logs
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    return (row and row["last_activity_at"]) or ""


def _enrich_project_summary(conn: sqlite3.Connection, project: dict) -> dict:
    task_stats = _task_stats(conn, project["id"])
    issue_stats = _issue_stats(conn, project)
    current_task = _current_task(conn, project["id"])
    area = _project_area(project)
    project.update(task_stats)
    project.update(issue_stats)
    project["current_number"] = _project_number(project)
    project["workbench_area"] = area
    project["workbench_phase"] = STATUS_TO_PHASE.get(project.get("status_code") or "", "inq_intake")
    project["current_owner"] = current_task.get("owner_name") if current_task else ""
    project["next_action"] = current_task.get("title") if current_task else ""
    project["next_task_id"] = current_task.get("id") if current_task else ""
    project["last_activity_at"] = _last_activity_at(conn, project["id"]) or project.get("updated_at") or project.get("created_at")
    return project


def list_workbench_projects(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    filters = []
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
    filters = [f"t.status NOT IN ({done_sql})"]
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
    filters = ["d.status = 'submitted'"]
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
    kpis = {
        "total": len(tasks) + len(deliverables),
        "blocked": task_payload["kpis"].get("blocked", 0),
        "submitted": len(deliverables) if role == "pm" else task_payload["kpis"].get("submitted", 0),
        "overdue": task_payload["kpis"].get("overdue", 0),
    }
    return {
        "role": role,
        "tasks": tasks,
        "deliverables": deliverables,
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
    return {"project": project, "tasks": tasks, "deliverables": deliverables, "issues": issues, "logs": logs}


def create_task(conn: sqlite3.Connection, project_id: str, data: dict) -> dict:
    _project_row(conn, project_id)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("任务名称不能为空")
    status = _clean_task_status(data.get("status"))
    task_id = make_id()
    now = now_iso()
    completed_at = now if status in {"confirmed", "completed"} else None
    conn.execute(
        """
        INSERT INTO execution_tasks (
          id, project_id, work_package, phase_code, title, description,
          owner_name, status, due_date, completed_at, is_required,
          requires_deliverable, blocked_reason, notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            project_id,
            _clean_work_package(data.get("work_package")),
            _nullable_text(data.get("phase_code")),
            title,
            _nullable_text(data.get("description")),
            _nullable_text(data.get("owner_name")),
            status,
            _date_or_none(data.get("due_date")),
            completed_at,
            0 if data.get("is_required") == "0" else 1,
            _bool_value(data.get("requires_deliverable")),
            _nullable_text(data.get("blocked_reason")),
            _nullable_text(data.get("notes")),
            now,
            now,
        ),
    )
    record_activity(conn, project_id, "task_created", "新增任务", title, task_id=task_id)
    create_event(conn, project_id, "workbench_task_created", "新增执行任务", title)
    return {"id": task_id, "created": True}


def update_task(conn: sqlite3.Connection, task_id: str, data: dict) -> dict:
    row = conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("任务不存在")
    title = (data.get("title") or row["title"] or "").strip()
    if not title:
        raise ValueError("任务名称不能为空")
    status = _clean_task_status(data.get("status") or row["status"])
    now = now_iso()
    started_at = row["started_at"]
    submitted_at = row["submitted_at"]
    confirmed_at = row["confirmed_at"]
    completed_at = row["completed_at"]
    if status == "in_progress" and not started_at:
        started_at = now
    if status == "submitted" and not submitted_at:
        submitted_at = now
    if status == "confirmed" and not confirmed_at:
        confirmed_at = now
        completed_at = now
    if status == "completed" and not completed_at:
        completed_at = now
    if status not in {"confirmed", "completed"}:
        completed_at = None
    conn.execute(
        """
        UPDATE execution_tasks
        SET work_package = ?,
            phase_code = ?,
            title = ?,
            description = ?,
            owner_name = ?,
            status = ?,
            due_date = ?,
            started_at = ?,
            submitted_at = ?,
            confirmed_at = ?,
            completed_at = ?,
            is_required = ?,
            requires_deliverable = ?,
            blocked_reason = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            _clean_work_package(data.get("work_package")),
            _nullable_text(data.get("phase_code")),
            title,
            _nullable_text(data.get("description")),
            _nullable_text(data.get("owner_name")),
            status,
            _date_or_none(data.get("due_date")),
            started_at,
            submitted_at,
            confirmed_at,
            completed_at,
            0 if data.get("is_required") == "0" else 1,
            _bool_value(data.get("requires_deliverable")),
            _nullable_text(data.get("blocked_reason")),
            _nullable_text(data.get("notes")),
            now,
            task_id,
        ),
    )
    record_activity(conn, row["project_id"], "task_updated", "更新任务", title, task_id=task_id)
    return {"id": task_id, "updated": True}


def delete_task(conn: sqlite3.Connection, task_id: str) -> dict:
    row = conn.execute("SELECT project_id, title FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("任务不存在")
    conn.execute("DELETE FROM execution_tasks WHERE id = ?", (task_id,))
    record_activity(conn, row["project_id"], "task_deleted", "删除任务", row["title"])
    return {"deleted": True}


def apply_template(conn: sqlite3.Connection, project_id: str, template_code: str) -> dict:
    project = row_to_dict(_project_row(conn, project_id))
    template = (template_code or "").strip() or ("wo" if project.get("equipment_no") else "inq")
    if template not in TEMPLATES:
        raise ValueError("任务模板不存在")
    created = 0
    base = date.today()
    for title, work_package, phase_code, offset_days, requires_deliverable in TEMPLATES[template]:
        exists = conn.execute(
            "SELECT 1 FROM execution_tasks WHERE project_id = ? AND title = ?",
            (project_id, title),
        ).fetchone()
        if exists:
            continue
        create_task(
            conn,
            project_id,
            {
                "title": title,
                "work_package": work_package,
                "phase_code": phase_code,
                "due_date": (base + timedelta(days=offset_days)).isoformat(),
                "requires_deliverable": requires_deliverable,
            },
        )
        created += 1
    record_activity(conn, project_id, "template_applied", "生成任务模板", f"{template} · 新增 {created} 个任务")
    return {"created": created, "template": template}


def _category_row(conn: sqlite3.Connection, category_code: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT code, name, default_folder FROM file_categories WHERE code = ? AND is_active = 1",
        (category_code,),
    ).fetchone()
    if row is None:
        raise ValueError("文件类别无效")
    return row


def _unique_path(folder: Path, filename: str) -> Path:
    path = folder / filename
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = folder / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _refresh_project_file_flags(conn: sqlite3.Connection, project_id: str) -> None:
    flags = conn.execute(
        """
        SELECT
          COALESCE(MAX(CASE WHEN category_code IN ('customer_quote', 'internal_quote') THEN 1 ELSE 0 END), 0) AS has_quote,
          COALESCE(MAX(CASE WHEN category_code = 'po' THEN 1 ELSE 0 END), 0) AS has_po,
          COALESCE(MAX(is_3d_model), 0) AS has_3d_model
        FROM project_files
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE projects
        SET has_quote = ?, has_po = ?, has_3d_model = ?, updated_at = ?
        WHERE id = ?
        """,
        (flags["has_quote"], flags["has_po"], flags["has_3d_model"], now_iso(), project_id),
    )


def submit_task_file(
    conn: sqlite3.Connection,
    task_id: str,
    filename: str,
    content: bytes,
    fields: dict,
) -> dict:
    if not filename or not content:
        raise ValueError("请选择要上传的文件")
    task = conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        raise ValueError("任务不存在")
    project = _project_row(conn, task["project_id"])
    project_folder = Path(project["project_folder_path"] or "")
    if not project_folder.exists() or not project_folder.is_dir():
        raise ValueError("项目文件夹不存在，无法归档上传文件")

    category = _category_row(conn, (fields.get("category_code") or "other").strip() or "other")
    raw_name = Path(filename).name
    safe_stem = sanitize_path_part(Path(raw_name).stem, "交付文件")
    suffix = Path(raw_name).suffix
    safe_name = f"{safe_stem}{suffix}"
    target_folder = project_folder / category["default_folder"]
    target_folder.mkdir(parents=True, exist_ok=True)
    target_path = _unique_path(target_folder, safe_name)
    target_path.write_bytes(content)

    ext = target_path.suffix.lower()
    stat = target_path.stat()
    text_extracted, extracted_text = extract_text(target_path)
    file_id = make_id()
    now = now_iso()
    conn.execute(
        """
        INSERT INTO project_files (
          id, project_id, original_name, current_name, extension, category_code,
          file_path, original_source_path, size_bytes, modified_at, is_3d_model,
          text_extracted, extracted_text, content_hash, import_method, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, 'new_project_copy', ?, ?)
        """,
        (
            file_id,
            task["project_id"],
            raw_name,
            target_path.name,
            ext,
            category["code"],
            str(target_path),
            stat.st_size,
            datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
            1 if ext in MODEL_EXTENSIONS else 0,
            text_extracted,
            extracted_text,
            sha256_file(target_path),
            now,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO file_search (file_id, project_id, file_name, extracted_text)
        VALUES (?, ?, ?, ?)
        """,
        (file_id, task["project_id"], target_path.name, extracted_text),
    )
    deliverable_id = make_id()
    conn.execute(
        """
        INSERT INTO task_deliverables (
          id, task_id, project_id, file_id, deliverable_type, version_note,
          status, submitted_by, submitted_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?)
        """,
        (
            deliverable_id,
            task_id,
            task["project_id"],
            file_id,
            category["code"],
            _nullable_text(fields.get("version_note")),
            _nullable_text(fields.get("submitted_by")),
            now,
            now,
            now,
        ),
    )
    conn.execute(
        """
        UPDATE execution_tasks
        SET status = 'submitted', submitted_at = ?, updated_at = ?, requires_deliverable = 1
        WHERE id = ?
        """,
        (now, now, task_id),
    )
    _refresh_project_file_flags(conn, task["project_id"])
    record_activity(conn, task["project_id"], "deliverable_submitted", "提交交付文件", target_path.name, task_id=task_id)
    create_event(conn, task["project_id"], "workbench_file_submitted", "提交交付文件", target_path.name)
    return {
        "id": deliverable_id,
        "file_id": file_id,
        "file_name": target_path.name,
        "file_path": str(target_path),
        "submitted": True,
    }


def review_deliverable(conn: sqlite3.Connection, deliverable_id: str, data: dict) -> dict:
    row = conn.execute("SELECT * FROM task_deliverables WHERE id = ?", (deliverable_id,)).fetchone()
    if row is None:
        raise ValueError("交付物不存在")
    action = (data.get("status") or data.get("action") or "").strip()
    now = now_iso()
    if action == "confirmed":
        reviewer = _nullable_text(data.get("confirmed_by")) or "PM"
        conn.execute(
            """
            UPDATE task_deliverables
            SET status = 'confirmed', confirmed_by = ?, confirmed_at = ?, reject_reason = NULL, updated_at = ?
            WHERE id = ?
            """,
            (reviewer, now, now, deliverable_id),
        )
        conn.execute(
            """
            UPDATE execution_tasks
            SET status = 'confirmed', confirmed_at = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, now, row["task_id"]),
        )
        record_activity(conn, row["project_id"], "deliverable_confirmed", "确认交付物", reviewer, task_id=row["task_id"])
        return {"id": deliverable_id, "status": "confirmed"}
    if action == "rejected":
        reason = _nullable_text(data.get("reject_reason"))
        if not reason:
            raise ValueError("驳回交付物需要填写原因")
        reviewer = _nullable_text(data.get("confirmed_by")) or "PM"
        conn.execute(
            """
            UPDATE task_deliverables
            SET status = 'rejected', confirmed_by = ?, confirmed_at = ?, reject_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (reviewer, now, reason, now, deliverable_id),
        )
        conn.execute(
            """
            UPDATE execution_tasks
            SET status = 'rework', notes = COALESCE(notes || char(10), '') || ?, updated_at = ?
            WHERE id = ?
            """,
            (f"交付物驳回：{reason}", now, row["task_id"]),
        )
        record_activity(conn, row["project_id"], "deliverable_rejected", "驳回交付物", reason, task_id=row["task_id"])
        return {"id": deliverable_id, "status": "rejected"}
    raise ValueError("交付物操作无效")


def create_issue(conn: sqlite3.Connection, project_id: str, data: dict) -> dict:
    _project_row(conn, project_id)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("风险/问题标题不能为空")
    raw_task_id = _nullable_text(data.get("task_id"))
    scope = _clean_issue_scope(data.get("scope"), raw_task_id)
    task_id = raw_task_id if scope == "task" else None
    if scope == "task" and not task_id:
        raise ValueError("任务级风险必须关联任务")
    issue_id = make_id()
    now = now_iso()
    conn.execute(
        """
        INSERT INTO execution_issues (
          id, project_id, task_id, scope, title, issue_type, source, severity,
          owner_name, status, due_date, resolution, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            issue_id,
            project_id,
            task_id,
            scope,
            title,
            _nullable_text(data.get("issue_type")),
            _nullable_text(data.get("source")),
            _clean_issue_severity(data.get("severity")),
            _nullable_text(data.get("owner_name")),
            _clean_issue_status(data.get("status")),
            _date_or_none(data.get("due_date")),
            _nullable_text(data.get("resolution")),
            now,
            now,
        ),
    )
    record_activity(conn, project_id, "issue_created", "新增风险/问题", title, issue_id=issue_id)
    create_event(conn, project_id, "workbench_issue_created", "新增风险/问题", title)
    return {"id": issue_id, "created": True}


def update_issue(conn: sqlite3.Connection, issue_id: str, data: dict) -> dict:
    row = conn.execute("SELECT * FROM execution_issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise ValueError("风险/问题不存在")
    title = (data.get("title") or row["title"] or "").strip()
    if not title:
        raise ValueError("风险/问题标题不能为空")
    raw_task_id = _nullable_text(data.get("task_id"))
    scope = _clean_issue_scope(data.get("scope") or row["scope"], raw_task_id)
    task_id = raw_task_id if scope == "task" else None
    if scope == "task" and not task_id:
        raise ValueError("任务级风险必须关联任务")
    status = _clean_issue_status(data.get("status") or row["status"])
    now = now_iso()
    closed_at = row["closed_at"]
    if status in {"resolved", "accepted", "closed"} and not closed_at:
        closed_at = now
    if status in {"open", "following"}:
        closed_at = None
    conn.execute(
        """
        UPDATE execution_issues
        SET task_id = ?,
            scope = ?,
            title = ?,
            issue_type = ?,
            source = ?,
            severity = ?,
            owner_name = ?,
            status = ?,
            due_date = ?,
            resolution = ?,
            updated_at = ?,
            closed_at = ?
        WHERE id = ?
        """,
        (
            task_id,
            scope,
            title,
            _nullable_text(data.get("issue_type")),
            _nullable_text(data.get("source")),
            _clean_issue_severity(data.get("severity")),
            _nullable_text(data.get("owner_name")),
            status,
            _date_or_none(data.get("due_date")),
            _nullable_text(data.get("resolution")),
            now,
            closed_at,
            issue_id,
        ),
    )
    record_activity(conn, row["project_id"], "issue_updated", "更新风险/问题", title, issue_id=issue_id)
    return {"id": issue_id, "updated": True}


def delete_issue(conn: sqlite3.Connection, issue_id: str) -> dict:
    row = conn.execute("SELECT project_id, title FROM execution_issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise ValueError("风险/问题不存在")
    conn.execute("DELETE FROM execution_issues WHERE id = ?", (issue_id,))
    record_activity(conn, row["project_id"], "issue_deleted", "删除风险/问题", row["title"])
    return {"deleted": True}
