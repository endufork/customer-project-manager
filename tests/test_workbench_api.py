from __future__ import annotations


def auth_headers(client) -> dict[str, str]:
    email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": email, "code": code_payload["dev_code"]},
    ).json()
    return {"Authorization": f"Bearer {login_payload['token']}"}


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


def test_workbench_project_list_uses_aggregated_summary(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Mechanical Concept Review",
            "work_package": "机械设计",
            "owner_name": "Bob",
            "status": "blocked",
            "due_date": "2026-06-03",
        },
    )
    assert task_response.status_code == 201, task_response.text

    issue_response = client.post(
        f"/api/workbench/projects/{project_id}/issues",
        headers=headers,
        json={
            "title": "Customer 3D data missing",
            "scope": "equipment",
            "severity": "high",
            "status": "open",
        },
    )
    assert issue_response.status_code == 201, issue_response.text

    list_response = client.get("/api/workbench/projects", headers=headers)
    assert list_response.status_code == 200, list_response.text

    project = next(item for item in list_response.json()["projects"] if item["id"] == project_id)
    assert project["current_number"].startswith("INQ-")
    assert project["workbench_area"] == "inq"
    assert project["blocked_tasks"] >= 1
    assert project["open_issues"] >= 1
    assert project["high_issues"] >= 1
    assert project["current_owner"] == "Bob"
