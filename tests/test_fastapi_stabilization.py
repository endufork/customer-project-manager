from __future__ import annotations

from pathlib import Path

import pytest


def auth_headers(client) -> dict[str, str]:
    email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": email, "code": code_payload["dev_code"]},
    ).json()
    return {"Authorization": f"Bearer {login_payload['token']}"}


def test_production_runtime_config_fails_closed(monkeypatch):
    from customer_m import config

    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.setattr(config, "AUTH_SECRET", "local-dev-auth-secret")
    monkeypatch.setattr(config, "SMTP_HOST", "")
    monkeypatch.setattr(config, "SMTP_FROM_EMAIL", "")
    monkeypatch.setattr(config, "SMTP_USERNAME", "")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "")

    with pytest.raises(RuntimeError, match="生产环境配置不完整"):
        config.validate_runtime_config()


def test_security_headers_are_applied(client):
    response = client.get("/")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def create_project(client, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "customer_name": "Acme China",
            "site_name": "Suzhou",
            "contact_name": "Alice",
            "equipment_name": "Vision Test Machine",
            "project_name": "Vision Line",
            "project_nature": "新设备",
            "status_code": "inquiry",
            "currency_code": "CNY",
            "inquiry_date": "2026-06-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_strict_schema_rejects_unknown_request_fields(client):
    response = client.post(
        "/api/auth/request-code",
        json={"email": "rongkai@jinxiangsz.com", "unexpected": "field"},
    )

    assert response.status_code == 422


def test_lifespan_configures_file_logging(client, tmp_path):
    log_path = tmp_path / "logs" / "app.log"

    response = client.get("/api/health")

    assert response.status_code == 200
    assert log_path.exists()


def test_database_backup_uses_configured_backup_directory(client, tmp_path):
    headers = auth_headers(client)
    backup_dir = tmp_path / "db_backups"

    settings_response = client.patch(
        "/api/settings",
        headers=headers,
        json={"backup_target_path": str(backup_dir)},
    )
    assert settings_response.status_code == 200, settings_response.text
    assert settings_response.json()["settings"]["backup_target_path"] == str(backup_dir)

    backup_response = client.post("/api/system/backup", headers=headers)
    assert backup_response.status_code == 200, backup_response.text
    payload = backup_response.json()

    backup_path = Path(payload["backup_path"])
    assert payload["created"] is True
    assert backup_path.exists()
    assert backup_path.parent == backup_dir
    assert backup_path.suffix == ".db"


def test_scan_records_single_file_failures_without_aborting(client, monkeypatch):
    from customer_m.modules import scanner

    headers = auth_headers(client)
    project_id = create_project(client, headers)
    detail = client.get(f"/api/projects/{project_id}", headers=headers).json()
    project_folder = Path(detail["project"]["project_folder_path"])
    good_file = project_folder / "01_输入资料" / "good.txt"
    bad_file = project_folder / "01_输入资料" / "bad.txt"
    good_file.write_text("good", encoding="utf-8")
    bad_file.write_text("bad", encoding="utf-8")

    original = scanner.index_project_file

    def fail_one_file(conn, indexed_project_id, indexed_project_folder, file_path):
        if file_path.name == "bad.txt":
            raise OSError("simulated locked file")
        return original(conn, indexed_project_id, indexed_project_folder, file_path)

    monkeypatch.setattr(scanner, "index_project_file", fail_one_file)

    response = client.post(f"/api/projects/{project_id}/scan", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["new_files"] == 1
    assert payload["failed_files"] == 1
    assert payload["file_errors"][0]["file_path"].endswith("bad.txt")
