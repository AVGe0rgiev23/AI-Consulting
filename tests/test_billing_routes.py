from app.db import queries
from app.security import hash_password
from tests.conftest import login_as, make_client


def test_billing_page_shows_plans_and_balance():
    client, ctx = make_client("bill1@example.com")
    resp = client.get("/billing")
    assert resp.status_code == 200
    for label in ["Starter", "Professional", "Agency", "Credits remaining",
                  "Credit history"]:
        assert label in resp.text
    assert "Test mode" in resp.text


def test_checkout_redirects_to_mock_in_stub_mode():
    client, ctx = make_client("bill2@example.com")
    resp = client.post("/billing/checkout/professional", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/billing/mock-checkout?plan=professional"
    page = client.get("/billing/mock-checkout?plan=professional")
    assert "Mock Stripe Checkout" in page.text


def test_mock_payment_applies_plan_and_credits():
    client, ctx = make_client("bill3@example.com")
    before = queries.get_workspace(ctx["ws_id"])["credits_balance"]
    resp = client.post("/billing/mock-checkout", data={"plan": "agency"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "upgraded=agency" in resp.headers["location"]
    ws = queries.get_workspace(ctx["ws_id"])
    assert ws["plan"] == "agency"
    assert ws["credits_balance"] == before + 4000
    page = client.get("/billing?upgraded=agency")
    assert "Current plan" in page.text and "Agency" in page.text


def test_unknown_plan_404():
    client, ctx = make_client("bill4@example.com")
    assert client.post("/billing/checkout/platinum",
                       follow_redirects=False).status_code == 404
    assert client.get("/billing/mock-checkout?plan=platinum").status_code == 404


def test_member_cannot_checkout():
    client, ctx = make_client("bill5@example.com")
    uid = queries.create_user("billmem@example.com", "M", hash_password("password123"))
    queries.add_membership(uid, ctx["ws_id"], "member")
    mc = login_as(uid)
    mc.cookies.set("lg_ws", str(ctx["ws_id"]))
    assert mc.post("/billing/checkout/starter",
                   follow_redirects=False).status_code == 403
    assert mc.post("/billing/mock-checkout", data={"plan": "starter"},
                   follow_redirects=False).status_code == 403
    assert mc.get("/billing").status_code == 200


def test_webhook_rejected_in_stub_mode():
    client, ctx = make_client("bill6@example.com")
    resp = client.post("/billing/webhook", content=b"{}")
    assert resp.status_code == 400


def test_upgrade_lifts_seat_limit():
    client, ctx = make_client("bill7@example.com")
    resp = client.post("/team/invite", data={"email": "extra@example.com",
                                             "role": "member"}, follow_redirects=False)
    assert resp.status_code == 402
    client.post("/billing/mock-checkout", data={"plan": "agency"},
                follow_redirects=False)
    resp = client.post("/team/invite", data={"email": "extra@example.com",
                                             "role": "member"}, follow_redirects=False)
    assert resp.status_code == 303
