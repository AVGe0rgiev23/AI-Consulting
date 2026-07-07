import pytest

from app.db import queries
from app.jobs import pipeline
from app.security import hash_password
from app.services import feedback, sender
from tests.conftest import login_as, make_client


def _pushed_workspace(sample_list, provider="instantly"):
    pipeline.process_list_now(sample_list["ws_id"], sample_list["list_id"],
                              sample_list["profile_id"])
    for lead in queries.leads_for_list(sample_list["list_id"]):
        for a in queries.assets_for_lead(lead["id"]):
            queries.set_asset_status(a["id"], "approved")
    ws = queries.get_workspace(sample_list["ws_id"])
    settings = queries.get_settings(ws)
    settings[f"{provider}_api_key"] = "pull-test-key"
    queries.update_workspace_settings(ws["id"], settings)
    ws = queries.get_workspace(ws["id"])
    sender.push_list(ws, sample_list["list_id"], provider)
    return ws


def test_pull_requires_prior_push(sample_list):
    ws = queries.get_workspace(sample_list["ws_id"])
    settings = queries.get_settings(ws)
    settings["instantly_api_key"] = "k"
    queries.update_workspace_settings(ws["id"], settings)
    ws = queries.get_workspace(ws["id"])
    with pytest.raises(sender.SenderError, match="never pushed"):
        sender.pull_stats(ws, sample_list["list_id"], "instantly")


def test_pull_requires_api_key(sample_list):
    ws = queries.get_workspace(sample_list["ws_id"])
    with pytest.raises(sender.SenderError, match="API key"):
        sender.pull_stats(ws, sample_list["list_id"], "instantly")


def test_pull_feeds_leaderboard_and_funnel(sample_list):
    ws = _pushed_workspace(sample_list)
    assert feedback.leaderboard(ws["id"]) == []

    result = sender.pull_stats(ws, sample_list["list_id"], "instantly")
    assert result["pulled"] == 2
    assert result["matched"] == 2
    assert result["unmatched"] == 0

    board = feedback.leaderboard(ws["id"])
    assert board and board[0]["sent"] == 2
    assert sum(r["replied"] for r in board) == 1

    funnel = feedback.funnel(ws["id"])
    assert funnel["sent"] == 2 and funnel["replied"] == 1


def test_pull_is_idempotent(sample_list):
    ws = _pushed_workspace(sample_list)
    sender.pull_stats(ws, sample_list["list_id"], "instantly")
    sender.pull_stats(ws, sample_list["list_id"], "instantly")
    assert feedback.funnel(ws["id"])["sent"] == 2
    campaigns = queries.campaigns_for_workspace(ws["id"])
    assert len(campaigns) == 1


def test_pull_reuses_push_campaign(sample_list):
    ws = _pushed_workspace(sample_list)
    before = queries.campaigns_for_workspace(ws["id"])
    sender.pull_stats(ws, sample_list["list_id"], "instantly")
    after = queries.campaigns_for_workspace(ws["id"])
    assert len(before) == len(after) == 1
    assert after[0]["exported_to"] == "instantly"


def test_pull_route_redirects_to_analytics():
    client, ctx = make_client("pull1@example.com")
    list_id = queries.create_list(ctx["ws_id"], "Pull List", "csv")
    queries.insert_lead(list_id, {
        "company_name": "Acme Logistics", "domain": "acme-logistics.com",
        "contact_name": "Sam", "contact_title": "", "email": "sam@acme-logistics.com",
        "linkedin_url": "", "raw": {}, "dedupe_hash": "acme",
    })
    profile = queries.default_offer_profile(ctx["ws_id"])
    pipeline.process_list_now(ctx["ws_id"], list_id, profile["id"])
    for lead in queries.leads_for_list(list_id):
        for a in queries.assets_for_lead(lead["id"]):
            queries.set_asset_status(a["id"], "approved")
    ws = queries.get_workspace(ctx["ws_id"])
    settings = queries.get_settings(ws)
    settings["instantly_api_key"] = "route-key"
    queries.update_workspace_settings(ctx["ws_id"], settings)
    client.post(f"/lists/{list_id}/push/instantly", follow_redirects=False)

    resp = client.post(f"/lists/{list_id}/pull/instantly", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/analytics?pulled=")
    page = client.get(resp.headers["location"])
    assert "leaderboard updated" in page.text

    exports_page = client.get("/exports")
    assert "Pull stats" in exports_page.text


def test_pull_without_push_redirects_with_error():
    client, ctx = make_client("pull2@example.com")
    list_id = queries.create_list(ctx["ws_id"], "Never Pushed", "csv")
    ws = queries.get_workspace(ctx["ws_id"])
    settings = queries.get_settings(ws)
    settings["instantly_api_key"] = "route-key"
    queries.update_workspace_settings(ctx["ws_id"], settings)
    resp = client.post(f"/lists/{list_id}/pull/instantly", follow_redirects=False)
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]


def test_reviewer_cannot_pull():
    client, ctx = make_client("pull3@example.com")
    list_id = queries.create_list(ctx["ws_id"], "L", "csv")
    uid = queries.create_user("pullrev@example.com", "R", hash_password("password123"))
    queries.add_membership(uid, ctx["ws_id"], "reviewer")
    rc = login_as(uid)
    rc.cookies.set("lg_ws", str(ctx["ws_id"]))
    assert rc.post(f"/lists/{list_id}/pull/instantly",
                   follow_redirects=False).status_code == 403
