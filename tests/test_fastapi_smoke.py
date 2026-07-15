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

    assert {"users", "user_roles", "login_codes", "auth_sessions", "file_scan_jobs"}.issubset(tables)


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


def test_production_without_smtp_never_returns_dev_code_or_creates_user(client, monkeypatch):
    from customer_m import config, database

    email = "production-no-smtp@jinxiangsz.com"
    monkeypatch.setattr(config, "APP_ENV", "production")

    response = client.post("/api/auth/request-code", json={"email": email})

    assert response.status_code == 400
    assert response.json()["detail"] == "生产环境 SMTP 未配置，登录验证码不可用，请联系管理员"
    assert "dev_code" not in response.json()
    with database.db_connect() as conn:
        assert conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone() is None
        assert conn.execute("SELECT id FROM login_codes WHERE email = ?", (email,)).fetchone() is None


def test_new_user_stays_pending_until_admin_assigns_role(client):
    email = "pending-user@jinxiangsz.com"
    code_response = client.post("/api/auth/request-code", json={"email": email})
    assert code_response.status_code == 200

    login_response = client.post("/api/auth/login", json={"email": email, "code": code_response.json()["dev_code"]})
    assert login_response.status_code == 400
    assert login_response.json()["detail"] == "账号待管理员分配角色，请联系管理员"


