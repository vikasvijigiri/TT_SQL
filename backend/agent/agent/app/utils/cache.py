import os
import json
import time
import threading
from typing import Any, Optional

class MemoryCache:
    """A thread-safe in-memory cache with TTL support."""
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._data:
                return None
            val, expiry = self._data[key]
            if expiry is not None and time.time() > expiry:
                del self._data[key]
                return None
            return val

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            expiry = time.time() + ttl if ttl is not None else None
            self._data[key] = (value, expiry)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

class RedisCache:
    """Redis cache implementation."""
    def __init__(self, host: str, port: int):
        import redis
        self.client = redis.Redis(host=host, port=port, socket_timeout=1.0)

    def get(self, key: str) -> Optional[Any]:
        try:
            val = self.client.get(key)
            if val is not None:
                return json.loads(val.decode('utf-8'))
        except Exception:
            pass
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            val = json.dumps(value)
            if ttl is not None:
                self.client.setex(key, ttl, val)
            else:
                self.client.set(key, val)
        except Exception:
            pass

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except Exception:
            pass

    def clear(self) -> None:
        try:
            self.client.flushdb()
        except Exception:
            pass

class CacheService:
    """Unified Cache Service. Automatically falls back to thread-safe local memory
    if Redis is unavailable or fails to connect."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CacheService, cls).__new__(cls)
                cls._instance._init_cache()
            return cls._instance

    def _init_cache(self):
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        self._backend_type = "memory"
        self._backend = MemoryCache()

        try:
            import redis
            # Test connection
            r = redis.Redis(host=host, port=port, socket_timeout=1.0)
            r.ping()
            self._backend = RedisCache(host, port)
            self._backend_type = "redis"
            from agent.app.utils.logger import logger
            logger.info(f"CacheService: Connected successfully to Redis on {host}:{port}")
        except Exception as e:
            from agent.app.utils.logger import logger
            logger.info(f"CacheService: Redis connection failed ({e}). Falling back to fast local MemoryCache.")

    def get(self, key: str) -> Optional[Any]:
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._backend.set(key, value, ttl)

    def delete(self, key: str) -> None:
        self._backend.delete(key)

    def clear(self) -> None:
        self._backend.clear()

    @property
    def backend_type(self) -> str:
        return self._backend_type

cache_service = CacheService()
