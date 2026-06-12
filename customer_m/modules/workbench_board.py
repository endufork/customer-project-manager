"""Project board aggregation for meeting and daily follow-up views."""

from __future__ import annotations

import sqlite3

from ..database import row_to_dict
from .workbench_common import (
    DONE_STATUSES,
    _done_sql,
    _enrich_project_summaries,
    _placeholders,
    _soon,
    _today,
)


BOARD_STATUS_LABELS = {
    "overdue": "超期",
    "blocked_risk": "阻塞/风险",
    "pending": "待确认",
    "rework": "返工",
    "in_progress": "进行中",
    "pending_start": "待启动",
    "inq": "前期支持",
    "closed": "已关闭",
}


def list_workbench_board(conn: sqlite3.Connection, query: dict[str, list[str]], user: dict | None = None) -> dict:
    projects = _board_project_rows(conn, query)
    projects = _enrich_project_summaries(conn, projects)
    project_ids = [project["id"] for project in projects]

    task_status = _task_status_stats_by_project(conn, project_ids)
    pending_counts = _pending_counts_by_project(conn, project_ids)
    logs_by_project = _recent_logs_by_project(conn, project_ids)
    owner = (query.get("owner", [""])[0] or "").strip()
    view = (query.get("view", [""])[0] or "all").strip()

    board_projects = []
    for project in projects:
        project_id = project["id"]
        project.update(task_status.get(project_id, {}))
        project.update(pending_counts.get(project_id, {}))
        _set_count_defaults(project)
        project["pending_total"] = (
            project["pending_deliverables"]
            + project["pending_completions"]
            + project["pending_due_date_requests"]
            + project["pending_risk_reviews"]
        )
        project["board_flags"] = _board_flags(project)
        project["board_status"] = _board_status(project)
        project["board_status_label"] = BOARD_STATUS_LABELS[project["board_status"]]
        project["board_group"] = _board_group(project)
        project["board_group_label"] = _board_group_label(project["board_group"])
        project["board_priority"] = _board_priority(project)
        project["recent_logs"] = logs_by_project.get(project_id, [])
        board_projects.append(project)

    board_projects = _filter_board_projects(board_projects, view, owner)
    board_projects.sort(
        key=lambda project: (
            project["board_priority"],
            project.get("current_due_date") or project.get("expected_delivery_date") or "9999-12-31",
            project.get("current_number") or "",
        )
    )

    return {
        "kpis": _board_kpis(board_projects),
        "projects": board_projects,
        "groups": _board_groups(board_projects),
        "current_user": {
            "display_name": (user or {}).get("display_name") or "",
            "roles": (user or {}).get("roles") or [],
        },
    }


def _board_project_rows(conn: sqlite3.Connection, query: dict[str, list[str]]) -> list[dict]:
    filters = ["COALESCE(p.is_deleted, 0) = 0"]
    params: list[str] = []
    search = (query.get("search", [""])[0] or "").strip()
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
              OR c.name LIKE ?
              OR cg.name LIKE ?
              OR cs.name LIKE ?
              OR pg.name LIKE ?
              OR co.name LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like, like, like])

    where = "WHERE " + " AND ".join(filters)
    return [
        row_to_dict(row)
        for row in conn.execute(
            f"""
            SELECT p.id, p.intake_no, p.equipment_no, p.equipment_name, p.project_name,
              p.project_nature, p.project_group_id, p.status_code, s.name AS status_name,
              p.expected_delivery_date, p.project_folder_path, p.created_at, p.updated_at,
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
            LIMIT 500
            """,
            params,
        )
    ]


def _task_status_stats_by_project(conn: sqlite3.Connection, project_ids: list[str]) -> dict[str, dict]:
    if not project_ids:
        return {}
    done_sql = _done_sql()
    placeholders = _placeholders(project_ids)
    rows = conn.execute(
        f"""
        SELECT
          project_id,
          COALESCE(SUM(CASE WHEN status = 'rework' THEN 1 ELSE 0 END), 0) AS rework_tasks,
          COALESCE(SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END), 0) AS in_progress_tasks,
          COALESCE(SUM(CASE WHEN status = 'waiting_info' THEN 1 ELSE 0 END), 0) AS waiting_info_tasks,
          COALESCE(SUM(CASE WHEN due_date >= ? AND due_date <= ? AND status NOT IN ({done_sql}) THEN 1 ELSE 0 END), 0) AS due_soon_tasks
        FROM execution_tasks
        WHERE project_id IN ({placeholders})
        GROUP BY project_id
        """,
        [_today(), _soon(), *project_ids],
    ).fetchall()
    return {row["project_id"]: row_to_dict(row) for row in rows}


def _pending_counts_by_project(conn: sqlite3.Connection, project_ids: list[str]) -> dict[str, dict]:
    counts = {
        project_id: {
            "pending_deliverables": 0,
            "pending_completions": 0,
            "pending_due_date_requests": 0,
            "pending_risk_reviews": 0,
        }
        for project_id in project_ids
    }
    if not project_ids:
        return counts
    placeholders = _placeholders(project_ids)
    specs = [
        (
            "pending_deliverables",
            f"""
            SELECT project_id, COUNT(*) AS count
            FROM task_deliverables
            WHERE project_id IN ({placeholders}) AND status = 'submitted'
            GROUP BY project_id
            """,
        ),
        (
            "pending_completions",
            f"""
            SELECT project_id, COUNT(*) AS count
            FROM execution_tasks
            WHERE project_id IN ({placeholders}) AND status = 'submitted' AND requires_deliverable = 0
            GROUP BY project_id
            """,
        ),
        (
            "pending_due_date_requests",
            f"""
            SELECT project_id, COUNT(*) AS count
            FROM due_date_change_requests
            WHERE project_id IN ({placeholders}) AND status = 'pending'
            GROUP BY project_id
            """,
        ),
        (
            "pending_risk_reviews",
            f"""
            SELECT project_id, COUNT(*) AS count
            FROM execution_issues
            WHERE project_id IN ({placeholders}) AND status = 'resolved'
            GROUP BY project_id
            """,
        ),
    ]
    for field, sql in specs:
        for row in conn.execute(sql, project_ids):
            counts.setdefault(row["project_id"], {})[field] = int(row["count"] or 0)
    return counts


