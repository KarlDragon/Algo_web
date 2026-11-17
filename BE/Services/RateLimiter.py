"""Auth and comment rate limits.

Single worker: sliding window in RAM. REDIS_URL: atomic Redis fixed window shared
across processes (recommended for deployment). Do not trust X-Forwarded-For
from untrusted clients; AuthController uses request.client.host.
"""
from collections import defaultdict, deque
from hashlib import sha256
from threading import Lock
from time import monotonic

from Services.AuthError import AuthError
from Services.RedisClient import redis_client

_RATE_SCRIPT = """
local count=redis.call('INCR',KEYS[1])
if count==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end
return count
"""


class RateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        client = redis_client()
        if client is not None:
            hashed = sha256(key.encode('utf-8')).hexdigest()
            try:
                count = client.eval(_RATE_SCRIPT, 1, f'algoweb:rl:{hashed}', window_seconds)
            except Exception as exc:
                raise AuthError('Hệ thống giới hạn truy cập đang gián đoạn, vui lòng thử lại sau', 503) from exc
            if count > limit:
                raise AuthError('Bạn thao tác quá nhiều lần. Vui lòng thử lại sau.', 429)
            return
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise AuthError('Bạn thao tác quá nhiều lần. Vui lòng thử lại sau.', 429)
            events.append(now)
            # Bound memory on long-running development servers.
            if len(self._events) > 10000:
                stale = [k for k, v in self._events.items() if not v or now - v[-1] >= window_seconds]
                for k in stale:
                    self._events.pop(k, None)

    def clear(self, key: str) -> None:
        client = redis_client()
        if client is not None:
            try:
                client.delete('algoweb:rl:' + sha256(key.encode('utf-8')).hexdigest())
            except Exception as exc:
                raise AuthError('Không thể cập nhật giới hạn truy cập', 503) from exc
            return
        with self._lock:
            self._events.pop(key, None)


auth_rate_limiter = RateLimiter()
