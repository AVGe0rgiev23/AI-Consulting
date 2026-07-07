from app.db import queries
from app.jobs import pipeline
from app.services import credits


def test_process_list_runs_full_pipeline_and_charges_credits(sample_list):
    ws = sample_list["ws_id"]
    start = credits.balance(ws)
    result = pipeline.process_list_now(ws, sample_list["list_id"], sample_list["profile_id"])
    assert result["processed"] == 2
    assert credits.balance(ws) == start - 2
    assert queries.get_list(sample_list["list_id"])["status"] == "ready"
    for lead in queries.leads_for_list(sample_list["list_id"]):
        assert lead["status"] == "ready"
        assert queries.get_brief_by_lead(lead["id"])
        assert queries.assets_for_lead(lead["id"])


def test_process_list_is_idempotent_on_already_ready(sample_list):
    ws = sample_list["ws_id"]
    pipeline.process_list_now(ws, sample_list["list_id"], sample_list["profile_id"])
    mid = credits.balance(ws)
    result = pipeline.process_list_now(ws, sample_list["list_id"], sample_list["profile_id"])
    assert result["processed"] == 0
    assert credits.balance(ws) == mid
