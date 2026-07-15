from __future__ import annotations


def auth_headers(client) -> dict[str, str]:
    email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": email, "code": code_payload["dev_code"]},
    ).json()
    return {"Authorization": f"Bearer {login_payload['token']}"}


def login_headers(client, email: str) -> dict[str, str]:
    code_payload = client.post("/api/auth/request-code", json={"email": email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": email, "code": code_payload["dev_code"]},
    ).json()
    return {"Authorization": f"Bearer {login_payload['token']}"}


def user_by_email(client, headers: dict[str, str], email: str) -> dict:
    payload = client.get("/api/users", headers=headers).json()
    return next(user for user in payload["users"] if user["email"] == email)


def prepare_user(client, admin_headers: dict[str, str], email: str, display_name: str, roles: list[str]) -> dict:
    code_payload = client.post("/api/auth/request-code", json={"email": email}).json()
    user = user_by_email(client, admin_headers, email)
    response = client.patch(
        f"/api/users/{user['id']}",
        headers=admin_headers,
        json={"display_name": display_name, "status": "enabled", "roles": roles},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    payload["_dev_code"] = code_payload["dev_code"]
    return payload


def login_user_headers(client, user: dict) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": user["email"], "code": user["_dev_code"]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


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


def test_workbench_inbox_uses_logged_in_user_binding_and_legacy_owner_fallback(client):
    admin_headers = auth_headers(client)
    engineer = prepare_user(
        client,
        admin_headers,
        "engineer-bound@jinxiangsz.com",
        "Engineer Bound",
        ["engineer"],
    )
    other = prepare_user(
        client,
        admin_headers,
        "engineer-other@jinxiangsz.com",
        "Engineer Other",
        ["engineer"],
    )
    engineer_login = client.post(
        "/api/auth/login",
        json={"email": "engineer-bound@jinxiangsz.com", "code": engineer["_dev_code"]},
    )
    assert engineer_login.status_code == 200, engineer_login.text
    engineer_headers = {"Authorization": f"Bearer {engineer_login.json()['token']}"}
    project_id = create_project(client, admin_headers)

    bound_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=admin_headers,
        json={
            "title": "Bound account task",
            "work_package": "机械设计",
            "owner_user_id": engineer["id"],
            "owner_name": "Manual name should not win",
            "requires_deliverable": 0,
        },
    )
    assert bound_response.status_code == 201, bound_response.text

    legacy_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=admin_headers,
        json={
            "title": "Legacy owner task",
            "work_package": "前期方案",
            "owner_name": "Engineer Bound",
            "requires_deliverable": 0,
        },
    )
    assert legacy_response.status_code == 201, legacy_response.text

    other_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=admin_headers,
        json={
            "title": "Other engineer task",
            "work_package": "调试",
            "owner_user_id": other["id"],
            "requires_deliverable": 0,
        },
    )
    assert other_response.status_code == 201, other_response.text

    inbox_response = client.get("/api/workbench/inbox?role=engineer", headers=engineer_headers)
    assert inbox_response.status_code == 200, inbox_response.text
    titles = {task["title"] for task in inbox_response.json()["tasks"]}
    assert "Bound account task" in titles
    assert "Legacy owner task" in titles
    assert "Other engineer task" not in titles

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=admin_headers)
    bound_task = next(task for task in detail_response.json()["tasks"] if task["title"] == "Bound account task")
    assert bound_task["owner_user_id"] == engineer["id"]
    assert bound_task["owner_email"] == "engineer-bound@jinxiangsz.com"
    assert bound_task["owner_name"] == "Engineer Bound"


