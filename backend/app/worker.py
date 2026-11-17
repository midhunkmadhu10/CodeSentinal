"""In-process background worker.

A daemon thread polls the `jobs` table and executes queued jobs with retry
and per-type handlers. This keeps the deployment single-service (no Redis or
Celery needed) while making LLM-heavy work asynchronous. Start it from app
startup when WORKER_ENABLED=true; tests run with it disabled.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from .config import JOB_MAX_ATTEMPTS, WORKER_CONCURRENCY, WORKER_POLL_SECONDS
from .database import SessionLocal, ensure_init
from .db_models import Event, Job, utcnow
from .observability import METRICS, log_event

logger = logging.getLogger("codesentinal.worker")

_stop = threading.Event()
_threads: list[threading.Thread] = []
_started_once = False


def enqueue_job(
    db: Session,
    *,
    type: str,
    payload: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    repo_id: Optional[int] = None,
) -> Job:
    """Create a queued job row (committed immediately)."""
    job = Job(type=type, payload=payload or {}, user_id=user_id, repo_id=repo_id, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    log_event("job.enqueued", job_id=job.id, job_type=type)
    return job


def _claim_next_job() -> Optional[Job]:
    """Atomically claim one queued job (queued → running).

    The status check is repeated inside the UPDATE so that two worker threads
    cannot both claim the same row (a plain read-then-write race under
    WORKER_CONCURRENCY > 1). The conditional UPDATE is portable across
    Postgres and SQLite, unlike SELECT ... FOR UPDATE SKIP LOCKED.
    """
    db = SessionLocal()
    try:
        for _ in range(5):
            candidate = (
                db.query(Job.id)
                .filter(Job.status == "queued", Job.attempts < JOB_MAX_ATTEMPTS)
                .order_by(Job.created_at)
                .first()
            )
            if candidate is None:
                return None
            job_id = candidate[0]
            claimed = (
                db.query(Job)
                .filter(
                    Job.id == job_id,
                    Job.status == "queued",
                    Job.attempts < JOB_MAX_ATTEMPTS,
                )
                .update(
                    {
                        "status": "running",
                        "attempts": Job.attempts + 1,
                        "started_at": utcnow(),
                    },
                    synchronize_session=False,
                )
            )
            db.commit()
            if claimed:
                return db.get(Job, job_id)
        return None
    finally:
        db.close()


def handle_job(db: Session, job: Job) -> Dict[str, Any]:
    """Dispatch a job to its handler; returns the result payload."""
    payload = job.payload or {}
    if job.type == "index_repository":
        from .db_models import Repository
        from .indexer import index_repository

        repo = db.get(Repository, payload.get("repo_id"))
        if repo is None:
            raise ValueError("Repository not found for indexing job.")
        token = payload.get("access_token") or None
        local_root = payload.get("local_root") or None
        index_repository(db, repo, access_token=token, local_root=local_root)
        return {"repo_id": repo.id, "status": repo.index_status}

    if job.type == "review_pull_request":
        return _handle_pr_review(db, payload, job_id=job.id)

    raise ValueError(f"Unknown job type: {job.type}")


def _resolve_review_user_id(db: Session, payload: Dict[str, Any], owner: str, name: str) -> int:
    """Owner for an automated review.

    Webhook deliveries arrive without a session, so the owning user is resolved
    from the connected repository (or the first account). Persisting a review
    with a user id that does not exist used to fail the NOT NULL foreign key.
    """
    from .db_models import Repository, User

    if payload.get("user_id"):
        return int(payload["user_id"])
    repo = (
        db.query(Repository).filter(Repository.full_name == f"{owner}/{name}").first()
    )
    if repo is not None and repo.user_id:
        return int(repo.user_id)
    owner_user = db.query(User).order_by(User.id).first()
    if owner_user is None:
        raise ValueError(
            "No account exists to own this automated review. Register a user or "
            "set AUTH_USERNAME/AUTH_PASSWORD before enabling webhooks."
        )
    return int(owner_user.id)


def _handle_pr_review(
    db: Session, payload: Dict[str, Any], job_id: Optional[int] = None
) -> Dict[str, Any]:
    """Fetch a PR diff, run the full pipeline, optionally post a GitHub comment."""
    import os

    from . import github_service
    from .db_models import Repository
    from .pipeline import review_to_dict, run_review

    owner, name = payload["owner"], payload["name"]
    pull_number = int(payload["pull_number"])
    user_id = _resolve_review_user_id(db, payload, owner, name)
    token = payload.get("access_token") or os.getenv("GITHUB_TOKEN", "").strip() or None
    repo_id = payload.get("repo_id")
    if repo_id is None:
        linked = (
            db.query(Repository)
            .filter(Repository.full_name == f"{owner}/{name}")
            .first()
        )
        repo_id = linked.id if linked is not None else None

    pr_meta = github_service.fetch_pr_metadata(owner, name, pull_number, token)
    diff = github_service.fetch_pr_diff(owner, name, pull_number, token)
    if not diff.strip():
        raise ValueError("The pull request has no diff to review.")

    review = run_review(
        db,
        user_id=user_id,
        job_id=job_id,
        diff=diff,
        rules_text="",
        trigger="webhook" if payload.get("trigger") == "webhook" else "manual",
        repository=f"{owner}/{name}",
        title=pr_meta.get("title") or f"PR #{pull_number}",
        pr_number=pull_number,
        head_sha=(pr_meta.get("head") or {}).get("sha") or "",
        repo_id=repo_id,
        depth=payload.get("depth", "standard"),
    )
    data = review_to_dict(review)

    comment_url = None
    if payload.get("post_comment", True) and token:
        body = github_service.format_review_comment(
            review.title or f"PR #{pull_number}", review.summary, data["findings"]
        )
        comment_url = github_service.post_pr_comment(owner, name, pull_number, body, token)
    data["comment_url"] = comment_url
    return data


def _execute(job_id: int) -> None:
    ensure_init()
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        started = time.time()
        try:
            result = handle_job(db, job)
            job.result = result
            job.status = "succeeded"
            job.error = None
            METRICS.inc("jobs_total", type=job.type, status="succeeded")
        except Exception as exc:  # noqa: BLE001 — job isolation
            logger.exception("Job %s (%s) failed", job.id, job.type)
            job.error = str(exc)[:2000] or "Job failed unexpectedly."
            if job.attempts >= JOB_MAX_ATTEMPTS:
                job.status = "failed"
                METRICS.inc("jobs_total", type=job.type, status="failed")
            else:
                job.status = "queued"  # retry
            db.add(
                Event(
                    event="job.failed" if job.status == "failed" else "job.retry",
                    user_id=job.user_id,
                    data={"job_id": job.id, "type": job.type, "error": job.error[:200]},
                )
            )
        job.finished_at = utcnow()
        db.commit()
        log_event(
            "job.finished",
            job_id=job.id,
            job_type=job.type,
            duration_ms=int((time.time() - started) * 1000),
        )
    finally:
        db.close()


def _worker_loop(worker_id: int) -> None:
    logger.info("Worker %d started (poll=%.1fs)", worker_id, WORKER_POLL_SECONDS)
    while not _stop.is_set():
        try:
            job = _claim_next_job()
        except Exception:  # noqa: BLE001 — polling must survive DB hiccups
            logger.exception("Worker %d failed to claim a job", worker_id)
            job = None
        if job is None:
            _stop.wait(WORKER_POLL_SECONDS)
            continue
        _execute(job.id)
    logger.info("Worker %d stopped", worker_id)


def worker_status() -> bool:
    """True when at least one worker thread is alive and not stopping."""
    return not _stop.is_set() and any(t.is_alive() for t in _threads)


def start_worker() -> None:
    """Start the worker threads (idempotent; no-op when WORKER_ENABLED=false)."""
    global _started_once
    from .config import WORKER_ENABLED

    if _started_once or not WORKER_ENABLED:
        return
    _started_once = True
    for worker_id in range(max(1, WORKER_CONCURRENCY)):
        thread = threading.Thread(target=_worker_loop, args=(worker_id,), daemon=True,
                                  name=f"codesentinal-worker-{worker_id}")
        thread.start()
        _threads.append(thread)


def stop_worker() -> None:
    _stop.set()
