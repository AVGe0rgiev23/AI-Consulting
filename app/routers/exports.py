from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from urllib.parse import quote

from app import config, deps
from app.db import queries
from app.services import export, sender
from app.templating import templates

router = APIRouter()


@router.get("/exports", response_class=HTMLResponse)
def exports_page(request: Request, pushed: str = "", error: str = ""):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lists = queries.lists_for_workspace(ws["id"])
    return templates.TemplateResponse(
        "exports.html",
        {"request": request, "user": user, "ws": ws, "lists": lists,
         "formats": export.FORMATS, "providers": sender.PROVIDERS,
         "connected": sender.connected_providers(ws),
         "pushes": queries.pushes_for_workspace(ws["id"]),
         "pushed": pushed, "error": error,
         "sender_stub": config.USE_SENDER_STUB},
    )


@router.post("/lists/{list_id}/push/{provider}")
def push_campaign(request: Request, list_id: int, provider: str):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return PlainTextResponse("Not found", status_code=404)
    if provider not in sender.PROVIDERS:
        return PlainTextResponse("Unknown provider", status_code=404)
    if not deps.has_min_role(user, ws, "member"):
        return PlainTextResponse("Forbidden", status_code=403)
    try:
        result = sender.push_list(ws, list_id, provider, user["id"])
    except sender.SenderError as e:
        return RedirectResponse(f"/exports?error={quote(str(e))}", status_code=303)
    return RedirectResponse(
        f"/exports?pushed={result['lead_count']} leads to {provider}", status_code=303
    )


@router.post("/lists/{list_id}/pull/{provider}")
def pull_stats(request: Request, list_id: int, provider: str):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return PlainTextResponse("Not found", status_code=404)
    if provider not in sender.PROVIDERS:
        return PlainTextResponse("Unknown provider", status_code=404)
    if not deps.has_min_role(user, ws, "member"):
        return PlainTextResponse("Forbidden", status_code=403)
    try:
        result = sender.pull_stats(ws, list_id, provider, user["id"])
    except sender.SenderError as e:
        return RedirectResponse(f"/exports?error={quote(str(e))}", status_code=303)
    return RedirectResponse(
        f"/analytics?pulled={result['matched']} of {result['pulled']} leads matched "
        f"from {provider}", status_code=303,
    )


@router.get("/lists/{list_id}/export")
def download_export(request: Request, list_id: int, format: str = "csv"):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return PlainTextResponse("Not found", status_code=404)
    if not deps.has_min_role(user, ws, "member"):
        return PlainTextResponse("Forbidden", status_code=403)
    if format not in export.FORMATS:
        format = "csv"
    content, count = export.build_export(list_id, format)
    if count == 0:
        return PlainTextResponse("No approved emails to export yet.", status_code=400)
    queries.record_export(ws["id"], list_id, format, count, "")
    queries.get_or_create_campaign(ws["id"], list_id, lst["name"], format)
    queries.log(ws["id"], user["id"], "export", f"{lst['name']} ({format})")
    prefix = "PREVIEW_" if config.USE_SENDER_STUB else ""
    filename = f"{prefix}{lst['name'].replace(' ', '_')}_{format}.csv"
    return PlainTextResponse(
        content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type="text/csv",
    )
