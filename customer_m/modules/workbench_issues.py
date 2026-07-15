"""Workbench issue and risk commands."""

import sqlite3

from ..utils import make_id, now_iso
from .lifecycle import create_event
from .notifications import create_notification, notify_pm_users, notify_task_owner
from .workbench_common import (
    _clean_issue_scope,
    _clean_issue_severity,
    _clean_issue_status,
    _clean_task_status,
    _date_or_none,
    _nullable_text,
    _project_row,
    record_activity,
)
from .workbench_permissions import (
    require_issue_create,
    require_issue_patch_fields,
    require_issue_write,
)


ISSUE_ACTIVE_STATUSES = {"open", "following", "resolved"}
ISSUE_CLOSED_STATUSES = {"accepted", "closed"}
TASK_RESTART_STATUSES = {"not_started", "in_progress", "waiting_info", "rework"}
TASK_DONE_STATUSES = {"submitted", "confirmed", "completed", "cancelled"}


def _is_pm(user: dict | None) -> bool:
    roles = set((user or {}).get("roles", []))
    return "pm" in roles


def _actor_name(user: dict | None) -> str:
    if not user:
        return "系统"
    return user.get("display_name") or user.get("email") or "系统"


def _task_row(conn: sqlite3.Connection, task_id: str | None) -> sqlite3.Row | None:
    if not task_id:
        return None
    return conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()


def _review_detail(data: dict, user: dict | None) -> str | None:
    note = _nullable_text(data.get("review_note"))
    actor = _actor_name(user)
    if note:
        return f"{actor}：{note}"
    return actor


def _resolve_note(data: dict, row: sqlite3.Row) -> str | None:
    return _nullable_text(data.get("resolution")) or _nullable_text(row["resolution"])


def _task_next_status(data: dict) -> str:
    status = _clean_task_status(data.get("task_next_status") or "in_progress")
    if status not in TASK_RESTART_STATUSES:
        raise ValueError("风险关闭后的任务状态无效")
    return status


def _sync_linked_blocked_task(
    conn: sqlite3.Connection,
    issue: sqlite3.Row,
    status: str,
    data: dict,
    user: dict | None,
) -> None:
    task = _task_row(conn, issue["task_id"])
    if task is None or task["status"] in TASK_DONE_STATUSES:
        return
    now = now_iso()
    if status in ISSUE_CLOSED_STATUSES and task["status"] == "blocked":
        next_status = _task_next_status(data)
        detail = _review_detail(data, user)
        conn.execute(
            """
            UPDATE execution_tasks
            SET status = ?,
                notes = COALESCE(notes || char(10), '') || ?,
                updated_at = ?
            WHERE id = ?
            """,
            (next_status, f"阻塞风险已处理，任务恢复为 {next_status}：{detail}", now, task["id"]),
        )
        record_activity(
            conn,
            task["project_id"],
            "task_unblocked_by_issue",
            "风险关闭后恢复任务",
            detail,
            task_id=task["id"],
            issue_id=issue["id"],
        )
    elif status in {"open", "following"} and issue["status"] == "resolved":
        reason = _review_detail(data, user)
        conn.execute(
            """
            UPDATE execution_tasks
            SET status = 'blocked',
                blocked_reason = COALESCE(blocked_reason, ?),
                notes = COALESCE(notes || char(10), '') || ?,
                updated_at = ?
            WHERE id = ?
            """,
            (reason, f"风险退回继续跟进：{reason}", now, task["id"]),
        )
        record_activity(
            conn,
            task["project_id"],
            "task_blocked_by_issue_reopen",
            "风险退回后任务保持阻塞",
            reason,
            task_id=task["id"],
            issue_id=issue["id"],
        )


