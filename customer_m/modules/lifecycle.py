"""lifecycle module."""

import sqlite3

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
