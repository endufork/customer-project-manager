"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

from . import config


def resolve_log_dir() -> Path:
    if config.LOG_DIR_PATH:
        return Path(config.LOG_DIR_PATH)
    return config.DATA_DIR / "logs"


def configure_logging() -> Path:
    log_dir = resolve_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"

    root_logger = logging.getLogger()
    level_name = os.environ.get("CUSTOMER_PROJECT_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        if not getattr(handler, "_customer_project_file_handler", False):
            continue
        if getattr(handler, "_customer_project_log_path", None) == str(log_path):
            return log_path
        root_logger.removeHandler(handler)
        handler.close()

    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8")
    handler._customer_project_file_handler = True
    handler._customer_project_log_path = str(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.setLevel(level)
    root_logger.addHandler(handler)
    logging.getLogger(__name__).info("Application logging configured path=%s", log_path)
    return log_path
