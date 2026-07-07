import json
import time

import httpx
import pytest

from app import config
from app.db import queries
from app.fetch import crawl


class FakeResponse:
    def __init__(self, url, status_code=200, text="", headers=None, content=None):
        self.url = url
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"content-type": "text/html"}
        self.content = content if content is not None else text.encode()


class FakeClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        result = self.routes.get(url)
        if result is None:
            return FakeResponse(url, status_code=404)
        if isinstance(result, Exception):
            raise result
        if isinstance(result, list):
            item = result.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return result


@pytest.fixture(autouse=True)
def fast_and_raw(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(crawl, "_extract_text", lambda html: html)


def _deadline():
    return time.monotonic() + config.CRAWL_TIME_BUDGET_SECONDS


HOME_TEXT = "Acme ships freight across Europe with a dispatch team of forty people."


def test_robots_disallow_all_blocks_crawl():
    robots = FakeResponse("https://blocked.com/robots.txt",
                          text="User-agent: *\nDisallow: /",
                          headers={"content-type": "text/plain"})
    client = FakeClient({"https://blocked.com/robots.txt": robots})
    result = crawl._crawl_with_client(client, "blocked.com", _deadline())
    assert result == {"pages": [], "reason": "robots_disallowed"}
    assert all(url.endswith("robots.txt") for url in client.calls)


def test_robots_partial_disallow_skips_that_path():
    robots = FakeResponse("https://site.com/robots.txt",
                          text="User-agent: *\nDisallow: /pricing",
                          headers={"content-type": "text/plain"})
    client = FakeClient({
        "https://site.com/robots.txt": robots,
        "https://site.com": FakeResponse("https://site.com", text=HOME_TEXT),
    })
    result = crawl._crawl_with_client(client, "site.com", _deadline())
    assert [p["path"] for p in result["pages"]] == ["home"]
    assert "https://site.com/pricing" not in client.calls


def test_retry_recovers_from_transient_500():
    client = FakeClient({
        "https://r.com/robots.txt": FakeResponse("https://r.com/robots.txt", status_code=404),
        "https://r.com": [
            FakeResponse("https://r.com", status_code=500),
            FakeResponse("https://r.com", text=HOME_TEXT),
        ],
    })
    result = crawl._crawl_with_client(client, "r.com", _deadline())
    assert [p["path"] for p in result["pages"]] == ["home"]
    assert client.calls.count("https://r.com") == 2


def test_retry_recovers_from_connection_error():
    client = FakeClient({
        "https://r.com/robots.txt": FakeResponse("https://r.com/robots.txt", status_code=404),
        "https://r.com": [httpx.ConnectError("boom"), FakeResponse("https://r.com", text=HOME_TEXT)],
    })
    result = crawl._crawl_with_client(client, "r.com", _deadline())
    assert [p["path"] for p in result["pages"]] == ["home"]


def test_unreachable_domain_reports_reason():
    client = FakeClient({
        "https://dead.com/robots.txt": httpx.ConnectError("x"),
        "https://www.dead.com/robots.txt": httpx.ConnectError("x"),
        "http://dead.com/robots.txt": httpx.ConnectError("x"),
    })
    result = crawl._crawl_with_client(client, "dead.com", _deadline())
    assert result == {"pages": [], "reason": "unreachable"}


def test_falls_back_to_www_variant():
    client = FakeClient({
        "https://x.com/robots.txt": httpx.ConnectError("no apex"),
        "https://www.x.com/robots.txt": FakeResponse("https://www.x.com/robots.txt",
                                                     status_code=404),
        "https://www.x.com": FakeResponse("https://www.x.com", text=HOME_TEXT),
    })
    result = crawl._crawl_with_client(client, "x.com", _deadline())
    assert [p["path"] for p in result["pages"]] == ["home"]


def test_offsite_redirect_is_skipped():
    client = FakeClient({
        "https://y.com/robots.txt": FakeResponse("https://y.com/robots.txt", status_code=404),
        "https://y.com": FakeResponse("https://login.other.com/auth", text=HOME_TEXT),
    })
    result = crawl._crawl_with_client(client, "y.com", _deadline())
    assert result["pages"] == []
    assert result["reason"] == "no_content"


def test_non_html_content_is_skipped():
    client = FakeClient({
        "https://z.com/robots.txt": FakeResponse("https://z.com/robots.txt", status_code=404),
        "https://z.com": FakeResponse("https://z.com", text=HOME_TEXT,
                                      headers={"content-type": "application/pdf"}),
    })
    result = crawl._crawl_with_client(client, "z.com", _deadline())
    assert result["pages"] == []


def test_giant_page_is_skipped(monkeypatch):
    monkeypatch.setattr(config, "CRAWL_MAX_PAGE_BYTES", 100)
    client = FakeClient({
        "https://g.com/robots.txt": FakeResponse("https://g.com/robots.txt", status_code=404),
        "https://g.com": FakeResponse("https://g.com", text="x" * 500),
    })
    result = crawl._crawl_with_client(client, "g.com", _deadline())
    assert result["pages"] == []


def test_time_budget_stops_crawl():
    client = FakeClient({
        "https://slow.com/robots.txt": FakeResponse("https://slow.com/robots.txt",
                                                    status_code=404),
        "https://slow.com": FakeResponse("https://slow.com", text=HOME_TEXT),
    })
    result = crawl._crawl_with_client(client, "slow.com", time.monotonic() - 1)
    assert result == {"pages": [], "reason": "time_budget"}


def test_politeness_delay_respects_robots_with_cap():
    robots = FakeResponse("https://s.com/robots.txt",
                          text="User-agent: *\nCrawl-delay: 99\nDisallow: /private",
                          headers={"content-type": "text/plain"})
    rules = crawl._robots_rules(robots)
    assert crawl._politeness_delay(rules) == config.CRAWL_MAX_DELAY_SECONDS
    assert crawl._politeness_delay(None) == config.CRAWL_DELAY_SECONDS


def test_user_agent_identifies_bot_with_contact_url():
    assert "LeadGeniusBot" in config.CRAWL_USER_AGENT
    assert "+http" in config.CRAWL_USER_AGENT


def test_old_cache_format_still_readable():
    pages = [{"url": "https://c.com", "path": "home", "text": "cached text"}]
    queries.set_cached_domain("c.com", json.dumps(pages))
    result = crawl.crawl_domain("c.com")
    assert result == {"pages": pages, "reason": ""}
