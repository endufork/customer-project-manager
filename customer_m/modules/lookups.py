"""Lookup payloads for forms and filters."""

import sqlite3

from ..config import (
    PROJECT_NATURE_OPTIONS,
    STATUS_DATE_LABELS,
    WORKBENCH_AREAS,
    WORKBENCH_DELIVERABLE_STATUSES,
    WORKBENCH_ISSUE_SCOPES,
    WORKBENCH_ISSUE_SEVERITIES,
    WORKBENCH_ISSUE_SOURCES,
    WORKBENCH_ISSUE_STATUSES,
    WORKBENCH_ISSUE_TYPES,
    WORKBENCH_PHASES,
    WORKBENCH_TASK_STATUSES,
    WORKBENCH_WORK_PACKAGES,
)
from ..database import row_to_dict


def get_bootstrap_payload(conn: sqlite3.Connection) -> dict:
    return {
        "settings": {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM app_settings ORDER BY key")
        },
        "statuses": [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT code, name, sort_order FROM project_statuses WHERE is_active = 1 ORDER BY sort_order"
            )
        ],
        "currencies": [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT code, name, symbol FROM currencies WHERE is_active = 1 ORDER BY code"
            )
        ],
        "project_natures": list(PROJECT_NATURE_OPTIONS),
        "status_date_labels": STATUS_DATE_LABELS,
        "workbench_areas": list(WORKBENCH_AREAS),
        "workbench_work_packages": list(WORKBENCH_WORK_PACKAGES),
        "workbench_task_statuses": list(WORKBENCH_TASK_STATUSES),
        "workbench_phases": list(WORKBENCH_PHASES),
        "workbench_issue_types": list(WORKBENCH_ISSUE_TYPES),
        "workbench_issue_sources": list(WORKBENCH_ISSUE_SOURCES),
        "workbench_issue_scopes": list(WORKBENCH_ISSUE_SCOPES),
        "workbench_issue_severities": list(WORKBENCH_ISSUE_SEVERITIES),
        "workbench_issue_statuses": list(WORKBENCH_ISSUE_STATUSES),
        "workbench_deliverable_statuses": list(WORKBENCH_DELIVERABLE_STATUSES),
        "assignees": [
            row_to_dict(row)
            for row in conn.execute(
                """
                SELECT DISTINCT users.id, users.email, COALESCE(users.display_name, '') AS display_name
                FROM users
                JOIN user_roles ON user_roles.user_id = users.id
                WHERE users.status = 'enabled'
                  AND user_roles.role_code IN ('pm', 'engineer')
                ORDER BY COALESCE(users.display_name, users.email), users.email
                """
            )
        ],
        "file_categories": [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT code, name, default_folder, default_visibility FROM file_categories WHERE is_active = 1 ORDER BY sort_order"
            )
        ],
        "customer_groups": [
            row_to_dict(row)
            for row in conn.execute("SELECT id, name FROM customer_groups ORDER BY name")
        ],
        "customers": [
            row_to_dict(row)
            for row in conn.execute("SELECT id, group_id, name FROM customers ORDER BY name")
        ],
        "sites": [
            row_to_dict(row)
            for row in conn.execute("SELECT id, customer_id, name, site_type FROM customer_sites ORDER BY name")
        ],
        "project_groups": [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT id, customer_id, site_id, name, shared_folder_path FROM project_groups ORDER BY name"
            )
        ],
        "contacts": [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT id, customer_id, site_id, name, role, department FROM contacts ORDER BY name"
            )
        ],
        "project_field_options": {
            "departments": [
                row["value"]
                for row in conn.execute(
                    """
                    SELECT DISTINCT trim(department) AS value
                    FROM projects
                    WHERE department IS NOT NULL AND trim(department) <> ''
                    ORDER BY value
                    """
                )
            ],
            "equipment_names": [
                row["value"]
                for row in conn.execute(
                    """
                    SELECT DISTINCT trim(equipment_name) AS value
                    FROM projects
                    WHERE equipment_name IS NOT NULL AND trim(equipment_name) <> ''
                    ORDER BY value
                    """
                )
            ],
            "legacy_numbers": [
                row["value"]
                for row in conn.execute(
                    """
                    SELECT DISTINCT trim(related_legacy_no) AS value
                    FROM projects
                    WHERE related_legacy_no IS NOT NULL AND trim(related_legacy_no) <> ''
                    ORDER BY value
                    """
                )
            ],
            "equipment_numbers": [
                row["value"]
                for row in conn.execute(
                    """
                    SELECT DISTINCT trim(equipment_no) AS value
                    FROM projects
                    WHERE equipment_no IS NOT NULL AND trim(equipment_no) <> ''
                    ORDER BY value
                    """
                )
            ],
        },
    }
