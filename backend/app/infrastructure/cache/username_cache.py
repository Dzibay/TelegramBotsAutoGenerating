"""TTL-кэш проверок username в Telegram (снижение ResolveUsername)."""
from __future__ import annotations

import time

_TG_USERNAME_CACHE: dict[str, tuple[bool, float]] = {}
_CACHE_TTL_SEC = 300.0
_CACHE_MAX = 2000


def _cache_get(username: str) -> bool | None:
    key = username.lower().lstrip("@")
    entry = _TG_USERNAME_CACHE.get(key)
    if not entry:
        return None
    free, ts = entry
    if time.monotonic() - ts > _CACHE_TTL_SEC:
        _TG_USERNAME_CACHE.pop(key, None)
        return None
    return free


def _cache_set(username: str, free: bool) -> None:
    key = username.lower().lstrip("@")
    if len(_TG_USERNAME_CACHE) >= _CACHE_MAX:
        oldest = min(_TG_USERNAME_CACHE.items(), key=lambda x: x[1][1])
        _TG_USERNAME_CACHE.pop(oldest[0], None)
    _TG_USERNAME_CACHE[key] = (free, time.monotonic())


def invalidate_username_cache(username: str | None = None) -> None:
    if username:
        _TG_USERNAME_CACHE.pop(username.lower().lstrip("@"), None)
    else:
        _TG_USERNAME_CACHE.clear()


def cached_username_checks() -> int:
    return len(_TG_USERNAME_CACHE)
