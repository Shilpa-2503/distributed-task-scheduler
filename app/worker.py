import logging
import os
import signal
import socket
import time

import redis

from app import config
from app.db import SessionLocal
from app.service import claim_job, mark_failed, mark_succeeded, reap_stale
from app.tasks import TASKS

log = logging.getLogger("worker")
_stop = False


def _request_stop(signum, frame):
    global _stop
    _stop = True


def heartbeat(r, worker_id):
    try:
        r.set(f"{config.WORKER_KEY_PREFIX}{worker_id}", int(time.time()), ex=15)
    except redis.RedisError:
        pass


def wait_for_wake(r):
    """Sleep until the API signals a new job, or the poll interval passes."""
    try:
        r.blpop(config.WAKE_KEY, timeout=max(1, int(config.POLL_INTERVAL)))
    except redis.RedisError:
        time.sleep(config.POLL_INTERVAL)


def execute(claimed):
    try:
        handler = TASKS.get(claimed.task_name)
        if handler is None:
            raise LookupError(f"no handler for task '{claimed.task_name}'")
        handler(claimed.payload)
    except Exception as exc:
        with SessionLocal() as session:
            status = mark_failed(session, claimed.id, f"{type(exc).__name__}: {exc}")
        log.warning("job %s failed (attempt %s/%s) -> %s: %s",
                    claimed.id, claimed.attempts, claimed.max_attempts, status, exc)
    else:
        with SessionLocal() as session:
            mark_succeeded(session, claimed.id)
        log.info("job %s succeeded", claimed.id)


def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    r = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)
    last_reap = 0.0
    log.info("worker %s started", worker_id)

    while not _stop:
        heartbeat(r, worker_id)

        if time.time() - last_reap > 30:
            with SessionLocal() as session:
                recovered = reap_stale(session, config.VISIBILITY_TIMEOUT)
            if recovered:
                log.warning("recovered %s stale job(s)", recovered)
            last_reap = time.time()

        with SessionLocal() as session:
            claimed = claim_job(session, worker_id)

        if claimed is None:
            wait_for_wake(r)
            continue

        log.info("job %s (%s) claimed, attempt %s", claimed.id, claimed.task_name, claimed.attempts)
        execute(claimed)

    log.info("worker %s stopped", worker_id)


if __name__ == "__main__":
    run()
