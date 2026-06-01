"""lifecycle module."""

import sqlite3
from datetime import datetime

from ..utils import make_id, now_iso, today_compact

def generate_intake_no(conn: sqlite3.Connection) -> str:
    prefix = f"INQ-{today_compact()}-"
    row = conn.execute(
        "SELECT intake_no FROM projects WHERE intake_no LIKE ? ORDER BY intake_no DESC LIMIT 1",
        (prefix + "%",),
    ).fetchone()
    if row is None:
        return prefix + "001"
    try:
        next_no = int(row["intake_no"].rsplit("-", 1)[1]) + 1
    except (IndexError, ValueError):
        next_no = 1
    return f"{prefix}{next_no:03d}"

def create_event(conn: sqlite3.Connection, project_id: str, event_type: str, title: str, detail: str = "") -> None:
    conn.execute(
        """
        INSERT INTO project_events (id, project_id, event_type, title, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (make_id(), project_id, event_type, title, detail or None, now_iso()),
    )


def create_todo(
    conn: sqlite3.Connection,
    project_id: str,
    type_code: str,
    title: str,
    due_date: str,
) -> None:
    conn.execute(
        """
        INSERT INTO todos (id, project_id, type_code, title, due_date, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
        """,
        (make_id(), project_id, type_code, title, due_date, now_iso(), now_iso()),
    )


def create_default_project_todos(
    conn: sqlite3.Connection,
    project_id: str,
    equipment_no: str | None,
    inquiry_date: str | None,
    quote_due_date: str,
) -> None:
    if not equipment_no:
        create_todo(
            conn,
            project_id,
            "equipment_no_assignment",
            "补充内部设备号",
            inquiry_date or datetime.now().date().isoformat(),
        )
    if quote_due_date:
        create_todo(
            conn,
            project_id,
            "quote_deadline",
            "完成并发送报价",
            quote_due_date,
        )
