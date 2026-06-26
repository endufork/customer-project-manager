from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "customer_projects.db"

EXACT_TEST_EMAILS = {
    "adminonly@jinxiangsz.com",
    "board.viewer@jinxiangsz.com",
    "delete-me@jinxiangsz.com",
    "engineer-bound@jinxiangsz.com",
    "engineer-other@jinxiangsz.com",
    "engineer-preserve@jinxiangsz.com",
    "second-admin@jinxiangsz.com",
    "smtp-failure@jinxiangsz.com",
}

TEST_PROJECT_KEYWORDS = (
    "acme china",
    "delete user customer",
    "delete user machine",
    "delete user line",
    "vision test machine",
    "vision line",
    "playwright",
    "测试",
)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def find_test_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in EXACT_TEST_EMAILS)
    return conn.execute(
        f"""
        SELECT id, email, display_name, status, created_at, last_login_at
        FROM users
        WHERE lower(email) IN ({placeholders})
           OR lower(email) LIKE '%test%'
           OR COALESCE(display_name, '') LIKE '%测试%'
           OR lower(COALESCE(display_name, '')) LIKE '%test%'
        ORDER BY created_at DESC
        """,
        sorted(EXACT_TEST_EMAILS),
    ).fetchall()


def find_test_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT
          p.id,
          p.intake_no,
          p.equipment_no,
          p.equipment_name,
          p.project_name,
          p.is_deleted,
          p.created_at,
          c.name AS customer_name
        FROM projects p
        JOIN customers c ON c.id = p.customer_id
        WHERE COALESCE(p.is_deleted, 0) = 0
        ORDER BY p.created_at DESC
        """
    ).fetchall()
    matches = []
    for row in rows:
        haystack = " ".join(
            str(row[key] or "")
            for key in ("intake_no", "equipment_no", "equipment_name", "project_name", "customer_name")
        ).lower()
        if any(keyword in haystack for keyword in TEST_PROJECT_KEYWORDS):
            matches.append(row)
    return matches


def print_rows(title: str, rows: list[sqlite3.Row], fields: tuple[str, ...]) -> None:
    print(title)
    if not rows:
        print("  none")
        return
    for row in rows:
        values = " | ".join(f"{field}={row[field] or ''}" for field in fields)
        print(f"  {values}")


def apply_cleanup(conn: sqlite3.Connection, users: list[sqlite3.Row], projects: list[sqlite3.Row]) -> None:
    for project in projects:
        conn.execute(
            """
            UPDATE projects
            SET is_deleted = 1,
                deleted_at = datetime('now'),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (project["id"],),
        )

    for user in users:
        conn.execute(
            """
            UPDATE execution_tasks
            SET owner_user_id = NULL,
                owner_email = NULL,
                updated_at = datetime('now')
            WHERE owner_user_id = ?
            """,
            (user["id"],),
        )
        conn.execute("DELETE FROM login_codes WHERE email = ?", (user["email"],))
        conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM notifications WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM user_roles WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit or clean obvious local test users and test projects.")
    parser.add_argument("--apply", action="store_true", help="Actually clean matching records.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"database not found: {DB_PATH}")
        return 1

    with connect() as conn:
        users = find_test_users(conn)
        projects = find_test_projects(conn)
        print_rows("test users", users, ("id", "email", "display_name", "status", "last_login_at"))
        print_rows("test projects", projects, ("id", "intake_no", "equipment_no", "customer_name", "equipment_name", "project_name"))
        if args.apply:
            apply_cleanup(conn, users, projects)
            conn.commit()
            print(f"cleaned users={len(users)} projects={len(projects)}")
        else:
            print("dry run only. pass --apply to clean these records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
