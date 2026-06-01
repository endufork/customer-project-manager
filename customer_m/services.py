import hashlib
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from .config import (
    CATEGORY_DEFAULT_FOLDERS,
    EQUIPMENT_NO_RE,
    LEGACY_CATEGORY_FOLDERS,
    MODEL_EXTENSIONS,
    PROJECT_GROUP_CONTAINER,
    PROJECT_NATURES,
    SHARED_FOLDER_NAME,
    SINGLE_DEVICE_CONTAINER,
    STANDARD_FOLDER_FALLBACK_CATEGORIES,
    STANDARD_PROJECT_FOLDERS,
    TEXT_EXTENSIONS,
)
from .database import get_setting
from .utils import make_id, now_iso, sanitize_path_part, today_compact

def generate_intake_no(conn: sqlite3.Connection) -> str:
    prefix = f"INQ-{today_compact()}-"
    row = conn.execute(
        "SELECT intake_no FROM projects WHERE intake_no LIKE ? ORDER BY intake_no DESC LIMIT 1",
        (prefix + "%",),
    ).fetchone()
    if row is None:
        return prefix + "001"
    try:
        next_no = int(row["intake_no"].rsplit("-", 1)[1]) + 1
    except (IndexError, ValueError):
        next_no = 1
    return f"{prefix}{next_no:03d}"


def get_or_create_customer_group(conn: sqlite3.Connection, group_name: str) -> str | None:
    group_name = group_name.strip()
    if not group_name:
        return None
    existing = conn.execute(
        "SELECT id FROM customer_groups WHERE name = ? COLLATE NOCASE",
        (group_name,),
    ).fetchone()
    if existing:
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO customer_groups (id, name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (new_id, group_name, now_iso(), now_iso()),
    )
    return new_id


