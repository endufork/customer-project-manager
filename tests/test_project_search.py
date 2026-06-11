from __future__ import annotations


def auth_headers(client) -> dict[str, str]:
    email = "rongkai@jinxiangsz.com"
    code_payload = client.post("/api/auth/request-code", json={"email": email}).json()
    login_payload = client.post(
        "/api/auth/login",
        json={"email": email, "code": code_payload["dev_code"]},
    ).json()
    return {"Authorization": f"Bearer {login_payload['token']}"}


def create_project(client, headers: dict[str, str], **overrides) -> str:
    payload = {
        "customer_name": "Acme China",
        "site_name": "Suzhou",
        "contact_name": "Alice",
        "equipment_name": "Vision Test Machine",
        "project_name": "Vision Line",
        "project_nature": "新设备",
        "status_code": "inquiry",
        "currency_code": "CNY",
        "inquiry_date": "2026-06-01",
    }
    payload.update(overrides)
    response = client.post("/api/projects", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_project_search_prefers_number_matches_over_broad_text(client):
    headers = auth_headers(client)
    sc_project_id = create_project(
        client,
        headers,
        equipment_no="SC1290",
        equipment_name="EOLT",
        status_code="po_received",
        po_date="2026-06-11",
    )
    text_project_id = create_project(
        client,
        headers,
        equipment_name="Screw Fastener Unit",
        project_name="Text Search Project",
    )

    search_response = client.get("/api/projects?search=SC", headers=headers)

    assert search_response.status_code == 200, search_response.text
    ids = {project["id"] for project in search_response.json()["projects"]}
    assert sc_project_id in ids
    assert text_project_id not in ids


def test_project_search_falls_back_to_text_when_no_number_matches(client):
    headers = auth_headers(client)
    text_project_id = create_project(
        client,
        headers,
        equipment_name="Screw Fastener Unit",
        project_name="Text Search Project",
    )

    search_response = client.get("/api/projects?search=Screw", headers=headers)

    assert search_response.status_code == 200, search_response.text
    ids = {project["id"] for project in search_response.json()["projects"]}
    assert text_project_id in ids
