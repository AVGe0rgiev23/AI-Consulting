import re
from datetime import date, datetime, timezone

from app import config
from app.db import queries
from app.fetch import crawl, search
from app.llm import client, prompt_library, prompts

_THIN_REASONS = {
    "no_domain": "no website on file",
    "dns_failure": "domain does not resolve (dead or mistyped)",
    "unreachable": "website unreachable",
    "robots_disallowed": "site blocks crawlers (robots.txt)",
    "time_budget": "crawl ran out of time before finding enough content",
    "no_content": "no readable content on the site",
}


def research_lead(lead_id, deep=False):
    lead = queries.get_lead(lead_id)
    if not lead:
        return None
    queries.set_lead_status(lead_id, "researching")
    company = lead["company_name"] or lead["domain"] or "the company"
    lst = queries.get_list(lead["list_id"])
    ws_id = lst["workspace_id"] if lst else None

    crawl_result = crawl.crawl_domain(lead["domain"], deep=deep)
    pages = crawl_result["pages"]
    results = search.search_company(company, lead["domain"], force=deep)

    extracted = _extract_findings(company, pages, results, ws_id)
    findings = ground_findings(extracted["findings"], pages, results)
    findings = _apply_recency(findings, results)
    tech = _detect_tech(pages)
    quality = research_quality(pages, results, findings)
    thin = quality < config.QUALITY_FLOOR

    brief = {
        "company_summary": extracted.get("summary", f"{company} is a B2B company."),
        "industry": extracted.get("industry", ""),
        "size_estimate": extracted.get("size", ""),
        "tech_stack": tech,
        "positioning": extracted.get("positioning", ""),
        "digest_md": "",
        "thin": thin,
        "quality": quality,
        "thin_reason": _thin_reason(crawl_result, pages, findings) if thin else "",
    }
    brief["digest_md"] = _digest(company, brief, findings)

    brief_id = queries.save_brief(lead_id, brief)
    queries.clear_findings(brief_id)
    for f in findings:
        queries.insert_finding(brief_id, f)
    queries.set_lead_status(lead_id, "researched")
    return brief_id


def confidence_label(quality):
    if quality >= config.CONFIDENCE_HIGH:
        return "high"
    if quality >= config.QUALITY_FLOOR:
        return "medium"
    return "low"


def research_quality(pages, results, findings):
    text_chars = sum(len(p["text"]) for p in pages)
    sourced = [f for f in findings if f.get("source_url") and f.get("snippet")]
    page_score = min(30, 10 * len(pages))
    depth_score = min(20, text_chars // 400)
    finding_score = min(35, 9 * len(sourced))
    search_weight = sum(recency_weight(r.get("published_at", "")) for r in results)
    search_score = min(15, round(5 * search_weight))
    total = min(100, page_score + depth_score + finding_score + search_score)
    if not findings:
        return min(total, config.QUALITY_FLOOR - 1)
    return total


def recency_weight(published_at):
    age = _age_days(published_at)
    if age is None:
        return 1.0
    if age <= 30:
        return 1.15
    if age <= 90:
        return 1.0
    if age <= 365:
        return 0.7
    return 0.4


def _age_days(published_at):
    value = (published_at or "").strip()
    if not value:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if match:
        return (date.today() - date.fromisoformat(match.group())).days
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed).days
    except (TypeError, ValueError):
        return None


_TEMPORAL_PATTERNS = [
    (re.compile(r"\brecently\b", re.IGNORECASE), "previously"),
    (re.compile(r"\bjust (announced|raised|closed|launched|secured|landed|hired)\b",
                re.IGNORECASE), r"\1"),
    (re.compile(r"\brecent\b", re.IGNORECASE), "past"),
    (re.compile(r"\bnewly\b ?", re.IGNORECASE), ""),
    (re.compile(r"\bbrand-new\b", re.IGNORECASE), "existing"),
    (re.compile(r"\blatest\b", re.IGNORECASE), "past"),
    (re.compile(r"\bthis (week|month|quarter|year)\b", re.IGNORECASE), "at the time"),
]


def strip_temporal_framing(text):
    for pattern, replacement in _TEMPORAL_PATTERNS:
        text = pattern.sub(replacement, text)
    return re.sub(r" {2,}", " ", text)


def stale_evidence_only(findings, evidence_ids):
    by_id = {f["id"]: f for f in findings if "id" in f}
    ages = []
    for fid in evidence_ids or []:
        f = by_id.get(fid)
        if f and f.get("published_at"):
            age = _age_days(f["published_at"])
            if age is not None:
                ages.append(age)
    return bool(ages) and all(age > config.STALE_SIGNAL_DAYS for age in ages)


def _apply_recency(findings, results):
    dates = {_norm_url(r["url"]): r.get("published_at", "") for r in results}
    for f in findings:
        published = dates.get(_norm_url(f.get("source_url", "")), "")
        if published:
            f["published_at"] = published
            f["confidence"] = round(
                min(1.0, f["confidence"] * recency_weight(published)), 2
            )
    return findings


