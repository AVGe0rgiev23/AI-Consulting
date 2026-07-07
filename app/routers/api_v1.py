from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import config, deps, security
from app.db import queries
from app.services import export, ratelimit

router = APIRouter(prefix="/api/v1")


def _unauthorized():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


def _auth(request):
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return _key_auth(header[7:].strip())
    user = deps.current_user(request)
    if not user:
        return None, _unauthorized()
    ws = deps.active_workspace(request, user)
    if not ws:
        return None, _unauthorized()
    return ws, None


def _key_auth(raw_key):
    if not raw_key:
        return None, _unauthorized()
    row = queries.get_api_key_by_hash(security.hash_api_key(raw_key))
    if not row or row["revoked_at"]:
        return None, _unauthorized()
    if not ratelimit.allow(f"api:ws:{row['workspace_id']}",
                           config.API_REQUESTS_PER_WINDOW, config.RATE_WINDOW_SECONDS):
        return None, JSONResponse({"error": "rate_limited"}, status_code=429)
    ws = queries.get_workspace(row["workspace_id"])
    if not ws:
        return None, _unauthorized()
    queries.touch_api_key(row["id"])
    return ws, None


@router.get("/lists")
def api_lists(request: Request):
    ws, err = _auth(request)
    if err:
        return err
    return {"lists": queries.lists_for_workspace(ws["id"])}


@router.get("/lists/{list_id}")
def api_list(request: Request, list_id: int):
    ws, err = _auth(request)
    if err:
        return err
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return JSONResponse({"error": "not_found"}, status_code=404)
    counts = queries.list_job_counts(list_id)
    return {"list": lst, "counts": {c["status"]: c["n"] for c in counts}}


@router.get("/leads/{lead_id}")
def api_lead(request: Request, lead_id: int):
    ws, err = _auth(request)
    if err:
        return err
    lead = queries.get_lead(lead_id)
    lst = queries.get_list(lead["list_id"]) if lead else None
    if not lead or not lst or lst["workspace_id"] != ws["id"]:
        return JSONResponse({"error": "not_found"}, status_code=404)
    brief = queries.get_brief_by_lead(lead_id)
    findings = queries.findings_for_brief(brief["id"]) if brief else []
    hyps = queries.hypotheses_for_brief(brief["id"]) if brief else []
    assets = queries.assets_for_lead(lead_id)
    return {"lead": lead, "brief": brief, "findings": findings,
            "hypotheses": hyps, "assets": assets}


@router.get("/lists/{list_id}/export")
def api_export(request: Request, list_id: int, format: str = "csv"):
    ws, err = _auth(request)
    if err:
        return err
    lst = queries.get_list(list_id)
    if not lst or lst["workspace_id"] != ws["id"]:
        return JSONResponse({"error": "not_found"}, status_code=404)
    fmt = format if format in export.FORMATS else "csv"
    content, count = export.build_export(list_id, fmt)
    return {"format": fmt, "row_count": count, "csv": content}


@router.get("/leaderboard")
def api_leaderboard(request: Request):
    ws, err = _auth(request)
    if err:
        return err
    from app.services import feedback

    return {"funnel": feedback.funnel(ws["id"]), "leaderboard": feedback.leaderboard(ws["id"])}


@router.get("/audits/{report_id}")
def api_audit(request: Request, report_id: int):
    ws, err = _auth(request)
    if err:
        return err
    report = queries.get_audit_report(report_id)
    if not report or report["workspace_id"] != ws["id"]:
        return JSONResponse({"error": "not_found"}, status_code=404)
    import json as _json

    return {"report": report, "opportunities": _json.loads(report["opportunities_json"])}


@router.get("/campaigns")
def api_campaigns(request: Request):
    ws, err = _auth(request)
    if err:
        return err
    return {"campaigns": queries.campaigns_for_workspace(ws["id"])}


@router.get("/prompts")
def api_prompts(request: Request):
    ws, err = _auth(request)
    if err:
        return err
    from app.llm import prompt_library

    overrides = prompt_library.overrides(ws["id"])
    return {
        "prompts": [
            {"key": s["key"], "label": s["label"], "group": s["group"],
             "customized": s["key"] in overrides,
             "content": overrides.get(s["key"], s["default"])}
            for s in prompt_library.slots()
        ]
    }


@router.get("/usage")
def api_usage(request: Request):
    ws, err = _auth(request)
    if err:
        return err
    return {
        "credits_balance": ws["credits_balance"],
        "plan": ws["plan"],
        "ledger": queries.ledger(ws["id"], 20),
    }
