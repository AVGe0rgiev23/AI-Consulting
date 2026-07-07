import json

from app import config
from app.db import queries
from app.llm import client, prompt_library, prompts
from app.services import analyze, credits, ingest, research

_TEMPLATES = {
    "revenue_leak": (
        "Recover revenue lost to slow response",
        "Even a modest speed-up in quoting or follow-up tends to recover several deals a month.",
        "Automate inbound intake so no request or quote sits idle.",
    ),
    "scaling": (
        "Scale operations without adding headcount",
        "Manual coordination quietly caps throughput as volume grows.",
        "Introduce workflow automation for the highest-volume manual steps.",
    ),
    "inefficiency": (
        "Remove manual process bottlenecks",
        "Repetitive manual work is slow, costly, and error-prone.",
        "Automate the repetitive handoffs surfaced in the findings.",
    ),
    "automation": (
        "Automate high-frequency tasks",
        "High-frequency manual tasks are the clearest candidates for fast ROI.",
        "Start with one high-volume task and measure hours saved.",
    ),
    "acquisition": (
        "Close lead-response gaps",
        "Slow first-touch follow-up loses buyers who were ready to talk.",
        "Automate first-touch follow-up so every inbound gets a reply in minutes.",
    ),
}


def run_audit(ws_id, company_name, domain, offer):
    domain = _clean(domain)
    list_id = queries.get_or_create_audit_list(ws_id)
    lead = {
        "company_name": company_name or domain, "domain": domain, "contact_name": "",
        "contact_title": "", "email": "", "linkedin_url": "", "raw": {},
        "dedupe_hash": f"audit:{domain}",
    }
    lead_id = queries.insert_lead(list_id, lead)

    credits.charge(ws_id, config.RESEARCH_COST, "audit", None)
    brief_id = research.research_lead(lead_id)
    analyze.analyze_lead(lead_id, offer, ws_id)

    findings = queries.findings_for_brief(brief_id) if brief_id else []
    hyps = queries.hypotheses_for_brief(brief_id) if brief_id else []
    for h in hyps:
        h["evidence"] = json.loads(h["evidence_json"])

    exec_summary, opportunities = _compose(company_name or domain, offer, findings, hyps, ws_id)
    report_id = queries.create_audit_report(
        ws_id, lead_id, company_name or domain, domain, exec_summary, opportunities
    )
    queries.log(ws_id, None, "audit_generated", company_name or domain)
    return report_id


def _compose(company, offer, findings, hyps, ws_id=None):
    by_id = {f["id"]: f for f in findings}

    def stub():
        opps = []
        for h in hyps[:4]:
            title, impact, rec = _TEMPLATES.get(
                h["category"], ("Operational opportunity", h["statement"], "Automate the step above.")
            )
            evidence = [
                {"claim": by_id[e]["claim"], "url": by_id[e]["source_url"]}
                for e in h["evidence"] if e in by_id
            ]
            opps.append(
                {"title": title, "category": h["category"], "impact": impact,
                 "recommendation": rec, "evidence": evidence}
            )
        summary = (
            f"Based on public information about {company}, we identified "
            f"{len(opps)} concrete opportunities to improve operations and revenue. "
            + (f"The most significant is: {opps[0]['title'].lower()}." if opps else "")
        )
        return summary, opps

    if config.USE_LLM_STUB or not hyps:
        return stub()

    data = client.complete_json(
        config.MODEL_SMART,
        prompt_library.resolve(ws_id, "audit"),
        prompts.audit_user(company, offer, findings, hyps),
        lambda: {"exec_summary": stub()[0], "opportunities": stub()[1]},
    )
    if isinstance(data, list):
        data = {"opportunities": data}
    opps = [o for o in data.get("opportunities", []) if isinstance(o, dict)]
    hyp_by_cat = {h["category"]: h for h in hyps}
    for o in opps:
        o.setdefault("evidence", [])
        if not o["evidence"]:
            h = hyp_by_cat.get(o.get("category"))
            if h:
                o["evidence"] = [
                    {"claim": by_id[e]["claim"], "url": by_id[e]["source_url"]}
                    for e in h["evidence"] if e in by_id
                ]
    return data.get("exec_summary", stub()[0]), opps or stub()[1]


def _clean(domain):
    return ingest._clean_domain(domain)
