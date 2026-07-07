from datetime import date, timedelta

import httpx

from tests.conftest import login_as
from app import config
from app.db import queries
from app.fetch import crawl, search
from app.services import research, write
from app.services import credits as credits_service

from tests.test_crawl_safety import FakeResponse


def _insert_lead(list_id, company, domain):
    return queries.insert_lead(list_id, {
        "company_name": company, "domain": domain, "contact_name": "",
        "contact_title": "", "email": "", "linkedin_url": "", "raw": {},
        "dedupe_hash": f"{company}:{domain}"[:16],
    })


def test_recency_weight_tiers():
    today = date.today()
    assert research.recency_weight((today - timedelta(days=5)).isoformat()) == 1.15
    assert research.recency_weight((today - timedelta(days=60)).isoformat()) == 1.0
    assert research.recency_weight((today - timedelta(days=200)).isoformat()) == 0.7
    assert research.recency_weight((today - timedelta(days=700)).isoformat()) == 0.4
    assert research.recency_weight("") == 1.0
    assert research.recency_weight("Tue, 05 May 2020 10:00:00 GMT") == 0.4
    assert research.recency_weight("not a date") == 1.0


def test_stale_search_signal_confidence_discounted(sample_list):
    lead = queries.leads_for_list(sample_list["list_id"])[0]
    brief_id = research.research_lead(lead["id"])
    findings = queries.findings_for_brief(brief_id)
    by_kind = {f["kind"]: f for f in findings}
    assert by_kind["review"]["confidence"] < 0.5
    assert by_kind["hiring"]["confidence"] > 0.55
    assert by_kind["review"]["published_at"]


def test_research_quality_discounts_stale_results():
    pages = []
    findings = []
    fresh = [{"kind": "news", "title": "t", "url": "u", "snippet": "s",
              "published_at": date.today().isoformat()}] * 2
    stale = [{"kind": "news", "title": "t", "url": "u", "snippet": "s",
              "published_at": (date.today() - timedelta(days=700)).isoformat()}] * 2
    assert (research.research_quality(pages, fresh, findings)
            > research.research_quality(pages, stale, findings))


def test_multi_source_queries_hit_named_sources(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_API_KEY", "tvly-test")
    payloads = []

    class FakePost:
        def json(self):
            return {"results": [{"title": "T", "url": "https://x.example/1",
                                 "content": "c", "published_date": "2026-07-01"}]}

    def fake_post(url, json=None, timeout=None):
        payloads.append(json)
        return FakePost()

    monkeypatch.setattr(httpx, "post", fake_post)
    results = search._live_query("funding", "Acme funding investment",
                                 ["crunchbase.com", "dealroom.co", "techcrunch.com"])
    assert payloads[0]["include_domains"] == ["crunchbase.com", "dealroom.co", "techcrunch.com"]
    assert results[0]["kind"] == "funding"
    assert results[0]["published_at"] == "2026-07-01"

    kinds = [q[0] for q in search.SOURCE_QUERIES]
    assert {"news", "hiring", "funding", "review"} <= set(kinds)


def test_tech_hints_from_html_and_headers():
    resp = FakeResponse(
        "https://t.com",
        text='<html><script src="https://js.hs-scripts.com/123.js"></script>'
             '<link href="/wp-content/theme.css"><script src="https://js.stripe.com/v3"></script>'
             '<p>' + 'Real page content about freight operations. ' * 5 + '</p></html>',
        headers={"content-type": "text/html", "x-powered-by": "PHP"},
    )
    hints = crawl._tech_hints(resp)
    assert "hubspot" in hints
    assert "wordpress" in hints
    assert "stripe" in hints

    page = crawl._page_from_response("t.com", "https://t.com", "", resp)
    assert page and "hubspot" in page["tech_hints"]


def test_detect_tech_prefers_real_signals(sample_list):
    pages = [{"url": "u", "path": "home", "text": "plain text mentioning calendly",
              "tech_hints": ["hubspot", "stripe"]}]
    tech = research._detect_tech(pages)
    assert tech[:2] == ["hubspot", "stripe"]
    assert "calendly" in tech


def test_deep_crawl_bypasses_cache_and_goes_wider(workspace):
    import json as jsonlib

    queries.set_cached_domain("acme-logistics.com",
                              jsonlib.dumps({"pages": [], "reason": "unreachable"}))
    shallow = crawl.crawl_domain("acme-logistics.com")
    assert shallow["pages"] == []
    deep = crawl.crawl_domain("acme-logistics.com", deep=True)
    assert len(deep["pages"]) == 5
    assert any(p["path"] == "customers" for p in deep["pages"])
    refreshed = crawl.crawl_domain("acme-logistics.com")
    assert len(refreshed["pages"]) == 5


def test_deep_research_route_charges_and_regenerates(sample_list):
    list_id = sample_list["list_id"]
    lead_id = _insert_lead(list_id, "Ghost Co", "")
    research.research_lead(lead_id)
    offer = queries.get_offer_profile(sample_list["profile_id"])
    write.generate_for_lead(lead_id, offer)
    queries.set_lead_status(lead_id, "needs_review", "no website on file")
    before = credits_service.balance(sample_list["ws_id"])

    client = login_as(sample_list["user_id"])
    resp = client.post(f"/leads/{lead_id}/deep-research",
                       data={"list_id": list_id, "i": 0}, follow_redirects=False)
    assert resp.status_code == 303
    assert "err" not in resp.headers["location"]
    assert credits_service.balance(sample_list["ws_id"]) == before - config.RESEARCH_COST
    assert queries.get_lead(lead_id)["status"] == "needs_review"
    assert queries.assets_for_lead(lead_id)


def test_deep_research_route_rejects_foreign_lead(sample_list):
    from tests.conftest import make_client

    other_client, _ = make_client("other@example.com")
    lead = queries.leads_for_list(sample_list["list_id"])[0]
    resp = other_client.post(f"/leads/{lead['id']}/deep-research",
                             data={"list_id": sample_list["list_id"], "i": 0},
                             follow_redirects=False)
    assert resp.status_code == 404


def test_review_page_shows_hitl_framing_and_deep_button(sample_list):
    list_id = sample_list["list_id"]
    lead_id = _insert_lead(list_id, "Ghost Co", "")
    research.research_lead(lead_id)
    offer = queries.get_offer_profile(sample_list["profile_id"])
    write.generate_for_lead(lead_id, offer)
    queries.set_lead_status(lead_id, "needs_review", "no website on file")

    client = login_as(sample_list["user_id"])
    resp = client.get(f"/review/{list_id}?i=0")
    assert "the AI drafts, you approve" in resp.text
    assert "Dig deeper" in resp.text
