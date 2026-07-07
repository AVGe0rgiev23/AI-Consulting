from app.db import queries
from app.services import analyze, research


def test_research_produces_cited_findings(sample_list):
    lead = queries.leads_for_list(sample_list["list_id"])[0]
    brief_id = research.research_lead(lead["id"])
    assert brief_id
    findings = queries.findings_for_brief(brief_id)
    assert findings
    assert all(f["source_url"] for f in findings)
    assert queries.get_lead(lead["id"])["status"] == "researched"


def test_analyze_ranks_hypotheses_with_evidence(sample_list):
    lead = queries.leads_for_list(sample_list["list_id"])[0]
    research.research_lead(lead["id"])
    offer = queries.get_offer_profile(sample_list["profile_id"])
    ids = analyze.analyze_lead(lead["id"], offer)
    assert ids
    brief = queries.get_brief_by_lead(lead["id"])
    hyps = queries.hypotheses_for_brief(brief["id"])
    assert hyps[0]["rank"] == 1
    import json
    assert json.loads(hyps[0]["evidence_json"])
