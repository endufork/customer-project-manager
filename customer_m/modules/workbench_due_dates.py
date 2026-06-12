"""Due date change request workflows for workbench tasks."""

import sqlite3

from ..database import row_to_dict
from ..utils import make_id, now_iso
from .workbench_common import _date_or_none, _nullable_text, _project_area, _project_number, record_activity


REQUEST_STATUSES = {"pending", "approved", "rejected"}


def _actor_name(user: dict | None) -> str:
    if not user:
        return "系统"
    return user.get("display_name") or user.get("email") or "系统"


def _is_pm(user: dict | None) -> bool:
    roles = set((user or {}).get("roles", []))
    return "pm" in roles


def _task_row(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("任务不存在")
    return row


def _request_row(conn: sqlite3.Connection, request_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM due_date_change_requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        raise ValueError("改期申请不存在")
    return row


def _request_detail(conn: sqlite3.Connection, request_id: str) -> dict:
    row = conn.execute(
        """
        SELECT
          r.*,
          t.title AS task_title,
          t.owner_name AS task_owner_name,
          t.work_package AS task_work_package,
          p.intake_no,
          p.equipment_no,
          p.equipment_name,
          p.project_name,
          p.project_nature,
          p.status_code,
          p.expected_delivery_date,
          p.project_folder_path,
          c.name AS customer_name,
          cg.name AS customer_group_name,
          cs.name AS site_name,
          pg.name AS project_group_name,
          co.name AS contact_name
        FROM due_date_change_requests r
        JOIN execution_tasks t ON t.id = r.task_id
        JOIN projects p ON p.id = r.project_id
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
        LEFT JOIN customer_sites cs ON cs.id = p.site_id
        LEFT JOIN project_groups pg ON pg.id = p.project_group_id
        LEFT JOIN contacts co ON co.id = p.contact_id
        WHERE r.id = ?
        """,
        (request_id,),
    ).fetchone()
    if row is None:
        raise ValueError("改期申请不存在")
    item = row_to_dict(row)
    item["current_number"] = _project_number(item)
    item["workbench_area"] = _project_area(item)
    return item


def guard_regular_task_due_date_update(conn: sqlite3.Connection, task_id: str, data: dict) -> dict:
    """Keep regular task updates from changing due_date without a request reason."""
    if "due_date" not in data:
        return data
    task = _task_row(conn, task_id)
    requested_due = _date_or_none(data.get("due_date"))
    current_due = task["due_date"] or None
    cleaned = dict(data)
    cleaned.pop("due_date", None)
    if requested_due != current_due:
        raise ValueError("Due Date 修改请使用改期窗口，并填写原因")
    return cleaned


def list_due_date_requests(conn: sqlite3.Connection, query: dict[str, list[str]]) -> list[dict]:
    filters = []
    params: list[str] = []
    status = (query.get("status", ["pending"])[0] or "pending").strip().lower()
    search = (query.get("search", [""])[0] or "").strip()
    view = (query.get("view", [""])[0] or "all").strip()

    if status != "all":
        if status not in REQUEST_STATUSES:
            status = "pending"
        filters.append("r.status = ?")
        params.append(status)
    if view not in {"", "all", "submitted"} and status == "pending":
        return []
    if search:
        like = f"%{search}%"
        filters.append(
            """
            (
              t.title LIKE ?
              OR t.owner_name LIKE ?
              OR r.requested_by LIKE ?
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

    where = "WHERE " + " AND ".join(filters) if filters else ""
    rows = []
    for row in conn.execute(
        f"""
        SELECT
          r.*,
          t.title AS task_title,
          t.owner_name AS task_owner_name,
          t.work_package AS task_work_package,
          p.intake_no,
          p.equipment_no,
          p.equipment_name,
          p.project_name,
          p.project_nature,
          p.status_code,
          p.expected_delivery_date,
          p.project_folder_path,
          c.name AS customer_name,
          cg.name AS customer_group_name,
          cs.name AS site_name,
          pg.name AS project_group_name,
          co.name AS contact_name
        FROM due_date_change_requests r
        JOIN execution_tasks t ON t.id = r.task_id
        JOIN projects p ON p.id = r.project_id
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN customer_groups cg ON cg.id = p.customer_group_id
        LEFT JOIN customer_sites cs ON cs.id = p.site_id
        LEFT JOIN project_groups pg ON pg.id = p.project_group_id
        LEFT JOIN contacts co ON co.id = p.contact_id
        {where}
        ORDER BY r.requested_at DESC, r.created_at DESC
        LIMIT 300
        """,
        params,
    ):
        item = row_to_dict(row)
        item["current_number"] = _project_number(item)
        item["workbench_area"] = _project_area(item)
        rows.append(item)
    return rows


def due_date_requests_for_project(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    return [
        row_to_dict(row)
        for row in conn.execute(
            """
            SELECT *
            FROM due_date_change_requests
            WHERE project_id = ?
            ORDER BY
              CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
              requested_at DESC
            """,
            (project_id,),
        )
    ]


def request_due_date_change(conn: sqlite3.Connection, task_id: str, data: dict, user: dict | None) -> dict:
    task = _task_row(conn, task_id)
    proposed_due_date = _date_or_none(data.get("proposed_due_date") or data.get("due_date"))
    if not proposed_due_date:
        raise ValueError("请选择新的 Due Date")
    old_due_date = task["due_date"] or None
    if proposed_due_date == old_due_date:
        raise ValueError("新的 Due Date 与当前 Due Date 一致")
    reason = _nullable_text(data.get("reason"))
    if not reason:
        raise ValueError("修改 Due Date 必须填写理由")
    impact_note = _nullable_text(data.get("impact_note"))
    now = now_iso()
    actor = _actor_name(user)
    auto_approve = _is_pm(user) and bool(data.get("direct"))

    pending = conn.execute(
        """
        SELECT id
        FROM due_date_change_requests
        WHERE task_id = ? AND status = 'pending'
        """,
        (task_id,),
    ).fetchone()
    if pending is not None and not auto_approve:
        raise ValueError("该任务已有待审批改期申请")

    request_id = make_id()
    status = "approved" if auto_approve else "pending"
    final_due_date = proposed_due_date if auto_approve else None
    reviewed_by = actor if auto_approve else None
    reviewed_at = now if auto_approve else None
    review_note = "PM直接修改" if auto_approve else None
    conn.execute(
        """
        INSERT INTO due_date_change_requests (
          id, task_id, project_id, old_due_date, proposed_due_date, final_due_date,
          reason, impact_note, status, requested_by, requested_at, reviewed_by,
          reviewed_at, review_note, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_id,
            task_id,
            task["project_id"],
            old_due_date,
            proposed_due_date,
            final_due_date,
            reason,
            impact_note,
            status,
            actor,
            now,
            reviewed_by,
            reviewed_at,
            review_note,
            now,
            now,
        ),
    )
    detail = f"{old_due_date or '未设置'} -> {proposed_due_date}：{reason}"
    if impact_note:
        detail = f"{detail}；影响：{impact_note}"
    if auto_approve:
        conn.execute(
            "UPDATE execution_tasks SET due_date = ?, updated_at = ? WHERE id = ?",
            (proposed_due_date, now, task_id),
        )
        record_activity(conn, task["project_id"], "due_date_changed", "修改Due Date", detail, task_id=task_id)
    else:
        record_activity(conn, task["project_id"], "due_date_change_requested", "申请修改Due Date", detail, task_id=task_id)
    return _request_detail(conn, request_id)


def review_due_date_change(conn: sqlite3.Connection, request_id: str, data: dict, user: dict | None) -> dict:
    request = _request_row(conn, request_id)
    if request["status"] != "pending":
        raise ValueError("该改期申请已经处理")
    action = (data.get("status") or data.get("action") or "").strip().lower()
    if action not in {"approved", "rejected"}:
        raise ValueError("改期审批操作无效")
    now = now_iso()
    reviewer = _actor_name(user)
    review_note = _nullable_text(data.get("review_note"))

    if action == "approved":
        final_due_date = _date_or_none(data.get("final_due_date") or request["proposed_due_date"])
        conn.execute(
            """
            UPDATE due_date_change_requests
            SET status = 'approved', final_due_date = ?, reviewed_by = ?,
              reviewed_at = ?, review_note = ?, updated_at = ?
            WHERE id = ?
            """,
            (final_due_date, reviewer, now, review_note, now, request_id),
        )
        conn.execute(
            "UPDATE execution_tasks SET due_date = ?, updated_at = ? WHERE id = ?",
            (final_due_date, now, request["task_id"]),
        )
        detail = f"{request['old_due_date'] or '未设置'} -> {final_due_date}"
        if review_note:
            detail = f"{detail}；{review_note}"
        record_activity(
            conn,
            request["project_id"],
            "due_date_change_approved",
            "批准Due Date修改",
            detail,
            task_id=request["task_id"],
        )
    else:
        if not review_note:
            raise ValueError("驳回改期申请需要填写原因")
        conn.execute(
            """
            UPDATE due_date_change_requests
            SET status = 'rejected', reviewed_by = ?, reviewed_at = ?,
              review_note = ?, updated_at = ?
            WHERE id = ?
            """,
            (reviewer, now, review_note, now, request_id),
        )
        record_activity(
            conn,
            request["project_id"],
            "due_date_change_rejected",
            "驳回Due Date修改",
            review_note,
            task_id=request["task_id"],
        )
    return _request_detail(conn, request_id)
