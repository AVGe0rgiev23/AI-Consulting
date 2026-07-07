from tests.conftest import make_client, login_as
from app.db import queries


def _invite_link(client):
    token = queries.invites_for_workspace(_ws_of(client))[-1]["token"]
    return f"/join/{token}"


def _ws_of(client):
    from app import config, security
    uid = security.read_session(client.cookies.get(config.SESSION_COOKIE))
    return queries.workspaces_for_user(uid)[0]["id"]


def test_owner_invites_and_new_user_joins_with_role():
    client, ctx = make_client("owner@a.com", plan="agency")
    resp = client.post("/team/invite", data={"email": "rev@a.com", "role": "reviewer"},
                       follow_redirects=False)
    assert resp.status_code == 303
    link = _invite_link(client)

    from fastapi.testclient import TestClient
    from app.main import app
    joiner = TestClient(app)
    page = joiner.get(link)
    assert page.status_code == 200
    assert b"Join" in page.content
    resp = joiner.post(link, data={"name": "Rev", "password": "password123"},
                       follow_redirects=False)
    assert resp.status_code == 303

    new_user = queries.get_user_by_email("rev@a.com")
    assert queries.membership_role(new_user["id"], ctx["ws_id"]) == "reviewer"
    assert queries.invites_for_workspace(ctx["ws_id"]) == []


def test_seat_limit_blocks_invite_on_trial():
    client, ctx = make_client("solo@a.com")
    resp = client.post("/team/invite", data={"email": "x@a.com", "role": "member"},
                       follow_redirects=False)
    assert resp.status_code == 402


def test_reviewer_cannot_run_research_or_create_lists():
    client, ctx = make_client("own2@a.com", plan="agency")
    reviewer_id = queries.create_user("r2@a.com", "R2", "hash")
    queries.add_membership(reviewer_id, ctx["ws_id"], "reviewer")
    rc = login_as(reviewer_id)
    rc.cookies.set("lg_ws", str(ctx["ws_id"]))

    resp = rc.post("/lists", data={"name": "Nope"}, follow_redirects=False)
    assert resp.status_code == 403

    csv = b"Company,Domain\nAcme,acme.com\n"
    client.post("/lists", data={"name": "L"}, files={"file": ("l.csv", csv, "text/csv")},
                follow_redirects=False)
    lst = queries.lists_for_workspace(ctx["ws_id"])[0]
    resp = rc.post(f"/lists/{lst['id']}/research", data={}, follow_redirects=False)
    assert resp.status_code == 403


def test_member_cannot_invite_or_change_settings():
    client, ctx = make_client("own3@a.com", plan="agency")
    member_id = queries.create_user("m3@a.com", "M3", "hash")
    queries.add_membership(member_id, ctx["ws_id"], "member")
    mc = login_as(member_id)
    mc.cookies.set("lg_ws", str(ctx["ws_id"]))

    assert mc.post("/team/invite", data={"email": "y@a.com", "role": "member"},
                   follow_redirects=False).status_code == 403
    assert mc.post("/settings", data={"brand_name": "Hack"},
                   follow_redirects=False).status_code == 403


def test_admin_cannot_touch_owner():
    client, ctx = make_client("own4@a.com", plan="agency")
    admin_id = queries.create_user("ad@a.com", "Ad", "hash")
    queries.add_membership(admin_id, ctx["ws_id"], "admin")
    ac = login_as(admin_id)
    ac.cookies.set("lg_ws", str(ctx["ws_id"]))

    assert ac.post("/team/role", data={"user_id": ctx["user_id"], "role": "member"},
                   follow_redirects=False).status_code == 403
    assert ac.post("/team/remove", data={"user_id": ctx["user_id"]},
                   follow_redirects=False).status_code == 403
    assert queries.membership_role(ctx["user_id"], ctx["ws_id"]) == "owner"


def test_workspace_switch_requires_membership():
    client, ctx = make_client("own5@a.com")
    other_client, other_ctx = make_client("other@a.com")
    resp = client.post("/workspace/switch", data={"workspace_id": other_ctx["ws_id"]},
                       follow_redirects=False)
    assert resp.status_code == 403
    resp = client.post("/workspace/switch", data={"workspace_id": ctx["ws_id"]},
                       follow_redirects=False)
    assert resp.status_code == 303
