from app.db import queries
from app.services import analyze, research, write


def _prepare(sample_list):
    lead = queries.leads_for_list(sample_list["list_id"])[0]
    research.research_lead(lead["id"])
    offer = queries.get_offer_profile(sample_list["profile_id"])
    analyze.analyze_lead(lead["id"], offer)
    return lead, offer


def test_generate_creates_full_sequence_and_linkedin(sample_list):
    lead, offer = _prepare(sample_list)
    created = write.generate_for_lead(lead["id"], offer)
    kinds = {a["kind"] for a in created}
    assert {"email_1", "email_2", "email_3", "email_4", "email_5"} <= kinds
    assert "li_connect" in kinds and "li_dm" in kinds


def test_email_one_subject_is_company_name(sample_list):
    lead, offer = _prepare(sample_list)
    write.generate_for_lead(lead["id"], offer)
    assets = queries.assets_for_lead(lead["id"])
    email1 = [a for a in assets if a["kind"] == "email_1"][0]
    assert email1["subject"] == lead["company_name"]


def test_generated_emails_are_scored(sample_list):
    lead, offer = _prepare(sample_list)
    write.generate_for_lead(lead["id"], offer)
    assets = queries.assets_for_lead(lead["id"])
    email1 = [a for a in assets if a["kind"] == "email_1"][0]
    assert email1["score"] > 0


def test_step5_pivots_to_second_hypothesis(sample_list):
    lead, offer = _prepare(sample_list)
    write.generate_for_lead(lead["id"], offer)
    assets = {a["kind"]: a for a in queries.assets_for_lead(lead["id"])}
    assert assets["email_5"]["content"] != assets["email_1"]["content"]
