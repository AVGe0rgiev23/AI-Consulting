import re

from app import config
from app.db import queries
from app.llm import client, prompt_library, prompts
from app.services import research

_CONTRADICTION_THEMES = [
    (re.compile(r"\bai[- ](powered|driven|run|first|native|enabled)\b|\brun by ai\b"
                r"|\bpowered by ai\b|\bai (automation|agents?|platform|auditor)\b"
                r"|\bartificial intelligence\b"),
     re.compile(r"\bai\b|\bartificial intelligence\b")),
    (re.compile(r"\b(fully|already) automated\b|\bautomation platform\b|\bautomates\b"),
     re.compile(r"\bautomat(e|es|ed|ion|ing)\b")),
]
_ABSENCE_RE = re.compile(
    r"\b(could|can be|should|lacks?|lack of|manual|manually|further|adopt|adopting"
    r"|introduce|introducing|implement|implementing|needs?|missing)\b"
)


def analyze_lead(lead_id, offer, ws_id=None):
    brief = queries.get_brief_by_lead(lead_id)
    if not brief:
        return []
    ws_id = ws_id or offer.get("workspace_id")
    findings = queries.findings_for_brief(brief["id"])
    hypotheses = _generate(brief, findings, offer, ws_id)
    hypotheses = _drop_contradicted(hypotheses, findings)
    hypotheses = _neutralize_stale(hypotheses, findings)
    hypotheses = _reweight(hypotheses, ws_id)

    _clear_hypotheses(brief["id"])
    ids = []
    for h in hypotheses:
        ids.append(queries.insert_hypothesis(brief["id"], h))
    return ids


def _drop_contradicted(hypotheses, findings):
    evidence_text = " ".join(
        f"{f['claim']} {f.get('snippet', '')}" for f in findings
    ).lower()
    active_themes = [statement_re for evidence_re, statement_re in _CONTRADICTION_THEMES
                     if evidence_re.search(evidence_text)]
    if not active_themes:
        return hypotheses
    kept = []
    for h in hypotheses:
        statement = h["statement"].lower()
        contradicted = (_ABSENCE_RE.search(statement)
                        and any(theme.search(statement) for theme in active_themes))
        if not contradicted:
            kept.append(h)
    return kept


def _neutralize_stale(hypotheses, findings):
    for h in hypotheses:
        if research.stale_evidence_only(findings, h.get("evidence", [])):
            h["statement"] = research.strip_temporal_framing(h["statement"])
    return hypotheses


def _reweight(hypotheses, ws_id):
    if not ws_id or not hypotheses:
        return hypotheses
    from app.services import feedback

    weights = feedback.category_weights(ws_id)
    if not weights:
        return hypotheses
    ranked = sorted(
        hypotheses,
        key=lambda h: h["confidence"] * (1 + weights.get(h["category"], 0.0)),
        reverse=True,
    )
    for i, h in enumerate(ranked, start=1):
        h["rank"] = i
    return ranked


def _clear_hypotheses(brief_id):
    from app.db import core

    core.execute("DELETE FROM hypotheses WHERE brief_id=?", (brief_id,))


def _generate(brief, findings, offer, ws_id=None):
    def stub():
        out = []
        by_kind = {f["kind"]: f for f in findings}
        catalog = [
            ("pricing", "revenue_leak",
             "Quote-based pricing with no self-serve path likely means slow quote turnaround "
             "is costing deals."),
            ("hiring", "scaling",
             "Active hiring for operations roles suggests manual processes are straining as "
             "they scale."),
            ("news", "inefficiency",
             "Public mentions of manual invoicing and quoting point to an automation "
             "opportunity."),
            ("review", "acquisition",
             "Reviews mentioning slow response times suggest lead follow-up gaps."),
        ]
        rank = 1
        for kind, category, statement in catalog:
            if kind in by_kind:
                out.append(
                    {
                        "rank": rank,
                        "category": category,
                        "statement": statement,
                        "evidence": [by_kind[kind]["id"]],
                        "confidence": round(0.85 - 0.1 * (rank - 1), 2),
                    }
                )
                rank += 1
            if rank > 5:
                break
        if not out and findings:
            out.append(
                {
                    "rank": 1,
                    "category": "inefficiency",
                    "statement": "Limited public detail; a discovery-first angle fits best.",
                    "evidence": [findings[0]["id"]],
                    "confidence": 0.4,
                }
            )
        return out

    if config.USE_LLM_STUB:
        return stub()

    company = brief["company_summary"][:60]
    data = client.complete_json(
        config.MODEL_SMART,
        prompt_library.resolve(ws_id, "analysis"),
        prompts.analyze_user(company, offer, findings),
        lambda: {"hypotheses": stub()},
    )
    if isinstance(data, list):
        data = {"hypotheses": data}
    valid_ids = {f["id"] for f in findings}
    out = []
    hypotheses = [h for h in data.get("hypotheses", []) if isinstance(h, dict)]
    for i, h in enumerate(hypotheses[:5], start=1):
        evidence = [e for e in h.get("evidence", []) if e in valid_ids]
        out.append(
            {
                "rank": h.get("rank", i),
                "category": h.get("category", "inefficiency"),
                "statement": h.get("statement", ""),
                "evidence": evidence,
                "confidence": float(h.get("confidence", 0.5)),
            }
        )
    return out or stub()
