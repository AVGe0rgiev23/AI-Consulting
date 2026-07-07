import pytest

from app.db import queries
from app.jobs import pipeline
from app.services import sender


def _research_and_approve(sample_list):
    pipeline.process_list_now(sample_list["ws_id"], sample_list["list_id"],
                              sample_list["profile_id"])
    for lead in queries.leads_for_list(sample_list["list_id"]):
        for a in queries.assets_for_lead(lead["id"]):
            queries.set_asset_status(a["id"], "approved")


def _connect(ws_id, provider, key="test-key"):
    ws = queries.get_workspace(ws_id)
    settings = queries.get_settings(ws)
    settings[f"{provider}_api_key"] = key
    queries.update_workspace_settings(ws_id, settings)
    return queries.get_workspace(ws_id)


def test_push_requires_api_key(sample_list):
    _research_and_approve(sample_list)
    ws = queries.get_workspace(sample_list["ws_id"])
    with pytest.raises(sender.SenderError, match="API key"):
        sender.push_list(ws, sample_list["list_id"], "instantly")


def test_push_requires_approved_emails(sample_list):
    ws = _connect(sample_list["ws_id"], "instantly")
    with pytest.raises(sender.SenderError, match="approved"):
        sender.push_list(ws, sample_list["list_id"], "instantly")


def test_push_rejects_unknown_provider(sample_list):
    ws = queries.get_workspace(sample_list["ws_id"])
    with pytest.raises(sender.SenderError, match="Unknown provider"):
        sender.push_list(ws, sample_list["list_id"], "mailchimp")


def test_push_records_everything(sample_list):
    _research_and_approve(sample_list)
    ws = _connect(sample_list["ws_id"], "instantly")
    result = sender.push_list(ws, sample_list["list_id"], "instantly")
    assert result["lead_count"] == 2
    pushes = queries.pushes_for_workspace(ws["id"])
    assert len(pushes) == 1
    assert pushes[0]["provider"] == "instantly"
    assert pushes[0]["lead_count"] == 2
    assert pushes[0]["external_id"]
    campaigns = queries.campaigns_for_workspace(ws["id"])
    assert campaigns and campaigns[0]["exported_to"] == "instantly"
    for lead in queries.leads_for_list(sample_list["list_id"]):
        assert lead["status"] == "exported"
    assert queries.get_list(sample_list["list_id"])["status"] == "exported"


def test_instantly_payloads_carry_sequence_and_variables(sample_list, monkeypatch):
    _research_and_approve(sample_list)
    ws = _connect(sample_list["ws_id"], "instantly")
    calls = []

    def spy(url, headers, payload):
        calls.append({"url": url, "headers": headers, "payload": payload})
        return {"id": "camp-123"}

    monkeypatch.setattr(sender, "_post", spy)
    sender.push_list(ws, sample_list["list_id"], "instantly")

    campaign_call = calls[0]
    assert campaign_call["url"].endswith("/campaigns")
    assert campaign_call["headers"]["Authorization"] == "Bearer test-key"
    steps = campaign_call["payload"]["sequences"][0]["steps"]
    assert len(steps) == 5
    assert steps[0]["variants"][0]["subject"] == "{{email_1_subject}}"
    assert steps[4]["variants"][0]["body"] == "{{email_5_body}}"

    lead_calls = calls[1:]
    assert len(lead_calls) == 2
    first = lead_calls[0]["payload"]
    assert first["campaign"] == "camp-123"
    assert first["email"].startswith("sam@")
    assert first["custom_variables"]["email_1_body"]
    assert first["custom_variables"]["email_5_body"]


def test_smartlead_payloads_carry_sequence_and_lead_list(sample_list, monkeypatch):
    _research_and_approve(sample_list)
    ws = _connect(sample_list["ws_id"], "smartlead", "sl-key")
    calls = []

    def spy(url, headers, payload):
        calls.append({"url": url, "payload": payload})
        return {"id": 777}

    monkeypatch.setattr(sender, "_post", spy)
    sender.push_list(ws, sample_list["list_id"], "smartlead")

    assert "campaigns/create" in calls[0]["url"] and "api_key=sl-key" in calls[0]["url"]
    seq_call = calls[1]
    assert "/campaigns/777/sequences" in seq_call["url"]
    assert len(seq_call["payload"]["sequences"]) == 5
    assert seq_call["payload"]["sequences"][0]["subject"] == "{{email_1_subject}}"
    assert seq_call["payload"]["sequences"][1]["subject"] == ""
    lead_call = calls[2]
    assert "/campaigns/777/leads" in lead_call["url"]
    assert len(lead_call["payload"]["lead_list"]) == 2
    assert lead_call["payload"]["lead_list"][0]["custom_fields"]["email_1_subject"]


def test_leads_without_email_are_skipped(sample_list):
    _research_and_approve(sample_list)
    lead = queries.leads_for_list(sample_list["list_id"])[0]
    from app.db import core

    core.execute("UPDATE leads SET email='' WHERE id=?", (lead["id"],))
    rows = sender.sequence_rows(sample_list["list_id"])
    assert len(rows) == 1
