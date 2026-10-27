import random

from app.config import BACKOFF_BASE, BACKOFF_CAP


def backoff_seconds(attempts: int, base: float = BACKOFF_BASE,
                    cap: float = BACKOFF_CAP, jitter: bool = True) -> float:
    """Exponential backoff: base ** attempts, capped. Equal jitter keeps
    retries from many failed jobs from all landing at the same moment."""
    delay = min(cap, base ** attempts)
    if jitter:
        delay = random.uniform(delay / 2, delay)
    return delay
