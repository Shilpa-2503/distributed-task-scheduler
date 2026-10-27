# Distributed Task Scheduler

Python · FastAPI · PostgreSQL · Redis · Docker

A job queue where many workers pull from one Postgres table safely.

## Run it

1. Install Docker Desktop and open this folder in VS Code.
2. In the terminal: `docker compose up --build --scale worker=3`
3. Open http://localhost:8000/docs

## Try it

```bash
# a job that succeeds
curl -X POST localhost:8000/jobs -H "Content-Type: application/json" \
  -d '{"task_name":"echo","payload":{"msg":"hi"}}'

# a job that always fails -> retries with backoff -> dead-letter
curl -X POST localhost:8000/jobs -H "Content-Type: application/json" \
  -d '{"task_name":"fail","max_attempts":3}'

curl localhost:8000/stats
curl localhost:8000/dead-letter
curl localhost:8000/workers
curl -X POST localhost:8000/jobs/1/retry     # re-queue a dead job
```

## How it works

- **Claiming jobs:** `SELECT ... FOR UPDATE SKIP LOCKED` (app/service.py). A worker locks one due row; other workers skip locked rows instead of waiting. No job is claimed twice at once.
- **Retries:** on failure, `run_at` is pushed out by exponential backoff with jitter (app/backoff.py).
- **Dead-letter:** after `max_attempts` the job gets status `dead`. See `/dead-letter`, re-queue with `/jobs/{id}/retry`.
- **Scaling:** add workers with `--scale worker=N`. No coordination needed.
- **Crash recovery:** a job stuck in `running` past `VISIBILITY_TIMEOUT` is put back in the queue.
- **Redis:** the API pushes a wake-up signal so idle workers react immediately. Workers also write heartbeats (shown at `/workers`). If Redis is down, workers fall back to polling.
- **Graceful shutdown:** workers finish the current job on SIGTERM.

## Add a task

In `app/tasks.py`:

```python
@task("send_email")
def send_email(payload):
    ...
```

## Tests

`python -m unittest discover tests` (backoff logic only)

## Known limits

- Tables are created with `create_all`, not migrations (use Alembic for production).
- Delivery is at-least-once: a task can run twice if a worker dies mid-job, so make tasks safe to repeat.
