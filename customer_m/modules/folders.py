"""folders module."""

import shutil
import sqlite3
from pathlib import Path

from ..config import (
    PROJECT_GROUP_CONTAINER,
    SHARED_FOLDER_NAME,
    SINGLE_DEVICE_CONTAINER,
    STANDARD_PROJECT_FOLDERS,
)
from ..database import get_setting
from ..utils import make_id, now_iso, sanitize_path_part
from .lifecycle import create_event

def customer_context_folder_for(
    conn: sqlite3.Connection,
    customer_group_name: str,
    customer_name: str,
    site_name: str,
) -> Path:
    root = Path(get_setting(conn, "project_root_path", r"D:\01_CustomerProject"))
    base = root
    group = sanitize_path_part(customer_group_name, "")
    company = sanitize_path_part(customer_name)
    site = sanitize_path_part(site_name, "")
    if group:
        base = base / group
    base = base / company
    if site:
        base = base / site
    return base

def project_group_folder_for(
    conn: sqlite3.Connection,
    customer_group_name: str,
    customer_name: str,
    site_name: str,
    project_group_name: str,
) -> Path:
    return (
        customer_context_folder_for(conn, customer_group_name, customer_name, site_name)
        / PROJECT_GROUP_CONTAINER
        / sanitize_path_part(project_group_name)
    )

def project_parent_folder_for(
    conn: sqlite3.Connection,
    customer_group_name: str,
    customer_name: str,
    site_name: str,
    project_group_name: str,
) -> Path:
    if project_group_name.strip():
        return project_group_folder_for(
            conn,
            customer_group_name,
            customer_name,
            site_name,
            project_group_name,
        )
    return customer_context_folder_for(conn, customer_group_name, customer_name, site_name) / SINGLE_DEVICE_CONTAINER

