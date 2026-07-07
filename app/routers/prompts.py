from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import deps
from app.db import queries
from app.llm import prompt_library
from app.templating import templates

router = APIRouter()


@router.get("/prompts")
def prompts_page(request: Request):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    overrides = prompt_library.overrides(ws["id"])
    grouped = {g: [] for g in prompt_library.GROUP_ORDER}
    for s in prompt_library.slots():
        grouped[s["group"]].append(
            {**s, "content": overrides.get(s["key"], s["default"]),
             "customized": s["key"] in overrides}
        )
    return templates.TemplateResponse(
        "prompts.html",
        {"request": request, "user": user, "ws": ws,
         "groups": [(g, grouped[g]) for g in prompt_library.GROUP_ORDER],
         "can_edit": deps.has_min_role(user, ws, "admin")},
    )


@router.post("/prompts/{key}")
def save_prompt(request: Request, key: str, content: str = Form("")):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    try:
        customized = prompt_library.set_override(ws["id"], key, content)
    except ValueError:
        return HTMLResponse("Unknown prompt slot.", status_code=404)
    action = "prompt_customized" if customized else "prompt_reset"
    queries.log(ws["id"], user["id"], action, key)
    return RedirectResponse("/prompts", status_code=303)


@router.post("/prompts/{key}/reset")
def reset_prompt(request: Request, key: str):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    try:
        prompt_library.clear_override(ws["id"], key)
    except ValueError:
        return HTMLResponse("Unknown prompt slot.", status_code=404)
    queries.log(ws["id"], user["id"], "prompt_reset", key)
    return RedirectResponse("/prompts", status_code=303)
