import pytest

from app.db import queries
from app.services import billing


def test_apply_plan_sets_plan_and_grants_credits(workspace):
    ws_id = workspace["ws_id"]
    before = queries.get_workspace(ws_id)["credits_balance"]
    balance = billing.apply_plan(ws_id, "professional")
    ws = queries.get_workspace(ws_id)
    assert ws["plan"] == "professional"
    assert balance == before + billing.PLANS["professional"]["credits"]
    entry = queries.ledger(ws_id)[0]
    assert entry["reason"] == "plan_purchase"
    assert entry["delta"] == 1000


def test_apply_plan_rejects_unknown_plan(workspace):
    with pytest.raises(billing.BillingError):
        billing.apply_plan(workspace["ws_id"], "platinum")


def test_checkout_url_stub_points_to_mock(workspace):
    url = billing.checkout_url(workspace["ws_id"], "starter")
    assert url == "/billing/mock-checkout?plan=starter"


def test_checkout_url_rejects_unknown_plan(workspace):
    with pytest.raises(billing.BillingError):
        billing.checkout_url(workspace["ws_id"], "platinum")


def test_plan_catalog_includes_seats():
    catalog = {p["key"]: p for p in billing.plan_catalog()}
    assert catalog["starter"]["seats"] == 1
    assert catalog["professional"]["seats"] == 3
    assert catalog["agency"]["seats"] == 10


def test_checkout_completed_event_applies_plan(workspace):
    ws_id = workspace["ws_id"]
    result = billing.handle_event({
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"workspace_id": str(ws_id), "plan": "agency"}}},
    })
    assert result == {"handled": True, "action": "plan_purchase"}
    assert queries.get_workspace(ws_id)["plan"] == "agency"


def test_renewal_invoice_refreshes_credits(workspace):
    ws_id = workspace["ws_id"]
    billing.apply_plan(ws_id, "starter")
    before = queries.get_workspace(ws_id)["credits_balance"]
    result = billing.handle_event({
        "type": "invoice.paid",
        "data": {"object": {
            "billing_reason": "subscription_cycle",
            "subscription_details": {"metadata": {"workspace_id": str(ws_id),
                                                  "plan": "starter"}},
        }},
    })
    assert result["action"] == "monthly_refresh"
    assert queries.get_workspace(ws_id)["credits_balance"] == before + 250


def test_first_invoice_does_not_double_grant(workspace):
    ws_id = workspace["ws_id"]
    before = queries.get_workspace(ws_id)["credits_balance"]
    result = billing.handle_event({
        "type": "invoice.paid",
        "data": {"object": {
            "billing_reason": "subscription_create",
            "metadata": {"workspace_id": str(ws_id), "plan": "starter"},
        }},
    })
    assert result == {"handled": False}
    assert queries.get_workspace(ws_id)["credits_balance"] == before


def test_events_without_metadata_ignored(workspace):
    result = billing.handle_event({
        "type": "checkout.session.completed",
        "data": {"object": {}},
    })
    assert result == {"handled": False}
