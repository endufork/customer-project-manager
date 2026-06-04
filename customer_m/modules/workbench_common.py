"""Shared helpers for engineering workbench modules."""

import sqlite3
from datetime import date, timedelta

from ..config import (
    WORKBENCH_DONE_TASK_STATUSES,
    WORKBENCH_ISSUE_SCOPES,
    WORKBENCH_ISSUE_SEVERITIES,
    WORKBENCH_ISSUE_STATUSES,
    WORKBENCH_TASK_STATUSES,
    WORKBENCH_WORK_PACKAGES,
)
from ..database import row_to_dict
from ..utils import make_id, now_iso


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
