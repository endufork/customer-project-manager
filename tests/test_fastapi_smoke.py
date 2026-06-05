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
