"""Публикация сигналов bot-runner через Redis."""
from __future__ import annotations

from app.config import Config
from app.core.logging import get_logger
from app.infrastructure.cache.redis_client import get_redis

logger = get_logger(__name__)


async def signal_bot_runner_reload(reason: str = "config_change") -> None:
    redis = get_redis()
    if not redis:
        return
    try:
        await redis.publish(Config.REDIS_BOT_RUNNER_RELOAD_CHANNEL, reason)
    except Exception as exc:
        logger.debug("bot_runner reload signal failed: %s", exc)
