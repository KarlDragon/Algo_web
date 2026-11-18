"""TTL cache for public catalog data only.

Local: bounded cache for development. With REDIS_URL: shared cache and invalidation
across workers. Never cache user-specific responses (e.g., /users/me).
"""
import json
import os
from collections import OrderedDict
from threading import RLock
from time import monotonic

from fastapi.encoders import jsonable_encoder
from Services.RedisClient import redis_client

_lock = RLock()
_cache: OrderedDict[str, tuple[float, object]] = OrderedDict()
_MAX_ENTRIES = 256


def get_or_build(builder, ttl_seconds=300, key='home'):
    client = redis_client()
    if client is not None:
        try:
            version = client.get('algoweb:cache:epoch') or b'0'
            if isinstance(version, bytes):
                version = version.decode('ascii')
            cache_key = f'algoweb:cache:{version}:{key}'
            cached = client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
            data = jsonable_encoder(builder())
            client.set(cache_key, json.dumps(data, ensure_ascii=False), ex=int(ttl_seconds))
            return data
        except Exception as exc:
            raise RuntimeError('Redis cache không khả dụng; vui lòng kiểm tra REDIS_URL') from exc

    with _lock:
        now = monotonic()
        found = _cache.get(key)
        if found is not None and found[0] > now:
            _cache.move_to_end(key)
            return found[1]
        if found is not None:
            _cache.pop(key, None)
        data = builder()
        _cache[key] = (monotonic() + ttl_seconds, data)
        _cache.move_to_end(key)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
        return data


def invalidate():
    client = redis_client()
    if client is not None:
        try:
            client.incr('algoweb:cache:epoch')
        except Exception as exc:
            raise RuntimeError('Không thể làm mới cache Redis') from exc
    with _lock:
        _cache.clear()
