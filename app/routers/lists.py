from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app import config, deps
from app.db import queries
from app.jobs import pipeline
from app.services import credits, ingest, ratelimit
from app.templating import templates

router = APIRouter()


def _rate_key(action, request, user):
    ip = request.client.host if request.client else "unknown"
    return f"{action}:{ip}:{user['id']}"


@router.get("/lists", response_class=HTMLResponse)
def lists_page(request: Request):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    rows = queries.lists_for_workspace(ws["id"])
    return templates.TemplateResponse(
        "lists.html", {"request": request, "user": user, "ws": ws, "lists": rows}
    )


@router.post("/lists")
async def create_list(request: Request, name: str = Form(...), file: UploadFile = None,
                      sheet_url: str = Form("")):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "member"):
        return deps.forbid()
    if not ratelimit.allow(_rate_key("upload", request, user),
                           config.UPLOADS_PER_WINDOW, config.RATE_WINDOW_SECONDS):
        return HTMLResponse("Too many uploads — please wait a few minutes.", status_code=429)
    rows = []
    errors = []
    source = "csv"
    if sheet_url.strip():
        source = "gsheets"
        rows, errors = ingest.parse_google_sheet(sheet_url)
    elif file is not None and file.filename:
        raw = await file.read()
        if file.filename.lower().endswith((".xlsx", ".xlsm")):
            source = "xlsx"
            rows, errors = ingest.parse_xlsx(raw)
        else:
            rows, errors = ingest.parse_csv(raw)
    cap = config.PLAN_LEAD_CAPS.get(ws["plan"], config.PLAN_LEAD_CAPS["trial"])
    if len(rows) > cap:
        errors.append(f"{len(rows) - cap} rows skipped — the {ws['plan']} plan is capped "
                      f"at {cap} leads per list")
        rows = rows[:cap]
    list_id = queries.create_list(ws["id"], name or "Untitled list", source)
    inserted = 0
    if rows:
        inserted, _dupes = ingest.import_rows(list_id, rows)
    queries.set_list_counts(list_id, inserted, len(errors))
    queries.log(ws["id"], user["id"], "list_imported", name)
    return RedirectResponse(f"/lists/{list_id}", status_code=303)


@router.get("/lists/{list_id}", response_class=HTMLResponse)
def list_detail(request: Request, list_id: int):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return HTMLResponse("Not found", status_code=404)
    leads = queries.leads_for_list(list_id)
    profiles = queries.offer_profiles(ws["id"])
    return templates.TemplateResponse(
        "list_detail.html",
        {
            "request": request, "user": user, "ws": ws, "list": lst,
            "leads": leads, "profiles": profiles,
            "briefs": queries.briefs_by_lead_for_list(list_id),
            "credits": credits.balance(ws["id"]),
        },
    )


@router.post("/lists/{list_id}/research")
def run_research(request: Request, list_id: int, offer_profile_id: int = Form(None)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return HTMLResponse("Not found", status_code=404)
    if not deps.has_min_role(user, ws, "member"):
        return deps.forbid()
    if not ratelimit.allow(_rate_key("research", request, user),
                           config.RESEARCH_RUNS_PER_WINDOW, config.RATE_WINDOW_SECONDS):
        return HTMLResponse("Too many research runs — please wait a few minutes.",
                            status_code=429)
    pending = [l for l in queries.leads_for_list(list_id) if l["status"] == "pending"]
    try:
        credits.ensure(ws["id"], len(pending))
    except credits.InsufficientCredits as exc:
        return HTMLResponse(f'<div class="err">{exc}</div>', status_code=402)
    pipeline.enqueue_research(ws["id"], list_id, offer_profile_id)
    queries.log(ws["id"], user["id"], "research_run", lst["name"])
    return RedirectResponse(f"/research/{list_id}", status_code=303)