def test_engineer_mutations_are_limited_to_owned_bound_objects(client):
    pm_headers = auth_headers(client)
    engineer = prepare_user(
        client,
        pm_headers,
        "engineer-owner@jinxiangsz.com",
        "Engineer Owner",
        ["engineer"],
    )
    other = prepare_user(
        client,
        pm_headers,
        "engineer-cross-account@jinxiangsz.com",
        "Engineer Cross Account",
        ["engineer"],
    )
    engineer_headers = login_user_headers(client, engineer)
    other_headers = login_user_headers(client, other)
    project_id = create_project(client, pm_headers)

    owned_task = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=pm_headers,
        json={"title": "Owned task", "owner_user_id": engineer["id"], "requires_deliverable": 0},
    ).json()["id"]
    legacy_task = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=pm_headers,
        json={"title": "Legacy task", "owner_name": "Unbound legacy owner", "requires_deliverable": 0},
    ).json()["id"]

    own_status = client.patch(
        f"/api/workbench/tasks/{owned_task}",
        headers=engineer_headers,
        json={"status": "in_progress", "notes": "Started"},
    )
    assert own_status.status_code == 200, own_status.text

    forbidden_fields = client.patch(
        f"/api/workbench/tasks/{owned_task}",
        headers=engineer_headers,
        json={"title": "Engineer renamed task"},
    )
    assert forbidden_fields.status_code == 403

    cross_account = client.patch(
        f"/api/workbench/tasks/{owned_task}",
        headers=other_headers,
        json={"status": "blocked", "blocked_reason": "Should not be accepted"},
    )
    assert cross_account.status_code == 403

    legacy_write = client.patch(
        f"/api/workbench/tasks/{legacy_task}",
        headers=engineer_headers,
        json={"status": "in_progress"},
    )
    assert legacy_write.status_code == 403
    assert "仅 PM" in legacy_write.json()["detail"]

    cross_completion = client.post(
        f"/api/workbench/tasks/{owned_task}/completion",
        headers=other_headers,
        json={"completion_note": "Cross-account completion"},
    )
    assert cross_completion.status_code == 403

    cross_upload = client.post(
        f"/api/workbench/tasks/{owned_task}/deliverables",
        headers=other_headers,
        data={"category_code": "other", "version_note": "Cross-account upload"},
        files={"file": ("cross-account.txt", b"not allowed", "text/plain")},
    )
    assert cross_upload.status_code == 403

    own_due_request = client.post(
        f"/api/workbench/tasks/{owned_task}/due-date-requests",
        headers=engineer_headers,
        json={"proposed_due_date": "2026-07-20", "reason": "Supplier delay"},
    )
    assert own_due_request.status_code == 201, own_due_request.text

    issue_response = client.post(
        f"/api/workbench/projects/{project_id}/issues",
        headers=engineer_headers,
        json={"task_id": owned_task, "scope": "task", "title": "Owned task risk", "status": "open"},
    )
    assert issue_response.status_code == 201, issue_response.text
    issue_id = issue_response.json()["id"]

    cross_issue = client.patch(
        f"/api/workbench/issues/{issue_id}",
        headers=other_headers,
        json={"status": "following"},
    )
    assert cross_issue.status_code == 403

    issue_metadata = client.patch(
        f"/api/workbench/issues/{issue_id}",
        headers=engineer_headers,
        json={"title": "Engineer renamed risk"},
    )
    assert issue_metadata.status_code == 403

    own_issue_action = client.patch(
        f"/api/workbench/issues/{issue_id}",
        headers=engineer_headers,
        json={"status": "resolved", "resolution": "Mitigation completed"},
    )
    assert own_issue_action.status_code == 200, own_issue_action.text


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


def test_workbench_board_aggregates_project_attention_state(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Prepare fixture concept",
            "work_package": "前期方案",
            "owner_name": "Bob",
            "status": "blocked",
            "due_date": "2026-06-03",
            "requires_deliverable": 0,
            "blocked_reason": "Customer 3D data is missing.",
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    submit_response = client.post(
        f"/api/workbench/tasks/{task_id}/completion",
        headers=headers,
        json={"completion_note": "Concept direction checked by phone.", "submitted_by": "Bob"},
    )
    assert submit_response.status_code == 201, submit_response.text

    board_response = client.get("/api/workbench/board", headers=headers)
    assert board_response.status_code == 200, board_response.text

    payload = board_response.json()
    project = next(item for item in payload["projects"] if item["id"] == project_id)
    assert payload["kpis"]["active_projects"] >= 1
    assert payload["kpis"]["overdue_tasks"] >= 1
    assert payload["kpis"]["pending_confirmations"] >= 1
    assert project["board_group"] == "attention"
    assert project["board_status"] == "overdue"
    assert "超期" in project["board_flags"]
    assert "高风险" in project["board_flags"]
    assert project["pending_completions"] >= 1
    assert project["current_owner"] == "Bob"
    assert project["next_action"] == "Prepare fixture concept"


def test_workbench_risk_overview_lists_cross_project_risks(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Wait for customer sample",
            "work_package": "前期方案",
            "owner_name": "Bob",
            "status": "blocked",
            "blocked_reason": "Customer sample is missing.",
        },
    )
    assert task_response.status_code == 201, task_response.text

    risk_response = client.get("/api/workbench/risks?view=high", headers=headers)
    assert risk_response.status_code == 200, risk_response.text

    payload = risk_response.json()
    risk = next(item for item in payload["risks"] if item["project_id"] == project_id)
    assert payload["kpis"]["active"] >= 1
    assert payload["kpis"]["high"] >= 1
    assert risk["title"] == "任务阻塞：Wait for customer sample"
    assert risk["scope"] == "task"
    assert risk["scope_label"] == "任务"
    assert risk["severity"] == "high"
    assert risk["status"] == "open"
    assert risk["current_number"].startswith("INQ-")
    assert risk["task_title"] == "Wait for customer sample"


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

    direct_submit = client.patch(
        f"/api/workbench/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Customer alignment call",
            "work_package": "项目管理",
            "owner_name": "Bob",
            "status": "submitted",
            "requires_deliverable": 0,
        },
    )
    assert direct_submit.status_code == 400

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
    assert review_response.json()["project_id"] == project_id

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
    assert submit_response.json()["project_id"] == project_id

    inbox_response = client.get("/api/workbench/inbox?role=pm&view=submitted", headers=headers)
    assert inbox_response.status_code == 200, inbox_response.text
    assert all(item["id"] != task_id for item in inbox_response.json()["task_completions"])

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    task = next(item for item in detail_response.json()["tasks"] if item["id"] == task_id)
    assert task["status"] == "confirmed"
    assert task["confirmed_at"]
    assert task["completed_at"]


