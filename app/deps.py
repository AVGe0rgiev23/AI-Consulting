from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import config, security
from app.db import queries

ROLE_RANK = {"reviewer": 1, "member": 2, "admin": 3, "owner": 4}


class AuthRedirect(Exception):
    pass


def current_user(request: Request):
    token = request.cookies.get(config.SESSION_COOKIE)
    uid = security.read_session(token)
    if not uid:
        return None
    return queries.get_user(uid)


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise AuthRedirect()
    return user


def active_workspace(request: Request, user):
    ws_list = queries.workspaces_for_user(user["id"])
    if not ws_list:
        return None
    wanted = request.cookies.get("lg_ws")
    if wanted:
        for ws in ws_list:
            if str(ws["id"]) == wanted:
                return ws
    return ws_list[0]


def redirect_login():
    return RedirectResponse("/login", status_code=303)


def role_of(user, ws):
    return queries.membership_role(user["id"], ws["id"])


def has_min_role(user, ws, minimum):
    return ROLE_RANK.get(role_of(user, ws), 0) >= ROLE_RANK[minimum]


def forbid():
    return HTMLResponse("You don't have permission to do that in this workspace.",
                        status_code=403)
