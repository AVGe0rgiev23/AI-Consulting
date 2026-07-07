from app import config
from app.db import queries
from app.llm import client
from app.services import analyze, research, write


_PAGES = [{"url": "https://acme.com", "path": "home", "text": "Acme ships freight."}]


def test_extraction_accepts_bare_json_array(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(client, "complete_json", lambda model, system, user, stub: [
        {"kind": "news", "claim": "Acme expanded", "source_url": "https://acme.com",
         "snippet": "expanded"},
    ])
    out = research._extract_findings("Acme", _PAGES, [], None)
    assert out["findings"][0]["claim"] == "Acme expanded"


def test_analysis_accepts_bare_json_array(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(client, "complete_json", lambda model, system, user, stub: [
        {"rank": 1, "category": "scaling", "statement": "Growing fast",
         "evidence": [1], "confidence": 0.6},
    ])
    brief = {"company_summary": "Acme is a logistics company."}
    findings = [{"id": 1, "kind": "news", "claim": "c", "confidence": 0.5,
                 "published_at": ""}]
    offer = {"what_we_sell": "automation", "icp": "B2B"}
    out = analyze._generate(brief, findings, offer, None)
    assert out[0]["statement"] == "Growing fast"


def test_extraction_drops_non_dict_items(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(client, "complete_json", lambda model, system, user, stub: {
        "findings": ["garbage string", {"kind": "news", "claim": "real",
                                        "source_url": "https://a.com", "snippet": "s"}],
    })
    out = research._extract_findings("Acme", _PAGES, [], None)
    assert [f["claim"] for f in out["findings"]] == ["real"]


def test_extraction_normalizes_null_fields(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(client, "complete_json", lambda model, system, user, stub: {
        "findings": [
            {"kind": None, "claim": "Real claim", "source_url": "https://a.com",
             "snippet": None, "confidence": None},
            {"kind": "news", "claim": None, "source_url": "https://a.com", "snippet": "s"},
        ],
    })
    out = research._extract_findings("Acme", _PAGES, [], None)
    assert len(out["findings"]) == 1
    f = out["findings"][0]
    assert f["kind"] == "other"
    assert f["snippet"] == ""
    assert f["confidence"] == 0.5


def test_research_lead_inserts_null_laden_findings_without_error(workspace, monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    page_text = "Acme Logistics ships freight across Europe with a dispatch team."
    monkeypatch.setattr(research.crawl, "crawl_domain",
                        lambda domain, deep=False: {"pages": [
                            {"url": "https://acme-logistics.com", "path": "home",
                             "text": page_text}], "reason": ""})
    monkeypatch.setattr(research.search, "search_company",
                        lambda company, domain, force=False: [])
    monkeypatch.setattr(client, "complete_json", lambda model, system, user, stub: {
        "findings": [{"kind": "other", "claim": "Acme ships freight across Europe",
                      "source_url": "https://acme-logistics.com", "snippet": None,
                      "confidence": None}],
    })
    list_id = queries.create_list(workspace["ws_id"], "N", "csv")
    lead_id = queries.insert_lead(list_id, {
        "company_name": "Acme Logistics", "domain": "acme-logistics.com",
        "contact_name": "", "contact_title": "", "email": "", "linkedin_url": "",
        "raw": {}, "dedupe_hash": "nulls-acme",
    })
    brief_id = research.research_lead(lead_id)
    stored = queries.findings_for_brief(brief_id)
    assert len(stored) == 1
    assert stored[0]["snippet"] == ""


def test_empty_extraction_retries_with_smart_model(monkeypatch):
    calls = []

    def fake(model, system, user, stub):
        calls.append(model)
        if len(calls) == 1:
            return {"findings": []}
        return {"findings": [{"kind": "news", "claim": "Real signal",
                              "source_url": "https://a.com", "snippet": "s"}]}

    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(client, "complete_json", fake)
    pages = [{"url": "https://a.com", "path": "home", "text": "content"}]
    out = research._extract_findings("Acme", pages, [], None)
    assert calls == [config.MODEL_FAST, config.MODEL_SMART]
    assert out["findings"][0]["claim"] == "Real signal"


def test_no_llm_call_without_source_material(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(client, "complete_json",
                        lambda model, system, user, stub: calls.append(model) or {})
    out = research._extract_findings("Acme", [], [], None)
    assert calls == []
    assert out["findings"] == []


def test_email_generation_survives_non_dict_response(workspace, monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(client, "complete_json",
                        lambda model, system, user, stub: ["not", "a", "dict"])
    list_id = queries.create_list(workspace["ws_id"], "G", "csv")
    lead_id = queries.insert_lead(list_id, {
        "company_name": "Acme", "domain": "acme.com", "contact_name": "",
        "contact_title": "", "email": "", "linkedin_url": "", "raw": {},
        "dedupe_hash": "shapes-acme",
    })
    offer = queries.get_offer_profile(workspace["profile_id"])
    hyp = {"id": None, "rank": 1, "category": "scaling",
           "statement": "Acme is scaling operations", "evidence": [], "confidence": 0.6}
    asset = write._make_email(lead_id, "Acme", offer, hyp, [], 1, None)
    assert asset["content"]
    assert "Acme" in asset["content"]
