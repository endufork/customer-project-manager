"""In-app notification commands and queries."""

import sqlite3

from ..database import row_to_dict
from ..utils import make_id, now_iso


def create_notification(
    conn: sqlite3.Connection,
    user_id: str | None,
    notification_type: str,
    title: str,
    body: str | None = None,
    *,
    related_type: str | None = None,
    related_id: str | None = None,
) -> str | None:
    if not user_id:
        return None
    user = conn.execute("SELECT status FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None or user["status"] != "enabled":
        return None
    notification_id = make_id()
    conn.execute(
        """
        INSERT INTO notifications (
          id, user_id, type, title, body, related_type, related_id, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'unread', ?)
        """,
        (notification_id, user_id, notification_type, title, body, related_type, related_id, now_iso()),
    )
    return notification_id


def notify_pm_users(
    conn: sqlite3.Connection,
    notification_type: str,
    title: str,
    body: str | None,
    project_id: str,
    *,
    exclude_user_id: str | None = None,
) -> int:
    users = conn.execute(
        """
        SELECT DISTINCT u.id
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id AND ur.role_code = 'pm'
        WHERE u.status = 'enabled' AND (? IS NULL OR u.id <> ?)
        """,
        (exclude_user_id, exclude_user_id),
    ).fetchall()
    for user in users:
        create_notification(
            conn,
            user["id"],
            notification_type,
            title,
            body,
            related_type="project",
            related_id=project_id,
        )
    return len(users)


def notify_task_owner(
    conn: sqlite3.Connection,
    task: sqlite3.Row | dict,
    notification_type: str,
    title: str,
    body: str | None,
    *,
    exclude_user_id: str | None = None,
) -> str | None:
    owner_user_id = task["owner_user_id"]
    if not owner_user_id or owner_user_id == exclude_user_id:
        return None
    return create_notification(
        conn,
        owner_user_id,
        notification_type,
        title,
        body,
        related_type="project",
        related_id=task["project_id"],
    )


def list_notifications(conn: sqlite3.Connection, user_id: str, limit: int = 30) -> dict:
    safe_limit = max(1, min(limit, 100))
    items = [
        row_to_dict(row)
        for row in conn.execute(
            """
            SELECT id, type, title, body, related_type, related_id, status, created_at, read_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, safe_limit),
        ).fetchall()
    ]
    unread_count = conn.execute(
        "SELECT COUNT(*) AS count FROM notifications WHERE user_id = ? AND status = 'unread'",
        (user_id,),
    ).fetchone()["count"]
    return {"notifications": items, "unread_count": unread_count}


def mark_notification_read(conn: sqlite3.Connection, notification_id: str, user_id: str) -> dict:
    row = conn.execute(
        "SELECT id, status FROM notifications WHERE id = ? AND user_id = ?",
        (notification_id, user_id),
    ).fetchone()
    if row is None:
        raise ValueError("通知不存在")
    now = now_iso()
    conn.execute(
        "UPDATE notifications SET status = 'read', read_at = COALESCE(read_at, ?) WHERE id = ?",
        (now, notification_id),
    )
    return {"id": notification_id, "status": "read"}


def mark_all_notifications_read(conn: sqlite3.Connection, user_id: str) -> dict:
    now = now_iso()
    cursor = conn.execute(
        "UPDATE notifications SET status = 'read', read_at = ? WHERE user_id = ? AND status = 'unread'",
        (now, user_id),
    )
    return {"updated": cursor.rowcount}
