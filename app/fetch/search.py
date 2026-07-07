import json
from datetime import date, timedelta

from app import config
from app.db import queries
from app.services import budget

SOURCE_QUERIES = [
    ("news", "{company} news", None),
    ("hiring", "{company} hiring jobs",
     ["linkedin.com", "indeed.com", "greenhouse.io", "lever.co"]),
    ("funding", "{company} funding investment",
     ["crunchbase.com", "dealroom.co", "techcrunch.com"]),
    ("review", "{company} reviews",
     ["g2.com", "capterra.com", "trustpilot.com"]),
]


def search_company(company_name, domain, force=False):
    if config.USE_FETCH_STUB or not config.SEARCH_API_KEY:
        return _stub_results(company_name)
    cache_key = (domain or company_name).strip().lower()
    if not force:
        cached = queries.get_cached_search(cache_key, config.SEARCH_CACHE_DAYS)
        if cached:
            return json.loads(cached["results_json"])
    out = []
    for kind, template, include_domains in SOURCE_QUERIES:
        try:
            budget.guard("search", config.SEARCH_COST_USD)
        except budget.BudgetExceeded:
            break
        query = template.format(company=company_name)
        out.extend(_live_query(kind, query, include_domains))
        budget.record("search", config.SEARCH_COST_USD)
    if out:
        queries.set_cached_search(cache_key, json.dumps(out))
    return out


def _stub_results(company_name):
    slug = company_name.lower().replace(" ", "-")
    fresh = (date.today() - timedelta(days=7)).isoformat()
    stale = (date.today() - timedelta(days=200)).isoformat()
    return [
        {
            "kind": "hiring",
            "title": f"{company_name} is expanding its operations team",
            "url": f"https://news.example/{slug}-hiring",
            "snippet": f"{company_name} announced plans to add several roles this quarter.",
            "published_at": fresh,
        },
        {
            "kind": "review",
            "title": f"{company_name} reviews",
            "url": f"https://reviews.example/{slug}",
            "snippet": f"Customers praise {company_name} but mention slow response times on quotes.",
            "published_at": stale,
        },
    ]


def _live_query(kind, query, include_domains):
    import httpx

    payload = {
        "api_key": config.SEARCH_API_KEY,
        "query": query,
        "max_results": 3,
        "topic": "news" if kind == "news" else "general",
    }
    if include_domains:
        payload["include_domains"] = include_domains
    try:
        resp = httpx.post("https://api.tavily.com/search", json=payload, timeout=10)
        data = resp.json()
        out = []
        for item in data.get("results", []):
            out.append(
                {
                    "kind": kind,
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:400],
                    "published_at": item.get("published_date", "") or "",
                }
            )
        return out
    except (httpx.HTTPError, ValueError):
        return []
