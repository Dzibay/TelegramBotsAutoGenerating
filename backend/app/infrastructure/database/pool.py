from typing import Optional

import asyncpg

from app.config import Config
from app.core.logging import get_logger

logger = get_logger(__name__)
_pool: Optional[asyncpg.Pool] = None


def _dsn() -> str:
    return (
        f"postgresql://{Config.DB_USER}:{Config.DB_PASSWORD}"
        f"@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
    )


async def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    _pool = await asyncpg.create_pool(
        dsn=_dsn(),
        min_size=Config.DB_POOL_MIN,
        max_size=Config.DB_POOL_MAX,
    )
    logger.info("PostgreSQL pool ready")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool
