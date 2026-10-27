"""Queue logic: claiming, completing, failing, and recovering jobs."""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.backoff import backoff_seconds
from app.models import Job, utcnow


@dataclass
class ClaimedJob:
    id: int
    task_name: str
    payload: dict
    attempts: int
    max_attempts: int


def claim_job(session: Session, worker_id: str) -> ClaimedJob | None:
    """Atomically claim one due job.

    FOR UPDATE SKIP LOCKED: rows another worker has already locked are skipped
    instead of waited on, so many workers can pull from the same table
    without blocking each other or claiming the same job twice.
    """
    stmt = (
        select(Job)
        .where(Job.status == "pending", Job.run_at <= utcnow())
        .order_by(Job.run_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = session.execute(stmt).scalar_one_or_none()
    if job is None:
        session.rollback()
        return None
    job.status = "running"
    job.locked_by = worker_id
    job.locked_at = utcnow()
    job.attempts += 1
    claimed = ClaimedJob(job.id, job.task_name, job.payload, job.attempts, job.max_attempts)
    session.commit()
    return claimed


def mark_succeeded(session: Session, job_id: int) -> None:
    job = session.get(Job, job_id)
    job.status = "succeeded"
    job.locked_by = None
    job.locked_at = None
    job.last_error = None
    session.commit()


def mark_failed(session: Session, job_id: int, error: str) -> str:
    """Retry with exponential backoff, or move to the dead-letter state."""
    job = session.get(Job, job_id)
    job.last_error = error[:2000]
    job.locked_by = None
    job.locked_at = None
    if job.attempts >= job.max_attempts:
        job.status = "dead"
    else:
        job.status = "pending"
        job.run_at = utcnow() + timedelta(seconds=backoff_seconds(job.attempts))
    session.commit()
    return job.status


def reap_stale(session: Session, timeout_seconds: int) -> int:
    """Recover jobs stuck in 'running' because their worker died."""
    cutoff = utcnow() - timedelta(seconds=timeout_seconds)
    stale = (Job.status == "running") & (Job.locked_at < cutoff)
    dead = session.execute(
        update(Job)
        .where(stale, Job.attempts >= Job.max_attempts)
        .values(status="dead", locked_by=None, locked_at=None,
                last_error="worker died; max attempts reached")
    ).rowcount
    requeued = session.execute(
        update(Job).where(stale).values(status="pending", locked_by=None, locked_at=None)
    ).rowcount
    session.commit()
    return dead + requeued
