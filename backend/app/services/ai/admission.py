"""Bounded single-worker admission. No queue and no lock held over provider I/O."""
from collections import Counter
from threading import Lock
from app.core.config import settings
from app.services.ai.errors import AIError
from app.services.rate_limit import ai_limiter

_lock = Lock()
_running = Counter()


def acquire(user_id, operation):
    if not settings.AI_ACCEPT_NEW_REQUESTS:
        raise AIError('AI_ADMISSION_CLOSED', 503)
    ai_limiter.check(f'{user_id}:operations', limit=settings.AI_RATE_LIMIT_REQUESTS,
                     window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS)
    with _lock:
        if sum(_running.values()) >= settings.AI_MAX_CONCURRENT or _running[user_id] >= settings.AI_MAX_CONCURRENT_PER_USER:
            raise AIError('AI_CAPACITY_EXCEEDED', 429)
        _running[user_id] += 1


def release(user_id):
    with _lock:
        _running[user_id] -= 1
        if _running[user_id] <= 0:
            _running.pop(user_id, None)
