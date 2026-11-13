"""Simple in-process rate limiting for one Uvicorn worker (use Redis in production)."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from Services.AuthError import AuthError


class RateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise AuthError("Bạn thao tác quá nhiều lần. Vui lòng thử lại sau.", 429)
            events.append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


auth_rate_limiter = RateLimiter()
