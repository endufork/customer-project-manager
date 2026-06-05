"""Workbench issue and risk commands."""

import sqlite3

from ..utils import make_id, now_iso
from .lifecycle import create_event
from .workbench_common import (
    _clean_issue_scope,
    _clean_issue_severity,
    _clean_issue_status,
    _date_or_none,
    _nullable_text,
    _project_row,
    record_activity,
)


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

def link_issue_to_task(conn: sqlite3.Connection, issue_id: str, task: sqlite3.Row | dict, reason: str | None = None) -> dict:
    row = conn.execute("SELECT * FROM execution_issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise ValueError("关联风险不存在")
    if row["project_id"] != task["project_id"]:
        raise ValueError("只能关联当前项目下的风险")
    if row["status"] not in {"open", "following"}:
        raise ValueError("只能关联打开或跟进中的风险")
    if row["task_id"] and row["task_id"] != task["id"]:
        raise ValueError("该风险已关联其他任务")
    now = now_iso()
    resolution = _nullable_text(row["resolution"])
    clean_reason = _nullable_text(reason)
    if clean_reason and f"任务阻塞关联：{clean_reason}" not in (resolution or ""):
        resolution = f"{resolution}\n任务阻塞关联：{clean_reason}".strip() if resolution else f"任务阻塞关联：{clean_reason}"
    conn.execute(
        """
        UPDATE execution_issues
        SET task_id = ?,
            scope = 'task',
            resolution = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (task["id"], resolution, now, issue_id),
    )
    record_activity(conn, task["project_id"], "issue_linked_to_task", "关联阻塞风险", row["title"], task_id=task["id"], issue_id=issue_id)
    return {"id": issue_id, "linked": True}

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
