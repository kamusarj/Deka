"""Small single-process sliding-window limits for sensitive/costly endpoints."""

from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException


class SlidingWindowRateLimiter:
    def __init__(self):
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    @staticmethod
    def _discard_expired(events: deque[float], cutoff: float) -> None:
        while events and events[0] <= cutoff:
            events.popleft()

    def _prune(self, cutoff: float) -> None:
        for event_key, event_times in list(self._events.items()):
            self._discard_expired(event_times, cutoff)
            if not event_times:
                self._events.pop(event_key, None)

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            self._prune(cutoff)
            events = self._events.setdefault(key, deque())
            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window_seconds - now) + 1)
                raise HTTPException(
                    status_code=429,
                    detail="Bạn thao tác quá nhanh. Vui lòng thử lại sau.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)

    def active_key_count(self) -> int:
        with self._lock:
            return len(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


login_limiter = SlidingWindowRateLimiter()
ai_limiter = SlidingWindowRateLimiter()
