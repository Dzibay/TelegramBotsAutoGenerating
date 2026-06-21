"""Проверка и выделение уникальных username ботов."""
import secrets
from typing import Callable, Optional

import httpx

from app.core.logging import get_logger
from app.infrastructure.cache.username_cache import _cache_get, _cache_set
from app.infrastructure.database import repository as db
from app.utils.telegram_username import (
    build_username_from_keyword,
    normalize_bot_username,
    username_variants,
)

logger = get_logger(__name__)


async def get_reserved_usernames(*, exclude_bot_id: Optional[int] = None) -> set[str]:
    """Username, уже занятые в нашей БД."""
    if exclude_bot_id:
        rows = await db.fetch_all(
            """
            SELECT LOWER(TRIM(username)) AS u FROM bots
            WHERE username IS NOT NULL AND TRIM(username) != ''
              AND id != $1
            """,
            exclude_bot_id,
        )
    else:
        rows = await db.fetch_all(
            """
            SELECT LOWER(TRIM(username)) AS u FROM bots
            WHERE username IS NOT NULL AND TRIM(username) != ''
            """
        )
    return {r["u"] for r in rows if r.get("u")}


async def is_username_taken_in_db(username: str, *, exclude_bot_id: Optional[int] = None) -> bool:
    u = username.lower().strip().lstrip("@")
    reserved = await get_reserved_usernames(exclude_bot_id=exclude_bot_id)
    return u in reserved


async def check_username_on_telegram(client, username: str) -> bool:
    """
    True — username свободен в Telegram.
    False — занят или недоступен для регистрации.
    """
    name = username.lstrip("@").lower()
    if not name:
        return False
    cached = _cache_get(name)
    if cached is not None:
        return cached
    try:
        from telethon.errors import UsernameNotOccupiedError, UsernameOccupiedError
        from telethon.tl.functions.contacts import ResolveUsernameRequest

        await client(ResolveUsernameRequest(username=name))
        _cache_set(name, False)
        return False
    except Exception as exc:
        exc_name = type(exc).__name__
        if exc_name == "UsernameNotOccupiedError":
            _cache_set(name, True)
            return True
        if exc_name == "UsernameOccupiedError":
            _cache_set(name, False)
            return False
        logger.debug("ResolveUsername @%s: %s — fallback HTTP", name, exc)
        free = await _check_username_http(name)
        _cache_set(name, free)
        return free


async def _check_username_http(username: str) -> bool:
    """Эвристика через t.me (если Telethon недоступен)."""
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as http:
            resp = await http.get(f"https://t.me/{username}")
            if resp.status_code != 200:
                return True
            body = resp.text.lower()
            if "if you have telegram" in body and "tgme_page_extra" not in body:
                return True
            if f"@{username}" in body or "tgme_page_title" in body:
                return False
            return True
    except Exception as exc:
        logger.warning("HTTP username check failed for @%s: %s", username, exc)
        return True


async def allocate_unique_username(
    keyword: str,
    *,
    preferred: Optional[str] = None,
    campaign_id: Optional[int] = None,
    exclude_bot_id: Optional[int] = None,
    telethon_client=None,
) -> str:
    """
    Возвращает username, свободный в БД и (по возможности) в Telegram.
    """
    reserved = await get_reserved_usernames(exclude_bot_id=exclude_bot_id)
    candidates = username_variants(
        keyword,
        preferred=preferred,
        campaign_id=campaign_id,
    )

    for candidate in candidates:
        key = candidate.lower()
        if key in reserved:
            continue
        if telethon_client is not None:
            free = await check_username_on_telegram(telethon_client, candidate)
            if not free:
                reserved.add(key)
                continue
        return candidate

    fallback = build_username_from_keyword(
        keyword or "bot",
        variant=99,
        campaign_id=campaign_id,
        unique_token=secrets.token_hex(3),
    )
    while fallback.lower() in reserved:
        fallback = build_username_from_keyword(
            keyword or "bot",
            variant=100,
            campaign_id=campaign_id,
            unique_token=secrets.token_hex(4),
        )
    return fallback


def make_username_factory(
    keyword: str,
    *,
    preferred: Optional[str] = None,
    campaign_id: Optional[int] = None,
    reserved: Optional[set[str]] = None,
) -> Callable[[int], str]:
    """Фабрика для повторных попыток в BotFather (синхронная, по attempt)."""
    reserved_set = set(reserved or [])
    variants = username_variants(keyword, preferred=preferred, campaign_id=campaign_id)

    def next_username(attempt: int) -> str:
        idx = min(attempt, len(variants) - 1)
        for i in range(idx, len(variants)):
            u = variants[i]
            if u.lower() not in reserved_set:
                reserved_set.add(u.lower())
                return u
        u = build_username_from_keyword(
            keyword,
            variant=attempt + 10,
            campaign_id=campaign_id,
            unique_token=secrets.token_hex(3),
        )
        reserved_set.add(u.lower())
        return u

    return next_username
