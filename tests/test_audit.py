import json

from app.db import queries
from app.services import audit, credits
from app.branding import branding


def test_run_audit_produces_report_with_opportunities(workspace):
    offer = queries.get_offer_profile(workspace["profile_id"])
    start = credits.balance(workspace["ws_id"])
    report_id = audit.run_audit(workspace["ws_id"], "Acme Logistics", "acme-logistics.com", offer)
    report = queries.get_audit_report(report_id)
    assert report["company_name"] == "Acme Logistics"
    assert report["exec_summary"]
    opps = json.loads(report["opportunities_json"])
    assert opps
    assert opps[0]["title"]
    assert opps[0]["recommendation"]
    assert credits.balance(workspace["ws_id"]) == start - 1


def test_audit_opportunities_carry_evidence(workspace):
    offer = queries.get_offer_profile(workspace["profile_id"])
    report_id = audit.run_audit(workspace["ws_id"], "Acme", "acme-logistics.com", offer)
    opps = json.loads(queries.get_audit_report(report_id)["opportunities_json"])
    with_evidence = [o for o in opps if o.get("evidence")]
    assert with_evidence
    assert with_evidence[0]["evidence"][0]["url"]


def test_audit_list_hidden_from_normal_lists(workspace):
    offer = queries.get_offer_profile(workspace["profile_id"])
    audit.run_audit(workspace["ws_id"], "Acme", "acme-logistics.com", offer)
    visible = queries.lists_for_workspace(workspace["ws_id"])
    assert all(l["source"] != "audit" for l in visible)


def test_branding_defaults_and_overrides(workspace):
    ws = queries.get_workspace(workspace["ws_id"])
    brand = branding(ws)
    assert brand["report_title"] == "AI Opportunity Audit"
    queries.update_workspace_settings(workspace["ws_id"], {"accent": "#123456",
                                                           "report_title": "Growth Audit"})
    ws = queries.get_workspace(workspace["ws_id"])
    brand = branding(ws)
    assert brand["accent"] == "#123456"
    assert brand["report_title"] == "Growth Audit"
