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


async def _bot_api_call(client: httpx.AsyncClient, token: str, method: str) -> dict[str, Any]:
    """Вызов метода Bot API, возвращает result или {} (для best-effort полей)."""
    resp = await client.get(f"https://api.telegram.org/bot{token}/{method}")
    data = resp.json()
    if not data.get("ok"):
        return {}
    result = data.get("result")
    return result if isinstance(result, dict) else {}


async def fetch_bot_profile(token: str) -> dict[str, Any]:
    """Читает профиль существующего бота (read-only) для импорта по токену.

    getMe обязателен (подтверждает валидность токена). Имя/описание/about —
    best-effort: при сбое отдельного метода поле остаётся пустым.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            me_resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            me_data = me_resp.json()
            if not me_data.get("ok"):
                desc = me_data.get("description", "неизвестная ошибка")
                raise BadRequestError(f"Невалидный токен: {desc}")
            me = me_data["result"]
            name = await _bot_api_call(client, token, "getMyName")
            description = await _bot_api_call(client, token, "getMyDescription")
            short = await _bot_api_call(client, token, "getMyShortDescription")
    except httpx.HTTPError as exc:
        raise BadRequestError(f"Не удалось связаться с Telegram API: {exc}") from exc

    username = me.get("username")
    display_name = (name.get("name") or me.get("first_name") or "").strip()
    return {
        "telegram_bot_id": me.get("id"),
        "username": username,
        "display_name": display_name,
        "description": (description.get("description") or "").strip(),
        "about_text": (short.get("short_description") or "").strip(),
        "telegram_url": telegram_bot_url(username),
    }
