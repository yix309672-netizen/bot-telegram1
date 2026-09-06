# coding=utf-8
"""缓存层：Redis 可达则用，不可达自动降级为进程内存 dict（接口一致）"""
import logging
import os
import time

logger = logging.getLogger(__name__)


class MemoryCache:
    # 降级缓存：支持过期时间的最小实现
    def __init__(self):
        self._store = {}

    def get(self, key):
        val, exp = self._store.get(key, (None, 0))
        if exp and exp < time.time():
            self._store.pop(key, None)
            return None
        return val

    def set(self, key, value, ex=None):
        self._store[key] = (value, time.time() + ex if ex else 0)
        return True

    def incr(self, key):
        val = self.get(key)
        val = int(val or 0) + 1
        _, exp = self._store.get(key, (None, 0))
        self._store[key] = (val, exp)
        return val

    def expire(self, key, seconds):
        if key in self._store:
            val, _ = self._store[key]
            self._store[key] = (val, time.time() + seconds)
        return True

    def delete(self, key):
        self._store.pop(key, None)
        return True


def _connect_redis():
    url = os.getenv("REDIS_URL", "")
    if not url:
        host = os.getenv("REDIS_HOST", "")
        if host:
            port = os.getenv("REDIS_PORT", "6379")
            url = f"redis://{host}:{port}/0"
    if not url:
        return None
    try:
        import redis
        client = redis.Redis.from_url(url, socket_connect_timeout=3, decode_responses=True)
        client.ping()
        logger.info("Redis 已连接")
        return client
    except Exception as e:
        logger.warning(f"Redis 不可达，使用内存缓存: {e}")
        return None


redis_client = _connect_redis()
cache = redis_client if redis_client is not None else MemoryCache()


def is_redis_live() -> bool:
    return redis_client is not None