def test_pending_user_cannot_be_enabled_without_a_role(client):
    initial_email = "rongkai@jinxiangsz.com"
    initial_code = client.post("/api/auth/request-code", json={"email": initial_email}).json()["dev_code"]
    initial_login = client.post("/api/auth/login", json={"email": initial_email, "code": initial_code}).json()
    admin_headers = {"Authorization": f"Bearer {initial_login['token']}"}

    email = "pending-without-role@jinxiangsz.com"
    client.post("/api/auth/request-code", json={"email": email})
    users = client.get("/api/users", headers=admin_headers).json()["users"]
    user = next(item for item in users if item["email"] == email)

    response = client.patch(
        f"/api/users/{user['id']}",
        headers=admin_headers,
        json={"status": "enabled"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "启用用户至少需要一个角色"


def test_disabling_user_immediately_invalidates_existing_session(client):
    initial_email = "rongkai@jinxiangsz.com"
    initial_code = client.post("/api/auth/request-code", json={"email": initial_email}).json()["dev_code"]
    initial_login = client.post("/api/auth/login", json={"email": initial_email, "code": initial_code}).json()
    admin_headers = {"Authorization": f"Bearer {initial_login['token']}"}

    email = "disable-session@jinxiangsz.com"
    code = client.post("/api/auth/request-code", json={"email": email}).json()["dev_code"]
    users = client.get("/api/users", headers=admin_headers).json()["users"]
    user = next(item for item in users if item["email"] == email)
    enabled = client.patch(
        f"/api/users/{user['id']}",
        headers=admin_headers,
        json={"status": "enabled", "roles": ["engineer"]},
    )
    assert enabled.status_code == 200, enabled.text
    login = client.post("/api/auth/login", json={"email": email, "code": code})
    assert login.status_code == 200, login.text
    user_headers = {"Authorization": f"Bearer {login.json()['token']}"}
    assert client.get("/api/auth/me", headers=user_headers).status_code == 200

    disabled = client.patch(
        f"/api/users/{user['id']}",
        headers=admin_headers,
        json={"status": "disabled", "roles": ["engineer"]},
    )

    assert disabled.status_code == 200, disabled.text
    assert client.get("/api/auth/me", headers=user_headers).status_code == 401
    assert client.get("/api/projects", headers=user_headers).status_code == 401


def test_readonly_user_migration_revokes_existing_sessions(client):
    from customer_m import database
    from customer_m.modules import auth
    from customer_m.utils import make_id, now_iso

    now = now_iso()
    token = "legacy-readonly-token"
    user_id = make_id()
    with database.db_connect() as conn:
        conn.execute(
            """
            INSERT INTO users (id, email, display_name, status, created_at, updated_at)
            VALUES (?, 'legacy-readonly@jinxiangsz.com', 'Legacy Readonly', 'enabled', ?, ?)
            """,
            (user_id, now, now),
        )
        conn.execute(
            "INSERT INTO user_roles (user_id, role_code, created_at) VALUES (?, 'readonly', ?)",
            (user_id, now),
        )
        conn.execute(
            """
            INSERT INTO auth_sessions (id, user_id, token_hash, expires_at, created_at, last_seen_at)
            VALUES (?, ?, ?, '2099-01-01T00:00:00+00:00', ?, ?)
            """,
            (make_id(), user_id, auth._hash_value(token), now, now),
        )
        database.migrate_db(conn)
        conn.commit()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    with database.db_connect() as conn:
        user = conn.execute("SELECT status FROM users WHERE id = ?", (user_id,)).fetchone()
        session = conn.execute("SELECT revoked_at FROM auth_sessions WHERE user_id = ?", (user_id,)).fetchone()
    assert user["status"] == "pending"
    assert session["revoked_at"] is not None


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
    file_ids = {}
    with database.db_connect() as conn:
        for file_name, category_code, visibility_code in file_rows:
            file_id = make_id()
            file_ids[file_name] = file_id
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
                    file_id,
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

    task_response = client.post(
        f"/api/workbench/projects/{project_id}/tasks",
        headers=admin_headers,
        json={"title": "Visibility task", "owner_user_id": engineer["id"]},
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]
    with database.db_connect() as conn:
        for file_name, _, _ in file_rows:
            conn.execute(
                """
                INSERT INTO task_deliverables (
                  id, task_id, project_id, file_id, deliverable_type, version_note,
                  status, submitted_by, submitted_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'test', NULL, 'submitted', 'Tester', ?, ?, ?)
                """,
                (make_id(), task_id, project_id, file_ids[file_name], now, now, now),
            )
        conn.execute(
            """
            INSERT INTO execution_activity_logs (
              id, project_id, task_id, issue_id, activity_type, title, detail, created_at
            )
            VALUES (?, ?, ?, NULL, 'deliverable_submitted', '提交交付文件', 'customer.xlsx', ?)
            """,
            (make_id(), project_id, task_id, now),
        )
        conn.execute(
            """
            INSERT INTO project_events (id, project_id, event_type, title, detail, created_at)
            VALUES (?, ?, 'workbench_file_submitted', '提交交付文件', 'customer.xlsx', ?)
            """,
            (make_id(), project_id, now),
        )
        conn.commit()

    engineer_detail = client.get(f"/api/projects/{project_id}", headers=engineer_headers)
    assert engineer_detail.status_code == 200, engineer_detail.text
    assert [item["current_name"] for item in engineer_detail.json()["files"]] == ["internal.xlsx"]
    submitted_event = next(
        item for item in engineer_detail.json()["events"] if item["event_type"] == "workbench_file_submitted"
    )
    assert submitted_event["detail"] is None

    engineer_workbench = client.get(f"/api/workbench/projects/{project_id}", headers=engineer_headers)
    assert engineer_workbench.status_code == 200, engineer_workbench.text
    workbench_payload = engineer_workbench.json()
    assert [item["file_name"] for item in workbench_payload["deliverables"]] == ["internal.xlsx"]
    assert [item["file_name"] for item in workbench_payload["tasks"][0]["deliverables"]] == ["internal.xlsx"]
    submitted_log = next(
        item for item in workbench_payload["logs"] if item["activity_type"] == "deliverable_submitted"
    )
    assert submitted_log["detail"] is None

    forced_pm_inbox = client.get("/api/workbench/inbox?role=pm", headers=engineer_headers)
    assert forced_pm_inbox.status_code == 200, forced_pm_inbox.text
    assert forced_pm_inbox.json()["role"] == "engineer"
    assert forced_pm_inbox.json()["deliverables"] == []

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