def get_or_create_customer(
    conn: sqlite3.Connection,
    customer_id: str,
    name: str,
    group_id: str | None = None,
) -> str:
    if customer_id:
        row = conn.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if row:
            if group_id:
                conn.execute(
                    "UPDATE customers SET group_id = COALESCE(group_id, ?), updated_at = ? WHERE id = ?",
                    (group_id, now_iso(), customer_id),
                )
            return customer_id
    name = name.strip()
    if not name:
        raise ValueError("客户公司/法人主体不能为空")
    existing = conn.execute("SELECT id FROM customers WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if existing:
        if group_id:
            conn.execute(
                "UPDATE customers SET group_id = COALESCE(group_id, ?), updated_at = ? WHERE id = ?",
                (group_id, now_iso(), existing["id"]),
            )
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO customers (id, name, group_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (new_id, name, group_id, now_iso(), now_iso()),
    )
    return new_id


def get_or_create_site(
    conn: sqlite3.Connection,
    customer_id: str,
    site_id: str,
    name: str,
) -> str | None:
    if site_id:
        row = conn.execute("SELECT id FROM customer_sites WHERE id = ?", (site_id,)).fetchone()
        if row:
            return site_id
    name = name.strip()
    if not name:
        return None
    existing = conn.execute(
        "SELECT id FROM customer_sites WHERE customer_id = ? AND name = ? COLLATE NOCASE",
        (customer_id, name),
    ).fetchone()
    if existing:
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO customer_sites (id, customer_id, name, site_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (new_id, customer_id, name, "工厂/站点", now_iso(), now_iso()),
    )
    return new_id


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


def get_or_create_contact(
    conn: sqlite3.Connection,
    customer_id: str,
    site_id: str | None,
    contact_id: str,
    name: str,
    role: str = "",
    department: str = "",
) -> str | None:
    if contact_id:
        row = conn.execute("SELECT id FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if row:
            conn.execute(
                """
                UPDATE contacts
                SET site_id = COALESCE(site_id, ?),
                    department = COALESCE(NULLIF(department, ''), ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (site_id, department.strip() or None, now_iso(), contact_id),
            )
            return contact_id
    name = name.strip()
    if not name:
        return None
    existing = conn.execute(
        "SELECT id FROM contacts WHERE customer_id = ? AND name = ? COLLATE NOCASE",
        (customer_id, name),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE contacts
            SET site_id = COALESCE(site_id, ?),
                department = COALESCE(NULLIF(department, ''), ?),
                updated_at = ?
            WHERE id = ?
            """,
            (site_id, department.strip() or None, now_iso(), existing["id"]),
        )
        return existing["id"]
    new_id = make_id()
    conn.execute(
        """
        INSERT INTO contacts (id, customer_id, site_id, name, role, department, is_primary, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            new_id,
            customer_id,
            site_id,
            name,
            role.strip() or None,
            department.strip() or None,
            now_iso(),
            now_iso(),
        ),
    )
    return new_id


def validate_equipment_no(
    conn: sqlite3.Connection,
    equipment_no: str,
    exclude_project_id: str | None = None,
) -> str | None:
    value = equipment_no.strip()
    if not value:
        return None
    if not EQUIPMENT_NO_RE.fullmatch(value):
        raise ValueError("内部设备号只能包含英文字母、数字、横杠和下划线")
    if exclude_project_id:
        existing = conn.execute(
            "SELECT id FROM projects WHERE equipment_no = ? COLLATE NOCASE AND id <> ?",
            (value, exclude_project_id),
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT id FROM projects WHERE equipment_no = ? COLLATE NOCASE",
            (value,),
        ).fetchone()
    if existing:
        raise ValueError("内部设备号已存在")
    return value


def normalize_project_nature(value: str) -> str:
    nature = value.strip() or "新设备"
    if nature not in PROJECT_NATURES:
        raise ValueError("项目性质无效")
    return nature


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


def classify_file(path: Path) -> str:
    lower_name = path.name.lower()
    ext = path.suffix.lower()
    if ext in MODEL_EXTENSIONS:
        return "drawing_model"
    if any(word in lower_name for word in ["purchase order", "po", "订单"]):
        return "po"
    if any(word in lower_name for word in ["内部报价", "成本", "cost"]):
        return "internal_quote"
    if any(word in lower_name for word in ["报价", "quote", "quotation"]):
        return "customer_quote"
    if any(word in lower_name for word in ["方案", "proposal", "solution", "spec"]):
        return "solution"
    if any(word in lower_name for word in ["询价", "rfq", "需求", "requirement"]):
        return "inquiry"
    if any(word in lower_name for word in ["email", "邮件", "微信", "聊天", "meeting"]):
        return "communication"
    if any(word in lower_name for word in ["验收", "fat", "发货", "delivery", "shipment"]):
        return "acceptance_delivery"
    return "other"


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


def move_project_folder_if_needed(
    conn: sqlite3.Connection,
    project_id: str,
    target_folder: Path,
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

    target = target_folder
    if current.exists() and current.is_dir():
        if target.exists():
            target = unique_directory_destination(target)
        shutil.move(str(current), str(target))
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
    create_event(conn, project_id, "folder_moved", "项目文件夹已迁移到标准目录", new_prefix)
    return target


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_text(path: Path) -> tuple[int, str]:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTENSIONS:
            return 1, path.read_text(encoding="utf-8", errors="ignore")[:200_000]
        if ext == ".docx":
            return 1, extract_docx_text(path)[:200_000]
        if ext == ".xlsx":
            return 1, extract_xlsx_text(path)[:200_000]
        if ext == ".pdf":
            return 1, extract_pdf_text(path)[:200_000]
    except Exception:
        return 0, ""
    return 0, ""


def extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    texts = [node.text or "" for node in root.findall(".//w:t", namespace)]
    return "\n".join(texts)


def extract_xlsx_text(path: Path) -> str:
    values: list[str] = []
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for item in root.findall(".//a:si", ns):
                parts = [node.text or "" for node in item.findall(".//a:t", ns)]
                shared_strings.append("".join(parts))
        for name in archive.namelist():
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            root = ElementTree.fromstring(archive.read(name))
            ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for cell in root.findall(".//a:c", ns):
                value_node = cell.find("a:v", ns)
                if value_node is None or value_node.text is None:
                    continue
                if cell.attrib.get("t") == "s":
                    try:
                        values.append(shared_strings[int(value_node.text)])
                    except (ValueError, IndexError):
                        continue
                else:
                    values.append(value_node.text)
    return "\n".join(values)


def iter_source_files(source_path: Path) -> list[Path]:
    if not source_path.exists():
        raise ValueError("导入路径不存在")
    if source_path.is_file():
        return [source_path]
    return [path for path in source_path.rglob("*") if path.is_file()]


def import_source_path(
    conn: sqlite3.Connection,
    project_id: str,
    project_folder: Path,
    source_path_value: str,
) -> tuple[int, bool]:
    source_path_value = source_path_value.strip().strip('"')
    if not source_path_value:
        return 0, False

    files = iter_source_files(Path(source_path_value))
    imported = 0
    has_model = False
    for source in files:
        category = classify_file(source)
        target_dir = project_folder / default_folder_for(conn, category)
        target_dir.mkdir(parents=True, exist_ok=True)
        destination = unique_destination(target_dir / source.name)
        shutil.copy2(source, destination)
        ext = destination.suffix.lower()
        is_model = 1 if ext in MODEL_EXTENSIONS else 0
        has_model = has_model or bool(is_model)
        text_extracted, extracted_text = extract_text(destination)
        file_hash = sha256_file(destination)
        stat = destination.stat()
        file_id = make_id()
        conn.execute(
            """
            INSERT INTO project_files (
              id, project_id, original_name, current_name, extension, category_code,
              file_path, original_source_path, size_bytes, modified_at, is_3d_model,
              text_extracted, extracted_text, content_hash, import_method, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new_project_copy', ?, ?)
            """,
            (
                file_id,
                project_id,
                source.name,
                destination.name,
                ext,
                category,
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
    return imported, has_model


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
    new_count = 0
    skipped_count = 0
    for file_path in files:
        file_path_text = str(file_path)
        exists = conn.execute(
            "SELECT 1 FROM project_files WHERE project_id = ? AND file_path = ?",
            (project_id, file_path_text),
        ).fetchone()
        if exists:
            skipped_count += 1
            continue

        category = category_from_project_path(conn, project_folder, file_path)
        ext = file_path.suffix.lower()
        is_model = 1 if ext in MODEL_EXTENSIONS else 0
        text_extracted, extracted_text = extract_text(file_path)
        stat = file_path.stat()
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
                datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                is_model,
                text_extracted,
                extracted_text,
                sha256_file(file_path),
                now_iso(),
                now_iso(),
            ),
        )
        conn.execute(
            """
            INSERT INTO file_search (file_id, project_id, file_name, extracted_text)
            VALUES (?, ?, ?, ?)
            """,
            (file_id, project_id, file_path.name, extracted_text),
        )
        new_count += 1

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
    if new_count:
        create_event(conn, project_id, "folder_scanned", f"扫描项目文件夹，新增 {new_count} 个文件")
    return {
        "total_files": len(files),
        "new_files": new_count,
        "skipped_files": skipped_count,
    }


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
    new_count = 0
    skipped_count = 0
    for file_path in files:
        file_path_text = str(file_path)
        exists = conn.execute(
            "SELECT 1 FROM project_group_files WHERE project_group_id = ? AND file_path = ?",
            (project_group_id, file_path_text),
        ).fetchone()
        if exists:
            skipped_count += 1
            continue

        category = classify_file(file_path)
        ext = file_path.suffix.lower()
        is_model = 1 if ext in MODEL_EXTENSIONS else 0
        text_extracted, extracted_text = extract_text(file_path)
        stat = file_path.stat()
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
                datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
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
        "skipped_files": skipped_count,
    }


def delete_project_folder_if_requested(conn: sqlite3.Connection, folder_path: str) -> bool:
    if not folder_path:
        raise ValueError("项目文件夹路径为空，无法删除资料")

    root = Path(get_setting(conn, "project_root_path", r"D:\01_CustomerProject")).resolve(strict=False)
    target = Path(folder_path).resolve(strict=False)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError("为安全起见，只能删除项目根目录下的项目文件夹") from exc

    if target == root or len(relative.parts) < 2:
        raise ValueError("为安全起见，不能删除项目根目录或客户级目录")
    if not target.exists():
        return False
    if not target.is_dir():
        raise ValueError("项目资料路径不是文件夹，无法删除")

    shutil.rmtree(target)
    return True


def create_event(conn: sqlite3.Connection, project_id: str, event_type: str, title: str, detail: str = "") -> None:
    conn.execute(
        """
        INSERT INTO project_events (id, project_id, event_type, title, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (make_id(), project_id, event_type, title, detail or None, now_iso()),
    )
