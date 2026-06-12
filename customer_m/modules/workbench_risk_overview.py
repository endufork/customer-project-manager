"""Cross-project risk overview queries for the project board."""

from __future__ import annotations

import sqlite3

from ..database import row_to_dict
from .workbench_common import _project_area, _project_number, _soon, _today


ACTIVE_RISK_STATUSES = {"open", "following", "resolved"}


def list_workbench_risks(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    risks = _risk_rows(conn, query)
    for risk in risks:
        risk["current_number"] = _project_number(risk)
        risk["workbench_area"] = _project_area(risk)
        risk["is_overdue"] = bool(risk.get("due_date") and risk["due_date"] < _today() and risk["status"] in ACTIVE_RISK_STATUSES)
        risk["is_due_soon"] = bool(
            risk.get("due_date")
            and _today() <= risk["due_date"] <= _soon()
            and risk["status"] in ACTIVE_RISK_STATUSES
        )
        risk["risk_priority"] = _risk_priority(risk)
        risk["scope_label"] = _scope_label(risk.get("scope"))
        risk["severity_label"] = _severity_label(risk.get("severity"))
        risk["status_label"] = _status_label(risk.get("status"))
    risks.sort(
        key=lambda item: (
            item["risk_priority"],
            item.get("due_date") or "9999-12-31",
            item.get("current_number") or "",
        )
    )
    return {"risks": risks, "kpis": _risk_kpis(risks)}


def _risk_rows(conn: sqlite3.Connection, query: dict[str, list[str]]) -> list[dict]:
    filters = ["COALESCE(p.is_deleted, 0) = 0"]
    params: list[str] = []
    view = (query.get("view", ["active"])[0] or "active").strip()
    search = (query.get("search", [""])[0] or "").strip()
    owner = (query.get("owner", [""])[0] or "").strip()

    if view in {"", "active", "all"}:
        if view != "all":
            filters.append("ei.status IN ('open', 'following', 'resolved')")
    elif view == "high":
        filters.append("ei.status IN ('open', 'following', 'resolved')")
        filters.append("ei.severity = 'high'")
    elif view == "resolved":
        filters.append("ei.status = 'resolved'")
    elif view == "closed":
        filters.append("ei.status IN ('accepted', 'closed')")
    elif view == "overdue":
        filters.append("ei.status IN ('open', 'following', 'resolved')")
        filters.append("ei.due_date < ?")
        params.append(_today())
    elif view == "due_soon":
        filters.append("ei.status IN ('open', 'following', 'resolved')")
        filters.append("ei.due_date >= ? AND ei.due_date <= ?")
        params.extend([_today(), _soon()])

    if owner:
        filters.append("ei.owner_name LIKE ?")
        params.append(f"%{owner}%")
    if search:
        like = f"%{search}%"
        filters.append(
            """
            (
              ei.title LIKE ?
              OR ei.owner_name LIKE ?
              OR ei.resolution LIKE ?
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
        params.extend([like, like, like, like, like, like, like, like, like, like, like])

    where = "WHERE " + " AND ".join(filters)
    return [
        row_to_dict(row)
        for row in conn.execute(
            f"""
            SELECT
              ei.id, ei.project_id, ei.task_id, ei.scope, ei.title, ei.issue_type,
              ei.source, ei.severity, ei.owner_name, ei.status, ei.due_date,
              ei.resolution, ei.created_at, ei.updated_at, ei.closed_at,
              t.title AS task_title,
              t.status AS task_status,
              p.intake_no, p.equipment_no, p.equipment_name, p.project_name,
              p.project_nature, p.status_code, p.expected_delivery_date,
              c.name AS customer_name,
              cg.name AS customer_group_name,
              cs.name AS site_name,
              pg.name AS project_group_name,
              co.name AS contact_name
            FROM execution_issues ei
            JOIN projects p ON p.id = ei.project_id
            JOIN customers c ON c.id = p.customer_id
            LEFT JOIN execution_tasks t ON t.id = ei.task_id
            LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
            LEFT JOIN customer_sites cs ON cs.id = p.site_id
            LEFT JOIN project_groups pg ON pg.id = p.project_group_id
            LEFT JOIN contacts co ON co.id = p.contact_id
            {where}
            ORDER BY ei.updated_at DESC
            LIMIT 500
            """,
            params,
        )
    ]


def _risk_priority(risk: dict) -> int:
    if risk.get("is_overdue"):
        return 0
    if risk.get("severity") == "high" and risk.get("status") in ACTIVE_RISK_STATUSES:
        return 1
    if risk.get("status") == "resolved":
        return 2
    if risk.get("is_due_soon"):
        return 3
    if risk.get("status") in {"open", "following"}:
        return 4
    return 5


def _risk_kpis(risks: list[dict]) -> dict:
    return {
        "active": sum(1 for item in risks if item.get("status") in ACTIVE_RISK_STATUSES),
        "high": sum(1 for item in risks if item.get("severity") == "high" and item.get("status") in ACTIVE_RISK_STATUSES),
        "overdue": sum(1 for item in risks if item.get("is_overdue")),
        "due_soon": sum(1 for item in risks if item.get("is_due_soon")),
        "resolved": sum(1 for item in risks if item.get("status") == "resolved"),
    }


def _scope_label(scope: str | None) -> str:
    return {"product": "产品/产线", "equipment": "设备/WO", "task": "任务"}.get(scope or "", scope or "")


def _severity_label(severity: str | None) -> str:
    return {"low": "低", "medium": "中", "high": "高"}.get(severity or "", severity or "")


def _status_label(status: str | None) -> str:
    return {
        "open": "打开",
        "following": "跟进中",
        "resolved": "待PM确认",
        "accepted": "已接受风险",
        "closed": "已关闭",
    }.get(status or "", status or "")
