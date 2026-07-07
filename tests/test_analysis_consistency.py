from datetime import date, timedelta

from app.db import queries
from app.services import analyze, research, write


def _insert_lead(list_id, company, domain):
    return queries.insert_lead(list_id, {
        "company_name": company, "domain": domain, "contact_name": "",
        "contact_title": "", "email": "", "linkedin_url": "", "raw": {},
        "dedupe_hash": f"{company}:{domain}"[:16],
    })


def test_contradicted_hypothesis_dropped():
    findings = [{"id": 1, "kind": "tech",
                 "claim": "Flexport is increasingly run by AI with AI-driven tariff automation",
                 "snippet": "Our AI-powered logistics platform automates customs entries"}]
    hyps = [
        {"rank": 1, "category": "automation",
         "statement": "Flexport's logistics platform can be further optimized with AI automation",
         "evidence": [1], "confidence": 0.8},
        {"rank": 2, "category": "acquisition",
         "statement": "Slow quote follow-up is losing inbound deals",
         "evidence": [1], "confidence": 0.6},
    ]
    kept = analyze._drop_contradicted(hyps, findings)
    assert [h["rank"] for h in kept] == [2]


def test_hypothesis_kept_without_capability_evidence():
    findings = [{"id": 1, "kind": "hiring",
                 "claim": "They are hiring three dispatchers",
                 "snippet": "hiring 3 dispatchers and an ops manager"}]
    hyps = [{"rank": 1, "category": "automation",
             "statement": "Dispatch could be streamlined with AI automation",
             "evidence": [1], "confidence": 0.7}]
    assert analyze._drop_contradicted(hyps, findings) == hyps


def test_non_proposing_ai_mention_survives_ai_evidence():
    findings = [{"id": 1, "kind": "tech",
                 "claim": "The company is powered by AI across its platform",
                 "snippet": "powered by AI"}]
    hyps = [{"rank": 1, "category": "scaling",
             "statement": "Their AI platform is growing fast, straining support capacity",
             "evidence": [1], "confidence": 0.7}]
    assert analyze._drop_contradicted(hyps, findings) == hyps


def test_stale_evidence_neutralizes_temporal_language():
    stale = (date.today() - timedelta(days=5 * 365)).isoformat()
    findings = [{"id": 1, "published_at": stale}]
    hyps = [{"rank": 1, "category": "scaling",
             "statement": "Project44 recently raised a $202M investment and just announced expansion",
             "evidence": [1], "confidence": 0.7}]
    out = analyze._neutralize_stale(hyps, findings)
    lowered = out[0]["statement"].lower()
    assert "recent" not in lowered
    assert "just announced" not in lowered
    assert "$202m" in lowered


def test_fresh_evidence_keeps_temporal_language():
    fresh = (date.today() - timedelta(days=30)).isoformat()
    findings = [{"id": 1, "published_at": fresh}]
    statement = "They recently raised a round"
    hyps = [{"rank": 1, "category": "scaling", "statement": statement,
             "evidence": [1], "confidence": 0.7}]
    assert analyze._neutralize_stale(hyps, findings)[0]["statement"] == statement


def test_undated_evidence_left_untouched():
    findings = [{"id": 1, "published_at": ""}]
    statement = "They recently published a hiring post"
    hyps = [{"rank": 1, "category": "hiring", "statement": statement,
             "evidence": [1], "confidence": 0.7}]
    assert analyze._neutralize_stale(hyps, findings)[0]["statement"] == statement


def test_strip_temporal_framing_examples():
    out = research.strip_temporal_framing(
        "They recently launched a newly built hub and just raised $5M — "
        "their latest round this year."
    )
    lowered = out.lower()
    for banned in ["recently", "newly", "just raised", "latest", "this year"]:
        assert banned not in lowered
    assert "raised $5m" in lowered


def test_rich_brief_with_no_surviving_hypotheses_gets_no_angle_copy(workspace):
    list_id = queries.create_list(workspace["ws_id"], "NA", "csv")
    lead_id = _insert_lead(list_id, "Flexport", "flexport.com")
    queries.save_brief(lead_id, {
        "company_summary": "Flexport is an AI-run logistics platform.",
        "industry": "logistics", "size_estimate": "", "tech_stack": [],
        "positioning": "", "digest_md": "", "thin": 0, "quality": 100,
        "thin_reason": "",
    })
    offer = queries.get_offer_profile(workspace["profile_id"])
    created = write.generate_for_lead(lead_id, offer)
    email1 = next(a for a in created if a["kind"] == "email_1")
    assert email1["status"] == "flagged"
    assert "plenty of public detail" in email1["content"]
    assert "couldn't find enough public detail" not in email1["content"]


def test_email_on_stale_evidence_avoids_recent_framing(workspace):
    list_id = queries.create_list(workspace["ws_id"], "S", "csv")
    lead_id = _insert_lead(list_id, "Project44", "project44.com")
    brief_id = queries.save_brief(lead_id, {
        "company_summary": "Project44 is a logistics visibility platform.",
        "industry": "logistics", "size_estimate": "", "tech_stack": [],
        "positioning": "", "digest_md": "", "thin": 0, "quality": 80,
        "thin_reason": "",
    })
    fid = queries.insert_finding(brief_id, {
        "kind": "funding", "claim": "Project44 raised a $202M investment",
        "source_url": "https://techcrunch.com/project44-202m",
        "snippet": "raised $202M", "confidence": 0.8, "published_at": "2021-01-12",
    })
    queries.insert_hypothesis(brief_id, {
        "rank": 1, "category": "scaling",
        "statement": "Project44 recently raised a $202M investment and is scaling operations",
        "evidence": [fid], "confidence": 0.8,
    })
    offer = queries.get_offer_profile(workspace["profile_id"])
    created = write.generate_for_lead(lead_id, offer)
    email1 = next(a for a in created if a["kind"] == "email_1")
    assert "recently" not in email1["content"].lower()
    assert "$202m" in email1["content"].lower()