def test_task_update_without_due_date_preserves_existing_due_date(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Fixture design",
            "work_package": "机械设计",
            "owner_name": "Bob",
            "due_date": "2026-06-12",
            "requires_deliverable": 1,
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    update_response = client.patch(
        f"/api/workbench/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Fixture design updated",
            "work_package": "机械设计",
            "owner_name": "Bob",
            "status": "in_progress",
            "requires_deliverable": 1,
        },
    )
    assert update_response.status_code == 200, update_response.text

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    task = next(item for item in detail_response.json()["tasks"] if item["id"] == task_id)
    assert task["title"] == "Fixture design updated"
    assert task["status"] == "in_progress"
    assert task["due_date"] == "2026-06-12"


def test_template_due_dates_use_workdays_and_pm_can_override(client, monkeypatch):
    from datetime import date

    from customer_m.modules import workbench_tasks

    class Friday(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 17)

    monkeypatch.setattr(workbench_tasks, "date", Friday)
    headers = auth_headers(client)
    project_id = create_project(client, headers)
    template_response = client.post(
        f"/api/workbench/projects/{project_id}/templates",
        headers=headers,
        json={"template": "inq"},
    )
    assert template_response.status_code == 200, template_response.text

    detail = client.get(f"/api/workbench/projects/{project_id}", headers=headers).json()
    tasks = {task["title"]: task for task in detail["tasks"]}
    assert tasks["澄清客户需求"]["due_date"] == "2026-07-21"
    assert tasks["输出大致方案"]["due_date"] == "2026-07-22"
    assert all(date.fromisoformat(task["due_date"]).weekday() < 5 for task in tasks.values())

    manual_task = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={"title": "PM override task", "due_date": "2026-07-18"},
    )
    assert manual_task.status_code == 201, manual_task.text
    task_id = manual_task.json()["id"]
    override = client.post(
        f"/api/workbench/tasks/{task_id}/due-date-requests",
        headers=headers,
        json={
            "proposed_due_date": "2026-07-19",
            "reason": "PM confirmed weekend commissioning",
            "direct": True,
        },
    )
    assert override.status_code == 201, override.text
    assert override.json()["status"] == "approved"
    assert override.json()["final_due_date"] == "2026-07-19"


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


def test_updating_task_to_blocked_auto_creates_task_issue(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Fixture debug",
            "work_package": "调试",
            "owner_name": "Bob",
            "status": "in_progress",
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    update_response = client.patch(
        f"/api/workbench/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Fixture debug",
            "work_package": "调试",
            "owner_name": "Bob",
            "status": "blocked",
            "blocked_reason": "Customer PLC access is unavailable.",
        },
    )
    assert update_response.status_code == 200, update_response.text

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    issues = detail_response.json()["issues"]
    linked_issue = next(item for item in issues if item["task_id"] == task_id)
    assert linked_issue["scope"] == "task"
    assert linked_issue["status"] == "open"
    assert "Customer PLC access" in linked_issue["resolution"]


