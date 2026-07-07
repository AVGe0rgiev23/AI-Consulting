import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import branding, deps
from app.db import queries
from app.services import audit, credits
from app.templating import templates

router = APIRouter()


@router.get("/audit", response_class=HTMLResponse)
def audit_home(request: Request):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    return templates.TemplateResponse(
        "audit_home.html",
        {
            "request": request, "user": user, "ws": ws,
            "reports": queries.audit_reports_for_workspace(ws["id"]),
            "credits": credits.balance(ws["id"]),
        },
    )


@router.post("/audit")
def create_audit(request: Request, company_name: str = Form(""), domain: str = Form(...)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "member"):
        return deps.forbid()
    try:
        credits.ensure(ws["id"], 1)
    except credits.InsufficientCredits as exc:
        return HTMLResponse(f'<div class="err">{exc}</div>', status_code=402)
    offer = queries.default_offer_profile(ws["id"]) or {"what_we_sell": "automation services"}
    report_id = audit.run_audit(ws["id"], company_name, domain, offer)
    return RedirectResponse(f"/audit/{report_id}", status_code=303)


@router.get("/audit/{report_id}", response_class=HTMLResponse)
def view_audit(request: Request, report_id: int):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    report = queries.get_audit_report(report_id)
    if not report or report["workspace_id"] != ws["id"]:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        "audit_report.html",
        {
            "request": request, "report": report,
            "opportunities": json.loads(report["opportunities_json"]),
            "brand": branding.branding(ws),
        },
    )
