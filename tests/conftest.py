from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from customer_m import config, database
    from customer_m.fastapi_app import app

    data_dir = tmp_path / "data"
    project_root = tmp_path / "project_root"
    log_dir = tmp_path / "logs"
    db_path = data_dir / "customer_projects.db"

    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "LOG_DIR_PATH", str(log_dir))
    monkeypatch.setattr(database, "DATA_DIR", data_dir)
    monkeypatch.setattr(database, "DB_PATH", db_path)

    with TestClient(app) as test_client:
        with database.db_connect() as conn:
            database.set_setting(conn, "project_root_path", str(project_root))
            conn.commit()
        yield test_client
