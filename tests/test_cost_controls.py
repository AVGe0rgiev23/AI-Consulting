import pytest

from tests.conftest import make_client
from app import config
from app.db import queries
from app.fetch import search
from app.llm import client as llm_client
from app.services import budget


def test_per_request_ceiling_blocks_oversized_call(monkeypatch):
    monkeypatch.setattr(config, "REQUEST_MAX_USD", 0.001)
    with pytest.raises(budget.BudgetExceeded):
        budget.guard("llm", 0.002)


def test_daily_budget_kill_switch(monkeypatch):
    monkeypatch.setattr(config, "DAILY_BUDGET_USD", 0.05)
    budget.record("llm", 0.04)
    budget.guard("llm", 0.005)
    budget.record("llm", 0.02)
    with pytest.raises(budget.BudgetExceeded):
        budget.guard("llm", 0.005)


def test_daily_call_cap(monkeypatch):
    monkeypatch.setattr(config, "DAILY_LLM_CALL_CAP", 2)
    budget.record("llm", 0.0)
    budget.record("llm", 0.0)
    with pytest.raises(budget.BudgetExceeded):
        budget.guard("llm", 0.0)


def test_llm_falls_back_to_stub_when_budget_exhausted(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(config, "DAILY_LLM_CALL_CAP", 0)
    result = llm_client.complete_json("model", "sys", "usr", lambda: {"stub": True})
    assert result == {"stub": True}


def test_search_caches_and_respects_budget(monkeypatch):
    monkeypatch.setattr(config, "USE_FETCH_STUB", False)
    monkeypatch.setattr(config, "SEARCH_API_KEY", "tvly-test")
    calls = []

    def fake_query(kind, query, include_domains):
        calls.append(kind)
        return [{"kind": kind, "title": "T", "url": f"https://n.example/{kind}",
                 "snippet": "s", "published_at": ""}]

    monkeypatch.setattr(search, "_live_query", fake_query)
    first = search.search_company("Acme", "acme.com")
    second = search.search_company("Acme", "acme.com")
    assert first == second
    assert len(calls) == len(search.SOURCE_QUERIES)
    spent, count = budget.spent_today()
    assert count == len(search.SOURCE_QUERIES)
    assert spent == pytest.approx(config.SEARCH_COST_USD * len(search.SOURCE_QUERIES))

    monkeypatch.setattr(config, "DAILY_BUDGET_USD", 0.0)
    assert search.search_company("Beta", "beta.com") == []
    assert len(calls) == len(search.SOURCE_QUERIES)


def test_upload_rate_limit(monkeypatch):
    monkeypatch.setattr(config, "UPLOADS_PER_WINDOW", 2)
    client, _ = make_client()
    for _ in range(2):
        assert client.post("/lists", data={"name": "L"},
                           follow_redirects=False).status_code == 303
    assert client.post("/lists", data={"name": "L"},
                       follow_redirects=False).status_code == 429


def test_research_rate_limit(monkeypatch):
    monkeypatch.setattr(config, "RESEARCH_RUNS_PER_WINDOW", 1)
    client, _ = make_client()
    resp = client.post("/lists", data={"name": "L"}, follow_redirects=False)
    list_id = int(resp.headers["location"].split("/")[-1])
    assert client.post(f"/lists/{list_id}/research", data={},
                       follow_redirects=False).status_code == 303
    assert client.post(f"/lists/{list_id}/research", data={},
                       follow_redirects=False).status_code == 429


def test_trial_plan_list_cap(monkeypatch):
    monkeypatch.setitem(config.PLAN_LEAD_CAPS, "trial", 5)
    client, _ = make_client()
    lines = ["Company,Domain"] + [f"C{i},c{i}.com" for i in range(8)]
    csv = ("\n".join(lines) + "\n").encode()
    resp = client.post("/lists", data={"name": "Cap"},
                       files={"file": ("l.csv", csv, "text/csv")}, follow_redirects=False)
    list_id = int(resp.headers["location"].split("/")[-1])
    lst = queries.get_list(list_id)
    assert lst["row_count"] == 5
    assert lst["error_count"] == 1


def test_healthz_reports_budget_and_provider():
    client, _ = make_client()
    data = client.get("/healthz").json()
    assert data["budget"]["exceeded"] is False
    assert data["llm_provider"] == config.LLM_PROVIDER
