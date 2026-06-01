"""Lookup payloads for forms and filters."""

import sqlite3

from ..config import PROJECT_NATURE_OPTIONS, STATUS_DATE_LABELS
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
    }
