"""Workbench task deliverable file workflows."""

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from .. import config
from ..utils import make_id, now_iso, sanitize_path_part
from .lifecycle import create_event
from .notifications import notify_pm_users, notify_task_owner
from .parsers import extract_text
from .workbench_common import _nullable_text, _project_row, record_activity
from .workbench_permissions import require_task_write


logger = logging.getLogger(__name__)


class UploadTooLargeError(ValueError):
    pass


class UploadTypeError(ValueError):
    pass


def _category_row(conn: sqlite3.Connection, category_code: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT code, name, default_folder, default_visibility FROM file_categories WHERE code = ? AND is_active = 1",
        (category_code,),
    ).fetchone()
    if row is None:
        raise ValueError("文件类别无效")
    return row

def _unique_path(folder: Path, filename: str) -> Path:
    path = folder / filename
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = folder / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _validate_upload_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if not extension or extension not in config.UPLOAD_ALLOWED_EXTENSIONS:
        raise UploadTypeError(f"不允许上传此文件类型：{extension or '无扩展名'}")
    return extension


def _stream_to_path(source: BinaryIO, target_path: Path) -> tuple[int, str]:
    source.seek(0)
    total = 0
    digest = hashlib.sha256()
    with target_path.open("xb") as target:
        while True:
            chunk = source.read(config.UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > config.UPLOAD_MAX_BYTES:
                raise UploadTooLargeError(
                    f"文件超过上传上限 {config.UPLOAD_MAX_BYTES // (1024 * 1024)} MB"
                )
            target.write(chunk)
            digest.update(chunk)
    if total == 0:
        raise ValueError("请选择要上传的文件")
    return total, digest.hexdigest()


def _remove_partial_upload(target_path: Path | None) -> None:
    if target_path is None or not target_path.exists():
        return
    try:
        target_path.unlink()
    except OSError:
        logger.exception("Failed to remove partial upload path=%s", target_path)

def _refresh_project_file_flags(conn: sqlite3.Connection, project_id: str) -> None:
    flags = conn.execute(
        """
        SELECT
          COALESCE(MAX(CASE WHEN category_code IN ('customer_quote', 'internal_quote') THEN 1 ELSE 0 END), 0) AS has_quote,
          COALESCE(MAX(CASE WHEN category_code = 'po' THEN 1 ELSE 0 END), 0) AS has_po,
          COALESCE(MAX(is_3d_model), 0) AS has_3d_model
        FROM project_files
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE projects
        SET has_quote = ?, has_po = ?, has_3d_model = ?, updated_at = ?
        WHERE id = ?
        """,
        (flags["has_quote"], flags["has_po"], flags["has_3d_model"], now_iso(), project_id),
    )

def submit_task_file(
    conn: sqlite3.Connection,
    task_id: str,
    filename: str,
    source: BinaryIO,
    fields: dict,
    user: dict | None = None,
) -> dict:
    if not filename:
        raise ValueError("请选择要上传的文件")
    task = require_task_write(conn, task_id, user)
    project = _project_row(conn, task["project_id"])
    project_folder = Path(project["project_folder_path"] or "")
    if not project_folder.exists() or not project_folder.is_dir():
        raise ValueError("项目文件夹不存在，无法归档上传文件")

    category = _category_row(conn, (fields.get("category_code") or "other").strip() or "other")
    raw_name = Path(filename).name
    ext = _validate_upload_extension(raw_name)
    safe_stem = sanitize_path_part(Path(raw_name).stem, "交付文件")
    suffix = Path(raw_name).suffix
    safe_name = f"{safe_stem}{suffix}"
    target_folder = project_folder / category["default_folder"]
    target_path: Path | None = None
    try:
        target_folder.mkdir(parents=True, exist_ok=True)
        target_path = _unique_path(target_folder, safe_name)
        streamed_size, file_hash = _stream_to_path(source, target_path)
        stat = target_path.stat()
        text_extracted, extracted_text = extract_text(target_path)
        if stat.st_size != streamed_size:
            raise OSError("上传文件写入大小校验失败")
    except (UploadTooLargeError, UploadTypeError, ValueError):
        _remove_partial_upload(target_path)
        raise
    except OSError as exc:
        _remove_partial_upload(target_path)
        logger.exception(
            "Failed to archive task deliverable task_id=%s filename=%s target_folder=%s",
            task_id,
            filename,
            target_folder,
        )
        raise ValueError(f"交付文件归档失败，请检查网络路径或权限：{exc}") from exc
    file_id = make_id()
    now = now_iso()
    conn.execute(
        """
        INSERT INTO project_files (
          id, project_id, original_name, current_name, extension, category_code,
          visibility_code, file_path, original_source_path, size_bytes, modified_at, is_3d_model,
          text_extracted, extracted_text, content_hash, import_method, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, 'new_project_copy', ?, ?)
        """,
        (
            file_id,
            task["project_id"],
            raw_name,
            target_path.name,
            ext,
            category["code"],
            category["default_visibility"],
            str(target_path),
            stat.st_size,
            datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
            1 if ext in config.MODEL_EXTENSIONS else 0,
            text_extracted,
            extracted_text,
            file_hash,
            now,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO file_search (file_id, project_id, file_name, extracted_text)
        VALUES (?, ?, ?, ?)
        """,
        (file_id, task["project_id"], target_path.name, extracted_text),
    )
    deliverable_id = make_id()
    conn.execute(
        """
        INSERT INTO task_deliverables (
          id, task_id, project_id, file_id, deliverable_type, version_note,
          status, submitted_by, submitted_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?)
        """,
        (
            deliverable_id,
            task_id,
            task["project_id"],
            file_id,
            category["code"],
            _nullable_text(fields.get("version_note")),
            _nullable_text(fields.get("submitted_by")),
            now,
            now,
            now,
        ),
    )
    conn.execute(
        """
        UPDATE execution_tasks
        SET status = 'submitted', submitted_at = ?, updated_at = ?, requires_deliverable = 1
        WHERE id = ?
        """,
        (now, now, task_id),
    )
    _refresh_project_file_flags(conn, task["project_id"])
    record_activity(conn, task["project_id"], "deliverable_submitted", "提交交付文件", target_path.name, task_id=task_id)
    create_event(conn, task["project_id"], "workbench_file_submitted", "提交交付文件", target_path.name)
    notify_pm_users(
        conn,
        "deliverable_submitted",
        "交付文件待确认",
        f"{task['title']}：{target_path.name}",
        task["project_id"],
        exclude_user_id=(user or {}).get("id"),
    )
    logger.info(
        "Archived task deliverable task_id=%s project_id=%s file_id=%s path=%s",
        task_id,
        task["project_id"],
        file_id,
        target_path,
    )
    return {
        "id": deliverable_id,
        "file_id": file_id,
        "file_name": target_path.name,
        "file_path": str(target_path),
        "submitted": True,
    }

def review_deliverable(
    conn: sqlite3.Connection,
    deliverable_id: str,
    data: dict,
    user: dict | None = None,
) -> dict:
    row = conn.execute("SELECT * FROM task_deliverables WHERE id = ?", (deliverable_id,)).fetchone()
    if row is None:
        raise ValueError("交付物不存在")
    if row["status"] != "submitted":
        raise ValueError("只能确认或驳回待确认的交付物；驳回后必须重新提交文件")
    task = conn.execute("SELECT * FROM execution_tasks WHERE id = ?", (row["task_id"],)).fetchone()
    action = (data.get("status") or data.get("action") or "").strip()
    now = now_iso()
    if action == "confirmed":
        reviewer = _nullable_text(data.get("confirmed_by")) or "PM"
        conn.execute(
            """
            UPDATE task_deliverables
            SET status = 'confirmed', confirmed_by = ?, confirmed_at = ?, reject_reason = NULL, updated_at = ?
            WHERE id = ?
            """,
            (reviewer, now, now, deliverable_id),
        )
        conn.execute(
            """
            UPDATE execution_tasks
            SET status = 'confirmed', confirmed_at = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, now, row["task_id"]),
        )
        record_activity(conn, row["project_id"], "deliverable_confirmed", "确认交付物", reviewer, task_id=row["task_id"])
        create_event(conn, row["project_id"], "workbench_file_confirmed", "确认交付物", reviewer)
        if task:
            notify_task_owner(
                conn,
                task,
                "deliverable_reviewed",
                "交付文件已确认",
                task["title"],
                exclude_user_id=(user or {}).get("id"),
            )
        return {"id": deliverable_id, "project_id": row["project_id"], "task_id": row["task_id"], "status": "confirmed"}
    if action == "rejected":
        reason = _nullable_text(data.get("reject_reason"))
        if not reason:
            raise ValueError("驳回交付物需要填写原因")
        reviewer = _nullable_text(data.get("confirmed_by")) or "PM"
        conn.execute(
            """
            UPDATE task_deliverables
            SET status = 'rejected', confirmed_by = ?, confirmed_at = ?, reject_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (reviewer, now, reason, now, deliverable_id),
        )
        conn.execute(
            """
            UPDATE execution_tasks
            SET status = 'rework', notes = COALESCE(notes || char(10), '') || ?, updated_at = ?
            WHERE id = ?
            """,
            (f"交付物驳回：{reason}", now, row["task_id"]),
        )
        record_activity(conn, row["project_id"], "deliverable_rejected", "驳回交付物", reason, task_id=row["task_id"])
        create_event(conn, row["project_id"], "workbench_file_rejected", "驳回交付物", reason)
        if task:
            notify_task_owner(
                conn,
                task,
                "deliverable_reviewed",
                "交付文件被驳回",
                f"{task['title']}：{reason}",
                exclude_user_id=(user or {}).get("id"),
            )
        return {"id": deliverable_id, "project_id": row["project_id"], "task_id": row["task_id"], "status": "rejected"}
    raise ValueError("交付物操作无效")
