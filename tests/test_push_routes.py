from app.db import queries
from app.jobs import pipeline
from app.security import hash_password
from tests.conftest import login_as, make_client


def _ready_workspace(email):
    client, ctx = make_client(email)
    list_id = queries.create_list(ctx["ws_id"], "Push List", "csv")
    queries.insert_lead(list_id, {
        "company_name": "Acme Logistics", "domain": "acme-logistics.com",
        "contact_name": "Sam Lee", "contact_title": "COO",
        "email": "sam@acme-logistics.com", "linkedin_url": "", "raw": {},
        "dedupe_hash": "acme",
    })
    profile = queries.default_offer_profile(ctx["ws_id"])
    pipeline.process_list_now(ctx["ws_id"], list_id, profile["id"])
    for lead in queries.leads_for_list(list_id):
        for a in queries.assets_for_lead(lead["id"]):
            queries.set_asset_status(a["id"], "approved")
    return client, ctx, list_id


def _connect(ws_id, provider):
    ws = queries.get_workspace(ws_id)
    settings = queries.get_settings(ws)
    settings[f"{provider}_api_key"] = "route-test-key"
    queries.update_workspace_settings(ws_id, settings)


def test_push_without_key_redirects_with_error():
    client, ctx, list_id = _ready_workspace("push1@example.com")
    resp = client.post(f"/lists/{list_id}/push/instantly", follow_redirects=False)
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]


def test_push_with_key_succeeds_and_shows_history():
    client, ctx, list_id = _ready_workspace("push2@example.com")
    _connect(ctx["ws_id"], "instantly")
    resp = client.post(f"/lists/{list_id}/push/instantly", follow_redirects=False)
    assert resp.status_code == 303
    assert "pushed=" in resp.headers["location"]
    page = client.get("/exports")
    assert "Recent pushes" in page.text
    assert "LeadGenius — Push List" in page.text
    assert queries.pushes_for_workspace(ctx["ws_id"])[0]["provider"] == "instantly"


def test_exports_page_shows_connect_link_until_key_added():
    client, ctx, list_id = _ready_workspace("push3@example.com")
    page = client.get("/exports")
    assert "Connect Instantly" in page.text
    _connect(ctx["ws_id"], "instantly")
    page = client.get("/exports")
    assert "Push to Instantly" in page.text


def test_unknown_provider_404():
    client, ctx, list_id = _ready_workspace("push4@example.com")
    assert client.post(f"/lists/{list_id}/push/mailchimp",
                       follow_redirects=False).status_code == 404


def test_foreign_list_404():
    client, ctx, list_id = _ready_workspace("push5@example.com")
    other, _ = make_client("push5b@example.com")
    assert other.post(f"/lists/{list_id}/push/instantly",
                      follow_redirects=False).status_code == 404


def test_reviewer_cannot_push():
    client, ctx, list_id = _ready_workspace("push6@example.com")
    _connect(ctx["ws_id"], "instantly")
    uid = queries.create_user("pushrev@example.com", "R", hash_password("password123"))
    queries.add_membership(uid, ctx["ws_id"], "reviewer")
    rc = login_as(uid)
    rc.cookies.set("lg_ws", str(ctx["ws_id"]))
    assert rc.post(f"/lists/{list_id}/push/instantly",
                   follow_redirects=False).status_code == 403


def test_settings_saves_api_keys():
    client, ctx = make_client("push7@example.com")
    resp = client.post("/settings", data={
        "brand_name": "", "accent": "", "report_title": "", "contact": "",
        "instantly_api_key": "inst-abc", "smartlead_api_key": "",
    }, follow_redirects=False)
    assert resp.status_code == 303
    ws = queries.get_workspace(ctx["ws_id"])
    assert queries.get_settings(ws)["instantly_api_key"] == "inst-abc"
