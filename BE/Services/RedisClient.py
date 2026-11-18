"""Optional shared Redis backend; imported lazily to keep local SQLite setup simple."""
import os
from functools import lru_cache


@lru_cache(maxsize=4)
def _connect(url: str):
    try:
        import redis
    except ImportError as exc:
        raise RuntimeError('Đã cấu hình REDIS_URL nhưng thiếu thư viện redis; cài requirements-production.txt') from exc
    return redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def redis_client():
    url = os.getenv('REDIS_URL', '').strip()
    return _connect(url) if url else None
