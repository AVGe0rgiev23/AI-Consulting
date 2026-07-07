from tests.conftest import make_client
from app.db import queries
from app.jobs import worker


def _seed_researched_list(client):
    csv = b"Company,Domain,Email\nAcme Logistics,acme-logistics.com,sam@acme-logistics.com\n"
    resp = client.post("/lists", data={"name": "Analytics"},
                       files={"file": ("l.csv", csv, "text/csv")}, follow_redirects=False)
    list_id = int(resp.headers["location"].split("/")[-1])
    client.post(f"/lists/{list_id}/research", data={}, follow_redirects=False)
    worker.run_pending_sync()
    for lead in queries.leads_for_list(list_id):
        for a in queries.assets_for_lead(lead["id"]):
            queries.set_asset_status(a["id"], "approved")
    return list_id


def test_analytics_page_renders():
    client, ctx = make_client()
    resp = client.get("/analytics")
    assert resp.status_code == 200
    assert b"Hypothesis leaderboard" in resp.content


def test_import_stats_updates_leaderboard_and_api():
    client, ctx = make_client()
    list_id = _seed_researched_list(client)
    stats = b"email,sent,replied\nsam@acme-logistics.com,1,1\n"
    resp = client.post(f"/lists/{list_id}/import-stats",
                       files={"file": ("s.csv", stats, "text/csv")}, follow_redirects=False)
    assert resp.status_code == 303

    api = client.get("/api/v1/leaderboard").json()
    assert api["funnel"]["sent"] == 1
    assert api["funnel"]["replied"] == 1
    assert api["leaderboard"][0]["reply_rate"] == 100.0


def test_leaderboard_requires_auth():
    from fastapi.testclient import TestClient
    from app.main import app
    anon = TestClient(app)
    assert anon.get("/api/v1/leaderboard").status_code == 401
