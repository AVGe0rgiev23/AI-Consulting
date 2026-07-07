from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import config, security
from app.db import queries
from app.templating import templates

router = APIRouter()


@router.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "error": None})


@router.post("/signup")
def signup(request: Request, email: str = Form(...), name: str = Form(""), password: str = Form(...)):
    email = email.lower().strip()
    if len(password) < 8:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Password must be at least 8 characters."},
            status_code=400,
        )
    if queries.get_user_by_email(email):
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "That email is already registered."},
            status_code=400,
        )
    user_id = queries.create_user(email, name or email.split("@")[0], security.hash_password(password))
    ws_id = queries.create_workspace(f"{name or 'My'} workspace", user_id, config.STARTING_CREDITS)
    queries.record_credits(ws_id, 0, "signup_bonus")
    queries.create_offer_profile(
        ws_id, "Default", "AI automation and lead generation services",
        "B2B agencies and service businesses", "", "consultative", "en", True
    )
    resp = RedirectResponse("/onboarding", status_code=303)
    resp.set_cookie(config.SESSION_COOKIE, security.make_session(user_id), httponly=True, samesite="lax")
    return resp


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = queries.get_user_by_email(email)
    if not user or not security.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Wrong email or password."},
            status_code=401,
        )
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(config.SESSION_COOKIE, security.make_session(user["id"]), httponly=True, samesite="lax")
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(config.SESSION_COOKIE)
    return resp
