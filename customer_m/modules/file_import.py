"""file import module."""

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import MODEL_EXTENSIONS
from ..utils import make_id, now_iso
from .file_types import classify_file
from .file_visibility import category_visibility
from .folders import default_folder_for, unique_destination
from .parsers import extract_text
from .scanner import sha256_file


logger = logging.getLogger(__name__)


def iter_source_files(source_path: Path) -> list[Path]:
    try:
        if not source_path.exists():
            raise ValueError("导入路径不存在")
        if source_path.is_file():
            return [source_path]
        return [path for path in source_path.rglob("*") if path.is_file()]
    except OSError as exc:
        logger.exception("Failed to enumerate import source path=%s", source_path)
        raise ValueError(f"读取导入路径失败，请检查网络路径或权限：{exc}") from exc

def import_source_path(
    conn: sqlite3.Connection,
    project_id: str,
    project_folder: Path,
    source_path_value: str,
) -> tuple[int, bool]:
    source_path_value = source_path_value.strip().strip('"')
    if not source_path_value:
        return 0, False

    source_root = Path(source_path_value)
    files = iter_source_files(source_root)
    logger.info(
        "Importing project source path project_id=%s source=%s file_count=%s",
        project_id,
        source_root,
        len(files),
    )
    imported = 0
    has_model = False
    for source in files:
        category = classify_file(source)
        target_dir = project_folder / default_folder_for(conn, category)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            destination = unique_destination(target_dir / source.name)
            shutil.copy2(source, destination)
            ext = destination.suffix.lower()
            is_model = 1 if ext in MODEL_EXTENSIONS else 0
            has_model = has_model or bool(is_model)
            text_extracted, extracted_text = extract_text(destination)
            file_hash = sha256_file(destination)
            stat = destination.stat()
        except OSError as exc:
            logger.exception(
                "Failed to import project source file project_id=%s source=%s target_dir=%s",
                project_id,
                source,
                target_dir,
            )
            raise ValueError(f"导入文件失败，请检查网络路径或权限：{exc}") from exc
        file_id = make_id()
        visibility_code = category_visibility(conn, category)
        conn.execute(
            """
            INSERT INTO project_files (
              id, project_id, original_name, current_name, extension, category_code,
              visibility_code, file_path, original_source_path, size_bytes, modified_at, is_3d_model,
              text_extracted, extracted_text, content_hash, import_method, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new_project_copy', ?, ?)
            """,
            (
                file_id,
                project_id,
                source.name,
                destination.name,
                ext,
                category,
                visibility_code,
                str(destination),
                str(source),
                stat.st_size,
                datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                is_model,
                text_extracted,
                extracted_text,
                file_hash,
                now_iso(),
                now_iso(),
            ),
        )
        conn.execute(
            """
            INSERT INTO file_search (file_id, project_id, file_name, extracted_text)
            VALUES (?, ?, ?, ?)
            """,
            (file_id, project_id, destination.name, extracted_text),
        )
        imported += 1
    logger.info("Imported project source path project_id=%s imported=%s has_model=%s", project_id, imported, has_model)
    return imported, has_model
