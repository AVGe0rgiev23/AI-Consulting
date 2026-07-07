from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app import config, deps
from app.db import queries
from app.services import billing
from app.templating import templates

router = APIRouter()


@router.get("/billing", response_class=HTMLResponse)
def billing_page(request: Request, upgraded: str = "", error: str = ""):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    return templates.TemplateResponse(
        "billing.html",
        {"request": request, "user": user, "ws": ws,
         "plans": billing.plan_catalog(),
         "ledger": queries.ledger(ws["id"], 20),
         "seats": config.PLAN_SEATS.get(ws["plan"], 1),
         "can_manage": deps.has_min_role(user, ws, "admin"),
         "stub": config.USE_BILLING_STUB,
         "upgraded": upgraded, "error": error},
    )


@router.post("/billing/checkout/{plan}")
def start_checkout(request: Request, plan: str):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    try:
        url = billing.checkout_url(ws["id"], plan)
    except billing.BillingError:
        return PlainTextResponse("Unknown plan", status_code=404)
    return RedirectResponse(url, status_code=303)


@router.get("/billing/mock-checkout", response_class=HTMLResponse)
def mock_checkout(request: Request, plan: str = ""):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    if not config.USE_BILLING_STUB or plan not in billing.PLANS:
        return PlainTextResponse("Not found", status_code=404)
    spec = billing.PLANS[plan]
    return HTMLResponse(
        "<body style='margin:0;background:#0c0b09;color:#f2ede1;min-height:100vh;"
        "display:flex;align-items:center;justify-content:center;"
        "font-family:Archivo,-apple-system,sans-serif'>"
        "<div style='max-width:380px;width:100%;padding:32px;background:#17140f;"
        "border:1px solid #2b2720;border-radius:14px'>"
        "<div style='font-size:10px;text-transform:uppercase;letter-spacing:.14em;"
        "color:#9c9280;margin-bottom:6px'>Test mode</div>"
        "<h2 style='margin:0 0 16px;font-weight:600'>Mock Stripe Checkout</h2>"
        f"<p style='color:#c9c2b2;line-height:1.6'>LeadGenius {spec['label']} — "
        f"${spec['price_cents'] // 100}/month, {spec['credits']} credits.</p>"
        "<form method='post' action='/billing/mock-checkout' "
        "style='display:flex;gap:10px;margin-top:20px;align-items:center'>"
        f"<input type='hidden' name='plan' value='{plan}'>"
        "<button type='submit' style='background:linear-gradient(155deg,#e8bd72,#c99a4b);"
        "color:#171006;border:none;border-radius:9px;padding:10px 18px;font-weight:600;"
        "cursor:pointer;font-family:inherit'>Pay (test mode)</button>"
        "<a href='/billing' style='color:#9c9280'>Cancel</a></form></div></body>"
    )


@router.post("/billing/mock-checkout")
def mock_checkout_pay(request: Request, plan: str = Form("")):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    if not config.USE_BILLING_STUB or plan not in billing.PLANS:
        return PlainTextResponse("Not found", status_code=404)
    billing.apply_plan(ws["id"], plan)
    return RedirectResponse(f"/billing?upgraded={plan}", status_code=303)


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    if config.USE_BILLING_STUB:
        return PlainTextResponse("Billing not configured", status_code=400)
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        result = billing.handle_webhook(payload, sig)
    except billing.BillingError:
        return PlainTextResponse("Invalid signature", status_code=400)
    return result
