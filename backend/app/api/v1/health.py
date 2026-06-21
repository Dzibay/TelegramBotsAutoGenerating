from fastapi import APIRouter

from app.config import Config
from app.domain.services.account_session_service import (
    acquire_cached_client,
    cached_sessions_count,
    release_cached_session,
    tracked_account_locks_count,
)
from app.infrastructure.cache.username_cache import cached_username_checks
from app.infrastructure.cache.redis_client import get_redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def api_health():
    queues: dict[str, int | None] = {}
    redis = get_redis()
    if redis:
        for key, name in (
            ("creation_jobs", Config.REDIS_JOB_QUEUE),
            ("bot_sync", Config.REDIS_BOT_SYNC_QUEUE),
            ("account_prep", Config.REDIS_PREP_QUEUE),
        ):
            try:
                queues[key] = int(await redis.llen(name))
            except Exception:
                queues[key] = None
    return {
        "status": "ok",
        "redis": bool(redis),
        "queues": queues,
        "account_session_locks": tracked_account_locks_count(),
        "username_cache_entries": cached_username_checks(),
        "telethon_session_cache": cached_sessions_count(),
    }
