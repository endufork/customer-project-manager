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
