from typing import Optional

import redis.asyncio as redis

from app.core.logging import get_logger

logger = get_logger(__name__)
_client: Optional[redis.Redis] = None


async def init_redis(url: str) -> None:
    global _client
    if not url:
        logger.info("Redis URL not set, cache disabled")
        return
    _client = redis.from_url(url, decode_responses=True)
    await _client.ping()
    logger.info("Redis connected")


async def close_redis() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None


def get_redis() -> Optional[redis.Redis]:
    return _client
