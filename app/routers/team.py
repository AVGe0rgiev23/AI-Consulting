import secrets

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import config, deps, security
from app.db import queries
from app.templating import templates

router = APIRouter()

_ASSIGNABLE_ROLES = ["admin", "member", "reviewer"]


@router.get("/team", response_class=HTMLResponse)
def team_page(request: Request):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    seats = config.PLAN_SEATS.get(ws["plan"], 1)
    return templates.TemplateResponse(
        "team.html",
        {
            "request": request, "user": user, "ws": ws,
            "members": queries.members_of_workspace(ws["id"]),
            "invites": queries.invites_for_workspace(ws["id"]),
            "my_role": deps.role_of(user, ws),
            "is_admin": deps.has_min_role(user, ws, "admin"),
            "seats": seats,
            "seats_used": queries.seat_count(ws["id"]),
            "roles": _ASSIGNABLE_ROLES,
            "workspaces": queries.workspaces_for_user(user["id"]),
            "base_url": str(request.base_url).rstrip("/"),
        },
    )


@router.post("/team/invite")
def invite(request: Request, email: str = Form(...), role: str = Form("member")):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    if role not in _ASSIGNABLE_ROLES:
        role = "member"
    seats = config.PLAN_SEATS.get(ws["plan"], 1)
    if queries.seat_count(ws["id"]) >= seats:
        return HTMLResponse(
            f'<div class="err">Seat limit reached ({seats} on the {ws["plan"]} plan). '
            f"Upgrade to invite more teammates.</div>",
            status_code=402,
        )
    token = secrets.token_urlsafe(24)
    queries.create_invite(ws["id"], email, role, token, user["id"])
    queries.log(ws["id"], user["id"], "invite_sent", email)
    return RedirectResponse("/team", status_code=303)


@router.post("/team/role")
def change_role(request: Request, user_id: int = Form(...), role: str = Form(...)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    if role not in _ASSIGNABLE_ROLES:
        return deps.forbid()
    if queries.membership_role(user_id, ws["id"]) == "owner":
        return deps.forbid()
    queries.update_membership_role(user_id, ws["id"], role)
    queries.log(ws["id"], user["id"], "role_changed", f"user {user_id} -> {role}")
    return RedirectResponse("/team", status_code=303)


@router.post("/team/remove")
def remove_member(request: Request, user_id: int = Form(...)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    if queries.membership_role(user_id, ws["id"]) == "owner":
        return deps.forbid()
    queries.remove_membership(user_id, ws["id"])
    queries.log(ws["id"], user["id"], "member_removed", f"user {user_id}")
    return RedirectResponse("/team", status_code=303)


@router.post("/team/invite/{invite_id}/revoke")
def revoke_invite(request: Request, invite_id: int):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    if not deps.has_min_role(user, ws, "admin"):
        return deps.forbid()
    queries.delete_invite(invite_id)
    return RedirectResponse("/team", status_code=303)


@router.get("/join/{token}", response_class=HTMLResponse)
def join_page(request: Request, token: str):
    invite_row = queries.get_invite(token)
    if not invite_row:
        return HTMLResponse("This invite link is invalid or has expired.", status_code=404)
    ws = queries.get_workspace(invite_row["workspace_id"])
    user = deps.current_user(request)
    if user:
        queries.add_membership(user["id"], ws["id"], invite_row["role"])
        queries.delete_invite(invite_row["id"])
        queries.log(ws["id"], user["id"], "member_joined", user["email"])
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("lg_ws", str(ws["id"]), httponly=True, samesite="lax")
        return resp
    existing = queries.get_user_by_email(invite_row["email"])
    return templates.TemplateResponse(
        "join.html",
        {"request": request, "invite": invite_row, "ws": ws, "existing": bool(existing)},
    )


@router.post("/join/{token}")
def join_signup(request: Request, token: str, name: str = Form(""), password: str = Form(...)):
    invite_row = queries.get_invite(token)
    if not invite_row:
        return HTMLResponse("This invite link is invalid or has expired.", status_code=404)
    if len(password) < 8:
        ws = queries.get_workspace(invite_row["workspace_id"])
        return templates.TemplateResponse(
            "join.html",
            {"request": request, "invite": invite_row, "ws": ws, "existing": False,
             "error": "Password must be at least 8 characters."},
            status_code=400,
        )
    if queries.get_user_by_email(invite_row["email"]):
        return RedirectResponse(f"/login?next=/join/{token}", status_code=303)
    user_id = queries.create_user(
        invite_row["email"], name or invite_row["email"].split("@")[0],
        security.hash_password(password),
    )
    queries.add_membership(user_id, invite_row["workspace_id"], invite_row["role"])
    queries.delete_invite(invite_row["id"])
    queries.log(invite_row["workspace_id"], user_id, "member_joined", invite_row["email"])
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(config.SESSION_COOKIE, security.make_session(user_id),
                    httponly=True, samesite="lax")
    resp.set_cookie("lg_ws", str(invite_row["workspace_id"]), httponly=True, samesite="lax")
    return resp


@router.post("/workspace/switch")
def switch_workspace(request: Request, workspace_id: int = Form(...)):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    if not queries.is_member(user["id"], workspace_id):
        return deps.forbid()
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("lg_ws", str(workspace_id), httponly=True, samesite="lax")
    return resp
