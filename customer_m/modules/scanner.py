"""scanner module."""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import (
    LEGACY_CATEGORY_FOLDERS,
    MODEL_EXTENSIONS,
    STANDARD_FOLDER_FALLBACK_CATEGORIES,
    STANDARD_PROJECT_FOLDERS,
)
from ..utils import make_id, now_iso
from .file_types import classify_file
from .lifecycle import create_event
from .parsers import extract_text

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def file_modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")

def category_from_project_path(conn: sqlite3.Connection, project_folder: Path, file_path: Path) -> str:
    try:
        relative_parts = file_path.relative_to(project_folder).parts[:-1]
    except ValueError:
        relative_parts = file_path.parts[:-1]
    classified = classify_file(file_path)
    for part in relative_parts:
        legacy_category = LEGACY_CATEGORY_FOLDERS.get(part)
        if legacy_category:
            return legacy_category
        if part in STANDARD_PROJECT_FOLDERS:
            if classified != "other":
                return classified
            return STANDARD_FOLDER_FALLBACK_CATEGORIES.get(part, "other")
    return classified

def remove_missing_project_files(conn: sqlite3.Connection, project_id: str, current_paths: set[str]) -> int:
    rows = conn.execute(
        "SELECT id, file_path FROM project_files WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    removed_ids = [row["id"] for row in rows if row["file_path"] not in current_paths]
    for file_id in removed_ids:
        conn.execute("DELETE FROM file_search WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM project_files WHERE id = ?", (file_id,))
    return len(removed_ids)

def refresh_project_file_flags(conn: sqlite3.Connection, project_id: str) -> None:
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
        (
            flags["has_quote"],
            flags["has_po"],
            flags["has_3d_model"],
            now_iso(),
            project_id,
        ),
    )

def upsert_file_search(conn: sqlite3.Connection, file_id: str, project_id: str, file_name: str, extracted_text: str) -> None:
    conn.execute("DELETE FROM file_search WHERE file_id = ?", (file_id,))
    conn.execute(
        """
        INSERT INTO file_search (file_id, project_id, file_name, extracted_text)
        VALUES (?, ?, ?, ?)
        """,
        (file_id, project_id, file_name, extracted_text),
    )

