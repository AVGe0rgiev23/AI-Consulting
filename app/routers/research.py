import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from app import deps
from app.db import queries
from app.templating import templates

router = APIRouter()

_POLL_SECONDS = 0.4
_MAX_TICKS = 4500


@router.get("/research/{list_id}", response_class=HTMLResponse)
def research_page(request: Request, list_id: int):
    user = deps.current_user(request)
    if not user:
        return deps.redirect_login()
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        "research.html", {"request": request, "user": user, "ws": ws, "list": lst}
    )


@router.get("/research/{list_id}/stream")
async def research_stream(request: Request, list_id: int):
    user = deps.current_user(request)
    if not user:
        return HTMLResponse("Unauthorized", status_code=401)
    ws = deps.active_workspace(request, user)
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return HTMLResponse("Not found", status_code=404)

    async def event_source():
        last_id = 0
        ticks = 0
        while ticks < _MAX_TICKS:
            if await request.is_disconnected():
                break
            events = await asyncio.to_thread(queries.events_since, list_id, last_id)
            for ev in events:
                last_id = ev["id"]
                payload = {
                    "phase": ev["phase"],
                    "message": ev["message"],
                    "done": ev["done"],
                    "total": ev["total"],
                }
                yield f"data: {json.dumps(payload)}\n\n"
                if ev["phase"] == "complete":
                    return
            ticks += 1
            await asyncio.sleep(_POLL_SECONDS)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