def _recent_logs_by_project(conn: sqlite3.Connection, project_ids: list[str]) -> dict[str, list[dict]]:
    if not project_ids:
        return {}
    placeholders = _placeholders(project_ids)
    rows = conn.execute(
        f"""
        SELECT project_id, activity_type, title, detail, created_at
        FROM execution_activity_logs
        WHERE project_id IN ({placeholders})
        ORDER BY project_id, created_at DESC
        """,
        project_ids,
    ).fetchall()
    logs: dict[str, list[dict]] = {}
    for row in rows:
        bucket = logs.setdefault(row["project_id"], [])
        if len(bucket) < 5:
            bucket.append(row_to_dict(row))
    return logs


def _set_count_defaults(project: dict) -> None:
    for key in (
        "task_total",
        "task_done",
        "blocked_tasks",
        "submitted_tasks",
        "overdue_tasks",
        "issue_total",
        "open_issues",
        "high_issues",
        "rework_tasks",
        "in_progress_tasks",
        "waiting_info_tasks",
        "due_soon_tasks",
        "pending_deliverables",
        "pending_completions",
        "pending_due_date_requests",
        "pending_risk_reviews",
    ):
        project[key] = int(project.get(key) or 0)


def _board_flags(project: dict) -> list[str]:
    flags = []
    if project["overdue_tasks"]:
        flags.append("超期")
    if project["blocked_tasks"] or project["waiting_info_tasks"]:
        flags.append("阻塞")
    if project["high_issues"]:
        flags.append("高风险")
    if project["pending_total"]:
        flags.append("待确认")
    if project["rework_tasks"]:
        flags.append("返工")
    if project.get("workbench_area") == "inq":
        flags.append("待WO")
    return flags


def _board_status(project: dict) -> str:
    if project.get("workbench_area") == "closed":
        return "closed"
    if project["overdue_tasks"]:
        return "overdue"
    if project["blocked_tasks"] or project["waiting_info_tasks"] or project["high_issues"]:
        return "blocked_risk"
    if project["pending_total"]:
        return "pending"
    if project["rework_tasks"]:
        return "rework"
    if project["in_progress_tasks"]:
        return "in_progress"
    if project.get("workbench_area") == "wo" and not project["task_total"]:
        return "pending_start"
    if project.get("workbench_area") == "inq":
        return "inq"
    return "in_progress"


def _board_priority(project: dict) -> int:
    return {
        "overdue": 0,
        "blocked_risk": 1,
        "pending": 2,
        "rework": 3,
        "in_progress": 4,
        "pending_start": 5,
        "inq": 6,
        "closed": 7,
    }.get(project["board_status"], 8)


def _board_group(project: dict) -> str:
    if project["board_status"] in {"overdue", "blocked_risk", "pending", "rework"}:
        return "attention"
    if project.get("workbench_area") == "closed":
        return "closed"
    if project.get("workbench_area") == "inq":
        return "inq"
    return "normal"


def _board_group_label(group: str) -> str:
    return {
        "attention": "需要处理",
        "normal": "正常推进",
        "inq": "前期支持",
        "closed": "已关闭 / 低关注",
    }.get(group, group)


def _filter_board_projects(projects: list[dict], view: str, owner: str) -> list[dict]:
    if view in {"", "all"}:
        return projects
    if view == "attention":
        return [project for project in projects if project["board_group"] == "attention"]
    if view == "due_soon":
        return [project for project in projects if project["due_soon_tasks"]]
    if view == "overdue":
        return [project for project in projects if project["overdue_tasks"]]
    if view == "blocked":
        return [
            project
            for project in projects
            if project["blocked_tasks"] or project["waiting_info_tasks"] or project["high_issues"] or project["open_issues"]
        ]
    if view == "pending":
        return [project for project in projects if project["pending_total"]]
    if view == "mine":
        if not owner:
            return []
        return [
            project
            for project in projects
            if owner.lower() in (project.get("current_owner") or "").lower()
        ]
    if view == "inq":
        return [project for project in projects if project.get("workbench_area") == "inq"]
    if view == "wo":
        return [project for project in projects if project.get("workbench_area") == "wo"]
    return projects


def _board_kpis(projects: list[dict]) -> dict:
    return {
        "active_projects": sum(1 for project in projects if project.get("workbench_area") != "closed"),
        "due_soon_tasks": sum(project["due_soon_tasks"] for project in projects),
        "overdue_tasks": sum(project["overdue_tasks"] for project in projects),
        "blocked_projects": sum(1 for project in projects if project["blocked_tasks"] or project["waiting_info_tasks"]),
        "pending_confirmations": sum(project["pending_total"] for project in projects),
        "high_risk_projects": sum(1 for project in projects if project["high_issues"]),
    }


def _board_groups(projects: list[dict]) -> list[dict]:
    groups = []
    for key in ("attention", "normal", "inq", "closed"):
        items = [project for project in projects if project["board_group"] == key]
        groups.append({"key": key, "label": _board_group_label(key), "count": len(items)})
    return groups
