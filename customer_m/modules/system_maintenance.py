"""System maintenance workflows such as database backup."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from pathlib import Path
import sqlite3

from .. import config
from ..database import db_connect, get_setting
from ..utils import make_id, now_iso
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


def _job_result(row: sqlite3.Row) -> dict:
    try:
        result = json.loads(row["result_json"] or "{}")
    except (TypeError, ValueError):
        result = {}
    total = int(row["total_projects"] or 0) + int(row["total_shared_groups"] or 0)
    processed = int(row["processed_projects"] or 0) + int(row["processed_shared_groups"] or 0)
    progress_percent = 100 if row["status"] == "completed" else int(processed * 100 / total) if total else 0
    return {
        "id": row["id"],
        "status": row["status"],
        "requested_by_user_id": row["requested_by_user_id"],
        "requested_by_email": row["requested_by_email"],
        "total_projects": int(row["total_projects"] or 0),
        "processed_projects": int(row["processed_projects"] or 0),
        "total_shared_groups": int(row["total_shared_groups"] or 0),
        "processed_shared_groups": int(row["processed_shared_groups"] or 0),
        "progress_percent": progress_percent,
        "result": result,
        "error": row["error"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "updated_at": row["updated_at"],
    }


def get_global_file_scan_job(job_id: str) -> dict:
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM file_scan_jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise ValueError("全局扫描任务不存在")
    return _job_result(row)


def get_latest_global_file_scan_job() -> dict | None:
    with db_connect() as conn:
        row = conn.execute(
            "SELECT * FROM file_scan_jobs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return _job_result(row) if row is not None else None


def create_global_file_scan_job(user: dict | None = None) -> dict:
    now = now_iso()
    with db_connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        active = conn.execute(
            """
            SELECT * FROM file_scan_jobs
            WHERE status IN ('pending', 'running')
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if active is not None:
            conn.commit()
            payload = _job_result(active)
            payload["created"] = False
            return payload
        job_id = make_id()
        conn.execute(
            """
            INSERT INTO file_scan_jobs (
              id, status, requested_by_user_id, requested_by_email,
              created_at, updated_at
            )
            VALUES (?, 'pending', ?, ?, ?, ?)
            """,
            (job_id, (user or {}).get("id"), (user or {}).get("email"), now, now),
        )
        row = conn.execute("SELECT * FROM file_scan_jobs WHERE id = ?", (job_id,)).fetchone()
        conn.commit()
    payload = _job_result(row)
    payload["created"] = True
    return payload


def _update_scan_job_progress(job_id: str, progress: dict) -> None:
    now = now_iso()
    with db_connect() as conn:
        conn.execute(
            """
            UPDATE file_scan_jobs
            SET total_projects = ?, processed_projects = ?,
                total_shared_groups = ?, processed_shared_groups = ?,
                result_json = ?, updated_at = ?
            WHERE id = ? AND status = 'running'
            """,
            (
                int(progress.get("total_projects") or 0),
                int(progress.get("processed_projects") or 0),
                int(progress.get("total_shared_groups") or 0),
                int(progress.get("processed_shared_groups") or 0),
                json.dumps(progress.get("result") or {}, ensure_ascii=False),
                now,
                job_id,
            ),
        )
        conn.commit()


def run_global_file_scan_job(job_id: str) -> None:
    started_at = now_iso()
    with db_connect() as conn:
        updated = conn.execute(
            """
            UPDATE file_scan_jobs
            SET status = 'running', started_at = ?, updated_at = ?, error = NULL
            WHERE id = ? AND status = 'pending'
            """,
            (started_at, started_at, job_id),
        ).rowcount
        conn.commit()
    if not updated:
        logger.warning("Global scan job was not pending job_id=%s", job_id)
        return
    try:
        result = run_global_file_scan(lambda progress: _update_scan_job_progress(job_id, progress))
        completed_at = now_iso()
        with db_connect() as conn:
            conn.execute(
                """
                UPDATE file_scan_jobs
                SET status = 'completed', result_json = ?, error = NULL,
                    completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(result, ensure_ascii=False), completed_at, completed_at, job_id),
            )
            conn.commit()
    except Exception as exc:
        completed_at = now_iso()
        logger.exception("Global scan background job failed job_id=%s", job_id)
        with db_connect() as conn:
            conn.execute(
                """
                UPDATE file_scan_jobs
                SET status = 'failed', error = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (str(exc), completed_at, completed_at, job_id),
            )
            conn.commit()


def run_global_file_scan(progress_callback: Callable[[dict], None] | None = None) -> dict:
    failures: list[dict] = []
    project_totals = _empty_scan_totals()
    shared_totals = _empty_scan_totals()

    with db_connect() as conn:
        projects = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, intake_no, equipment_no, project_folder_path
                FROM projects
                WHERE COALESCE(is_deleted, 0) = 0
                  AND project_folder_path IS NOT NULL
                  AND trim(project_folder_path) <> ''
                ORDER BY created_at
                """
            ).fetchall()
        ]
        project_groups = [
            dict(row)
            for row in conn.execute(
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
        ]

    processed_projects = 0
    processed_shared_groups = 0

    def report_progress() -> None:
        if progress_callback is None:
            return
        progress_callback(
            {
                "total_projects": len(projects),
                "processed_projects": processed_projects,
                "total_shared_groups": len(project_groups),
                "processed_shared_groups": processed_shared_groups,
                "result": {
                    "scanned_projects": processed_projects,
                    "scanned_shared_groups": processed_shared_groups,
                    "project": dict(project_totals),
                    "shared": dict(shared_totals),
                    "failures": list(failures),
                    "failed_scopes": len(failures),
                },
            }
        )

    report_progress()
    for project in projects:
        try:
            with db_connect() as scan_conn:
                result = scan_project_folder(scan_conn, project["id"])
                scan_conn.commit()
            _merge_scan_result(project_totals, result)
        except (ValueError, sqlite3.Error) as exc:
            logger.exception("Global project scan failed project_id=%s", project["id"])
            failures.append(
                {
                    "scope": "project",
                    "id": project["id"],
                    "name": project["equipment_no"] or project["intake_no"] or "",
                    "path": project["project_folder_path"] or "",
                    "error": str(exc),
                }
            )
        finally:
            processed_projects += 1
            report_progress()

    for group in project_groups:
        try:
            with db_connect() as scan_conn:
                result = scan_project_group_shared_folder(scan_conn, group["id"])
                scan_conn.commit()
            _merge_scan_result(shared_totals, result)
        except (ValueError, sqlite3.Error) as exc:
            logger.exception("Global shared-folder scan failed project_group_id=%s", group["id"])
            failures.append(
                {
                    "scope": "shared",
                    "id": group["id"],
                    "name": group["name"] or "",
                    "path": group["shared_folder_path"] or "",
                    "error": str(exc),
                }
            )
        finally:
            processed_shared_groups += 1
            report_progress()

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
