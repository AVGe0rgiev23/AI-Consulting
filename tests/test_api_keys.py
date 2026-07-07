import re

from fastapi.testclient import TestClient

from tests.conftest import make_client
from app import config
from app.db import core, queries
from app.main import app


def _issue_key(client, name="CI key"):
    resp = client.post("/settings/api-keys", data={"key_name": name})
    assert resp.status_code == 200
    assert "won't see this key again" in resp.text
    match = re.search(r"lg_[A-Za-z0-9_\-]+", resp.text)
    assert match
    return match.group()


def _setup_data(ctx):
    list_id = queries.create_list(ctx["ws_id"], "API List", "csv")
    lead_id = queries.insert_lead(list_id, {
        "company_name": "Acme", "domain": "acme.com", "contact_name": "Sam",
        "contact_title": "COO", "email": "sam@acme.com", "linkedin_url": "",
        "raw": {}, "dedupe_hash": "apikeys-acme",
    })
    report_id = queries.create_audit_report(ctx["ws_id"], lead_id, "Acme", "acme.com",
                                            "summary", [])
    queries.get_or_create_campaign(ctx["ws_id"], list_id, "API List", "csv")
    return list_id, lead_id, report_id


def _endpoint_paths(list_id, lead_id, report_id):
    return [
        "/api/v1/lists",
        f"/api/v1/lists/{list_id}",
        f"/api/v1/leads/{lead_id}",
        f"/api/v1/lists/{list_id}/export",
        "/api/v1/leaderboard",
        f"/api/v1/audits/{report_id}",
        "/api/v1/campaigns",
        "/api/v1/prompts",
        "/api/v1/usage",
    ]


def test_bearer_key_authenticates_every_endpoint():
    session_client, ctx = make_client()
    raw = _issue_key(session_client)
    paths = _endpoint_paths(*_setup_data(ctx))
    api = TestClient(app)
    for path in paths:
        resp = api.get(path, headers={"Authorization": f"Bearer {raw}"})
        assert resp.status_code == 200, path


def test_session_cookie_auth_unchanged_on_every_endpoint():
    client, ctx = make_client()
    paths = _endpoint_paths(*_setup_data(ctx))
    for path in paths:
        assert client.get(path).status_code == 200, path


def test_missing_or_malformed_key_rejected():
    api = TestClient(app)
    assert api.get("/api/v1/lists").status_code == 401
    assert api.get("/api/v1/lists",
                   headers={"Authorization": "Bearer "}).status_code == 401
    assert api.get("/api/v1/lists",
                   headers={"Authorization": "Bearer lg_forged_key"}).status_code == 401
    assert api.get("/api/v1/lists",
                   headers={"Authorization": "Basic abc123"}).status_code == 401


def test_revoked_key_fails_on_next_use():
    client, ctx = make_client()
    raw = _issue_key(client)
    api = TestClient(app)
    headers = {"Authorization": f"Bearer {raw}"}
    assert api.get("/api/v1/lists", headers=headers).status_code == 200
    key = queries.api_keys_for_workspace(ctx["ws_id"])[0]
    client.post(f"/settings/api-keys/{key['id']}/revoke", follow_redirects=False)
    assert api.get("/api/v1/lists", headers=headers).status_code == 401
    assert queries.api_keys_for_workspace(ctx["ws_id"])[0]["revoked_at"]


def test_last_used_at_updates_on_use():
    client, ctx = make_client()
    raw = _issue_key(client)
    assert queries.api_keys_for_workspace(ctx["ws_id"])[0]["last_used_at"] is None
    TestClient(app).get("/api/v1/usage", headers={"Authorization": f"Bearer {raw}"})
    assert queries.api_keys_for_workspace(ctx["ws_id"])[0]["last_used_at"]


def test_api_key_traffic_rate_limited_per_workspace(monkeypatch):
    monkeypatch.setattr(config, "API_REQUESTS_PER_WINDOW", 3)
    client, ctx = make_client()
    raw = _issue_key(client)
    api = TestClient(app)
    headers = {"Authorization": f"Bearer {raw}"}
    for _ in range(3):
        assert api.get("/api/v1/lists", headers=headers).status_code == 200
    assert api.get("/api/v1/lists", headers=headers).status_code == 429


def test_key_is_scoped_to_its_workspace():
    a_client, _ = make_client("a@example.com")
    _, b_ctx = make_client("b@example.com")
    raw = _issue_key(a_client)
    b_list, b_lead, b_report = _setup_data(b_ctx)
    api = TestClient(app)
    headers = {"Authorization": f"Bearer {raw}"}
    assert api.get(f"/api/v1/lists/{b_list}", headers=headers).status_code == 404
    assert api.get(f"/api/v1/leads/{b_lead}", headers=headers).status_code == 404
    assert api.get(f"/api/v1/audits/{b_report}", headers=headers).status_code == 404


def test_only_hash_is_stored_and_key_shown_once():
    client, ctx = make_client()
    raw = _issue_key(client)
    row = core.query_one("SELECT hashed_key FROM api_keys WHERE workspace_id=?",
                         (ctx["ws_id"],))
    assert raw not in row["hashed_key"]
    assert len(row["hashed_key"]) == 64
    followup = client.get("/settings")
    assert raw not in followup.text


def test_key_management_requires_admin(sample_list):
    from tests.conftest import login_as

    member_id = queries.create_user("member@example.com", "M", "x")
    core.execute("INSERT INTO memberships(user_id, workspace_id, role) VALUES(?,?,'reviewer')",
                 (member_id, sample_list["ws_id"]))
    client = login_as(member_id)
    resp = client.post("/settings/api-keys", data={"key_name": "nope"})
    assert resp.status_code == 403