def get_or_create_project_group(
    conn: sqlite3.Connection,
    name: str,
    customer_group_id: str | None,
    customer_id: str,
    site_id: str | None,
    shared_folder_path: Path,
) -> str | None:
    name = name.strip()
    if not name:
        return None
    if site_id:
        existing = conn.execute(
            """
            SELECT id, shared_folder_path FROM project_groups
            WHERE customer_id = ? AND site_id = ? AND name = ? COLLATE NOCASE
            """,
            (customer_id, site_id, name),
        ).fetchone()
    else:
        existing = conn.execute(
            """
            SELECT id, shared_folder_path FROM project_groups
            WHERE customer_id = ? AND site_id IS NULL AND name = ? COLLATE NOCASE
            """,
            (customer_id, name),
        ).fetchone()
    shared_path = str(shared_folder_path)
    if existing:
        old_shared_path = existing["shared_folder_path"] or ""
        conn.execute(
            """
            UPDATE project_groups
            SET customer_group_id = ?,
                shared_folder_path = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (customer_group_id, shared_path, now_iso(), existing["id"]),
        )
        if old_shared_path and old_shared_path != shared_path:
            rows = conn.execute(
                "SELECT id, file_path FROM project_group_files WHERE project_group_id = ?",
                (existing["id"],),
            ).fetchall()
            for file_row in rows:
                file_path = file_row["file_path"]
                if file_path.startswith(old_shared_path):
                    updated_path = shared_path + file_path[len(old_shared_path):]
                    conn.execute(
                        "UPDATE project_group_files SET file_path = ?, updated_at = ? WHERE id = ?",
                        (updated_path, now_iso(), file_row["id"]),
                    )
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO project_groups (
          id, name, customer_group_id, customer_id, site_id, shared_folder_path,
          created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (new_id, name, customer_group_id, customer_id, site_id, shared_path, now_iso(), now_iso()),
    )
    return new_id

def project_folder_for(
    conn: sqlite3.Connection,
    customer_group_name: str,
    customer_name: str,
    site_name: str,
    project_group_name: str,
    contact_name: str,
    equipment_name: str,
    intake_no: str,
    equipment_no: str | None,
) -> Path:
    folder_no = equipment_no or intake_no
    contact = sanitize_path_part(contact_name, "")
    device = sanitize_path_part(equipment_name)
    if contact:
        leaf = f"{folder_no}_{contact}_{device}"
    else:
        leaf = f"{folder_no}_{device}"
    return project_parent_folder_for(
        conn,
        customer_group_name,
        customer_name,
        site_name,
        project_group_name,
    ) / leaf

def ensure_standard_dirs(base_path: Path, conn: sqlite3.Connection) -> None:
    base_path.mkdir(parents=True, exist_ok=True)
    for folder in STANDARD_PROJECT_FOLDERS:
        (base_path / folder).mkdir(parents=True, exist_ok=True)

def default_folder_for(conn: sqlite3.Connection, category_code: str) -> str:
    row = conn.execute(
        "SELECT default_folder FROM file_categories WHERE code = ?",
        (category_code,),
    ).fetchone()
    return row["default_folder"] if row else "99_其他"

def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1

def unique_directory_destination(path: Path) -> Path:
    if not path.exists():
        return path
    parent = path.parent
    name = path.name
    index = 2
    while True:
        candidate = parent / f"{name} ({index})"
        if not candidate.exists():
            return candidate
        index += 1

def cleanup_empty_parent_dirs(conn: sqlite3.Connection, start_path: Path) -> list[str]:
    root = Path(get_setting(conn, "project_root_path", r"D:\01_CustomerProject")).resolve(strict=False)
    cleaned: list[str] = []
    current = start_path.resolve(strict=False)
    while current != root:
        try:
            current.relative_to(root)
        except ValueError:
            break
        if current.exists() and current.is_dir():
            for child in sorted((path for path in current.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
                try:
                    child.rmdir()
                except OSError:
                    pass
        try:
            current.rmdir()
        except OSError:
            break
        cleaned.append(str(current))
        current = current.parent.resolve(strict=False)
    return cleaned

def cleanup_orphan_project_group(conn: sqlite3.Connection, project_group_id: str | None) -> bool:
    if not project_group_id:
        return False
    referenced = conn.execute(
        """
        SELECT 1
        WHERE EXISTS (SELECT 1 FROM projects WHERE project_group_id = ?)
           OR EXISTS (SELECT 1 FROM project_group_files WHERE project_group_id = ?)
        """,
        (project_group_id, project_group_id),
    ).fetchone()
    if referenced:
        return False
    conn.execute("DELETE FROM project_groups WHERE id = ?", (project_group_id,))
    return True

def move_project_folder_if_needed(
    conn: sqlite3.Connection,
    project_id: str,
    target_folder: Path,
    event_type: str = "folder_moved",
    event_title: str = "项目文件夹已迁移到标准目录",
) -> Path | None:
    row = conn.execute(
        "SELECT project_folder_path FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if row is None or not row["project_folder_path"]:
        return None

    current = Path(row["project_folder_path"])
    target_folder.parent.mkdir(parents=True, exist_ok=True)
    try:
        if current.resolve(strict=False) == target_folder.resolve(strict=False):
            ensure_standard_dirs(target_folder, conn)
            return current
    except OSError:
        pass

    old_parent = current.parent
    target = target_folder
    if current.exists() and current.is_dir():
        if target.exists():
            target = unique_directory_destination(target)
        shutil.move(str(current), str(target))
        cleanup_empty_parent_dirs(conn, old_parent)
    else:
        ensure_standard_dirs(target, conn)

    old_prefix = str(current)
    new_prefix = str(target)
    conn.execute(
        "UPDATE projects SET project_folder_path = ?, updated_at = ? WHERE id = ?",
        (new_prefix, now_iso(), project_id),
    )
    rows = conn.execute(
        "SELECT id, file_path FROM project_files WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    for file_row in rows:
        file_path = file_row["file_path"]
        if file_path.startswith(old_prefix):
            updated_path = new_prefix + file_path[len(old_prefix):]
            conn.execute(
                "UPDATE project_files SET file_path = ?, updated_at = ? WHERE id = ?",
                (updated_path, now_iso(), file_row["id"]),
            )
    create_event(conn, project_id, event_type, event_title, new_prefix)
    return target

def _project_folder_row_for_path(conn: sqlite3.Connection, target: Path) -> sqlite3.Row | None:
    rows = conn.execute(
        """
        SELECT id, intake_no, equipment_no, project_folder_path
        FROM projects
        WHERE project_folder_path IS NOT NULL AND trim(project_folder_path) <> ''
        """
    ).fetchall()
    for row in rows:
        try:
            candidate = Path(row["project_folder_path"]).resolve(strict=False)
        except OSError:
            continue
        if candidate == target:
            return row
    return None

def _is_project_leaf_path(relative: Path) -> bool:
    parts = relative.parts
    return (
        len(parts) >= 3 and parts[-2] == SINGLE_DEVICE_CONTAINER
    ) or (
        len(parts) >= 4 and parts[-3] == PROJECT_GROUP_CONTAINER
    )

def _folder_name_contains_project_no(project: sqlite3.Row, target: Path) -> bool:
    markers = [project["equipment_no"], project["intake_no"]]
    return any(marker and marker in target.name for marker in markers)

def delete_project_folder_if_requested(conn: sqlite3.Connection, folder_path: str) -> bool:
    if not folder_path:
        raise ValueError("项目文件夹路径为空，无法删除资料")

    root = Path(get_setting(conn, "project_root_path", r"D:\01_CustomerProject")).resolve(strict=False)
    target = Path(folder_path).resolve(strict=False)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError("为安全起见，只能删除项目根目录下的项目文件夹") from exc

    if target == root or not _is_project_leaf_path(relative):
        raise ValueError("为安全起见，只能删除系统标准结构下的项目文件夹")
    project = _project_folder_row_for_path(conn, target)
    if project is None:
        raise ValueError("为安全起见，只能删除数据库中登记的项目文件夹")
    if not _folder_name_contains_project_no(project, target):
        raise ValueError("为安全起见，项目文件夹名称必须包含INQ号或WO号")
    if not target.exists():
        return False
    if not target.is_dir():
        raise ValueError("项目资料路径不是文件夹，无法删除")

    shutil.rmtree(target)
    return True
