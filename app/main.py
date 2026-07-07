import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import config, deps
from app.db import core
from app.jobs import worker
from app.routers import (
    analytics, api_v1, audit, auth, billing, dashboard, exports, lists, pages, prompts,
    research, review, settings, team,
)


@asynccontextmanager
async def lifespan(app):
    core.init_db()
    task = asyncio.create_task(worker.worker_loop())
    yield
    worker.stop()
    task.cancel()


app = FastAPI(title="LeadGenius", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "app" / "static")), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(lists.router)
app.include_router(research.router)
app.include_router(review.router)
app.include_router(exports.router)
app.include_router(analytics.router)
app.include_router(audit.router)
app.include_router(settings.router)
app.include_router(team.router)
app.include_router(prompts.router)
app.include_router(billing.router)
app.include_router(api_v1.router)
app.include_router(pages.router)


@app.exception_handler(deps.AuthRedirect)
async def auth_redirect_handler(request: Request, exc: deps.AuthRedirect):
    return RedirectResponse("/login", status_code=303)


@app.get("/healthz")
def healthz():
    from app.services import budget

    return {
        "ok": True,
        "llm_stub": config.USE_LLM_STUB,
        "fetch_stub": config.USE_FETCH_STUB,
        "llm_provider": config.LLM_PROVIDER,
        "budget": budget.status(),
    }
