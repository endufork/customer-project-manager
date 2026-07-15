from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from customer_m.database import db_connect
from customer_m.modules.auth import VALID_ROLES, default_display_name, normalize_email
from customer_m.utils import make_id, now_iso


def require_isolated_test_database() -> None:
    if os.environ.get("CUSTOMER_PROJECT_ENV") != "test":
        raise RuntimeError("E2E user preparation requires CUSTOMER_PROJECT_ENV=test")
    test_root_value = os.environ.get("CUSTOMER_PROJECT_TEST_ROOT", "").strip()
    db_path_value = os.environ.get("CUSTOMER_PROJECT_DB_PATH", "").strip()
    if not test_root_value or not db_path_value:
        raise RuntimeError("E2E test root and database path must be configured")
    test_root = Path(test_root_value).resolve(strict=False)
    db_path = Path(db_path_value).resolve(strict=False)
    if not db_path.is_relative_to(test_root):
        raise RuntimeError("E2E database must be located under CUSTOMER_PROJECT_TEST_ROOT")


def main() -> int:
    require_isolated_test_database()
    parser = argparse.ArgumentParser(description="Prepare an enabled test user for Playwright e2e tests.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--roles", default="pm,engineer")
    args = parser.parse_args()

    email = normalize_email(args.email)
    roles = [role.strip() for role in args.roles.split(",") if role.strip()]
    invalid_roles = [role for role in roles if role not in VALID_ROLES]
    if invalid_roles:
        raise ValueError(f"Invalid roles: {', '.join(invalid_roles)}")
    now = now_iso()
    with db_connect() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            user_id = row["id"]
            conn.execute(
                "UPDATE users SET status = 'enabled', updated_at = ? WHERE id = ?",
                (now, user_id),
            )
        else:
            user_id = make_id()
            conn.execute(
                """
                INSERT INTO users (id, email, display_name, status, created_at, updated_at)
                VALUES (?, ?, ?, 'enabled', ?, ?)
                """,
                (user_id, email, default_display_name(email), now, now),
            )
        conn.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        for role in sorted(set(roles)):
            conn.execute(
                "INSERT INTO user_roles (user_id, role_code, created_at) VALUES (?, ?, ?)",
                (user_id, role, now),
            )
        conn.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
