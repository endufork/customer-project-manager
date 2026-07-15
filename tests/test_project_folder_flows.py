from __future__ import annotations

import shutil
from pathlib import Path

from customer_m.config import STANDARD_PROJECT_FOLDERS


def auth_headers(client) -> dict[str, str]:
    email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": email, "code": code_payload["dev_code"]},
    ).json()
    return {"Authorization": f"Bearer {login_payload['token']}"}


def project_payload(**overrides) -> dict:
    payload = {
        "customer_group_name": "Global Customer",
        "customer_name": "Ministud Legal Entity",
        "site_name": "Suzhou Plant",
        "contact_name": "Alice",
        "equipment_name": "Ministud Test Fixture",
        "project_name": "Ministud Line",
        "project_nature": "夹具/治具",
        "status_code": "inquiry",
        "currency_code": "CNY",
        "inquiry_date": "2026-06-01",
    }
    payload.update(overrides)
    return payload


def create_project(client, headers: dict[str, str], **overrides) -> dict:
    response = client.post("/api/projects", headers=headers, json=project_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def project_detail(client, headers: dict[str, str], project_id: str) -> dict:
    response = client.get(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["project"]


def assert_standard_dirs(folder: Path) -> None:
    assert folder.is_dir()
    for name in STANDARD_PROJECT_FOLDERS:
        assert (folder / name).is_dir(), f"missing standard folder: {name}"


def remove_standard_dirs(folder: Path, *, keep: Path | None = None) -> None:
    for name in sorted(STANDARD_PROJECT_FOLDERS, key=lambda value: value.count("/"), reverse=True):
        candidate = folder / name
        if keep and (candidate == keep or keep.is_relative_to(candidate)):
            continue
        if candidate.exists():
            shutil.rmtree(candidate)


def test_create_project_with_wo_creates_project_folder(client):
    headers = auth_headers(client)

    created = create_project(
        client,
        headers,
        equipment_no="WO-20260611-001",
        status_code="po_received",
        po_date="2026-06-11",
    )

    detail = project_detail(client, headers, created["id"])
    folder = Path(detail["project_folder_path"])

    assert folder.name.startswith("WO-20260611-001")
    assert_standard_dirs(folder)


def test_create_project_with_group_creates_shared_folder(client):
    headers = auth_headers(client)

    created = create_project(client, headers, project_group_name="Shared Line")

    detail = project_detail(client, headers, created["id"])
    shared_folder = Path(detail["shared_folder_path"])

    assert shared_folder.name == "00_共享资料"
    assert shared_folder.is_dir()


def test_web_api_cannot_launch_server_file_explorer(client):
    headers = auth_headers(client)
    created = create_project(client, headers, project_group_name="LAN Path Line")
    project_id = created["id"]
    detail = project_detail(client, headers, project_id)

    assert detail["project_folder_path"]
    assert detail["shared_folder_path"]
    assert client.post(f"/api/projects/{project_id}/open-folder", headers=headers).status_code == 404
    assert client.post(f"/api/projects/{project_id}/open-shared-folder", headers=headers).status_code == 404


def test_inq_to_wo_keeps_empty_project_folder_and_standard_dirs(client):
    headers = auth_headers(client)
    created = create_project(client, headers)
    project_id = created["id"]
    before = Path(project_detail(client, headers, project_id)["project_folder_path"])
    assert_standard_dirs(before)

    response = client.patch(
        f"/api/projects/{project_id}",
        headers=headers,
        json=project_payload(
            equipment_no="WO-20260611-002",
            status_code="po_received",
            po_date="2026-06-11",
        ),
    )

    assert response.status_code == 200, response.text
    after = Path(project_detail(client, headers, project_id)["project_folder_path"])
    assert after != before
    assert after.name.startswith("WO-20260611-002")
    assert not before.exists()
    assert_standard_dirs(after)


def test_inq_to_wo_rebuilds_missing_standard_dirs_without_losing_files(client):
    headers = auth_headers(client)
    created = create_project(client, headers)
    project_id = created["id"]
    before = Path(project_detail(client, headers, project_id)["project_folder_path"])
    kept_folder = before / "01_输入资料"
    kept_file = kept_folder / "customer-input.pdf"
    kept_file.write_text("sample", encoding="utf-8")
    remove_standard_dirs(before, keep=kept_folder)

    response = client.patch(
        f"/api/projects/{project_id}",
        headers=headers,
        json=project_payload(
            equipment_no="WO-20260611-003",
            status_code="po_received",
            po_date="2026-06-11",
        ),
    )

    assert response.status_code == 200, response.text
    after = Path(project_detail(client, headers, project_id)["project_folder_path"])
    assert (after / "01_输入资料" / "customer-input.pdf").is_file()
    assert_standard_dirs(after)


def test_rename_to_wo_is_idempotent_and_repairs_missing_folder(client):
    headers = auth_headers(client)
    created = create_project(
        client,
        headers,
        equipment_no="WO-20260611-004",
        status_code="po_received",
        po_date="2026-06-11",
    )
    project_id = created["id"]
    folder = Path(project_detail(client, headers, project_id)["project_folder_path"])
    remove_standard_dirs(folder)
    folder.rmdir()

    response = client.post(f"/api/projects/{project_id}/rename-folder", headers=headers, json={})

    assert response.status_code == 200, response.text
    payload = response.json()
    repaired = Path(payload["project_folder_path"])
    assert payload["renamed"] is False
    assert repaired == folder
    assert_standard_dirs(repaired)


def test_scan_all_scans_project_and_shared_folders(client):
    headers = auth_headers(client)
    created = create_project(client, headers, project_group_name="Scan All Line")
    project_id = created["id"]
    detail = project_detail(client, headers, project_id)
    project_folder = Path(detail["project_folder_path"])
    shared_folder = Path(detail["shared_folder_path"])
    (project_folder / "01_输入资料" / "input.txt").write_text("project file", encoding="utf-8")
    (shared_folder / "common.txt").write_text("shared file", encoding="utf-8")

    response = client.post(f"/api/projects/{project_id}/scan-all", headers=headers, json={})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["project"]["new_files"] == 1
    assert payload["shared"]["new_files"] == 1


def test_admin_global_scan_scans_all_and_removes_stale_indexes(client, monkeypatch):
    from customer_m import database
    from customer_m.modules import system_maintenance
    from customer_m.utils import make_id, now_iso

    headers = auth_headers(client)
    created = create_project(client, headers, project_group_name="Global Scan Line")
    project_id = created["id"]
    detail = project_detail(client, headers, project_id)
    project_folder = Path(detail["project_folder_path"])
    shared_folder = Path(detail["shared_folder_path"])
    (project_folder / "01_输入资料" / "global-input.txt").write_text("project file", encoding="utf-8")
    (shared_folder / "global-common.txt").write_text("shared file", encoding="utf-8")

    now = now_iso()
    with database.db_connect() as conn:
        conn.execute(
            """
            INSERT INTO project_files (
              id, project_id, original_name, current_name, extension, category_code,
              visibility_code, file_path, original_source_path, size_bytes, modified_at,
              is_3d_model, text_extracted, extracted_text, content_hash, import_method,
              created_at, updated_at
            )
            VALUES (?, ?, 'missing-project.pdf', 'missing-project.pdf', '.pdf', 'other',
              'engineering', ?, NULL, 10, ?, 0, 0, NULL, ?, 'new_project_copy', ?, ?)
            """,
            (make_id(), project_id, str(project_folder / "missing-project.pdf"), now, make_id(), now, now),
        )
        conn.execute(
            """
            INSERT INTO project_group_files (
              id, project_group_id, original_name, current_name, extension, category_code,
              visibility_code, file_path, size_bytes, modified_at, is_3d_model,
              text_extracted, extracted_text, content_hash, created_at, updated_at
            )
            VALUES (?, ?, 'missing-shared.pdf', 'missing-shared.pdf', '.pdf', 'other',
              'engineering', ?, 10, ?, 0, 0, NULL, ?, ?, ?)
            """,
            (make_id(), detail["project_group_id"], str(shared_folder / "missing-shared.pdf"), now, make_id(), now, now),
        )
        conn.commit()

    connection_count = 0
    real_db_connect = database.db_connect

    def counted_db_connect():
        nonlocal connection_count
        connection_count += 1
        return real_db_connect()

    monkeypatch.setattr(system_maintenance, "db_connect", counted_db_connect)
    response = client.post("/api/system/global-scan", headers=headers, json={})

    assert response.status_code == 202, response.text
    created_job = response.json()
    assert created_job["created"] is True
    assert created_job["status"] == "pending"

    status_response = client.get(f"/api/system/global-scan/{created_job['id']}", headers=headers)
    assert status_response.status_code == 200, status_response.text
    job = status_response.json()
    assert job["status"] == "completed"
    assert job["progress_percent"] == 100
    assert job["processed_projects"] == 1
    assert job["processed_shared_groups"] == 1
    payload = job["result"]
    assert payload["scanned_projects"] == 1
    assert payload["scanned_shared_groups"] == 1
    assert payload["project"]["new_files"] == 1
    assert payload["project"]["removed_files"] == 1
    assert payload["shared"]["new_files"] == 1
    assert payload["shared"]["removed_files"] == 1
    assert payload["failed_scopes"] == 0

    latest_response = client.get("/api/system/global-scan", headers=headers)
    assert latest_response.status_code == 200, latest_response.text
    assert latest_response.json()["job"]["id"] == created_job["id"]
    assert connection_count >= 9


def test_global_scan_reuses_active_job(client):
    from customer_m.modules.system_maintenance import create_global_file_scan_job

    first = create_global_file_scan_job({"email": "admin@jinxiangsz.com"})
    second = create_global_file_scan_job({"email": "other-admin@jinxiangsz.com"})

    assert first["created"] is True
    assert first["status"] == "pending"
    assert second["created"] is False
    assert second["id"] == first["id"]


def test_interrupted_global_scan_is_marked_failed(client):
    from customer_m import database
    from customer_m.modules.system_maintenance import create_global_file_scan_job, get_global_file_scan_job

    created = create_global_file_scan_job({"email": "admin@jinxiangsz.com"})
    with database.db_connect() as conn:
        database.fail_interrupted_file_scan_jobs(conn)
        conn.commit()

    job = get_global_file_scan_job(created["id"])
    assert job["status"] == "failed"
    assert "服务重启" in job["error"]
    assert job["completed_at"] is not None


def test_global_scan_requires_admin(client):
    admin_headers = auth_headers(client)
    email = "global-scan-pm@jinxiangsz.com"
    code = client.post("/api/auth/request-code", json={"email": email}).json()["dev_code"]
    users_payload = client.get("/api/users", headers=admin_headers).json()
    user = next(user for user in users_payload["users"] if user["email"] == email)
    patch_response = client.patch(
        f"/api/users/{user['id']}",
        headers=admin_headers,
        json={"display_name": "Global Scan PM", "status": "enabled", "roles": ["pm"]},
    )
    assert patch_response.status_code == 200, patch_response.text
    login_response = client.post("/api/auth/login", json={"email": email, "code": code})
    assert login_response.status_code == 200, login_response.text
    pm_headers = {"Authorization": f"Bearer {login_response.json()['token']}"}

    response = client.post("/api/system/global-scan", headers=pm_headers, json={})

    assert response.status_code == 403
