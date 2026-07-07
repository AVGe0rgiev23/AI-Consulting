from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import deps
from app.db import queries
from app.services import credits
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lists = queries.lists_for_workspace(ws["id"])
    stats = _overview_stats(ws["id"], lists)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request, "user": user, "ws": ws, "lists": lists[:6],
            "stats": stats, "credits": credits.balance(ws["id"]),
            "activity": queries.recent_activity(ws["id"]),
        },
    )


@router.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    profile = queries.default_offer_profile(ws["id"])
    return templates.TemplateResponse(
        "onboarding.html", {"request": request, "user": user, "ws": ws, "profile": profile}
    )


@router.post("/onboarding")
def save_onboarding(request: Request, what_we_sell: str = Form(...), icp: str = Form(...),
                    proof_point: str = Form(""), voice_preset: str = Form("consultative")):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    profile = queries.default_offer_profile(ws["id"])
    from app.db import core

    core.execute(
        "UPDATE offer_profiles SET what_we_sell=?, icp=?, proof_point=?, voice_preset=? WHERE id=?",
        (what_we_sell, icp, proof_point, voice_preset, profile["id"]),
    )
    return RedirectResponse("/lists", status_code=303)


def _overview_stats(ws_id, lists):
    from app.db import core

    researched = core.query_one(
        "SELECT COUNT(*) n FROM leads l JOIN lead_lists ll ON ll.id=l.list_id "
        "WHERE ll.workspace_id=? AND ll.source!='audit' "
        "AND l.status IN ('ready','approved','exported')",
        (ws_id,),
    )["n"]
    awaiting = core.query_one(
        "SELECT COUNT(*) n FROM leads l JOIN lead_lists ll ON ll.id=l.list_id "
        "WHERE ll.workspace_id=? AND ll.source!='audit' AND l.status='ready'",
        (ws_id,),
    )["n"]
    avg_score = core.query_one(
        "SELECT AVG(a.score) s FROM assets a JOIN leads l ON l.id=a.lead_id "
        "JOIN lead_lists ll ON ll.id=l.list_id WHERE ll.workspace_id=? "
        "AND ll.source!='audit' AND a.kind='email_1'",
        (ws_id,),
    )["s"]
    return {
        "researched": researched,
        "awaiting": awaiting,
        "avg_score": round(avg_score) if avg_score else 0,
        "time_saved": round(researched * 0.2, 1),
    }
