from tests.conftest import make_client
from app.db import queries


def test_upload_research_review_export_flow():
    client, ctx = make_client()

    csv = b"Company,Domain,Email\nAcme Logistics,acme-logistics.com,sam@acme-logistics.com\n"
    resp = client.post("/lists", data={"name": "Flow"},
                       files={"file": ("leads.csv", csv, "text/csv")},
                       follow_redirects=False)
    assert resp.status_code == 303
    list_id = int(resp.headers["location"].split("/")[-1])
    assert queries.get_list(list_id)["row_count"] == 1

    resp = client.post(f"/lists/{list_id}/research", data={}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/research/{list_id}"

    from app.jobs import worker
    assert worker.run_pending_sync() == 1

    lead = queries.leads_for_list(list_id)[0]
    assert lead["status"] == "ready"

    review = client.get(f"/review/{list_id}?i=0")
    assert review.status_code == 200
    assert b"Research brief" in review.content

    assets = queries.assets_for_lead(lead["id"])
    email1 = [a for a in assets if a["kind"] == "email_1"][0]
    approve = client.post(f"/assets/{email1['id']}/approve",
                          data={"list_id": list_id, "i": 0}, follow_redirects=False)
    assert approve.status_code == 303
    assert queries.get_lead(lead["id"])["status"] == "approved"

    export = client.get(f"/lists/{list_id}/export?format=instantly")
    assert export.status_code == 200
    assert "step5" in export.text


def test_api_usage_endpoint():
    client, ctx = make_client()
    resp = client.get("/api/v1/usage")
    assert resp.status_code == 200
    assert resp.json()["credits_balance"] == 100


def test_api_unauthorized_without_session():
    from fastapi.testclient import TestClient
    from app.main import app
    anon = TestClient(app)
    assert anon.get("/api/v1/lists").status_code == 401
