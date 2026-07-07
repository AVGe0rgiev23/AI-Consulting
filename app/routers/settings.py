from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import branding, deps, security
from app.db import queries
from app.templating import templates

router = APIRouter()


def _render_settings(request, user, ws, new_key=None, new_key_name=""):
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "user": user, "ws": ws, "brand": branding.branding(ws),
         "settings": queries.get_settings(ws),
         "api_keys": queries.api_keys_for_workspace(ws["id"]),
         "new_key": new_key, "new_key_name": new_key_name},
    )


@router.get("/settings")
def settings_page(request: Request):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    return _render_settings(request, user, ws)


@router.post("/settings/api-keys")
def create_api_key(request: Request, key_name: str = Form("")):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    name = key_name.strip() or "API key"
    raw_key = security.make_api_key()
    queries.create_api_key(ws["id"], name, security.hash_api_key(raw_key))
    queries.log(ws["id"], user["id"], "api_key_created", name)
    return _render_settings(request, user, ws, new_key=raw_key, new_key_name=name)


@router.post("/settings/api-keys/{key_id}/revoke")
def revoke_api_key(request: Request, key_id: int):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    queries.revoke_api_key(key_id, ws["id"])
    queries.log(ws["id"], user["id"], "api_key_revoked", str(key_id))
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings")
def save_settings(request: Request, brand_name: str = Form(""), accent: str = Form(""),
                  report_title: str = Form(""), contact: str = Form(""),
                  instantly_api_key: str = Form(""), smartlead_api_key: str = Form("")):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    settings = queries.get_settings(ws)
    settings.update(
        {
            "brand_name": brand_name.strip(),
            "accent": accent.strip(),
            "report_title": report_title.strip(),
            "contact": contact.strip(),
            "instantly_api_key": instantly_api_key.strip(),
            "smartlead_api_key": smartlead_api_key.strip(),
        }
    )
    queries.update_workspace_settings(ws["id"], settings)
    if brand_name.strip():
        from app.db import core

        core.execute("UPDATE workspaces SET name=? WHERE id=?", (brand_name.strip(), ws["id"]))
    queries.log(ws["id"], user["id"], "settings_updated", "white-label")
    return RedirectResponse("/settings", status_code=303)
