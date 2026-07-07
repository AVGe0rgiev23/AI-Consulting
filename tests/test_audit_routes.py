from tests.conftest import make_client


def test_audit_flow_generates_and_renders_branded_report():
    client, ctx = make_client()
    resp = client.post("/audit", data={"company_name": "Acme Logistics",
                                       "domain": "acme-logistics.com"}, follow_redirects=False)
    assert resp.status_code == 303
    report_id = int(resp.headers["location"].split("/")[-1])

    page = client.get(f"/audit/{report_id}")
    assert page.status_code == 200
    assert b"AI Opportunity Audit" in page.content
    assert b"Acme Logistics" in page.content
    assert b"OPPORTUNITY 1" in page.content
    assert b"Print / Save as PDF" in page.content


def test_settings_updates_brand_on_report():
    client, ctx = make_client()
    client.post("/settings", data={"brand_name": "Growth Labs", "accent": "#0a7d55",
                                   "report_title": "Growth Opportunity Audit", "contact": "hi@gl.com"},
                follow_redirects=False)
    resp = client.post("/audit", data={"company_name": "Beta", "domain": "beta.com"},
                       follow_redirects=False)
    report_id = int(resp.headers["location"].split("/")[-1])
    page = client.get(f"/audit/{report_id}")
    assert b"Growth Labs" in page.content
    assert b"Growth Opportunity Audit" in page.content
    assert b"#0a7d55" in page.content
    assert b"hi@gl.com" in page.content


def test_api_audit_returns_json():
    client, ctx = make_client()
    resp = client.post("/audit", data={"company_name": "Acme", "domain": "acme-logistics.com"},
                       follow_redirects=False)
    report_id = int(resp.headers["location"].split("/")[-1])
    data = client.get(f"/api/v1/audits/{report_id}").json()
    assert data["report"]["company_name"] == "Acme"
    assert data["opportunities"]
