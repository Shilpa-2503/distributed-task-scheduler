import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://scheduler:scheduler@localhost:5432/scheduler"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2"))          # seconds an idle worker waits
BACKOFF_BASE = float(os.getenv("BACKOFF_BASE", "2"))            # delay = base ** attempts
BACKOFF_CAP = float(os.getenv("BACKOFF_CAP", "300"))            # max retry delay (seconds)
VISIBILITY_TIMEOUT = int(os.getenv("VISIBILITY_TIMEOUT", "300"))  # "running" longer than this = worker died

WAKE_KEY = "jobs:wake"
WORKER_KEY_PREFIX = "worker:"