def scan_project_folder(conn: sqlite3.Connection, project_id: str) -> dict:
    project = conn.execute(
        "SELECT project_folder_path FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if project is None:
        raise ValueError("项目不存在")
    project_folder = Path(project["project_folder_path"] or "")
    if not project_folder.exists() or not project_folder.is_dir():
        raise ValueError("项目文件夹不存在")

    files = [path for path in project_folder.rglob("*") if path.is_file()]
    current_paths = {str(path) for path in files}
    removed_count = remove_missing_project_files(conn, project_id, current_paths)
    new_count = 0
    updated_count = 0
    skipped_count = 0
    for file_path in files:
        file_path_text = str(file_path)
        exists = conn.execute(
            "SELECT id, size_bytes, modified_at, content_hash FROM project_files WHERE project_id = ? AND file_path = ?",
            (project_id, file_path_text),
        ).fetchone()
        if exists:
            stat = file_path.stat()
            modified_at = file_modified_at(file_path)
            if exists["size_bytes"] == stat.st_size and exists["modified_at"] == modified_at:
                skipped_count += 1
                continue
            content_hash = sha256_file(file_path)
            category = category_from_project_path(conn, project_folder, file_path)
            ext = file_path.suffix.lower()
            is_model = 1 if ext in MODEL_EXTENSIONS else 0
            text_extracted, extracted_text = extract_text(file_path)
            conn.execute(
                """
                UPDATE project_files
                SET original_name = ?, current_name = ?, extension = ?, category_code = ?,
                  size_bytes = ?, modified_at = ?, is_3d_model = ?, text_extracted = ?,
                  extracted_text = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    file_path.name,
                    file_path.name,
                    ext,
                    category,
                    stat.st_size,
                    modified_at,
                    is_model,
                    text_extracted,
                    extracted_text,
                    content_hash,
                    now_iso(),
                    exists["id"],
                ),
            )
            upsert_file_search(conn, exists["id"], project_id, file_path.name, extracted_text)
            updated_count += 1
            continue

        category = category_from_project_path(conn, project_folder, file_path)
        ext = file_path.suffix.lower()
        is_model = 1 if ext in MODEL_EXTENSIONS else 0
        text_extracted, extracted_text = extract_text(file_path)
        stat = file_path.stat()
        modified_at = file_modified_at(file_path)
        file_id = make_id()
        conn.execute(
            """
            INSERT INTO project_files (
              id, project_id, original_name, current_name, extension, category_code,
              file_path, original_source_path, size_bytes, modified_at, is_3d_model,
              text_extracted, extracted_text, content_hash, import_method, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, 'new_project_copy', ?, ?)
            """,
            (
                file_id,
                project_id,
                file_path.name,
                file_path.name,
                ext,
                category,
                file_path_text,
                stat.st_size,
                modified_at,
                is_model,
                text_extracted,
                extracted_text,
                sha256_file(file_path),
                now_iso(),
                now_iso(),
            ),
        )
        upsert_file_search(conn, file_id, project_id, file_path.name, extracted_text)
        new_count += 1

    refresh_project_file_flags(conn, project_id)
    if new_count or updated_count or removed_count:
        create_event(
            conn,
            project_id,
            "folder_scanned",
            f"扫描项目文件夹，新增 {new_count} 个，更新 {updated_count} 个，移除 {removed_count} 个文件记录",
        )
    return {
        "total_files": len(files),
        "new_files": new_count,
        "updated_files": updated_count,
        "removed_files": removed_count,
        "skipped_files": skipped_count,
    }

def remove_missing_project_group_files(conn: sqlite3.Connection, project_group_id: str, current_paths: set[str]) -> int:
    rows = conn.execute(
        "SELECT id, file_path FROM project_group_files WHERE project_group_id = ?",
        (project_group_id,),
    ).fetchall()
    removed_ids = [row["id"] for row in rows if row["file_path"] not in current_paths]
    for file_id in removed_ids:
        conn.execute("DELETE FROM project_group_files WHERE id = ?", (file_id,))
    return len(removed_ids)

def scan_project_group_shared_folder(conn: sqlite3.Connection, project_group_id: str) -> dict:
    group = conn.execute(
        "SELECT shared_folder_path FROM project_groups WHERE id = ?",
        (project_group_id,),
    ).fetchone()
    if group is None:
        raise ValueError("客户产品/生产线不存在")
    shared_folder = Path(group["shared_folder_path"] or "")
    if not shared_folder.exists() or not shared_folder.is_dir():
        raise ValueError("共享资料文件夹不存在")

    files = [path for path in shared_folder.rglob("*") if path.is_file()]
    current_paths = {str(path) for path in files}
    removed_count = remove_missing_project_group_files(conn, project_group_id, current_paths)
    new_count = 0
    updated_count = 0
    skipped_count = 0
    for file_path in files:
        file_path_text = str(file_path)
        exists = conn.execute(
            "SELECT id, size_bytes, modified_at, content_hash FROM project_group_files WHERE project_group_id = ? AND file_path = ?",
            (project_group_id, file_path_text),
        ).fetchone()
        if exists:
            stat = file_path.stat()
            modified_at = file_modified_at(file_path)
            if exists["size_bytes"] == stat.st_size and exists["modified_at"] == modified_at:
                skipped_count += 1
                continue
            category = classify_file(file_path)
            ext = file_path.suffix.lower()
            is_model = 1 if ext in MODEL_EXTENSIONS else 0
            text_extracted, extracted_text = extract_text(file_path)
            conn.execute(
                """
                UPDATE project_group_files
                SET original_name = ?, current_name = ?, extension = ?, category_code = ?,
                  size_bytes = ?, modified_at = ?, is_3d_model = ?, text_extracted = ?,
                  extracted_text = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    file_path.name,
                    file_path.name,
                    ext,
                    category,
                    stat.st_size,
                    modified_at,
                    is_model,
                    text_extracted,
                    extracted_text,
                    sha256_file(file_path),
                    now_iso(),
                    exists["id"],
                ),
            )
            updated_count += 1
            continue

        category = classify_file(file_path)
        ext = file_path.suffix.lower()
        is_model = 1 if ext in MODEL_EXTENSIONS else 0
        text_extracted, extracted_text = extract_text(file_path)
        stat = file_path.stat()
        modified_at = file_modified_at(file_path)
        conn.execute(
            """
            INSERT INTO project_group_files (
              id, project_group_id, original_name, current_name, extension, category_code,
              file_path, size_bytes, modified_at, is_3d_model, text_extracted,
              extracted_text, content_hash, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                make_id(),
                project_group_id,
                file_path.name,
                file_path.name,
                ext,
                category,
                file_path_text,
                stat.st_size,
                modified_at,
                is_model,
                text_extracted,
                extracted_text,
                sha256_file(file_path),
                now_iso(),
                now_iso(),
            ),
        )
        new_count += 1

    return {
        "total_files": len(files),
        "new_files": new_count,
        "updated_files": updated_count,
        "removed_files": removed_count,
        "skipped_files": skipped_count,
    }
