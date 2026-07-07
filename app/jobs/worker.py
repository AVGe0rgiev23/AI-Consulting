import asyncio

from app.db import queries
from app.jobs import pipeline

_POLL_SECONDS = 1.0
_running = False


async def worker_loop():
    global _running
    _running = True
    while _running:
        job = queries.claim_next_job()
        if not job:
            await asyncio.sleep(_POLL_SECONDS)
            continue
        try:
            await asyncio.to_thread(pipeline.run_job, job)
            queries.finish_job(job["id"], "done")
        except Exception as exc:
            queries.finish_job(job["id"], "failed", str(exc))


def stop():
    global _running
    _running = False


def run_pending_sync():
    processed = 0
    while True:
        job = queries.claim_next_job()
        if not job:
            break
        try:
            pipeline.run_job(job)
            queries.finish_job(job["id"], "done")
        except Exception as exc:
            queries.finish_job(job["id"], "failed", str(exc))
        processed += 1
    return processed
