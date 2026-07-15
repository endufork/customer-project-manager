from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from customer_m.database import db_connect, init_db, set_setting  # noqa: E402
from customer_m.modules.projects import create_project_record  # noqa: E402


def isolated_test_root() -> Path:
    if os.environ.get("CUSTOMER_PROJECT_ENV") != "test":
        raise RuntimeError("E2E environment preparation requires CUSTOMER_PROJECT_ENV=test")
    test_root_value = os.environ.get("CUSTOMER_PROJECT_TEST_ROOT", "").strip()
    db_path_value = os.environ.get("CUSTOMER_PROJECT_DB_PATH", "").strip()
    if not test_root_value or not db_path_value:
        raise RuntimeError("E2E test root and database path must be configured")
    test_root = Path(test_root_value).resolve(strict=False)
    db_path = Path(db_path_value).resolve(strict=False)
    if not db_path.is_relative_to(test_root):
        raise RuntimeError("E2E database must be located under CUSTOMER_PROJECT_TEST_ROOT")
    return test_root


def main() -> int:
    test_root = isolated_test_root()
    project_root = test_root / "projects"
    project_root.mkdir(parents=True, exist_ok=True)
    init_db()
    with db_connect() as conn:
        set_setting(conn, "project_root_path", str(project_root))
        set_setting(conn, "backup_target_path", str(test_root / "backups"))
        conn.commit()
    with db_connect() as conn:
        if conn.execute("SELECT 1 FROM projects LIMIT 1").fetchone() is None:
            create_project_record(
                conn,
                {
                    "customer_name": "E2E Customer",
                    "site_name": "E2E Site",
                    "project_group_name": "E2E Product Line",
                    "contact_name": "E2E Contact",
                    "equipment_name": "E2E Test Machine",
                    "project_name": "E2E Test Project",
                    "project_nature": "新设备",
                    "status_code": "inquiry",
                    "currency_code": "CNY",
                    "inquiry_date": "2026-01-01",
                },
            )
            conn.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