def test_task_risk_resolution_enters_pm_inbox_and_unblocks_task(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Wait for 3D data",
            "work_package": "前期方案",
            "owner_name": "Bob",
            "status": "blocked",
            "blocked_reason": "Customer 3D data is missing.",
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    issue = next(item for item in detail_response.json()["issues"] if item["task_id"] == task_id)

    resolve_response = client.patch(
        f"/api/workbench/issues/{issue['id']}",
        headers=headers,
        json={"status": "resolved", "resolution": "Customer supplied 3D data and Bob checked it."},
    )
    assert resolve_response.status_code == 200, resolve_response.text
    assert resolve_response.json()["status"] == "resolved"

    inbox_response = client.get("/api/workbench/inbox?role=pm&view=submitted", headers=headers)
    assert inbox_response.status_code == 200, inbox_response.text
    assert any(item["id"] == issue["id"] for item in inbox_response.json()["risk_reviews"])

    close_response = client.patch(
        f"/api/workbench/issues/{issue['id']}",
        headers=headers,
        json={"status": "closed", "review_note": "Confirmed by PM.", "task_next_status": "in_progress"},
    )
    assert close_response.status_code == 200, close_response.text
    assert close_response.json()["status"] == "closed"

    final_detail = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    task = next(item for item in final_detail.json()["tasks"] if item["id"] == task_id)
    closed_issue = next(item for item in final_detail.json()["issues"] if item["id"] == issue["id"])
    assert task["status"] == "in_progress"
    assert closed_issue["status"] == "closed"
    assert closed_issue["closed_at"]


def test_pm_action_center_aggregates_pending_approvals(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    completion_task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Customer requirement summary",
            "work_package": "前期方案",
            "owner_name": "Bob",
            "requires_deliverable": 0,
        },
    )
    assert completion_task_response.status_code == 201, completion_task_response.text
    completion_task_id = completion_task_response.json()["id"]

    completion_submit = client.post(
        f"/api/workbench/tasks/{completion_task_id}/completion",
        headers=headers,
        json={"completion_note": "Customer confirmed the concept scope.", "submitted_by": "Bob"},
    )
    assert completion_submit.status_code == 201, completion_submit.text

    due_task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Mechanical layout",
            "work_package": "机械设计",
            "owner_name": "Bob",
            "due_date": "2026-06-12",
        },
    )
    assert due_task_response.status_code == 201, due_task_response.text
    due_task_id = due_task_response.json()["id"]

    due_request = client.post(
        f"/api/workbench/tasks/{due_task_id}/due-date-requests",
        headers=headers,
        json={
            "proposed_due_date": "2026-06-18",
            "reason": "Customer data arrived late.",
            "impact_note": "May affect debug start.",
        },
    )
    assert due_request.status_code == 201, due_request.text

    blocked_task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Wait for sample",
            "work_package": "前期方案",
            "owner_name": "Bob",
            "status": "blocked",
            "blocked_reason": "Customer sample is missing.",
        },
    )
    assert blocked_task_response.status_code == 201, blocked_task_response.text
    blocked_task_id = blocked_task_response.json()["id"]

    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    issue = next(item for item in detail_response.json()["issues"] if item["task_id"] == blocked_task_id)
    resolve_response = client.patch(
        f"/api/workbench/issues/{issue['id']}",
        headers=headers,
        json={"status": "resolved", "resolution": "Sample received and checked."},
    )
    assert resolve_response.status_code == 200, resolve_response.text

    inbox_response = client.get("/api/workbench/pm-inbox", headers=headers)
    assert inbox_response.status_code == 200, inbox_response.text
    payload = inbox_response.json()
    types = {item["type"] for item in payload["items"]}
    assert {"completion", "due_date", "risk_review"}.issubset(types)
    assert payload["kpis"]["completions"] >= 1
    assert payload["kpis"]["due_date_requests"] >= 1
    assert payload["kpis"]["risk_reviews"] >= 1
    assert any(item["id"] == completion_task_id and item["type"] == "completion" for item in payload["items"])
    assert any(item["id"] == due_request.json()["id"] and item["type"] == "due_date" for item in payload["items"])
    assert any(item["id"] == issue["id"] and item["type"] == "risk_review" for item in payload["items"])

    review_response = client.patch(
        f"/api/workbench/tasks/{completion_task_id}/completion",
        headers=headers,
        json={"status": "confirmed", "confirmed_by": "PM"},
    )
    assert review_response.status_code == 200, review_response.text

    refreshed_response = client.get("/api/workbench/pm-inbox", headers=headers)
    refreshed_items = refreshed_response.json()["items"]
    assert all(not (item["id"] == completion_task_id and item["type"] == "completion") for item in refreshed_items)


