from datetime import date

from tests.conftest import login_as, make_client
from app import config
from app.db import queries
from app.jobs import pipeline
from app.services import research, write


def _insert_lead(list_id, company, domain):
    return queries.insert_lead(list_id, {
        "company_name": company, "domain": domain, "contact_name": "",
        "contact_title": "", "email": "", "linkedin_url": "", "raw": {},
        "dedupe_hash": f"{company}:{domain}"[:16],
    })


def test_no_domain_lead_is_marked_thin(workspace):
    list_id = queries.create_list(workspace["ws_id"], "T", "csv")
    lead_id = _insert_lead(list_id, "Ghost Co", "")
    research.research_lead(lead_id)
    brief = queries.get_brief_by_lead(lead_id)
    assert brief["thin"] == 1
    assert brief["thin_reason"] == "no website on file"
    assert brief["quality"] < config.QUALITY_FLOOR


def test_normal_stub_lead_is_not_thin(sample_list):
    lead = queries.leads_for_list(sample_list["list_id"])[0]
    research.research_lead(lead["id"])
    brief = queries.get_brief_by_lead(lead["id"])
    assert brief["thin"] == 0
    assert brief["quality"] >= config.QUALITY_FLOOR
    assert brief["thin_reason"] == ""


def test_thin_lead_gets_generic_flagged_assets(workspace):
    list_id = queries.create_list(workspace["ws_id"], "T", "csv")
    lead_id = _insert_lead(list_id, "Ghost Co", "")
    research.research_lead(lead_id)
    offer = queries.get_offer_profile(workspace["profile_id"])
    created = write.generate_for_lead(lead_id, offer)
    assert created
    for asset in created:
        assert asset["status"] == "flagged"
        assert asset["breakdown"]["insufficient_research"] is True
        assert asset["hypothesis_id"] is None
    email1 = next(a for a in created if a["kind"] == "email_1")
    assert "couldn't find enough public detail" in email1["content"]


def test_pipeline_routes_thin_lead_to_needs_review(workspace):
    list_id = queries.create_list(workspace["ws_id"], "T", "csv")
    thin_id = _insert_lead(list_id, "Ghost Co", "")
    ok_id = _insert_lead(list_id, "Acme Logistics", "acme-logistics.com")
    queries.set_list_counts(list_id, 2, 0)
    pipeline.process_list_now(workspace["ws_id"], list_id)
    assert queries.get_lead(thin_id)["status"] == "needs_review"
    assert queries.get_lead(ok_id)["status"] == "ready"


def test_grounding_drops_unbacked_claims():
    pages = [{"url": "https://acme.com", "path": "home",
              "text": "Acme ships freight across Europe with a dispatch team of forty."}]
    findings = [
        {"kind": "other", "claim": "Acme ships freight across Europe",
         "source_url": "https://acme.com", "snippet": ""},
        {"kind": "other", "claim": "Acme raised a $30M Series B round",
         "source_url": "https://acme.com", "snippet": ""},
        {"kind": "tech", "claim": "Acme uses HubSpot",
         "source_url": "https://invented.example/page", "snippet": ""},
    ]
    kept = research.ground_findings(findings, pages, [])
    assert [f["claim"] for f in kept] == ["Acme ships freight across Europe"]


def test_grounding_keeps_snippet_backed_finding():
    pages = [{"url": "https://acme.com/blog", "path": "blog",
              "text": "We announced our expansion to Berlin in March."}]
    findings = [{"kind": "news", "claim": "Berlin move confirmed",
                 "source_url": "https://acme.com/blog",
                 "snippet": "our expansion to Berlin"}]
    kept = research.ground_findings(findings, pages, [])
    assert len(kept) == 1


