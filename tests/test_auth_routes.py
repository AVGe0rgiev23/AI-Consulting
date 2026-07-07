from app.db import queries


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_signup_creates_user_workspace_and_credits():
    client = _client()
    resp = client.post(
        "/signup",
        data={"email": "new@example.com", "name": "New", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    user = queries.get_user_by_email("new@example.com")
    assert user
    ws = queries.workspaces_for_user(user["id"])[0]
    assert ws["credits_balance"] == 25


def test_login_rejects_bad_password():
    client = _client()
    client.post("/signup", data={"email": "a@b.com", "name": "A", "password": "password123"},
                follow_redirects=False)
    resp = client.post("/login", data={"email": "a@b.com", "password": "wrong"},
                       follow_redirects=False)
    assert resp.status_code == 401


def test_protected_page_redirects_when_logged_out():
    client = _client()
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
