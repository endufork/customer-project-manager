"""Workbench task commands and templates."""

import sqlite3
from datetime import date, timedelta

from ..database import row_to_dict
from ..utils import make_id, now_iso
from .lifecycle import create_event
from .workbench_issues import create_issue
from .workbench_common import (
    _bool_value,
    _clean_task_status,
    _clean_work_package,
    _date_or_none,
    _nullable_text,
    _project_row,
    record_activity,
)


TEMPLATES = {
    "inq": [
        ("澄清客户需求", "前期方案", "clarification", 2, 0),
        ("输出大致方案", "前期方案", "rough_solution", 3, 1),
        ("评估技术风险", "前期方案", "rough_solution", 3, 0),
        ("提供内部报价输入", "报价支持", "quote_support", 4, 1),
        ("确认客户报价资料", "报价支持", "quote_support", 5, 1),
    ],
    "wo": [
        ("细化方案确认", "项目管理", "wo_kickoff", 2, 1),
        ("机械设计", "机械设计", "detailed_design", 7, 1),
        ("电气设计", "电气设计", "detailed_design", 7, 1),
        ("BOM输出与确认", "BOM/采购", "bom_purchase", 10, 1),
        ("采购/来料跟进", "BOM/采购", "bom_purchase", 14, 0),
        ("装配", "装配", "assembly", 18, 0),
        ("接线", "接线", "wiring_debug", 20, 0),
        ("调试", "调试", "wiring_debug", 23, 1),
        ("验收资料", "验收", "acceptance_delivery", 26, 1),
        ("发货资料", "发货", "acceptance_delivery", 28, 1),
        ("项目关闭归档", "关闭归档", "closed", 30, 0),
    ],
}


