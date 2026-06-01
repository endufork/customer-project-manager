"""projects module."""

import sqlite3

from ..config import EQUIPMENT_NO_RE, PROJECT_NATURES

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
