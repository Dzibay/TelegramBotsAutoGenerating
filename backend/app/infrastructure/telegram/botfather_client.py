"""Создание бота через @BotFather (user-клиент Telethon)."""
import asyncio
import re
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

TOKEN_RE = re.compile(r"(\d{8,10}:[A-Za-z0-9_-]{30,})")


async def _wait_reply(conv, timeout: float = 25.0):
    try:
        return await asyncio.wait_for(conv.get_response(), timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError("BotFather не ответил вовремя")


async def create_bot_via_botfather(
    client,
    display_name: str,
    username: str,
) -> dict[str, str]:
    """Возвращает {token, username} после диалога с BotFather."""
    username = username.lower().strip()
    if not username.endswith("bot"):
        username = f"{username}_bot" if len(username) < 28 else username[:32]
    if len(username) < 5:
        username = f"tg_{username}_bot"

    async with client.conversation("BotFather", timeout=30) as conv:
        await conv.send_message("/newbot")
        await _wait_reply(conv)

        await conv.send_message(display_name[:64])
        reply = await _wait_reply(conv)
        text = reply.raw_text or ""

        if "invalid" in text.lower() or "sorry" in text.lower():
            raise ValueError(f"BotFather отклонил имя: {text}")

        await conv.send_message(username[:32])
        reply = await _wait_reply(conv)
        text = reply.raw_text or ""

        if "already taken" in text.lower() or "occupied" in text.lower():
            raise ValueError(f"Username занят: {username}")

        match = TOKEN_RE.search(text)
        if not match:
            raise ValueError(f"Токен не найден в ответе BotFather: {text[:200]}")

        token = match.group(1)
        logger.info("Bot created @%s", username)
        return {"token": token, "username": username}


async def set_bot_description(client, username: str, description: str) -> None:
    try:
        async with client.conversation("BotFather", timeout=20) as conv:
            await conv.send_message("/setdescription")
            await _wait_reply(conv)
            await conv.send_message(f"@{username.lstrip('@')}")
            await _wait_reply(conv)
            await conv.send_message(description[:512])
            await _wait_reply(conv)
    except Exception as exc:
        logger.warning("setdescription failed for @%s: %s", username, exc)


async def set_bot_photo(client, username: str, image_path: Path) -> None:
    path = Path(image_path)
    if not path.is_file():
        return
    try:
        async with client.conversation("BotFather", timeout=30) as conv:
            await conv.send_message("/setuserpic")
            await _wait_reply(conv)
            await conv.send_message(f"@{username.lstrip('@')}")
            await _wait_reply(conv)
            await conv.send_file(path)
            await _wait_reply(conv)
    except Exception as exc:
        logger.warning("setuserpic failed for @%s: %s", username, exc)
