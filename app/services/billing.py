from app import config
from app.db import queries

PLANS = {
    "starter": {"label": "Starter", "price_cents": 4900, "credits": 250},
    "professional": {"label": "Professional", "price_cents": 14900, "credits": 1000},
    "agency": {"label": "Agency", "price_cents": 39900, "credits": 4000},
}


class BillingError(Exception):
    pass


def plan_catalog():
    return [
        {"key": key, "seats": config.PLAN_SEATS.get(key, 1), **plan}
        for key, plan in PLANS.items()
    ]


def checkout_url(ws_id, plan):
    if plan not in PLANS:
        raise BillingError(f"Unknown plan: {plan}")
    if config.USE_BILLING_STUB:
        return f"/billing/mock-checkout?plan={plan}"
    return _stripe_checkout_url(ws_id, plan)


def _stripe_checkout_url(ws_id, plan):
    import stripe

    stripe.api_key = config.STRIPE_SECRET_KEY
    spec = PLANS[plan]
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": "usd",
                    "unit_amount": spec["price_cents"],
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": f"LeadGenius {spec['label']} — "
                                f"{spec['credits']} credits/month"
                    },
                },
            }
        ],
        success_url=f"{config.APP_BASE_URL}/billing?upgraded={plan}",
        cancel_url=f"{config.APP_BASE_URL}/billing",
        metadata={"workspace_id": str(ws_id), "plan": plan},
        subscription_data={"metadata": {"workspace_id": str(ws_id), "plan": plan}},
    )
    return session.url


def apply_plan(ws_id, plan, reason="plan_purchase"):
    if plan not in PLANS:
        raise BillingError(f"Unknown plan: {plan}")
    from app.db import core

    core.execute("UPDATE workspaces SET plan=? WHERE id=?", (plan, ws_id))
    balance = queries.record_credits(ws_id, PLANS[plan]["credits"], reason)
    queries.log(ws_id, None, "plan_activated", plan)
    return balance


def handle_event(event):
    kind = event.get("type", "")
    obj = event.get("data", {}).get("object", {})
    metadata = (
        obj.get("metadata")
        or obj.get("subscription_details", {}).get("metadata")
        or {}
    )
    ws_id = metadata.get("workspace_id")
    plan = metadata.get("plan")
    if not ws_id or plan not in PLANS:
        return {"handled": False}
    if kind == "checkout.session.completed":
        apply_plan(int(ws_id), plan, "plan_purchase")
        return {"handled": True, "action": "plan_purchase"}
    if kind in ("invoice.paid", "invoice.payment_succeeded"):
        if obj.get("billing_reason") != "subscription_cycle":
            return {"handled": False}
        apply_plan(int(ws_id), plan, "monthly_refresh")
        return {"handled": True, "action": "monthly_refresh"}
    return {"handled": False}


def handle_webhook(payload, sig_header):
    import stripe

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        raise BillingError(f"Invalid webhook: {e}") from e
    return handle_event(event)
