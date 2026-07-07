from fastapi.testclient import TestClient

from tests.conftest import login_as, make_client
from app.db import core, queries
from app.fetch import crawl
from app.jobs import pipeline
from app.services import ingest
from app.services import research as research_service


def _insert_lead(list_id, company, domain):
    return queries.insert_lead(list_id, {
        "company_name": company, "domain": domain, "contact_name": "",
        "contact_title": "", "email": "", "linkedin_url": "", "raw": {},
        "dedupe_hash": f"{company}:{domain}"[:16],
    })


def test_confidence_labels():
    assert research_service.confidence_label(80) == "high"
    assert research_service.confidence_label(50) == "medium"
    assert research_service.confidence_label(10) == "low"


def test_review_and_list_pages_show_confidence(sample_list):
    pipeline.process_list_now(sample_list["ws_id"], sample_list["list_id"],
                              sample_list["profile_id"])
    client = login_as(sample_list["user_id"])
    review = client.get(f"/review/{sample_list['list_id']}?i=0")
    assert "confidence" in review.text
    detail = client.get(f"/lists/{sample_list['list_id']}")
    assert "high" in detail.text


def test_failed_lead_is_isolated_and_marked(workspace, monkeypatch):
    list_id = queries.create_list(workspace["ws_id"], "F", "csv")
    bad_id = _insert_lead(list_id, "Bad Co", "bad-co.com")
    good_id = _insert_lead(list_id, "Acme Logistics", "acme-logistics.com")
    real = research_service.research_lead

    def flaky(lead_id):
        if lead_id == bad_id:
            raise RuntimeError("crawler exploded")
        return real(lead_id)

    monkeypatch.setattr(research_service, "research_lead", flaky)
    result = pipeline.process_list_now(workspace["ws_id"], list_id)
    assert result == {"processed": 2, "failed": 1}
    bad = queries.get_lead(bad_id)
    assert bad["status"] == "failed"
    assert "crawler exploded" in bad["status_reason"]
    assert queries.get_lead(good_id)["status"] == "ready"
    phases = [e["phase"] for e in queries.events_since(list_id, 0)]
    assert "failed" in phases
    assert phases[-1] == "complete"


def test_failed_lead_retried_on_next_run(workspace):
    list_id = queries.create_list(workspace["ws_id"], "R", "csv")
    lead_id = _insert_lead(list_id, "Acme Logistics", "acme-logistics.com")
    queries.set_lead_status(lead_id, "failed", "earlier crash")
    pipeline.process_list_now(workspace["ws_id"], list_id)
    lead = queries.get_lead(lead_id)
    assert lead["status"] == "ready"
    assert lead["status_reason"] == ""


def test_pipeline_stops_gracefully_when_credits_run_out(workspace):
    core.execute("UPDATE workspaces SET credits_balance=1 WHERE id=?",
                 (workspace["ws_id"],))
    list_id = queries.create_list(workspace["ws_id"], "C", "csv")
    first = _insert_lead(list_id, "Acme Logistics", "acme-logistics.com")
    second = _insert_lead(list_id, "Beta Freight", "betafreight.io")
    result = pipeline.process_list_now(workspace["ws_id"], list_id)
    assert result["processed"] == 1
    assert queries.get_lead(first)["status"] == "ready"
    assert queries.get_lead(second)["status"] == "pending"
    events = queries.events_since(list_id, 0)
    stopping = [e for e in events if e["phase"] == "failed"]
    assert stopping and "Stopping" in stopping[0]["message"]


def test_stale_running_job_is_requeued(workspace):
    job_id = queries.create_job(workspace["ws_id"], "research", {"list_id": 1})
    core.execute(
        "UPDATE jobs SET status='running', attempts=1, "
        "claimed_at=datetime('now', '-30 minutes') WHERE id=?",
        (job_id,),
    )
    job = queries.claim_next_job()
    assert job and job["id"] == job_id
    refreshed = queries.get_job(job_id)
    assert refreshed["status"] == "running"
    assert refreshed["attempts"] == 2


def test_repeatedly_stale_job_gives_up(workspace):
    job_id = queries.create_job(workspace["ws_id"], "research", {"list_id": 1})
    core.execute(
        "UPDATE jobs SET status='running', attempts=3, "
        "claimed_at=datetime('now', '-30 minutes') WHERE id=?",
        (job_id,),
    )
    assert queries.claim_next_job() is None
    job = queries.get_job(job_id)
    assert job["status"] == "failed"
    assert "gave up" in job["error"]


def test_fresh_running_job_is_left_alone(workspace):
    job_id = queries.create_job(workspace["ws_id"], "research", {"list_id": 1})
    core.execute("UPDATE jobs SET status='running', attempts=1, "
                 "claimed_at=datetime('now') WHERE id=?", (job_id,))
    assert queries.claim_next_job() is None
    assert queries.get_job(job_id)["status"] == "running"


def test_free_email_never_becomes_company_domain():
    raw = b"Company,Email\nJane's Plumbing,jane.plumber@gmail.com\n"
    rows, _ = ingest.parse_csv(raw)
    assert rows[0]["domain"] == ""


def test_free_email_website_column_rejected():
    raw = b"Company,Website\nSomeone,outlook.com\n"
    rows, _ = ingest.parse_csv(raw)
    assert rows[0]["domain"] == ""


def test_dedupe_is_per_person_not_per_company(workspace):
    list_id = queries.create_list(workspace["ws_id"], "D", "csv")
    raw = (b"Company,Domain,Email\n"
           b"Acme,acme.com,sam@acme.com\n"
           b"Acme,acme.com,ana@acme.com\n"
           b"Acme,acme.com,sam@acme.com\n")
    rows, _ = ingest.parse_csv(raw)
    inserted, duplicates = ingest.import_rows(list_id, rows)
    assert inserted == 2
    assert duplicates == 1


def test_dns_failure_short_circuits_crawl(monkeypatch):
    monkeypatch.setattr(crawl, "_resolves", lambda domain: False)
    assert crawl._live_crawl("dead.example") == {"pages": [], "reason": "dns_failure"}


def test_export_download_labeled_preview():
    client, ctx = make_client()
    list_id = queries.create_list(ctx["ws_id"], "P", "csv")
    lead_id = _insert_lead(list_id, "Acme", "acme.com")
    queries.insert_asset(lead_id, {"kind": "email_1", "subject": "s", "content": "body",
                                   "score": 80, "breakdown": {}, "status": "approved"})
    resp = client.get(f"/lists/{list_id}/export?format=csv")
    assert resp.status_code == 200
    assert "PREVIEW_" in resp.headers["content-disposition"]


def test_exports_page_shows_preview_banner_and_deliverability_note():
    client, _ = make_client()
    resp = client.get("/exports")
    assert "Preview mode" in resp.text
    assert "SPF, DKIM, DMARC" in resp.text


def test_legal_pages_are_public():
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    checks = [
        ("/privacy", "data controller"),
        ("/terms", "SPF, DKIM, DMARC"),
        ("/how-research-works", "robots.txt"),
    ]
    for path, phrase in checks:
        resp = client.get(path)
        assert resp.status_code == 200
        assert phrase in resp.text
