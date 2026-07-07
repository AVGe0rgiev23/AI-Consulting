from app.db import queries
from app.llm import prompt_library, prompts
from app.security import hash_password
from tests.conftest import login_as, make_client


def test_prompts_page_lists_all_slots():
    client, ctx = make_client("pl1@example.com")
    resp = client.get("/prompts")
    assert resp.status_code == 200
    for label in ["Writing voice", "Business analysis", "Email 1", "LinkedIn DM",
                  "Audit report voice"]:
        assert label in resp.text


def test_admin_saves_override_and_page_shows_customized():
    client, ctx = make_client("pl2@example.com")
    resp = client.post("/prompts/voice", data={"content": "Custom workspace voice"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert prompt_library.resolve(ctx["ws_id"], "voice") == "Custom workspace voice"
    page = client.get("/prompts")
    assert "Customized" in page.text
    assert "Custom workspace voice" in page.text


def test_reset_restores_default():
    client, ctx = make_client("pl3@example.com")
    client.post("/prompts/email_step_1", data={"content": "Custom opener spec"},
                follow_redirects=False)
    resp = client.post("/prompts/email_step_1/reset", follow_redirects=False)
    assert resp.status_code == 303
    assert prompt_library.resolve(ctx["ws_id"], "email_step_1") == prompts.EMAIL_STEP_SPECS[1]


def test_unknown_slot_returns_404():
    client, ctx = make_client("pl4@example.com")
    assert client.post("/prompts/nope", data={"content": "x"},
                       follow_redirects=False).status_code == 404
    assert client.post("/prompts/nope/reset", follow_redirects=False).status_code == 404


def test_member_and_reviewer_cannot_edit_prompts():
    client, ctx = make_client("pl5@example.com")
    for email, role in [("plmember@example.com", "member"), ("plrev@example.com", "reviewer")]:
        uid = queries.create_user(email, role, hash_password("password123"))
        queries.add_membership(uid, ctx["ws_id"], role)
        rc = login_as(uid)
        rc.cookies.set("lg_ws", str(ctx["ws_id"]))
        assert rc.post("/prompts/voice", data={"content": "x"},
                       follow_redirects=False).status_code == 403
        assert rc.post("/prompts/voice/reset", follow_redirects=False).status_code == 403
        assert rc.get("/prompts").status_code == 200


def test_api_prompts_reports_customization():
    client, ctx = make_client("pl6@example.com")
    client.post("/prompts/voice", data={"content": "API custom voice"},
                follow_redirects=False)
    data = client.get("/api/v1/prompts").json()
    by_key = {p["key"]: p for p in data["prompts"]}
    assert by_key["voice"]["customized"] is True
    assert by_key["voice"]["content"] == "API custom voice"
    assert by_key["analysis"]["customized"] is False
    assert set(by_key) == prompt_library.slot_keys()
