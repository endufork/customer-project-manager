"""System maintenance workflows such as database backup."""

from __future__ import annotations

import logging
from pathlib import Path
import sqlite3

from .. import config
from ..database import db_connect, get_setting
from ..utils import now_iso


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
