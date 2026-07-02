"""File visibility rules shared by imports, scans, and read models."""

from __future__ import annotations

import sqlite3


VISIBILITY_ENGINEERING = "engineering"
VISIBILITY_PM_ONLY = "pm_only"
VISIBILITY_ADMIN_ONLY = "admin_only"

VALID_VISIBILITY_CODES = (
    VISIBILITY_ENGINEERING,
    VISIBILITY_PM_ONLY,
    VISIBILITY_ADMIN_ONLY,
)

CATEGORY_DEFAULT_VISIBILITY = {
    "customer_quote": VISIBILITY_PM_ONLY,
    "po": VISIBILITY_PM_ONLY,
}


def default_visibility_for_category(category_code: str | None) -> str:
    return CATEGORY_DEFAULT_VISIBILITY.get(category_code or "", VISIBILITY_ENGINEERING)


def sync_file_category_visibility_defaults(conn: sqlite3.Connection) -> None:
    for row in conn.execute("SELECT code FROM file_categories").fetchall():
        conn.execute(
            "UPDATE file_categories SET default_visibility = ? WHERE code = ?",
            (default_visibility_for_category(row["code"]), row["code"]),
        )


def category_visibility(conn: sqlite3.Connection, category_code: str | None) -> str:
    row = conn.execute(
        "SELECT default_visibility FROM file_categories WHERE code = ?",
        (category_code,),
    ).fetchone()
    if row and row["default_visibility"] in VALID_VISIBILITY_CODES:
        return row["default_visibility"]
    return default_visibility_for_category(category_code)


def allowed_visibility_codes(user: dict | None) -> tuple[str, ...]:
    roles = set((user or {}).get("roles") or [])
    if "admin" in roles:
        return VALID_VISIBILITY_CODES
    if "pm" in roles:
        return (VISIBILITY_ENGINEERING, VISIBILITY_PM_ONLY)
    if "engineer" in roles:
        return (VISIBILITY_ENGINEERING,)
    return ()


def visibility_where_clause(alias: str, user: dict | None) -> tuple[str, list[str]]:
    allowed = allowed_visibility_codes(user)
    if not allowed:
        return "1 = 0", []
    placeholders = ", ".join("?" for _ in allowed)
    return f"COALESCE({alias}.visibility_code, fc.default_visibility, ?) IN ({placeholders})", [
        VISIBILITY_ENGINEERING,
        *allowed,
    ]