def test_zero_grounded_findings_force_thin_despite_rich_research():
    pages = [{"url": f"https://r.com/p{i}", "path": "home", "text": "x" * 2000}
             for i in range(4)]
    results = [{"kind": "news", "title": "t", "url": f"https://n.example/{i}",
                "snippet": "s", "published_at": date.today().isoformat()}
               for i in range(3)]
    assert research.research_quality(pages, results, []) < config.QUALITY_FLOOR


def test_single_grounded_finding_restores_normal_scoring():
    pages = [{"url": f"https://r.com/p{i}", "path": "home", "text": "x" * 2000}
             for i in range(4)]
    results = [{"kind": "news", "title": "t", "url": f"https://n.example/{i}",
                "snippet": "s", "published_at": date.today().isoformat()}
               for i in range(3)]
    findings = [{"source_url": "https://r.com/p0", "snippet": "x"}]
    assert research.research_quality(pages, results, findings) >= config.QUALITY_FLOOR


def test_zero_finding_lead_routes_to_honest_fallback(workspace, monkeypatch):
    monkeypatch.setattr(research, "ground_findings", lambda findings, pages, results: [])
    list_id = queries.create_list(workspace["ws_id"], "Z", "csv")
    lead_id = _insert_lead(list_id, "Acme Logistics", "acme-logistics.com")
    research.research_lead(lead_id)
    brief = queries.get_brief_by_lead(lead_id)
    assert brief["thin"] == 1
    assert brief["quality"] < config.QUALITY_FLOOR
    assert brief["thin_reason"] == "nothing verifiable found on the site or the web"
    offer = queries.get_offer_profile(workspace["profile_id"])
    created = write.generate_for_lead(lead_id, offer)
    email1 = next(a for a in created if a["kind"] == "email_1")
    assert email1["status"] == "flagged"
    assert "couldn't find enough public detail" in email1["content"]


def test_research_quality_scores_scale_with_evidence():
    assert research.research_quality([], [], []) == 0
    pages = [{"url": "u", "path": "home", "text": "x" * 500}] * 3
    results = [{"kind": "news", "title": "t", "url": "u2", "snippet": "s"}]
    findings = [{"source_url": "u", "snippet": "x"}] * 3
    assert research.research_quality(pages, results, findings) >= config.QUALITY_FLOOR


def test_approval_blocked_below_score_floor(sample_list):
    lead = queries.leads_for_list(sample_list["list_id"])[0]
    queries.set_lead_status(lead["id"], "ready")
    low_id = queries.insert_asset(lead["id"], {
        "kind": "email_1", "subject": "s", "content": "low effort",
        "score": config.APPROVAL_SCORE_FLOOR - 1, "breakdown": {}, "status": "draft",
    })
    client = login_as(sample_list["user_id"])
    resp = client.post(f"/assets/{low_id}/approve",
                       data={"list_id": sample_list["list_id"], "i": 0},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "err=floor" in resp.headers["location"]
    assert queries.get_lead(lead["id"])["status"] == "ready"

    good_id = queries.insert_asset(lead["id"], {
        "kind": "email_1", "subject": "s", "content": "solid draft",
        "score": config.APPROVAL_SCORE_FLOOR + 40, "breakdown": {}, "status": "draft",
    })
    resp = client.post(f"/assets/{good_id}/approve",
                       data={"list_id": sample_list["list_id"], "i": 0},
                       follow_redirects=False)
    assert "err" not in resp.headers["location"]
    assert queries.get_lead(lead["id"])["status"] == "approved"


def test_review_page_shows_thin_reason():
    client, ctx = make_client()
    list_id = queries.create_list(ctx["ws_id"], "T", "csv")
    lead_id = _insert_lead(list_id, "Ghost Co", "")
    research.research_lead(lead_id)
    offer = queries.default_offer_profile(ctx["ws_id"])
    write.generate_for_lead(lead_id, offer)
    queries.set_lead_status(lead_id, "needs_review")
    resp = client.get(f"/review/{list_id}?i=0")
    assert resp.status_code == 200
    assert "no website on file" in resp.text
    assert "Insufficient data" in resp.text
