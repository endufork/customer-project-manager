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
            "notes": "Customer fixture data is missing",
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


def test_non_file_task_requires_completion_review(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Customer alignment call",
            "work_package": "项目管理",
            "owner_name": "Bob",
            "requires_deliverable": 0,
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    direct_close = client.patch(
        f"/api/workbench/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Customer alignment call",
            "work_package": "项目管理",
            "owner_name": "Bob",
            "status": "completed",
            "requires_deliverable": 0,
        },
    )
    assert direct_close.status_code == 400

    submit_response = client.post(
        f"/api/workbench/tasks/{task_id}/completion",
        headers=headers,
        json={"completion_note": "Customer confirmed open questions by phone.", "submitted_by": "Bob"},
    )
    assert submit_response.status_code == 201, submit_response.text
    assert submit_response.json()["status"] == "submitted"

    inbox_response = client.get("/api/workbench/inbox?role=pm&view=submitted", headers=headers)
    assert inbox_response.status_code == 200, inbox_response.text
    assert any(item["id"] == task_id for item in inbox_response.json()["task_completions"])

    review_response = client.patch(
        f"/api/workbench/tasks/{task_id}/completion",
        headers=headers,
        json={"status": "confirmed", "confirmed_by": "PM"},
    )
    assert review_response.status_code == 200, review_response.text
    assert review_response.json()["status"] == "confirmed"

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    task = next(item for item in detail_response.json()["tasks"] if item["id"] == task_id)
    assert task["status"] == "confirmed"
    assert task["completed_at"]


def test_pm_can_submit_and_confirm_non_file_task_in_one_step(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "PM customer coordination",
            "work_package": "项目管理",
            "owner_name": "rongkai",
            "requires_deliverable": 0,
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    submit_response = client.post(
        f"/api/workbench/tasks/{task_id}/completion",
        headers=headers,
        json={
            "completion_note": "Customer scope and next step confirmed.",
            "submitted_by": "rongkai",
            "direct_confirm": True,
        },
    )
    assert submit_response.status_code == 201, submit_response.text
    assert submit_response.json()["status"] == "confirmed"
    assert submit_response.json()["direct_confirmed"] is True

    inbox_response = client.get("/api/workbench/inbox?role=pm&view=submitted", headers=headers)
    assert inbox_response.status_code == 200, inbox_response.text
    assert all(item["id"] != task_id for item in inbox_response.json()["task_completions"])

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    task = next(item for item in detail_response.json()["tasks"] if item["id"] == task_id)
    assert task["status"] == "confirmed"
    assert task["confirmed_at"]
    assert task["completed_at"]


def test_blocked_task_auto_creates_task_issue(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Debug blocked station",
            "work_package": "调试",
            "owner_name": "Bob",
            "status": "blocked",
            "notes": "Customer PLC access is unavailable.",
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    issues = detail_response.json()["issues"]

    linked_issue = next(item for item in issues if item["task_id"] == task_id)
    assert linked_issue["scope"] == "task"
    assert linked_issue["status"] == "open"
    assert linked_issue["severity"] == "high"


def test_blocked_task_can_link_existing_issue(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    issue_response = client.post(
        f"/api/workbench/projects/{project_id}/issues",
        headers=headers,
        json={
            "title": "Customer sample missing",
            "scope": "equipment",
            "severity": "high",
            "status": "open",
        },
    )
    assert issue_response.status_code == 201, issue_response.text
    issue_id = issue_response.json()["id"]

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Wait for customer sample",
            "work_package": "前期方案",
            "owner_name": "Bob",
            "status": "blocked",
            "notes": "Customer sample is required before fixture design.",
            "linked_issue_id": issue_id,
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    issues = detail_response.json()["issues"]
    assert len([item for item in issues if item["title"] == "Customer sample missing"]) == 1
    linked_issue = next(item for item in issues if item["id"] == issue_id)
    assert linked_issue["task_id"] == task_id
    assert linked_issue["scope"] == "task"
    assert "Customer sample is required" in linked_issue["resolution"]


def test_rejected_deliverable_must_be_resubmitted(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Submit concept file",
            "work_package": "前期方案",
            "owner_name": "Bob",
            "requires_deliverable": 1,
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    upload_response = client.post(
        f"/api/workbench/tasks/{task_id}/deliverables",
        headers=headers,
        data={"category_code": "solution", "submitted_by": "Bob"},
        files={"file": ("concept.txt", b"concept v1", "text/plain")},
    )
    assert upload_response.status_code == 201, upload_response.text
    deliverable_id = upload_response.json()["id"]

    reject_response = client.patch(
        f"/api/workbench/deliverables/{deliverable_id}",
        headers=headers,
        json={"status": "rejected", "reject_reason": "Missing layout", "confirmed_by": "PM"},
    )
    assert reject_response.status_code == 200, reject_response.text

    stale_confirm_response = client.patch(
        f"/api/workbench/deliverables/{deliverable_id}",
        headers=headers,
        json={"status": "confirmed", "confirmed_by": "PM"},
    )
    assert stale_confirm_response.status_code == 400

    resubmit_response = client.post(
        f"/api/workbench/tasks/{task_id}/deliverables",
        headers=headers,
        data={"category_code": "solution", "submitted_by": "Bob"},
        files={"file": ("concept-rework.txt", b"concept v2", "text/plain")},
    )
    assert resubmit_response.status_code == 201, resubmit_response.text

    confirm_response = client.patch(
        f"/api/workbench/deliverables/{resubmit_response.json()['id']}",
        headers=headers,
        json={"status": "confirmed", "confirmed_by": "PM"},
    )
    assert confirm_response.status_code == 200, confirm_response.text
