"""Сериализация доступа к Telethon-сессии одного аккаунта (SQLite .session)."""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from app.config import Config
from app.core.logging import get_logger
from app.infrastructure.telegram.session_loader import load_client_from_tdata

logger = get_logger(__name__)

_account_locks: dict[int, asyncio.Lock] = {}


@dataclass
class _CachedSession:
    client: Any
    me: Any
    last_used: float


_cache: dict[tuple[int, int], _CachedSession] = {}


def account_lock(account_id: int) -> asyncio.Lock:
    lock = _account_locks.get(account_id)
    if lock is None:
        lock = asyncio.Lock()
        _account_locks[account_id] = lock
    return lock


PREP_ACCOUNT_LOCK_OFFSET = 2_000_000_000


def prep_account_lock(prep_account_id: int) -> asyncio.Lock:
    """Lock для prep worker (отдельное пространство id)."""
    return account_lock(PREP_ACCOUNT_LOCK_OFFSET + int(prep_account_id))


def tracked_account_locks_count() -> int:
    return len(_account_locks)


def cached_sessions_count() -> int:
    return len(_cache)


async def _disconnect_cached(entry: _CachedSession) -> None:
    try:
        await entry.client.disconnect()
    except Exception:
        pass


async def ensure_client_connected(client) -> None:
    """Переподключить Telethon, если сессию отключили (maintenance TTL или сеть)."""
    try:
        if client.is_connected():
            return
    except Exception:
        pass
    await client.connect()
    if not await client.is_user_authorized():
        raise ValueError("Сессия Telegram не авторизована")


async def acquire_cached_client(
    campaign_id: int,
    account_id: int,
    account: dict,
) -> tuple[Any, Any]:
    """Получить Telethon-клиент (из кэша или загрузить). Вызывать под account_lock."""
    ttl = Config.SESSION_CACHE_TTL_SEC
    key = (campaign_id, account_id)
    now = time.monotonic()

    if ttl > 0:
        entry = _cache.get(key)
        if entry is not None:
            if now - entry.last_used <= ttl:
                try:
                    await ensure_client_connected(entry.client)
                    entry.last_used = now
                    return entry.client, entry.me
                except Exception:
                    pass
            await _disconnect_cached(entry)
            _cache.pop(key, None)

    session_file = (
        Config.STORAGE_ROOT / "sessions" / str(campaign_id) / f"{account_id}.session"
    )
    client, me = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
    if ttl > 0:
        _cache[key] = _CachedSession(client=client, me=me, last_used=now)
    return client, me


async def release_cached_session(
    campaign_id: int,
    account_id: int,
    *,
    force_disconnect: bool = False,
) -> None:
    """Освободить кэшированную сессию (опционально disconnect)."""
    key = (campaign_id, account_id)
    entry = _cache.pop(key, None)
    if entry is None:
        return
    if force_disconnect or Config.SESSION_CACHE_TTL_SEC <= 0:
        await _disconnect_cached(entry)


async def reap_stale_cached_sessions() -> int:
    """Отключить сессии, простаивающие дольше TTL."""
    ttl = Config.SESSION_CACHE_TTL_SEC
    if ttl <= 0:
        return 0
    now = time.monotonic()
    stale_keys = [
        key
        for key, entry in _cache.items()
        if now - entry.last_used > ttl and not account_lock(key[1]).locked()
    ]
    for key in stale_keys:
        entry = _cache.pop(key, None)
        if entry:
            await _disconnect_cached(entry)
    if stale_keys:
        logger.debug("Reaped %s cached Telethon session(s)", len(stale_keys))
    return len(stale_keys)


@asynccontextmanager
async def locked_account_session(
    campaign_id: int,
    account_id: int,
    account: dict,
) -> AsyncIterator[tuple]:
    """Загрузить Telethon-клиент под per-account lock; disconnect при выходе если кэш выключен."""
    async with account_lock(account_id):
        client, me = await acquire_cached_client(campaign_id, account_id, account)
        disconnect_on_exit = Config.SESSION_CACHE_TTL_SEC <= 0
        try:
            yield client, me
        finally:
            if disconnect_on_exit:
                await release_cached_session(campaign_id, account_id, force_disconnect=True)


@asynccontextmanager
async def borrowed_account_session(
    campaign_id: int,
    account_id: int,
    account: dict,
) -> AsyncIterator[tuple]:
    """Сессия под lock без disconnect при выходе (для длинных pipeline-циклов)."""
    async with account_lock(account_id):
        client, me = await acquire_cached_client(campaign_id, account_id, account)
        yield client, me