def test_rejected_due_date_request_can_be_resubmitted(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Mechanical layout",
            "work_package": "机械设计",
            "owner_name": "Bob",
            "due_date": "2026-06-12",
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    first_request = client.post(
        f"/api/workbench/tasks/{task_id}/due-date-requests",
        headers=headers,
        json={
            "proposed_due_date": "2026-06-18",
            "reason": "Customer data arrived late.",
        },
    )
    assert first_request.status_code == 201, first_request.text

    reject_response = client.patch(
        f"/api/workbench/due-date-requests/{first_request.json()['id']}",
        headers=headers,
        json={"status": "rejected", "review_note": "Need supplier confirmation."},
    )
    assert reject_response.status_code == 200, reject_response.text
    assert reject_response.json()["status"] == "rejected"

    second_request = client.post(
        f"/api/workbench/tasks/{task_id}/due-date-requests",
        headers=headers,
        json={
            "proposed_due_date": "2026-06-20",
            "reason": "Supplier confirmed the new material arrival date.",
        },
    )
    assert second_request.status_code == 201, second_request.text
    assert second_request.json()["status"] == "pending"


def test_pm_reopens_resolved_risk_and_keeps_task_blocked(client):
    headers = auth_headers(client)
    project_id = create_project(client, headers)

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Wait for customer sample",
            "work_package": "前期方案",
            "owner_name": "Bob",
            "status": "blocked",
            "blocked_reason": "Customer sample is missing.",
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]
    detail_response = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    issue = next(item for item in detail_response.json()["issues"] if item["task_id"] == task_id)

    resolve_response = client.patch(
        f"/api/workbench/issues/{issue['id']}",
        headers=headers,
        json={"status": "resolved", "resolution": "Supplier says sample will arrive tomorrow."},
    )
    assert resolve_response.status_code == 200, resolve_response.text

    reopen_response = client.patch(
        f"/api/workbench/issues/{issue['id']}",
        headers=headers,
        json={"status": "following", "review_note": "Sample not received yet."},
    )
    assert reopen_response.status_code == 200, reopen_response.text
    assert reopen_response.json()["status"] == "following"

    final_detail = client.get(f"/api/workbench/projects/{project_id}", headers=headers)
    task = next(item for item in final_detail.json()["tasks"] if item["id"] == task_id)
    reopened_issue = next(item for item in final_detail.json()["issues"] if item["id"] == issue["id"])
    assert task["status"] == "blocked"
    assert reopened_issue["status"] == "following"


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


def test_deliverable_upload_streams_with_size_type_and_parse_limits(client, monkeypatch):
    from customer_m import config, database

    headers = auth_headers(client)
    project_id = create_project(client, headers)
    monkeypatch.setattr(config, "UPLOAD_MAX_BYTES", 8)
    monkeypatch.setattr(config, "UPLOAD_CHUNK_BYTES", 4)
    monkeypatch.setattr(config, "PARSER_MAX_BYTES", 4)
    monkeypatch.setattr(config, "UPLOAD_ALLOWED_EXTENSIONS", {".txt", ".step"})

    def new_task(title: str) -> str:
        response = client.post(
            f"/api/workbench/projects/{project_id}/tasks",
            headers=headers,
            json={"title": title, "requires_deliverable": 1},
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    oversized = client.post(
        f"/api/workbench/tasks/{new_task('Oversized upload')}/deliverables",
        headers=headers,
        files={"file": ("oversized.txt", b"123456789", "text/plain")},
    )
    assert oversized.status_code == 413

    blocked_type = client.post(
        f"/api/workbench/tasks/{new_task('Blocked type')}/deliverables",
        headers=headers,
        files={"file": ("payload.exe", b"binary", "application/octet-stream")},
    )
    assert blocked_type.status_code == 415

    large_text = client.post(
        f"/api/workbench/tasks/{new_task('Archive text without parsing')}/deliverables",
        headers=headers,
        files={"file": ("large.txt", b"123456", "text/plain")},
    )
    assert large_text.status_code == 201, large_text.text

    model = client.post(
        f"/api/workbench/tasks/{new_task('Archive 3D model')}/deliverables",
        headers=headers,
        files={"file": ("fixture.step", b"123456", "application/octet-stream")},
    )
    assert model.status_code == 201, model.text

    with database.db_connect() as conn:
        files = {
            row["current_name"]: row
            for row in conn.execute(
                "SELECT current_name, is_3d_model, text_extracted, extracted_text FROM project_files WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        }
    assert "oversized.txt" not in files
    assert files["large.txt"]["text_extracted"] == 0
    assert not files["large.txt"]["extracted_text"]
    assert files["fixture.step"]["is_3d_model"] == 1
    assert files["fixture.step"]["text_extracted"] == 0