def _task_row(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("任务不存在")
    return row


def _open_task_issue_exists(conn: sqlite3.Connection, task_id: str) -> bool:
    return bool(
        conn.execute(
            """
            SELECT 1
            FROM execution_issues
            WHERE task_id = ?
              AND scope = 'task'
              AND status IN ('open', 'following')
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
    )


def ensure_blocked_task_has_issue(conn: sqlite3.Connection, task: sqlite3.Row | dict, data: dict) -> None:
    status = data.get("status") or task["status"]
    if status != "blocked":
        return
    reason = _nullable_text(data.get("blocked_reason")) or _nullable_text(data.get("notes"))
    if not reason:
        raise ValueError("阻塞任务必须填写阻塞原因")
    if _open_task_issue_exists(conn, task["id"]):
        return
    create_issue(
        conn,
        task["project_id"],
        {
            "task_id": task["id"],
            "scope": "task",
            "title": f"任务阻塞：{task['title']}",
            "issue_type": "交期风险",
            "source": "内部",
            "severity": "high",
            "owner_name": task["owner_name"],
            "status": "open",
            "resolution": reason,
        },
    )

def create_task(conn: sqlite3.Connection, project_id: str, data: dict) -> dict:
    _project_row(conn, project_id)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("任务名称不能为空")
    status = _clean_task_status(data.get("status"))
    task_id = make_id()
    now = now_iso()
    completed_at = now if status in {"confirmed", "completed"} else None
    conn.execute(
        """
        INSERT INTO execution_tasks (
          id, project_id, work_package, phase_code, title, description,
          owner_name, status, due_date, completed_at, is_required,
          requires_deliverable, blocked_reason, notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            project_id,
            _clean_work_package(data.get("work_package")),
            _nullable_text(data.get("phase_code")),
            title,
            _nullable_text(data.get("description")),
            _nullable_text(data.get("owner_name")),
            status,
            _date_or_none(data.get("due_date")),
            completed_at,
            0 if data.get("is_required") == "0" else 1,
            _bool_value(data.get("requires_deliverable")),
            _nullable_text(data.get("blocked_reason")),
            _nullable_text(data.get("notes")),
            now,
            now,
        ),
    )
    task = conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    ensure_blocked_task_has_issue(conn, task, data)
    record_activity(conn, project_id, "task_created", "新增任务", title, task_id=task_id)
    create_event(conn, project_id, "workbench_task_created", "新增执行任务", title)
    return {"id": task_id, "created": True}

def update_task(conn: sqlite3.Connection, task_id: str, data: dict) -> dict:
    row = _task_row(conn, task_id)
    title = (data.get("title") or row["title"] or "").strip()
    if not title:
        raise ValueError("任务名称不能为空")
    status = _clean_task_status(data.get("status") or row["status"])
    if status == "submitted" and row["status"] != "submitted":
        if row["requires_deliverable"]:
            raise ValueError("需要文件的任务必须通过上传交付物提交")
        raise ValueError("不需要文件的任务必须通过完成说明提交")
    if status in {"confirmed", "completed"} and not row["requires_deliverable"]:
        raise ValueError("任务关闭需要通过PM确认完成说明")
    if status in {"confirmed", "completed"} and row["requires_deliverable"]:
        raise ValueError("需要文件的任务必须通过交付物确认关闭")
    now = now_iso()
    started_at = row["started_at"]
    submitted_at = row["submitted_at"]
    confirmed_at = row["confirmed_at"]
    completed_at = row["completed_at"]
    if status == "in_progress" and not started_at:
        started_at = now
    if status == "submitted" and not submitted_at:
        submitted_at = now
    if status == "confirmed" and not confirmed_at:
        confirmed_at = now
        completed_at = now
    if status == "completed" and not completed_at:
        completed_at = now
    if status not in {"confirmed", "completed"}:
        completed_at = None
    conn.execute(
        """
        UPDATE execution_tasks
        SET work_package = ?,
            phase_code = ?,
            title = ?,
            description = ?,
            owner_name = ?,
            status = ?,
            due_date = ?,
            started_at = ?,
            submitted_at = ?,
            confirmed_at = ?,
            completed_at = ?,
            is_required = ?,
            requires_deliverable = ?,
            blocked_reason = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            _clean_work_package(data.get("work_package")),
            _nullable_text(data.get("phase_code")),
            title,
            _nullable_text(data.get("description")),
            _nullable_text(data.get("owner_name")),
            status,
            _date_or_none(data.get("due_date")),
            started_at,
            submitted_at,
            confirmed_at,
            completed_at,
            0 if data.get("is_required") == "0" else 1,
            _bool_value(data.get("requires_deliverable")),
            _nullable_text(data.get("blocked_reason")),
            _nullable_text(data.get("notes")),
            now,
            task_id,
        ),
    )
    updated_task = conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    ensure_blocked_task_has_issue(conn, updated_task, {**data, "status": status})
    record_activity(conn, row["project_id"], "task_updated", "更新任务", title, task_id=task_id)
    return {"id": task_id, "updated": True}

def submit_task_completion(conn: sqlite3.Connection, task_id: str, data: dict, user: dict | None = None) -> dict:
    row = _task_row(conn, task_id)
    if row["requires_deliverable"]:
        raise ValueError("该任务需要提交文件，不能只提交完成说明")
    if row["status"] in {"confirmed", "completed", "cancelled"}:
        raise ValueError("任务已关闭，不能重复提交")
    note = _nullable_text(data.get("completion_note"))
    if not note:
        raise ValueError("提交完成需要填写完成说明")
    submitted_by = _nullable_text(data.get("submitted_by")) or (user or {}).get("display_name") or (user or {}).get("email") or row["owner_name"] or "工程师"
    now = now_iso()
    detail = f"{submitted_by}：{note}"
    conn.execute(
        """
        UPDATE execution_tasks
        SET status = 'submitted',
            submitted_at = ?,
            notes = COALESCE(notes || char(10), '') || ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now, f"完成说明：{detail}", now, task_id),
    )
    record_activity(conn, row["project_id"], "task_completion_submitted", "提交完成说明", detail, task_id=task_id)
    create_event(conn, row["project_id"], "workbench_task_submitted", "提交完成说明", row["title"])
    return {"id": task_id, "submitted": True, "status": "submitted"}

def review_task_completion(conn: sqlite3.Connection, task_id: str, data: dict, user: dict | None = None) -> dict:
    row = _task_row(conn, task_id)
    if row["requires_deliverable"]:
        raise ValueError("需要文件的任务必须通过交付物确认/驳回")
    if row["status"] != "submitted":
        raise ValueError("只能确认或驳回已提交的任务")
    action = (data.get("status") or data.get("action") or "").strip()
    reviewer = _nullable_text(data.get("confirmed_by")) or (user or {}).get("display_name") or "PM"
    now = now_iso()
    if action == "confirmed":
        conn.execute(
            """
            UPDATE execution_tasks
            SET status = 'confirmed',
                confirmed_at = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, now, now, task_id),
        )
        record_activity(conn, row["project_id"], "task_completion_confirmed", "确认任务完成", reviewer, task_id=task_id)
        create_event(conn, row["project_id"], "workbench_task_confirmed", "确认任务完成", row["title"])
        return {"id": task_id, "status": "confirmed"}
    if action == "rejected":
        reason = _nullable_text(data.get("reject_reason")) or _nullable_text(data.get("review_note"))
        if not reason:
            raise ValueError("驳回任务需要填写原因")
        conn.execute(
            """
            UPDATE execution_tasks
            SET status = 'rework',
                notes = COALESCE(notes || char(10), '') || ?,
                updated_at = ?
            WHERE id = ?
            """,
            (f"任务完成驳回：{reason}", now, task_id),
        )
        record_activity(conn, row["project_id"], "task_completion_rejected", "驳回任务完成", reason, task_id=task_id)
        create_event(conn, row["project_id"], "workbench_task_rejected", "驳回任务完成", row["title"])
        return {"id": task_id, "status": "rework"}
    raise ValueError("任务确认操作无效")

def delete_task(conn: sqlite3.Connection, task_id: str) -> dict:
    row = conn.execute("SELECT project_id, title FROM execution_tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("任务不存在")
    conn.execute("DELETE FROM execution_tasks WHERE id = ?", (task_id,))
    record_activity(conn, row["project_id"], "task_deleted", "删除任务", row["title"])
    return {"deleted": True}

def apply_template(conn: sqlite3.Connection, project_id: str, template_code: str) -> dict:
    project = row_to_dict(_project_row(conn, project_id))
    template = (template_code or "").strip() or ("wo" if project.get("equipment_no") else "inq")
    if template not in TEMPLATES:
        raise ValueError("任务模板不存在")
    created = 0
    base = date.today()
    for title, work_package, phase_code, offset_days, requires_deliverable in TEMPLATES[template]:
        exists = conn.execute(
            "SELECT 1 FROM execution_tasks WHERE project_id = ? AND title = ?",
            (project_id, title),
        ).fetchone()
        if exists:
            continue
        create_task(
            conn,
            project_id,
            {
                "title": title,
                "work_package": work_package,
                "phase_code": phase_code,
                "due_date": (base + timedelta(days=offset_days)).isoformat(),
                "requires_deliverable": requires_deliverable,
            },
        )
        created += 1
    record_activity(conn, project_id, "template_applied", "生成任务模板", f"{template} · 新增 {created} 个任务")
    return {"created": created, "template": template}
