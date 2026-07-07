import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import config, deps
from app.db import queries
from app.llm import score
from app.services import analyze, credits, research, write
from app.templating import templates

router = APIRouter()


def _assemble(lead):
    brief = queries.get_brief_by_lead(lead["id"])
    findings = queries.findings_for_brief(brief["id"]) if brief else []
    hyps = queries.hypotheses_for_brief(brief["id"]) if brief else []
    for h in hyps:
        h["evidence"] = json.loads(h["evidence_json"])
    assets = queries.assets_for_lead(lead["id"])
    for a in assets:
        a["breakdown"] = json.loads(a["score_breakdown_json"])
    return brief, findings, hyps, assets


@router.get("/review/{list_id}", response_class=HTMLResponse)
def review_page(request: Request, list_id: int, i: int = 0, err: str = ""):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return HTMLResponse("Not found", status_code=404)
    leads = [l for l in queries.leads_for_list(list_id)
             if l["status"] in ("ready", "needs_review", "approved", "exported")]
    if not leads:
        return templates.TemplateResponse(
            "review_empty.html", {"request": request, "user": user, "ws": ws, "list": lst}
        )
    i = max(0, min(i, len(leads) - 1))
    lead = leads[i]
    brief, findings, hyps, assets = _assemble(lead)
    return templates.TemplateResponse(
        "review.html",
        {
            "request": request, "user": user, "ws": ws, "list": lst,
            "lead": lead, "brief": brief, "findings": findings,
            "hypotheses": hyps, "assets": assets, "idx": i, "total": len(leads),
            "err": err, "approval_floor": config.APPROVAL_SCORE_FLOOR,
        },
    )


@router.post("/assets/{asset_id}/approve")
def approve_asset(request: Request, asset_id: int, list_id: int = Form(...), i: int = Form(0)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    asset = queries.get_asset(asset_id)
    if asset and asset["score"] < config.APPROVAL_SCORE_FLOOR:
        return RedirectResponse(f"/review/{list_id}?i={i}&err=floor", status_code=303)
    if asset:
        for a in queries.assets_for_lead(asset["lead_id"]):
            queries.set_asset_status(a["id"], "approved")
        queries.set_lead_status(asset["lead_id"], "approved")
    return RedirectResponse(f"/review/{list_id}?i={i + 1}", status_code=303)


@router.post("/assets/{asset_id}/edit")
def edit_asset(request: Request, asset_id: int, content: str = Form(...),
               subject: str = Form(""), list_id: int = Form(...), i: int = Form(0)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    asset = queries.get_asset(asset_id)
    if asset:
        findings = _lead_findings(asset["lead_id"])
        is_email = asset["kind"].startswith("email_")
        total, breakdown = score.score_asset(content, findings, is_email=is_email)
        queries.update_asset(asset_id, content, subject, total, breakdown, "edited", asset["version"] + 1)
    return RedirectResponse(f"/review/{list_id}?i={i}", status_code=303)


@router.post("/leads/{lead_id}/regenerate")
def regenerate(request: Request, lead_id: int, list_id: int = Form(...), i: int = Form(0)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    offer = queries.default_offer_profile(ws["id"])
    write.generate_for_lead(lead_id, offer)
    return RedirectResponse(f"/review/{list_id}?i={i}", status_code=303)


@router.post("/leads/{lead_id}/deep-research")
def deep_research(request: Request, lead_id: int, list_id: int = Form(...), i: int = Form(0)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lead = queries.get_lead(lead_id)
    lst = queries.get_list(list_id)
    if not lead or not lst or lead["list_id"] != list_id or lst["workspace_id"] != ws["id"]:
        return HTMLResponse("Not found", status_code=404)
    if not deps.has_min_role(user, ws, "member"):
        return deps.forbid()
    try:
        credits.charge(ws["id"], config.RESEARCH_COST, "deep_research", None)
    except credits.InsufficientCredits:
        return RedirectResponse(f"/review/{list_id}?i={i}&err=credits", status_code=303)
    offer = queries.default_offer_profile(ws["id"])
    research.research_lead(lead_id, deep=True)
    analyze.analyze_lead(lead_id, offer, ws["id"])
    write.generate_for_lead(lead_id, offer)
    brief = queries.get_brief_by_lead(lead_id)
    if brief and brief["thin"]:
        queries.set_lead_status(lead_id, "needs_review", brief["thin_reason"])
    else:
        queries.set_lead_status(lead_id, "ready")
    queries.log(ws["id"], user["id"], "deep_research", lead["company_name"] or lead["domain"])
    return RedirectResponse(f"/review/{list_id}?i={i}", status_code=303)


def _lead_findings(lead_id):
    brief = queries.get_brief_by_lead(lead_id)
    return queries.findings_for_brief(brief["id"]) if brief else []
