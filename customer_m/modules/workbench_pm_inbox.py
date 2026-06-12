"""PM action-center aggregation for workbench approvals."""

import sqlite3

from .workbench_due_dates import list_due_date_requests
from .workbench_queries import (
    list_pending_deliverables,
    list_pending_risk_reviews,
    list_pending_task_completions,
)


TYPE_LABELS = {
    "deliverable": "待确认文件",
    "completion": "待确认完成说明",
    "due_date": "待审批改期",
    "risk_review": "待确认风险关闭",
}

TYPE_PRIORITY = {
    "risk_review": 0,
    "due_date": 1,
    "deliverable": 2,
    "completion": 3,
}


def _project_title(item: dict) -> str:
    return item.get("equipment_name") or item.get("project_name") or ""


def _customer_line(item: dict) -> str:
    return " · ".join(
        value
        for value in [
            item.get("customer_name") or "",
            item.get("site_name") or "",
            item.get("project_group_name") or "",
        ]
        if value
    )


def _base_item(source_type: str, item: dict) -> dict:
    submitted_at = (
        item.get("submitted_at")
        or item.get("requested_at")
        or item.get("updated_at")
        or item.get("created_at")
        or ""
    )
    return {
        "key": f"{source_type}:{item.get('id')}",
        "type": source_type,
        "type_label": TYPE_LABELS[source_type],
        "id": item.get("id") or "",
        "project_id": item.get("project_id") or "",
        "task_id": item.get("task_id"),
        "project_number": item.get("current_number") or item.get("equipment_no") or item.get("intake_no") or "",
        "project_title": _project_title(item),
        "customer_line": _customer_line(item),
        "task_title": item.get("task_title") or item.get("title") or "",
        "owner_name": item.get("task_owner_name") or item.get("owner_name") or "",
        "submitted_by": item.get("submitted_by") or item.get("requested_by") or "",
        "submitted_at": submitted_at,
        "status": item.get("status") or "",
        "raw": item,
    }


def _deliverable_item(item: dict) -> dict:
    row = _base_item("deliverable", item)
    row.update(
        {
            "title": item.get("file_name") or "交付文件",
            "summary": " · ".join(
                value
                for value in [item.get("task_title") or "", item.get("category_name") or item.get("deliverable_type") or ""]
                if value
            ),
            "primary_action": "确认文件",
            "secondary_action": "驳回文件",
        }
    )
    return row


def _completion_item(item: dict) -> dict:
    row = _base_item("completion", item)
    row.update(
        {
            "title": item.get("title") or "任务完成说明",
            "summary": item.get("notes") or item.get("work_package") or "",
            "primary_action": "确认完成",
            "secondary_action": "驳回说明",
        }
    )
    return row


def _due_date_item(item: dict) -> dict:
    row = _base_item("due_date", item)
    old_due = item.get("old_due_date") or "未设置"
    proposed_due = item.get("proposed_due_date") or ""
    row.update(
        {
            "title": f"{old_due} -> {proposed_due}",
            "summary": item.get("reason") or "",
            "primary_action": "批准改期",
            "secondary_action": "驳回改期",
            "due_date": proposed_due,
        }
    )
    return row


def _risk_item(item: dict) -> dict:
    row = _base_item("risk_review", item)
    row.update(
        {
            "title": item.get("title") or "风险待确认",
            "summary": item.get("resolution") or "",
            "primary_action": "确认关闭",
            "secondary_action": "退回跟进",
            "severity": item.get("severity") or "",
        }
    )
    return row


def _filter_query(query: dict[str, list[str]]) -> dict[str, list[str]]:
    filtered = dict(query)
    view = (query.get("view", ["all"])[0] or "all").strip()
    if view in {"", "all"}:
        filtered["view"] = ["submitted"]
    return filtered


def list_workbench_pm_inbox(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict:
    filtered_query = _filter_query(query)
    deliverables = list_pending_deliverables(conn, filtered_query)
    completions = list_pending_task_completions(conn, filtered_query)
    due_date_requests = list_due_date_requests(conn, filtered_query)
    risk_reviews = list_pending_risk_reviews(conn, filtered_query)

    items = (
        [_deliverable_item(item) for item in deliverables]
        + [_completion_item(item) for item in completions]
        + [_due_date_item(item) for item in due_date_requests]
        + [_risk_item(item) for item in risk_reviews]
    )
    items.sort(
        key=lambda item: (
            TYPE_PRIORITY.get(item["type"], 9),
            item.get("due_date") or "9999-12-31",
            item.get("submitted_at") or "",
        )
    )
    return {
        "items": items,
        "kpis": {
            "total": len(items),
            "deliverables": len(deliverables),
            "completions": len(completions),
            "due_date_requests": len(due_date_requests),
            "risk_reviews": len(risk_reviews),
        },
    }
