from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import deps
from app.templating import templates

router = APIRouter()


def _render(request, template):
    return templates.TemplateResponse(
        template, {"request": request, "user": deps.current_user(request)}
    )


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return _render(request, "privacy.html")


@router.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    return _render(request, "terms.html")


@router.get("/how-research-works", response_class=HTMLResponse)
def how_research_works(request: Request):
    return _render(request, "how_research_works.html")
