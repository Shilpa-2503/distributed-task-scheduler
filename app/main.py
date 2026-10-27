import logging
from datetime import timedelta

import redis
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.db import SessionLocal
from app.models import Job, utcnow
from app.schemas import JobCreate, JobOut
from app.tasks import TASKS

app = FastAPI(title="Distributed Task Scheduler")
log = logging.getLogger("api")
_redis = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)


def get_session():
    with SessionLocal() as session:
        yield session


def notify_workers():
    try:
        _redis.lpush(config.WAKE_KEY, "1")
        _redis.ltrim(config.WAKE_KEY, 0, 999)
    except redis.RedisError:
        log.warning("redis unavailable; workers will pick the job up on their next poll")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", response_model=JobOut, status_code=201)
def create_job(body: JobCreate, session: Session = Depends(get_session)):
    if body.task_name not in TASKS:
        raise HTTPException(400, f"Unknown task '{body.task_name}'. Available: {sorted(TASKS)}")
    job = Job(
        task_name=body.task_name,
        payload=body.payload,
        max_attempts=body.max_attempts,
        run_at=utcnow() + timedelta(seconds=body.delay_seconds),
    )
    session.add(job)
    session.commit()
    notify_workers()
    return job


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(status: str | None = None, limit: int = Query(50, ge=1, le=500),
              session: Session = Depends(get_session)):
    stmt = select(Job).order_by(Job.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(Job.status == status)
    return session.scalars(stmt).all()


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@app.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_dead_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status != "dead":
        raise HTTPException(409, "only dead-letter jobs can be retried")
    job.status = "pending"
    job.attempts = 0
    job.run_at = utcnow()
    session.commit()
    notify_workers()
    return job


@app.get("/dead-letter", response_model=list[JobOut])
def dead_letter(session: Session = Depends(get_session)):
    return session.scalars(select(Job).where(Job.status == "dead").order_by(Job.id.desc())).all()


@app.get("/stats")
def stats(session: Session = Depends(get_session)):
    rows = session.execute(select(Job.status, func.count()).group_by(Job.status)).all()
    return {status: count for status, count in rows}


@app.get("/workers")
def workers():
    try:
        keys = sorted(_redis.scan_iter(match=f"{config.WORKER_KEY_PREFIX}*"))
    except redis.RedisError:
        raise HTTPException(503, "redis unavailable")
    return {"count": len(keys), "workers": [k.removeprefix(config.WORKER_KEY_PREFIX) for k in keys]}
