"""Проверка бота через Telegram Bot API."""
from typing import Any

import httpx

from app.core.exceptions import BadRequestError


def telegram_bot_url(username: str | None) -> str | None:
    if not username:
        return None
    u = username.lower().strip().lstrip("@")
    return f"https://t.me/{u}" if u else None


async def verify_bot_token(token: str) -> dict[str, Any]:
    """Вызов getMe — подтверждает, что токен валиден и бот существует в Telegram."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            data = resp.json()
    except httpx.HTTPError as exc:
        raise BadRequestError(f"Не удалось связаться с Telegram API: {exc}") from exc

    if not data.get("ok"):
        desc = data.get("description", "неизвестная ошибка")
        raise BadRequestError(f"Telegram API: {desc}")

    result = data["result"]
    username = result.get("username")
    return {
        "telegram_bot_id": result.get("id"),
        "username": username,
        "display_name": result.get("first_name"),
        "can_join_groups": result.get("can_join_groups"),
        "can_read_all_group_messages": result.get("can_read_all_group_messages"),
        "supports_inline_queries": result.get("supports_inline_queries"),
        "telegram_url": telegram_bot_url(username),
    }
