import asyncio
from typing import Optional

import redis.asyncio as redis

from app.core.logging import get_logger

logger = get_logger(__name__)
_client: Optional[redis.Redis] = None
_redis_url: str = ""


async def init_redis(url: str) -> None:
    global _client, _redis_url
    if not url:
        logger.info("Redis URL not set, cache disabled")
        _redis_url = ""
        return
    _redis_url = url
    _client = redis.from_url(
        url,
        decode_responses=True,
        socket_keepalive=True,
        health_check_interval=30,
        retry_on_timeout=True,
        socket_connect_timeout=5,
    )
    await _client.ping()
    logger.info("Redis connected")


async def reconnect_redis() -> None:
    global _client
    if not _redis_url:
        return
    if _client:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None
    await init_redis(_redis_url)


async def close_redis() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def get_redis() -> Optional[redis.Redis]:
    return _client


async def blocking_pop(queue: str, timeout: int = 5) -> tuple[str, str] | None:
    """BRPOP с автоматическим переподключением при обрыве соединения."""
    result = await blocking_pop_any([queue], timeout=timeout)
    return result


async def blocking_pop_any(queues: list[str], timeout: int = 5) -> tuple[str, str] | None:
    """BRPOP из первой непустой очереди. Возвращает (queue_name, payload)."""
    while True:
        client = get_redis()
        if not client:
            logger.error("Redis не настроен — ожидание…")
            await asyncio.sleep(5)
            continue
        try:
            result = await client.brpop(queues, timeout=timeout)
            if not result:
                return None
            queue_name, payload = result
            return queue_name, payload
        except (redis.ConnectionError, redis.TimeoutError, OSError) as exc:
            logger.warning("Redis BRPOP failed (%s), reconnecting…", exc)
            await reconnect_redis()
            await asyncio.sleep(2)
