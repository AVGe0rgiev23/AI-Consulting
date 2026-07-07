from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app import deps
from app.db import queries
from app.services import feedback
from app.templating import templates

router = APIRouter()


@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, pulled: str = ""):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request, "user": user, "ws": ws,
            "funnel": feedback.funnel(ws["id"]),
            "board": feedback.leaderboard(ws["id"]),
            "campaigns": queries.campaigns_for_workspace(ws["id"]),
            "lists": queries.lists_for_workspace(ws["id"]),
            "pulled": pulled,
        },
    )


@router.post("/lists/{list_id}/import-stats")
async def import_stats(request: Request, list_id: int, file: UploadFile = None):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return HTMLResponse("Not found", status_code=404)
    if not deps.has_min_role(user, ws, "member"):
        return HTMLResponse("Forbidden", status_code=403)
    if file is not None:
        raw = await file.read()
        rows = feedback.parse_stats_csv(raw)
        result = feedback.import_stats(ws["id"], list_id, rows)
        queries.log(ws["id"], user["id"], "stats_imported",
                    f"{lst['name']} ({result['matched']} matched)")
    return RedirectResponse("/analytics", status_code=303)
