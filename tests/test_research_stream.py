from app.db import queries
from app.jobs import pipeline, worker


def test_enqueue_sets_researching_and_queues_job(sample_list):
    job_id = pipeline.enqueue_research(
        sample_list["ws_id"], sample_list["list_id"], sample_list["profile_id"]
    )
    assert job_id
    assert queries.get_list(sample_list["list_id"])["status"] == "researching"
    job = queries.get_job(job_id)
    assert job["status"] == "queued"


def test_worker_drains_job_and_emits_progress_events(sample_list):
    pipeline.enqueue_research(
        sample_list["ws_id"], sample_list["list_id"], sample_list["profile_id"]
    )
    processed = worker.run_pending_sync()
    assert processed == 1

    events = queries.events_since(sample_list["list_id"], 0)
    phases = [e["phase"] for e in events]
    assert "start" in phases
    assert "researching" in phases
    assert "found" in phases
    assert "written" in phases
    assert phases[-1] == "complete"

    complete = events[-1]
    assert complete["done"] == 2
    assert complete["total"] == 2


def test_events_since_returns_only_new(sample_list):
    pipeline.enqueue_research(
        sample_list["ws_id"], sample_list["list_id"], sample_list["profile_id"]
    )
    worker.run_pending_sync()
    all_events = queries.events_since(sample_list["list_id"], 0)
    mid = all_events[len(all_events) // 2]["id"]
    tail = queries.events_since(sample_list["list_id"], mid)
    assert all(e["id"] > mid for e in tail)
    assert len(tail) == sum(1 for e in all_events if e["id"] > mid)
