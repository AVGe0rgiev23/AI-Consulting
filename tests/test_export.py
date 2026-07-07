from app.db import queries
from app.jobs import pipeline
from app.services import export


def _research_and_approve(sample_list):
    pipeline.process_list_now(sample_list["ws_id"], sample_list["list_id"], sample_list["profile_id"])
    for lead in queries.leads_for_list(sample_list["list_id"]):
        for a in queries.assets_for_lead(lead["id"]):
            queries.set_asset_status(a["id"], "approved")


def test_export_csv_has_rows_after_approval(sample_list):
    _research_and_approve(sample_list)
    content, count = export.build_export(sample_list["list_id"], "csv")
    assert count == 2
    assert "email_1_body" in content


def test_instantly_format_includes_sequence_steps(sample_list):
    _research_and_approve(sample_list)
    content, count = export.build_export(sample_list["list_id"], "instantly")
    assert count == 2
    assert "step5" in content and "subject" in content


def test_export_empty_when_nothing_approved(sample_list):
    pipeline.process_list_now(sample_list["ws_id"], sample_list["list_id"], sample_list["profile_id"])
    content, count = export.build_export(sample_list["list_id"], "csv")
    assert count == 0