def create_issue(conn: sqlite3.Connection, project_id: str, data: dict, user: dict | None = None) -> dict:
    _project_row(conn, project_id)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("风险/问题标题不能为空")
    raw_task_id = _nullable_text(data.get("task_id"))
    scope = _clean_issue_scope(data.get("scope"), raw_task_id)
    task_id = raw_task_id if scope == "task" else None
    if scope == "task" and not task_id:
        raise ValueError("任务级风险必须关联任务")
    require_issue_create(conn, project_id, task_id, user)
    issue_id = make_id()
    now = now_iso()
    conn.execute(
        """
        INSERT INTO execution_issues (
          id, project_id, task_id, scope, title, issue_type, source, severity,
          owner_name, status, due_date, resolution, created_by_user_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            (user or {}).get("id"),
            now,
            now,
        ),
    )
    record_activity(conn, project_id, "issue_created", "新增风险/问题", title, issue_id=issue_id)
    create_event(conn, project_id, "workbench_issue_created", "新增风险/问题", title)
    if user and not _is_pm(user):
        notify_pm_users(
            conn,
            "risk_created",
            "新增风险待关注",
            title,
            project_id,
            exclude_user_id=user.get("id"),
        )
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

def update_issue(conn: sqlite3.Connection, issue_id: str, data: dict, user: dict | None = None) -> dict:
    row = conn.execute("SELECT * FROM execution_issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise ValueError("风险/问题不存在")
    require_issue_write(conn, row, user)
    require_issue_patch_fields(data, user)
    is_pm = _is_pm(user)
    title = (data.get("title") or row["title"] or "").strip()
    if not title:
        raise ValueError("风险/问题标题不能为空")
    raw_task_id = _nullable_text(data.get("task_id")) if "task_id" in data else row["task_id"]
    scope = _clean_issue_scope(data.get("scope") or row["scope"], raw_task_id)
    task_id = raw_task_id if scope == "task" else None
    if scope == "task" and not task_id:
        raise ValueError("任务级风险必须关联任务")
    status = _clean_issue_status(data.get("status") or row["status"])
    if status in ISSUE_CLOSED_STATUSES and not is_pm:
        raise ValueError("只有PM可以关闭或接受风险")
    if row["status"] == "resolved" and status in ISSUE_CLOSED_STATUSES and not _resolve_note(data, row):
        raise ValueError("关闭风险前需要填写解决说明")
    if status == "resolved" and not _resolve_note(data, row):
        raise ValueError("提交风险解决需要填写解决说明")
    now = now_iso()
    closed_at = row["closed_at"]
    if status in ISSUE_CLOSED_STATUSES and not closed_at:
        closed_at = now
    if status in ISSUE_ACTIVE_STATUSES:
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
            _nullable_text(data.get("issue_type")) if "issue_type" in data else row["issue_type"],
            _nullable_text(data.get("source")) if "source" in data else row["source"],
            _clean_issue_severity(data.get("severity")) if "severity" in data else row["severity"],
            _nullable_text(data.get("owner_name")) if "owner_name" in data else row["owner_name"],
            status,
            _date_or_none(data.get("due_date")) if "due_date" in data else row["due_date"],
            _nullable_text(data.get("resolution")) if "resolution" in data else row["resolution"],
            now,
            closed_at,
            issue_id,
        ),
    )
    updated_row = conn.execute("SELECT * FROM execution_issues WHERE id = ?", (issue_id,)).fetchone()
    if updated_row:
        _sync_linked_blocked_task(conn, updated_row, status, data, user)
    activity_type = {
        "resolved": "issue_resolved",
        "accepted": "issue_accepted",
        "closed": "issue_closed",
        "following": "issue_following",
        "open": "issue_reopened",
    }.get(status, "issue_updated")
    activity_title = {
        "resolved": "提交风险解决",
        "accepted": "接受残余风险",
        "closed": "关闭风险",
        "following": "风险继续跟进",
        "open": "重新打开风险",
    }.get(status, "更新风险/问题")
    record_activity(conn, row["project_id"], activity_type, activity_title, title, issue_id=issue_id)
    if user and not is_pm and status == "resolved":
        notify_pm_users(
            conn,
            "risk_resolved",
            "风险解决待确认",
            title,
            row["project_id"],
            exclude_user_id=user.get("id"),
        )
    elif user and is_pm and status != row["status"]:
        task = _task_row(conn, row["task_id"])
        notification_title = "风险处理结果已更新"
        if task:
            notify_task_owner(
                conn,
                task,
                "risk_reviewed",
                notification_title,
                f"{title}：{status}",
                exclude_user_id=user.get("id"),
            )
        else:
            create_notification(
                conn,
                row["created_by_user_id"],
                "risk_reviewed",
                notification_title,
                f"{title}：{status}",
                related_type="project",
                related_id=row["project_id"],
            )
    return {"id": issue_id, "project_id": row["project_id"], "status": status, "updated": True}

def delete_issue(conn: sqlite3.Connection, issue_id: str) -> dict:
    row = conn.execute("SELECT project_id, title FROM execution_issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise ValueError("风险/问题不存在")
    conn.execute("DELETE FROM execution_issues WHERE id = ?", (issue_id,))
    record_activity(conn, row["project_id"], "issue_deleted", "删除风险/问题", row["title"])
    return {"deleted": True}
