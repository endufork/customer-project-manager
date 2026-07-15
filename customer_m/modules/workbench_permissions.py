"""Object-level authorization for engineering workbench mutations."""

import sqlite3


ENGINEER_TASK_PATCH_FIELDS = {"status", "notes", "blocked_reason", "linked_issue_id"}
ENGINEER_ISSUE_PATCH_FIELDS = {"status", "resolution", "review_note"}


class WorkbenchPermissionError(Exception):
    """Raised when a signed-in user cannot mutate a workbench object."""


def is_pm(user: dict | None) -> bool:
    return "pm" in set((user or {}).get("roles", []))


def _task_row(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("任务不存在")
    return row


def require_task_write(conn: sqlite3.Connection, task_id: str, user: dict | None) -> sqlite3.Row:
    task = _task_row(conn, task_id)
    if is_pm(user):
        return task
    owner_user_id = task["owner_user_id"]
    if not owner_user_id:
        raise WorkbenchPermissionError("历史任务尚未绑定账号，仅 PM 可以修改")
    if owner_user_id != (user or {}).get("id"):
        raise WorkbenchPermissionError("只能操作分配给自己的任务")
    return task


def require_task_patch_fields(data: dict, user: dict | None) -> None:
    if is_pm(user):
        return
    if set(data) - ENGINEER_TASK_PATCH_FIELDS:
        raise WorkbenchPermissionError("Engineer 只能修改任务状态、备注和阻塞信息")


def require_issue_create(
    conn: sqlite3.Connection,
    project_id: str,
    task_id: str | None,
    user: dict | None,
) -> None:
    if user is None:
        return
    if not task_id:
        return
    task = require_task_write(conn, task_id, user)
    if task["project_id"] != project_id:
        raise ValueError("任务不属于当前项目")


def require_issue_write(conn: sqlite3.Connection, issue: sqlite3.Row, user: dict | None) -> None:
    if is_pm(user):
        return
    if issue["task_id"]:
        require_task_write(conn, issue["task_id"], user)
        return
    created_by_user_id = issue["created_by_user_id"]
    if not created_by_user_id:
        raise WorkbenchPermissionError("历史风险尚未绑定账号，仅 PM 可以修改")
    if created_by_user_id != (user or {}).get("id"):
        raise WorkbenchPermissionError("只能操作自己创建的非任务风险")


def require_issue_patch_fields(data: dict, user: dict | None) -> None:
    if is_pm(user):
        return
    if set(data) - ENGINEER_ISSUE_PATCH_FIELDS:
        raise WorkbenchPermissionError("Engineer 只能更新风险状态和解决说明")
