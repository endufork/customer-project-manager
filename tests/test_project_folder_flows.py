from __future__ import annotations

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
    for folder_name in STANDARD_PROJECT_FOLDERS:
        candidate = before / folder_name
        if candidate != kept_folder:
            candidate.rmdir()

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
    for folder_name in STANDARD_PROJECT_FOLDERS:
        (folder / folder_name).rmdir()
    folder.rmdir()

    response = client.post(f"/api/projects/{project_id}/rename-folder", headers=headers, json={})

    assert response.status_code == 200, response.text
    payload = response.json()
    repaired = Path(payload["project_folder_path"])
    assert payload["renamed"] is False
    assert repaired == folder
    assert_standard_dirs(repaired)
