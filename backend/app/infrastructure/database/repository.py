from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from app.infrastructure.database.pool import get_pool


def _row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row else {}


async def fetch_one(query: str, *args) -> Optional[dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
    return _row_to_dict(row) if row else None


async def fetch_all(query: str, *args) -> list[dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
    return [_row_to_dict(r) for r in rows]


async def execute(query: str, *args) -> str:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetch_val(query: str, *args) -> Any:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


@asynccontextmanager
async def transaction() -> AsyncIterator:
    """Транзакция PostgreSQL с advisory lock внутри одного connection."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def tx_fetch_one(conn, query: str, *args) -> Optional[dict[str, Any]]:
    row = await conn.fetchrow(query, *args)
    return _row_to_dict(row) if row else None


async def tx_execute(conn, query: str, *args) -> str:
    return await conn.execute(query, *args)


async def tx_fetch_all(conn, query: str, *args) -> list[dict[str, Any]]:
    rows = await conn.fetch(query, *args)
    return [_row_to_dict(r) for r in rows]
