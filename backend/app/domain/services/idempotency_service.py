"""Идемпотентность мутаций через Redis (защита от двойного клика)."""
from __future__ import annotations

import json
from typing import Any

from app.infrastructure.cache.redis_client import get_redis

_IDEM_PREFIX = "idem:"
_DEFAULT_TTL_SEC = 600


async def get_cached_response(key: str) -> dict[str, Any] | None:
    if not key:
        return None
    redis = get_redis()
    if not redis:
        return None
    raw = await redis.get(f"{_IDEM_PREFIX}{key}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def reserve_key(key: str, *, ttl_sec: int = _DEFAULT_TTL_SEC) -> bool:
    """True = ключ зарезервирован (первый запрос), False = уже обрабатывается."""
    if not key:
        return True
    redis = get_redis()
    if not redis:
        return True
    ok = await redis.set(f"{_IDEM_PREFIX}{key}", json.dumps({"pending": True}), nx=True, ex=ttl_sec)
    return bool(ok)


async def store_response(key: str, payload: dict[str, Any], *, ttl_sec: int = _DEFAULT_TTL_SEC) -> None:
    if not key:
        return
    redis = get_redis()
    if not redis:
        return
    await redis.set(f"{_IDEM_PREFIX}{key}", json.dumps(payload, ensure_ascii=False), ex=ttl_sec)


async def release_key(key: str) -> None:
    if not key:
        return
    redis = get_redis()
    if not redis:
        return
    await redis.delete(f"{_IDEM_PREFIX}{key}")