def ground_findings(findings, pages, results):
    sources = {}
    for p in pages:
        sources[_norm_url(p["url"])] = _norm_text(p["text"])
    for s in results:
        sources[_norm_url(s["url"])] = _norm_text(s["title"] + " " + s["snippet"])
    kept = []
    for f in findings:
        source_text = sources.get(_norm_url(f.get("source_url", "")))
        if source_text is None:
            continue
        words = _significant_words(f.get("claim", ""))
        hits = sum(1 for w in words if w in source_text)
        snippet = _norm_text(f.get("snippet", ""))
        snippet_backed = bool(snippet) and snippet[:150] in source_text
        if words and hits >= min(2, len(words)):
            kept.append(f)
        elif snippet_backed and hits >= 1:
            kept.append(f)
    return kept


def _norm_url(url):
    u = (url or "").strip().lower()
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            u = u[len(prefix):]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def _norm_text(text):
    return " ".join((text or "").lower().split())


def _significant_words(claim):
    return [w for w in re.findall(r"[a-z']+", (claim or "").lower()) if len(w) > 4]


def _thin_reason(crawl_result, pages, findings):
    if not pages:
        return _THIN_REASONS.get(crawl_result["reason"], "no usable pages found")
    if not findings:
        return "nothing verifiable found on the site or the web"
    return "site content too shallow for confident personalization"


def _extract_findings(company, pages, results, ws_id=None):
    def stub():
        findings = []
        for p in pages:
            findings.append(
                {
                    "kind": _kind_for_path(p["path"]),
                    "claim": _claim_for_path(company, p),
                    "source_url": p["url"],
                    "snippet": p["text"][:200],
                    "confidence": 0.8 if p["path"] in ("pricing", "careers") else 0.6,
                }
            )
        for s in results:
            findings.append(
                {
                    "kind": s["kind"],
                    "claim": s["title"],
                    "source_url": s["url"],
                    "snippet": s["snippet"],
                    "confidence": 0.55,
                }
            )
        return {
            "summary": f"{company} is a B2B company serving operations teams.",
            "industry": "logistics",
            "size": "estimated 20-60 employees",
            "positioning": "quote-based, sales-led",
            "findings": findings,
        }

    if config.USE_LLM_STUB:
        return stub()
    if not pages and not results:
        return {"summary": f"{company} is a B2B company.", "industry": "",
                "size": "", "positioning": "", "findings": []}

    system = prompt_library.resolve(ws_id, "research")
    user = prompts.extract_user(company, pages, results)
    data = client.complete_json(config.MODEL_FAST, system, user, lambda: {"findings": []})
    findings = _clean_findings(data)
    if not findings:
        data = client.complete_json(config.MODEL_SMART, system, user,
                                    lambda: {"findings": []})
        findings = _clean_findings(data)
    if isinstance(data, list):
        data = {}
    return {
        "summary": data.get("summary") or f"{company} is a B2B company.",
        "industry": data.get("industry", ""),
        "size": data.get("size", ""),
        "positioning": data.get("positioning", ""),
        "findings": findings,
    }


def _clean_findings(data):
    if isinstance(data, list):
        data = {"findings": data}
    findings = [f for f in data.get("findings", []) if isinstance(f, dict)]
    for f in findings:
        f["kind"] = str(f.get("kind") or "other")
        f["claim"] = str(f.get("claim") or "").strip()
        f["source_url"] = str(f.get("source_url") or "").strip()
        f["snippet"] = str(f.get("snippet") or "").strip()
        f["published_at"] = str(f.get("published_at") or "")
        try:
            f["confidence"] = float(f.get("confidence") or 0.5)
        except (TypeError, ValueError):
            f["confidence"] = 0.5
    return [f for f in findings if f["source_url"] and f["claim"]]


def _kind_for_path(path):
    return {"pricing": "pricing", "careers": "hiring", "blog": "news"}.get(path, "other")


def _claim_for_path(company, page):
    text = page["text"].lower()
    if page["path"] == "pricing":
        return f"{company} uses quote-based pricing with no self-serve checkout."
    if page["path"] == "careers":
        return f"{company} is actively hiring operations and dispatch roles."
    if page["path"] == "blog" and "manual" in text:
        return f"{company} has written about manual invoicing and quoting bottlenecks."
    return f"{company}: {page['text'][:80]}"


def _detect_tech(pages):
    tech = []
    for p in pages:
        for hint in p.get("tech_hints", []):
            if hint not in tech:
                tech.append(hint)
    joined = " ".join(p["text"].lower() for p in pages)
    for marker in ["calendly", "hubspot", "shopify", "wordpress", "intercom", "salesforce"]:
        if marker in joined and marker not in tech:
            tech.append(marker)
    return tech


def _digest(company, brief, findings):
    lines = [f"# {company}", "", brief["company_summary"], ""]
    if brief["industry"]:
        lines.append(f"- Industry: {brief['industry']}")
    if brief["size_estimate"]:
        lines.append(f"- Size: {brief['size_estimate']}")
    if brief["tech_stack"]:
        lines.append(f"- Tech: {', '.join(brief['tech_stack'])}")
    lines.append(f"- Research quality: {brief['quality']}/100")
    lines.append("")
    lines.append("## Findings")
    for f in findings:
        lines.append(f"- ({f['kind']}) {f['claim']} — {f['source_url']}")
    return "\n".join(lines)
