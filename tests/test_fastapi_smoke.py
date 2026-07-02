from __future__ import annotations


def test_health_endpoint(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_protected_routes_require_login(client):
    for method, url in [
        ("get", "/api/projects"),
        ("get", "/api/workbench/projects"),
        ("patch", "/api/settings"),
    ]:
        kwargs = {"json": {}} if method != "get" else {}
        response = getattr(client, method)(url, **kwargs)
        assert response.status_code == 401
        assert response.json()["detail"] == "请先登录"


def test_base_schema_contains_auth_tables(tmp_path):
    import sqlite3
    from pathlib import Path

    db_path = tmp_path / "schema-auth.db"
    schema_sql = Path("mvp-sqlite-schema-v0.2.sql").read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

    assert {"users", "user_roles", "login_codes", "auth_sessions"}.issubset(tables)


def test_login_code_dev_flow(client):
    email = "rongkai@jinxiangsz.com"
    code_response = client.post("/api/auth/request-code", json={"email": email})

    assert code_response.status_code == 200
    payload = code_response.json()
    assert payload["sent"] is False
    assert len(payload["dev_code"]) == 6

    login_response = client.post("/api/auth/login", json={"email": email, "code": payload["dev_code"]})
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["token"]
    assert login_payload["user"]["email"] == email

    auth_headers = {"Authorization": f"Bearer {login_payload['token']}"}
    me_response = client.get("/api/auth/me", headers=auth_headers)
    assert me_response.status_code == 200
    assert me_response.json()["user"]["is_admin"] is True
    assert me_response.json()["user"]["is_pm"] is True


def test_new_user_stays_pending_until_admin_assigns_role(client):
    email = "pending-user@jinxiangsz.com"
    code_response = client.post("/api/auth/request-code", json={"email": email})
    assert code_response.status_code == 200

    login_response = client.post("/api/auth/login", json={"email": email, "code": code_response.json()["dev_code"]})
    assert login_response.status_code == 400
    assert login_response.json()["detail"] == "账号待管理员分配角色，请联系管理员"


def test_wrong_login_code_attempts_are_persisted(client):
    from customer_m import database

    email = "rongkai@jinxiangsz.com"
    code_response = client.post("/api/auth/request-code", json={"email": email})
    assert code_response.status_code == 200
    wrong_code = "000000" if code_response.json()["dev_code"] != "000000" else "111111"

    for _ in range(5):
        response = client.post("/api/auth/login", json={"email": email, "code": wrong_code})
        assert response.status_code == 400
        assert response.json()["detail"] == "验证码不正确"

    with database.db_connect() as conn:
        row = conn.execute(
            """
            SELECT attempt_count
            FROM login_codes
            WHERE email = ? AND used_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (email,),
        ).fetchone()
    assert row["attempt_count"] == 5

    locked_response = client.post("/api/auth/login", json={"email": email, "code": wrong_code})
    assert locked_response.status_code == 400
    assert locked_response.json()["detail"] == "验证码错误次数过多，请重新获取"


def test_admin_role_does_not_implicitly_grant_pm_permissions(client):
    initial_email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": initial_email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": initial_email, "code": code_payload["dev_code"]},
    ).json()
    admin_headers = {"Authorization": f"Bearer {login_payload['token']}"}

    admin_only_email = "adminonly@jinxiangsz.com"
    admin_only_code = client.post("/api/auth/request-code", json={"email": admin_only_email}).json()["dev_code"]
    users_payload = client.get("/api/users", headers=admin_headers).json()
    admin_only_user = next(user for user in users_payload["users"] if user["email"] == admin_only_email)
    patch_response = client.patch(
        f"/api/users/{admin_only_user['id']}",
        headers=admin_headers,
        json={"display_name": "Admin Only", "status": "enabled", "roles": ["admin"]},
    )
    assert patch_response.status_code == 200, patch_response.text

    admin_only_login = client.post(
        "/api/auth/login",
        json={"email": admin_only_email, "code": admin_only_code},
    )
    assert admin_only_login.status_code == 200, admin_only_login.text
    admin_only_payload = admin_only_login.json()
    assert admin_only_payload["user"]["is_admin"] is True
    assert admin_only_payload["user"]["is_pm"] is False

    admin_only_headers = {"Authorization": f"Bearer {admin_only_payload['token']}"}
    users_response = client.get("/api/users", headers=admin_only_headers)
    assert users_response.status_code == 200, users_response.text

    pm_response = client.get("/api/workbench/pm-inbox", headers=admin_only_headers)
    assert pm_response.status_code == 403


def test_user_patch_without_roles_preserves_existing_roles(client):
    initial_email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": initial_email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": initial_email, "code": code_payload["dev_code"]},
    ).json()
    admin_headers = {"Authorization": f"Bearer {login_payload['token']}"}

    target_email = "engineer-preserve@jinxiangsz.com"
    client.post("/api/auth/request-code", json={"email": target_email})
    users_payload = client.get("/api/users", headers=admin_headers).json()
    target_user = next(user for user in users_payload["users"] if user["email"] == target_email)

    role_response = client.patch(
        f"/api/users/{target_user['id']}",
        headers=admin_headers,
        json={"display_name": "Engineer Preserve", "status": "enabled", "roles": ["engineer"]},
    )
    assert role_response.status_code == 200, role_response.text
    assert role_response.json()["roles"] == ["engineer"]

    name_response = client.patch(
        f"/api/users/{target_user['id']}",
        headers=admin_headers,
        json={"display_name": "Engineer Renamed"},
    )
    assert name_response.status_code == 200, name_response.text
    assert name_response.json()["display_name"] == "Engineer Renamed"
    assert name_response.json()["roles"] == ["engineer"]


def test_admin_can_delete_user_and_clear_sessions_and_task_binding(client):
    from customer_m import database

    initial_email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": initial_email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": initial_email, "code": code_payload["dev_code"]},
    ).json()
    admin_headers = {"Authorization": f"Bearer {login_payload['token']}"}

    target_email = "delete-me@jinxiangsz.com"
    target_code = client.post("/api/auth/request-code", json={"email": target_email}).json()["dev_code"]
    users_payload = client.get("/api/users", headers=admin_headers).json()
    target_user = next(user for user in users_payload["users"] if user["email"] == target_email)
    role_response = client.patch(
        f"/api/users/{target_user['id']}",
        headers=admin_headers,
        json={"display_name": "Delete Me", "status": "enabled", "roles": ["engineer"]},
    )
    assert role_response.status_code == 200, role_response.text

    target_login = client.post("/api/auth/login", json={"email": target_email, "code": target_code})
    assert target_login.status_code == 200, target_login.text
    target_headers = {"Authorization": f"Bearer {target_login.json()['token']}"}

    project_response = client.post(
        "/api/projects",
        headers=admin_headers,
        json={
            "customer_name": "Delete User Customer",
            "site_name": "Suzhou",
            "contact_name": "Alice",
            "equipment_name": "Delete User Machine",
            "project_name": "Delete User Line",
            "project_nature": "新设备",
            "status_code": "inquiry",
            "currency_code": "CNY",
            "inquiry_date": "2026-06-01",
        },
    )
    assert project_response.status_code == 201, project_response.text
    task_response = client.post(
        f"/api/workbench/projects/{project_response.json()['id']}/tasks",
        headers=admin_headers,
        json={"title": "Assigned before delete", "owner_user_id": target_user["id"]},
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    delete_response = client.delete(f"/api/users/{target_user['id']}", headers=admin_headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["deleted"] is True

    deleted_me_response = client.get("/api/auth/me", headers=target_headers)
    assert deleted_me_response.status_code == 401

    refreshed_users = client.get("/api/users", headers=admin_headers).json()["users"]
    assert all(user["email"] != target_email for user in refreshed_users)

    with database.db_connect() as conn:
        task = conn.execute(
            "SELECT owner_user_id, owner_email, owner_name FROM execution_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    assert task["owner_user_id"] is None
    assert task["owner_email"] is None
    assert task["owner_name"] == "Delete Me"


def test_user_delete_rejects_self_and_initial_admin(client):
    initial_email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": initial_email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": initial_email, "code": code_payload["dev_code"]},
    ).json()
    admin_headers = {"Authorization": f"Bearer {login_payload['token']}"}
    admin_user_id = login_payload["user"]["id"]

    delete_response = client.delete(f"/api/users/{admin_user_id}", headers=admin_headers)
    assert delete_response.status_code == 400
    assert delete_response.json()["detail"] == "不能删除当前登录用户"

    second_admin_email = "second-admin@jinxiangsz.com"
    second_code = client.post("/api/auth/request-code", json={"email": second_admin_email}).json()["dev_code"]
    users_payload = client.get("/api/users", headers=admin_headers).json()
    second_admin = next(user for user in users_payload["users"] if user["email"] == second_admin_email)
    patch_response = client.patch(
        f"/api/users/{second_admin['id']}",
        headers=admin_headers,
        json={"display_name": "Second Admin", "status": "enabled", "roles": ["admin"]},
    )
    assert patch_response.status_code == 200, patch_response.text
    second_login = client.post(
        "/api/auth/login",
        json={"email": second_admin_email, "code": second_code},
    )
    assert second_login.status_code == 200, second_login.text
    second_admin_headers = {"Authorization": f"Bearer {second_login.json()['token']}"}

    initial_delete_response = client.delete(f"/api/users/{admin_user_id}", headers=second_admin_headers)
    assert initial_delete_response.status_code == 400
    assert initial_delete_response.json()["detail"] == "不能删除初始管理员"


def test_project_detail_filters_files_by_user_role(client):
    from customer_m import database
    from customer_m.utils import make_id, now_iso

    initial_email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": initial_email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": initial_email, "code": code_payload["dev_code"]},
    ).json()
    admin_headers = {"Authorization": f"Bearer {login_payload['token']}"}

    engineer_email = "visibility-engineer@jinxiangsz.com"
    engineer_code = client.post("/api/auth/request-code", json={"email": engineer_email}).json()["dev_code"]
    users_payload = client.get("/api/users", headers=admin_headers).json()
    engineer = next(user for user in users_payload["users"] if user["email"] == engineer_email)
    patch_response = client.patch(
        f"/api/users/{engineer['id']}",
        headers=admin_headers,
        json={"display_name": "Visibility Engineer", "status": "enabled", "roles": ["engineer"]},
    )
    assert patch_response.status_code == 200, patch_response.text
    engineer_login = client.post(
        "/api/auth/login",
        json={"email": engineer_email, "code": engineer_code},
    )
    assert engineer_login.status_code == 200, engineer_login.text
    engineer_headers = {"Authorization": f"Bearer {engineer_login.json()['token']}"}

    project_response = client.post(
        "/api/projects",
        headers=admin_headers,
        json={
            "customer_name": "Visibility Customer",
            "site_name": "Suzhou",
            "contact_name": "Alice",
            "equipment_name": "Visibility Machine",
            "project_name": "Visibility Line",
            "project_nature": "新设备",
            "status_code": "inquiry",
            "currency_code": "CNY",
            "inquiry_date": "2026-06-01",
        },
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["id"]

    now = now_iso()
    file_rows = [
        ("internal.xlsx", "internal_quote", "engineering"),
        ("customer.xlsx", "customer_quote", "pm_only"),
        ("po.pdf", "po", "pm_only"),
    ]
    with database.db_connect() as conn:
        for file_name, category_code, visibility_code in file_rows:
            conn.execute(
                """
                INSERT INTO project_files (
                  id, project_id, original_name, current_name, extension, category_code,
                  visibility_code, file_path, original_source_path, size_bytes, modified_at,
                  is_3d_model, text_extracted, extracted_text, content_hash, import_method,
                  created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 10, ?, 0, 0, NULL, ?, 'new_project_copy', ?, ?)
                """,
                (
                    make_id(),
                    project_id,
                    file_name,
                    file_name,
                    "." + file_name.rsplit(".", 1)[1],
                    category_code,
                    visibility_code,
                    f"C:/tmp/{file_name}",
                    now,
                    make_id(),
                    now,
                    now,
                ),
            )
        conn.commit()

    engineer_detail = client.get(f"/api/projects/{project_id}", headers=engineer_headers)
    assert engineer_detail.status_code == 200, engineer_detail.text
    assert [item["current_name"] for item in engineer_detail.json()["files"]] == ["internal.xlsx"]

    pm_detail = client.get(f"/api/projects/{project_id}", headers=admin_headers)
    assert pm_detail.status_code == 200, pm_detail.text
    assert {item["current_name"] for item in pm_detail.json()["files"]} == {"internal.xlsx", "customer.xlsx", "po.pdf"}


def test_configured_smtp_failure_does_not_return_dev_code_or_persist_code(client, monkeypatch):
    from customer_m import database
    from customer_m.modules import auth

    class FailingSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, *args, **kwargs):
            raise OSError("smtp unavailable")

        def send_message(self, *args, **kwargs):
            raise AssertionError("send_message should not be reached")

    email = "smtp-failure@jinxiangsz.com"
    monkeypatch.setattr(auth, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(auth, "SMTP_FROM_EMAIL", "noreply@jinxiangsz.com")
    monkeypatch.setattr(auth, "SMTP_USERNAME", "noreply@jinxiangsz.com")
    monkeypatch.setattr(auth, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(auth, "SMTP_SECURITY", "ssl")
    monkeypatch.setattr(auth.smtplib, "SMTP_SSL", FailingSMTP)

    response = client.post("/api/auth/request-code", json={"email": email})
    assert response.status_code == 400
    assert response.json()["detail"] == "验证码邮件发送失败，请稍后再试或联系管理员"
    assert "dev_code" not in response.json()

    with database.db_connect() as conn:
        row = conn.execute("SELECT id FROM login_codes WHERE email = ?", (email,)).fetchone()
    assert row is None
