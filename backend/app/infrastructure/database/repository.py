from typing import Any, Optional

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
