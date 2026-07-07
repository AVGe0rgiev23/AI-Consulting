import json

from app import config
from app.db import queries
from app.services import analyze, credits, research, write


def run_job(job):
    kind = job["kind"]
    payload = json.loads(job["payload_json"])
    if kind == "research":
        return _run_research(job["workspace_id"], payload)
    if kind == "generate":
        return _run_generate(job["workspace_id"], payload)
    raise ValueError(f"Unknown job kind: {kind}")


def _run_research(ws_id, payload):
    list_id = payload["list_id"]
    profile_id = payload.get("offer_profile_id")
    offer = _offer(ws_id, profile_id)
    queries.set_list_status(list_id, "researching")
    leads = queries.leads_for_list(list_id)
    done_statuses = ("researched", "ready", "approved", "exported", "needs_review")
    todo = [l for l in leads if l["status"] not in done_statuses]
    total = len(todo)
    queries.emit_event(list_id, "start", f"Researching {total} leads", total=total)
    processed = 0
    failed = 0
    for lead in todo:
        company = lead["company_name"] or lead["domain"] or "company"
        try:
            credits.charge(ws_id, config.RESEARCH_COST, "research", None)
        except credits.InsufficientCredits as exc:
            queries.emit_event(list_id, "failed", f"Stopping: {exc}",
                               done=processed, total=total)
            break
        try:
            _research_one(list_id, lead, offer, ws_id, company, processed, total)
        except Exception as exc:
            failed += 1
            reason = f"{type(exc).__name__}: {exc}"[:200]
            queries.set_lead_status(lead["id"], "failed", reason)
            queries.emit_event(list_id, "failed", f"{company}: failed — {reason}",
                               lead_id=lead["id"], done=processed, total=total)
        processed += 1
    queries.set_list_status(list_id, "ready")
    summary = f"Done — {processed} leads processed"
    if failed:
        summary += f", {failed} failed (will retry on next run)"
    queries.emit_event(list_id, "complete", summary, done=processed, total=total)
    return {"processed": processed, "failed": failed}


def _research_one(list_id, lead, offer, ws_id, company, processed, total):
    queries.emit_event(list_id, "researching", f"Researching {company}",
                       lead_id=lead["id"], done=processed, total=total)
    brief_id = research.research_lead(lead["id"])
    queries.emit_event(list_id, "found", _found_summary(brief_id, company),
                       lead_id=lead["id"], done=processed, total=total)
    analyze.analyze_lead(lead["id"], offer, ws_id)
    queries.emit_event(list_id, "analyzed", _hyp_summary(brief_id, company),
                       lead_id=lead["id"], done=processed, total=total)
    assets = write.generate_for_lead(lead["id"], offer)
    brief = queries.get_brief_by_lead(lead["id"])
    thin = bool(brief and brief["thin"])
    if thin:
        queries.set_lead_status(lead["id"], "needs_review", brief["thin_reason"])
        message = _thin_summary(brief, company)
    else:
        queries.set_lead_status(lead["id"], "ready")
        message = _wrote_summary(assets, company)
    queries.emit_event(list_id, "written", message,
                       lead_id=lead["id"], done=processed + 1, total=total)


def _found_summary(brief_id, company):
    if not brief_id:
        return f"{company}: website unreachable, using web search only"
    findings = queries.findings_for_brief(brief_id)
    if not findings:
        return f"{company}: nothing verifiable found"
    kinds = sorted({f["kind"] for f in findings})
    brief = queries.get_brief(brief_id)
    label = research.confidence_label(brief["quality"]) if brief else "low"
    return (f"{company}: {len(findings)} findings ({', '.join(kinds)}) — "
            f"{label} confidence")


def _hyp_summary(brief_id, company):
    hyps = queries.hypotheses_for_brief(brief_id) if brief_id else []
    if not hyps:
        return f"{company}: no strong angle found"
    return f"{company}: top angle — {hyps[0]['statement'][:70]}"


def _wrote_summary(assets, company):
    emails = [a for a in assets if a["kind"].startswith("email_")]
    top = max((a["score"] for a in emails), default=0)
    return f"{company}: wrote {len(emails)}-step sequence, best score {top}/100"


def _thin_summary(brief, company):
    reason = brief["thin_reason"] or "insufficient data"
    return f"{company}: insufficient data ({reason}) — generic fallback, needs manual review"


def _run_generate(ws_id, payload):
    lead_id = payload["lead_id"]
    offer = _offer(ws_id, payload.get("offer_profile_id"))
    kinds = payload.get("kinds")
    created = write.generate_for_lead(lead_id, offer, kinds)
    queries.set_lead_status(lead_id, "ready")
    return {"created": len(created)}


def _offer(ws_id, profile_id):
    offer = queries.get_offer_profile(profile_id) if profile_id else None
    if not offer:
        offer = queries.default_offer_profile(ws_id)
    if not offer:
        return {"what_we_sell": "B2B services", "icp": "growing companies",
                "proof_point": "", "voice_preset": "consultative", "language": "en"}
    return offer


def enqueue_research(ws_id, list_id, profile_id=None):
    queries.clear_events(list_id)
    queries.set_list_status(list_id, "researching")
    todo = [l for l in queries.leads_for_list(list_id)
            if l["status"] not in ("researched", "ready", "approved", "exported",
                                   "needs_review")]
    queries.emit_event(list_id, "queued", "Queued for research", total=len(todo))
    return queries.create_job(ws_id, "research",
                              {"list_id": list_id, "offer_profile_id": profile_id})


def process_list_now(ws_id, list_id, profile_id=None):
    from app.db import core

    job_id = core.execute(
        "INSERT INTO jobs(workspace_id, kind, payload_json, status, claimed_at) "
        "VALUES(?,?,?,'running',datetime('now'))",
        (ws_id, "research", json.dumps({"list_id": list_id, "offer_profile_id": profile_id})),
    )
    result = _run_research(ws_id, {"list_id": list_id, "offer_profile_id": profile_id})
    queries.finish_job(job_id, "done")
    return result
