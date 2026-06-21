"""Хелперы завершения идемпотентных запросов."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.domain.services import idempotency_service


@dataclass
class IdempotencyContext:
    key: Optional[str] = None
    replay: Optional[dict[str, Any]] = None


async def complete_idempotent(ctx: IdempotencyContext, payload: dict[str, Any]) -> None:
    if ctx.key:
        await idempotency_service.store_response(ctx.key, payload)


async def fail_idempotent(ctx: IdempotencyContext) -> None:
    if ctx.key:
        await idempotency_service.release_key(ctx.key)
