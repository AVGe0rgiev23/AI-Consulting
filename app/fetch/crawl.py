import json
import time
from urllib import robotparser
from urllib.parse import urlsplit

from app import config
from app.db import queries

_PATHS = ["", "/about", "/services", "/pricing", "/blog", "/careers"]
_DEEP_PATHS = _PATHS + ["/team", "/customers", "/case-studies", "/news", "/products",
                        "/solutions", "/contact"]

_TECH_SIGNALS = {
    "hubspot": ["js.hs-scripts.com", "hubspot"],
    "intercom": ["widget.intercom.io", "intercom"],
    "calendly": ["calendly.com"],
    "shopify": ["cdn.shopify.com", "myshopify"],
    "wordpress": ["wp-content", "wp-includes", "wordpress"],
    "salesforce": ["salesforce", "pardot"],
    "google_analytics": ["googletagmanager.com", "google-analytics.com"],
    "segment": ["cdn.segment.com"],
    "klaviyo": ["klaviyo.com"],
    "zendesk": ["zdassets.com", "zendesk"],
    "drift": ["js.driftt.com"],
    "marketo": ["marketo.net", "munchkin"],
    "webflow": ["website-files.com", "webflow"],
    "wix": ["wixstatic.com"],
    "squarespace": ["squarespace"],
    "stripe": ["js.stripe.com"],
}


def crawl_domain(domain, deep=False):
    if not domain:
        return {"pages": [], "reason": "no_domain"}
    if not deep:
        cached = queries.get_cached_domain(domain, config.DOMAIN_CACHE_DAYS)
        if cached:
            return _parse_cached(cached["pages_json"])
    if config.USE_FETCH_STUB:
        result = {"pages": _stub_pages(domain, deep), "reason": ""}
    else:
        result = _live_crawl(domain, deep)
    queries.set_cached_domain(domain, json.dumps(result))
    return result


def _parse_cached(pages_json):
    data = json.loads(pages_json)
    if isinstance(data, list):
        return {"pages": data, "reason": ""}
    return data


def _stub_pages(domain, deep=False):
    name = domain.split(".")[0].replace("-", " ").title()
    base = f"https://{domain}"
    extra = []
    if deep:
        extra = [
            {
                "url": base + "/customers",
                "path": "customers",
                "text": f"{name} case study: customers report faster quote turnaround "
                f"after onboarding. Trusted by 40+ logistics teams across Europe.",
            }
        ]
    return extra + [
        {
            "url": base,
            "path": "home",
            "text": f"{name} helps mid-market companies move faster. "
            f"We serve logistics and operations teams across Europe.",
        },
        {
            "url": base + "/pricing",
            "path": "pricing",
            "text": f"{name} pricing is quote-based. Contact sales for a custom quote. "
            f"No self-serve checkout is available.",
        },
        {
            "url": base + "/careers",
            "path": "careers",
            "text": f"{name} is hiring 3 operations coordinators and a dispatch manager. "
            f"We are growing our support team.",
        },
        {
            "url": base + "/blog",
            "path": "blog",
            "text": f"{name} recently published an article on manual invoicing bottlenecks "
            f"and how spreadsheets slow down their quoting process.",
        },
    ]


def _live_crawl(domain, deep=False):
    import httpx

    if not _resolves(domain):
        return {"pages": [], "reason": "dns_failure"}
    budget_seconds = config.CRAWL_TIME_BUDGET_SECONDS * (2 if deep else 1)
    deadline = time.monotonic() + budget_seconds
    with httpx.Client(
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": config.CRAWL_USER_AGENT},
    ) as client:
        paths = _DEEP_PATHS if deep else _PATHS
        return _crawl_with_client(client, domain, deadline, paths)


def _crawl_with_client(client, domain, deadline, paths=None):
    base, robots_resp = _resolve_base(client, domain)
    if not base:
        return {"pages": [], "reason": "unreachable"}
    rules = _robots_rules(robots_resp)
    delay = _politeness_delay(rules)
    pages = []
    blocked = 0
    reason = ""
    fetched_any = False
    for path in (paths or _PATHS)[: config.CRAWL_MAX_PAGES]:
        url = base + path
        if time.monotonic() > deadline:
            reason = "time_budget"
            break
        if rules and not rules.can_fetch(config.CRAWL_USER_AGENT, url):
            blocked += 1
            continue
        if fetched_any:
            time.sleep(delay)
        resp = _get_with_retry(client, url, deadline)
        fetched_any = True
        page = _page_from_response(domain, url, path, resp)
        if page:
            pages.append(page)
    if not pages and not reason:
        reason = "robots_disallowed" if blocked else "no_content"
    return {"pages": pages, "reason": reason if not pages else ""}


def _resolves(domain):
    import socket

    for host in (domain, f"www.{domain}"):
        try:
            socket.getaddrinfo(host, 443)
            return True
        except OSError:
            continue
    return False


def _resolve_base(client, domain):
    import httpx

    for base in (f"https://{domain}", f"https://www.{domain}", f"http://{domain}"):
        try:
            resp = client.get(base + "/robots.txt")
            return base, resp
        except httpx.HTTPError:
            continue
    return None, None


def _robots_rules(robots_resp):
    if robots_resp is None or robots_resp.status_code != 200:
        return None
    content_type = robots_resp.headers.get("content-type", "")
    if content_type and "text" not in content_type:
        return None
    rules = robotparser.RobotFileParser()
    rules.parse(robots_resp.text.splitlines())
    return rules


def _politeness_delay(rules):
    delay = config.CRAWL_DELAY_SECONDS
    if rules:
        stated = rules.crawl_delay(config.CRAWL_USER_AGENT) or 0
        delay = max(delay, float(stated))
    return min(delay, config.CRAWL_MAX_DELAY_SECONDS)


def _get_with_retry(client, url, deadline):
    import httpx

    backoff = 0.5
    for attempt in range(1 + config.CRAWL_RETRIES):
        if time.monotonic() > deadline:
            return None
        try:
            resp = client.get(url)
            if resp.status_code >= 500 and attempt < config.CRAWL_RETRIES:
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        except httpx.HTTPError:
            if attempt < config.CRAWL_RETRIES:
                time.sleep(backoff)
                backoff *= 2
    return None


def _page_from_response(domain, url, path, resp):
    if resp is None or resp.status_code >= 400:
        return None
    final_url = str(getattr(resp, "url", url))
    if _norm_host(final_url) != _norm_host(f"https://{domain}"):
        return None
    content_type = resp.headers.get("content-type", "")
    if content_type and "html" not in content_type and "text" not in content_type:
        return None
    if len(resp.content) > config.CRAWL_MAX_PAGE_BYTES:
        return None
    text = _extract_text(resp.text)
    if len(text.strip()) < 40:
        return None
    return {
        "url": url,
        "path": path.strip("/") or "home",
        "text": text[:4000],
        "tech_hints": _tech_hints(resp),
    }


def _tech_hints(resp):
    header_blob = " ".join(f"{k}:{v}" for k, v in resp.headers.items())
    blob = (resp.text[:200_000] + " " + header_blob).lower()
    return [name for name, markers in _TECH_SIGNALS.items()
            if any(marker in blob for marker in markers)]


def _norm_host(url):
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _extract_text(html):
    try:
        import trafilatura
    except ImportError:
        return html[:4000]
    return trafilatura.extract(html) or ""
