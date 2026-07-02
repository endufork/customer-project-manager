from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from customer_m.config import CATEGORY_DEFAULT_FOLDERS, STANDARD_PROJECT_FOLDERS  # noqa: E402
from customer_m.database import db_connect, get_setting  # noqa: E402
from customer_m.modules.folders import unique_destination  # noqa: E402
from customer_m.utils import now_iso  # noqa: E402


OLD_CATEGORY_PARENT_FOLDERS = {
    "internal_quote": {"02_报价与订单", "03_内部报价"},
    "customer_quote": {"02_报价与订单", "04_客户报价"},
    "po": {"02_报价与订单", "05_PO订单"},
    "acceptance_delivery": {"04_交付与验收", "07_验收发货"},
}


def active_project_rows(conn: sqlite3.Connection, project_id: str | None) -> list[sqlite3.Row]:
    filters = ["COALESCE(is_deleted, 0) = 0", "project_folder_path IS NOT NULL", "trim(project_folder_path) <> ''"]
    params: list[str] = []
    if project_id:
        filters.append("id = ?")
        params.append(project_id)
    return conn.execute(
        f"""
        SELECT id, intake_no, equipment_no, project_folder_path
        FROM projects
        WHERE {" AND ".join(filters)}
        ORDER BY updated_at DESC
        """,
        params,
    ).fetchall()


def project_files(conn: sqlite3.Connection, project_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, category_code, file_path
        FROM project_files
        WHERE project_id = ?
        ORDER BY file_path
        """,
        (project_id,),
    ).fetchall()


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def relative_parent(path: Path, project_folder: Path) -> str:
    try:
        return path.parent.relative_to(project_folder).as_posix()
    except ValueError:
        return ""


def should_move(row: sqlite3.Row, file_path: Path, project_folder: Path, target_folder: Path, all_categorized: bool) -> bool:
    if file_path.parent.resolve(strict=False) == target_folder.resolve(strict=False):
        return False
    if all_categorized:
        return True
    category = row["category_code"]
    old_folders = OLD_CATEGORY_PARENT_FOLDERS.get(category, set())
    return relative_parent(file_path, project_folder) in old_folders


def ensure_standard_dirs(project_folder: Path, apply: bool) -> list[Path]:
    missing = [project_folder / folder for folder in STANDARD_PROJECT_FOLDERS if not (project_folder / folder).is_dir()]
    if apply:
        project_folder.mkdir(parents=True, exist_ok=True)
        for folder in STANDARD_PROJECT_FOLDERS:
            (project_folder / folder).mkdir(parents=True, exist_ok=True)
    return missing


def restructure_project(
    conn: sqlite3.Connection,
    project: sqlite3.Row,
    apply: bool,
    all_categorized: bool,
    summary_only: bool,
    moves_only: bool,
) -> tuple[int, int, int]:
    project_folder = Path(project["project_folder_path"])
    if not project_folder.is_dir():
        print(f"SKIP missing project folder: {project['equipment_no'] or project['intake_no']} {project_folder}")
        return 0, 0, 1

    missing_dirs = ensure_standard_dirs(project_folder, apply)
    if not summary_only and not moves_only:
        for missing in missing_dirs:
            print(("CREATE" if apply else "WOULD CREATE") + f": {missing}")

    moved = 0
    skipped = 0
    for row in project_files(conn, project["id"]):
        category = row["category_code"]
        default_folder = CATEGORY_DEFAULT_FOLDERS.get(category)
        if not default_folder:
            skipped += 1
            continue
        source = Path(row["file_path"])
        if not source.is_file() or not is_under(source, project_folder):
            skipped += 1
            print(f"SKIP file missing/outside project: {source}")
            continue
        target_folder = project_folder / default_folder
        if not should_move(row, source, project_folder, target_folder, all_categorized):
            skipped += 1
            continue
        target = unique_destination(target_folder / source.name)
        if not summary_only:
            print(("MOVE" if apply else "WOULD MOVE") + f": {source} -> {target}")
        if apply:
            target_folder.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            conn.execute(
                "UPDATE project_files SET file_path = ?, updated_at = ? WHERE id = ?",
                (str(target), now_iso(), row["id"]),
            )
        moved += 1
    if summary_only and (missing_dirs or moved):
        print(
            f"{'APPLY' if apply else 'PLAN'}: {project['equipment_no'] or project['intake_no']} | "
            f"create_dirs={len(missing_dirs)} | move_files={moved} | {project_folder}"
        )
    return len(missing_dirs), moved, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Create new standard subfolders and move indexed project files into category folders.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag the tool only prints the plan.")
    parser.add_argument("--project-id", help="Only process one project id.")
    parser.add_argument(
        "--all-categorized",
        action="store_true",
        help="Move all indexed files by category, not only files in known old top-level folders.",
    )
    parser.add_argument("--summary-only", action="store_true", help="Only print one summary line per affected project.")
    parser.add_argument("--moves-only", action="store_true", help="Print planned file moves and final totals, but skip directory create lines.")
    args = parser.parse_args()

    with db_connect() as conn:
        root = Path(get_setting(conn, "project_root_path", r"D:\01_CustomerProject")).resolve(strict=False)
        projects = active_project_rows(conn, args.project_id)
        total_created_dirs = 0
        total_moved = 0
        total_skipped = 0
        for project in projects:
            project_folder = Path(project["project_folder_path"]).resolve(strict=False)
            if not is_under(project_folder, root):
                print(f"SKIP outside project root: {project['equipment_no'] or project['intake_no']} {project_folder}")
                total_skipped += 1
                continue
            created_dirs, moved, skipped = restructure_project(
                conn,
                project,
                args.apply,
                args.all_categorized,
                args.summary_only,
                args.moves_only,
            )
            total_created_dirs += created_dirs
            total_moved += moved
            total_skipped += skipped
        if args.apply:
            conn.commit()
        print(f"Project root: {root}")
        print(f"Checked projects: {len(projects)}")
        print(f"{'Created dirs' if args.apply else 'Planned dirs to create'}: {total_created_dirs}")
        print(f"{'Moved' if args.apply else 'Planned moves'}: {total_moved}")
        print(f"Skipped file records: {total_skipped}")
        if not args.apply:
            print("Dry run only. Re-run with --apply after confirming the plan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
