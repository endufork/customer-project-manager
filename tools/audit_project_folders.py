from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from customer_m.config import DB_PATH, STANDARD_PROJECT_FOLDERS  # noqa: E402


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def project_root(conn: sqlite3.Connection) -> Path:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        ("project_root_path",),
    ).fetchone()
    return Path(row["value"] if row else r"D:\01_CustomerProject").resolve(strict=False)


def active_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, intake_no, equipment_no, equipment_name, project_folder_path
        FROM projects
        WHERE COALESCE(is_deleted, 0) = 0
          AND project_folder_path IS NOT NULL
          AND TRIM(project_folder_path) <> ''
        ORDER BY updated_at DESC
        """
    ).fetchall()


def is_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError:
        return False
    return True


def missing_standard_dirs(path: Path) -> list[str]:
    if not path.is_dir():
        return list(STANDARD_PROJECT_FOLDERS)
    return [name for name in STANDARD_PROJECT_FOLDERS if not (path / name).is_dir()]


def repair_project_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for name in STANDARD_PROJECT_FOLDERS:
        (path / name).mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit active project folders and standard subfolders.")
    parser.add_argument("--repair", action="store_true", help="Create missing project folders and standard subfolders.")
    args = parser.parse_args()

    with connect() as conn:
        root = project_root(conn)
        rows = active_projects(conn)
        issues = []
        repaired = 0
        skipped = 0

        for row in rows:
            path = Path(row["project_folder_path"])
            missing_dirs = missing_standard_dirs(path)
            folder_missing = not path.is_dir()
            if not folder_missing and not missing_dirs:
                continue

            issue = {
                "id": row["id"],
                "no": row["equipment_no"] or row["intake_no"],
                "equipment_name": row["equipment_name"],
                "folder_missing": folder_missing,
                "missing_standard_dirs": missing_dirs,
                "path": str(path),
            }
            issues.append(issue)

            if args.repair:
                if not is_under_root(path, root):
                    skipped += 1
                    print(f"SKIP outside root: {issue['no']} {path}")
                    continue
                repair_project_folder(path)
                repaired += 1
                print(f"REPAIRED: {issue['no']} {path}")

        print(f"Project root: {root}")
        print(f"Checked active projects: {len(rows)}")
        print(f"Projects with folder issues: {len(issues)}")
        if args.repair:
            print(f"Repaired: {repaired}")
            print(f"Skipped: {skipped}")
        else:
            for issue in issues[:50]:
                print(
                    "ISSUE: "
                    f"{issue['no']} | folder_missing={issue['folder_missing']} | "
                    f"missing_standard_dirs={len(issue['missing_standard_dirs'])} | "
                    f"{issue['path']}"
                )
            if len(issues) > 50:
                print(f"... {len(issues) - 50} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
