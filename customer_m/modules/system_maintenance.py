"""System maintenance workflows such as database backup."""

from __future__ import annotations

import logging
from pathlib import Path
import sqlite3

from .. import config
from ..database import db_connect, get_setting
from ..utils import now_iso
from .scanner import scan_project_folder, scan_project_group_shared_folder


logger = logging.getLogger(__name__)


def resolve_backup_target_dir(conn: sqlite3.Connection) -> Path:
    configured = get_setting(conn, "backup_target_path", "").strip()
    if configured:
        return Path(configured)
    return config.DATA_DIR / "backups"


def create_database_backup() -> dict:
    with db_connect() as settings_conn:
        backup_dir = resolve_backup_target_dir(settings_conn)

    timestamp = now_iso().replace(":", "").replace("-", "").replace("+", "_").replace(".", "_")
    destination = backup_dir / f"customer_projects_{timestamp}.db"

    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        with db_connect() as source_conn:
            with sqlite3.connect(destination) as destination_conn:
                source_conn.backup(destination_conn)
    except OSError as exc:
        logger.exception("Failed to create database backup destination=%s", destination)
        raise ValueError(f"数据库备份失败，请检查备份目录权限：{exc}") from exc
    except sqlite3.Error as exc:
        logger.exception("Failed to create database backup destination=%s", destination)
        raise ValueError(f"数据库备份失败：{exc}") from exc

    logger.info("Database backup created destination=%s", destination)
    return {
        "created": True,
        "backup_path": str(destination),
        "backup_dir": str(backup_dir),
    }


def _empty_scan_totals() -> dict:
    return {
        "total_files": 0,
        "new_files": 0,
        "updated_files": 0,
        "removed_files": 0,
        "skipped_files": 0,
        "failed_files": 0,
    }


def _merge_scan_result(totals: dict, result: dict) -> None:
    for key in totals:
        totals[key] += int(result.get(key) or 0)


def run_global_file_scan() -> dict:
    failures: list[dict] = []
    project_totals = _empty_scan_totals()
    shared_totals = _empty_scan_totals()

    with db_connect() as conn:
        projects = conn.execute(
            """
            SELECT id, intake_no, equipment_no, project_folder_path
            FROM projects
            WHERE COALESCE(is_deleted, 0) = 0
              AND project_folder_path IS NOT NULL
              AND trim(project_folder_path) <> ''
            ORDER BY created_at
            """
        ).fetchall()
        project_groups = conn.execute(
            """
            SELECT DISTINCT pg.id, pg.name, pg.shared_folder_path
            FROM project_groups pg
            JOIN projects p ON p.project_group_id = pg.id
            WHERE COALESCE(p.is_deleted, 0) = 0
              AND pg.shared_folder_path IS NOT NULL
              AND trim(pg.shared_folder_path) <> ''
            ORDER BY pg.name
            """
        ).fetchall()

        for project in projects:
            try:
                _merge_scan_result(project_totals, scan_project_folder(conn, project["id"]))
            except ValueError as exc:
                failures.append(
                    {
                        "scope": "project",
                        "id": project["id"],
                        "name": project["equipment_no"] or project["intake_no"] or "",
                        "path": project["project_folder_path"] or "",
                        "error": str(exc),
                    }
                )

        for group in project_groups:
            try:
                _merge_scan_result(shared_totals, scan_project_group_shared_folder(conn, group["id"]))
            except ValueError as exc:
                failures.append(
                    {
                        "scope": "shared",
                        "id": group["id"],
                        "name": group["name"] or "",
                        "path": group["shared_folder_path"] or "",
                        "error": str(exc),
                    }
                )

        conn.commit()

    result = {
        "scanned_projects": len(projects),
        "scanned_shared_groups": len(project_groups),
        "project": project_totals,
        "shared": shared_totals,
        "failures": failures,
        "failed_scopes": len(failures),
    }
    logger.info("Global file scan finished result=%s", result)
    return result
