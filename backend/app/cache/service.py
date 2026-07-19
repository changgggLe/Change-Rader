import json
from typing import Any, Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.settings.config import Settings


class CacheService(Protocol):
    def get_json(self, key: str) -> Any | None: ...
    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def delete_prefix(self, prefix: str) -> None: ...
    def health(self) -> bool: ...
    def close(self) -> None: ...


class NullCache:
    def get_json(self, key: str) -> None:
        return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        return None

    def delete_prefix(self, prefix: str) -> None:
        return None

    def health(self) -> bool:
        return True

    def close(self) -> None:
        return None


class MemoryCache:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get_json(self, key: str) -> Any | None:
        return self._values.get(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._values[key] = value

    def delete_prefix(self, prefix: str) -> None:
        for key in [item for item in self._values if item.startswith(prefix)]:
            self._values.pop(key, None)

    def health(self) -> bool:
        return True

    def close(self) -> None:
        self._values.clear()


class RedisCache:
    def __init__(self, url: str) -> None:
        self._client = Redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)

    def get_json(self, key: str) -> Any | None:
        try:
            value = self._client.get(key)
            return json.loads(value) if value else None
        except RedisError:
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            self._client.setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False))
        except RedisError:
            return None

    def delete_prefix(self, prefix: str) -> None:
        try:
            keys = list(self._client.scan_iter(match=f"{prefix}*", count=100))
            if keys:
                self._client.delete(*keys)
        except RedisError:
            return None

    def health(self) -> bool:
        try:
            return bool(self._client.ping())
        except RedisError:
            return False

    def close(self) -> None:
        self._client.close()


def build_cache(settings: Settings) -> CacheService:
    if settings.cache_backend == "redis":
        return RedisCache(settings.redis_url)
    if settings.cache_backend == "memory":
        return MemoryCache()
    return NullCache()
