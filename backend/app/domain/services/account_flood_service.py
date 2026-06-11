"""Лимит BotFather/Telegram на аккаунт — сохранение и ожидание между задачами."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from app.infrastructure.database import repository as db

_flood_account_id: ContextVar[int | None] = ContextVar("flood_account_id", default=None)


def set_flood_account_context(account_id: int | None):
    """Контекст аккаунта для записи FloodWait из botfather_client."""
    return _flood_account_id.set(account_id)


def reset_flood_account_context(token) -> None:
    _flood_account_id.reset(token)


def current_flood_account_id() -> int | None:
    return _flood_account_id.get()


def format_flood_wait_human(seconds: int) -> str:
    sec = max(0, int(seconds))
    if sec < 60:
        return f"{sec} сек"
    minutes, remainder = divmod(sec, 60)
    if minutes < 60:
        return f"{minutes} мин {remainder} сек" if remainder else f"{minutes} мин"
    hours, mins = divmod(minutes, 60)
    return f"{hours} ч {mins} мин" if mins else f"{hours} ч"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def record_flood_wait(account_id: int, wait_seconds: int) -> None:
    """Запомнить, до какого времени нельзя обращаться к BotFather с этого аккаунта."""
    wait = max(1, int(wait_seconds))
    await db.execute(
        """
        UPDATE telegram_accounts
        SET botfather_flood_until = GREATEST(
                COALESCE(botfather_flood_until, '-infinity'::timestamptz),
                NOW() + ($2 * INTERVAL '1 second')
            ),
            botfather_flood_seconds = GREATEST(COALESCE(botfather_flood_seconds, 0), $2),
            updated_at = NOW()
        WHERE id = $1
        """,
        account_id,
        wait,
    )


async def record_flood_from_details(account_id: int, details: dict | None) -> None:
    if not details or not details.get("flood_wait"):
        return
    wait = int(details.get("wait_seconds") or 0)
    if wait > 0:
        await record_flood_wait(account_id, wait)


async def clear_flood_wait(account_id: int) -> None:
    await db.execute(
        """
        UPDATE telegram_accounts
        SET botfather_flood_until = NULL,
            botfather_flood_seconds = NULL,
            updated_at = NOW()
        WHERE id = $1
        """,
        account_id,
    )


async def get_flood_remaining_seconds(account_id: int) -> int:
    row = await db.fetch_one(
        "SELECT botfather_flood_until FROM telegram_accounts WHERE id = $1",
        account_id,
    )
    if not row or not row.get("botfather_flood_until"):
        return 0
    until = row["botfather_flood_until"]
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    remaining = int((until - _utc_now()).total_seconds())
    if remaining <= 0:
        await clear_flood_wait(account_id)
        return 0
    return remaining


async def wait_for_flood_clear(
    account_id: int,
    *,
    sleep: Callable[[float], Awaitable[bool]],
    log: Optional[Callable[..., Awaitable[None]]] = None,
    label: str = "",
) -> None:
    """
    Ждёт окончания сохранённого лимита BotFather.
    sleep(seconds) -> True если задача отменена.
    """
    remaining = await get_flood_remaining_seconds(account_id)
    if remaining <= 0:
        return

    prefix = f"{label}: " if label else ""
    human = format_flood_wait_human(remaining)
    if log:
        await log(
            f"{prefix}ожидание лимита BotFather (с прошлой задачи), осталось {human}…",
            level="warn",
            context={
                "status": "waiting",
                "wait_seconds": remaining,
                "account_id": account_id,
                "flood_source": "account_saved",
            },
        )
    if await sleep(float(remaining + 1)):
        return
    await clear_flood_wait(account_id)


async def wait_for_flood_clear_simple(
    account_id: int,
    *,
    on_message: Optional[Callable[[str], Awaitable[None]]] = None,
) -> None:
    """Ожидание без отмены (одиночное создание бота)."""
    remaining = await get_flood_remaining_seconds(account_id)
    if remaining <= 0:
        return
    human = format_flood_wait_human(remaining)
    if on_message:
        await on_message(
            f"Ожидание лимита BotFather (с прошлой попытки), осталось {human}…"
        )
    await asyncio.sleep(remaining + 1)
    await clear_flood_wait(account_id)
