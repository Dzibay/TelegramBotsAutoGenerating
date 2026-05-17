"""Создание бота через @BotFather (user-клиент Telethon)."""
import asyncio
import re
from collections.abc import Callable
from pathlib import Path

from app.core.exceptions import BadRequestError
from app.core.logging import get_logger
from app.utils.telegram_username import normalize_bot_username

logger = get_logger(__name__)

TOKEN_RE = re.compile(r"(\d{8,10}:[A-Za-z0-9_-]{30,})")


async def _wait_reply(conv, timeout: float = 25.0):
    try:
        return await asyncio.wait_for(conv.get_response(), timeout=timeout)
    except asyncio.TimeoutError:
        raise BadRequestError("BotFather не ответил вовремя. Попробуйте ещё раз.")


def _is_username_taken_reply(text: str) -> bool:
    low = (text or "").lower()
    return (
        "already taken" in low
        or "occupied" in low
        or "is already" in low
        or ("sorry" in low and "username" in low and "invalid" not in low)
    )


def _is_username_invalid_reply(text: str) -> bool:
    low = (text or "").lower()
    return "username is invalid" in low or "invalid username" in low


def _raise_botfather_error(text: str, *, field: str, username: str = "") -> None:
    low = (text or "").lower()
    if _is_username_invalid_reply(text):
        raise BadRequestError(
            f"Username «@{username}» отклонён BotFather. "
            "Допустимо: латиница, цифры, _, длина 5–32, обязательно окончание bot."
        )
    if field == "display_name" and ("invalid" in low or "sorry" in low):
        raise BadRequestError(f"Имя бота отклонено BotFather: {text[:120]}")
    if _is_username_taken_reply(text):
        raise BadRequestError(f"Username @{username} уже занят в Telegram.")
    if "too many" in low:
        raise BadRequestError("Лимит BotFather: слишком много запросов. Подождите и повторите.")
    raise BadRequestError(f"BotFather: {text[:200]}")


async def create_bot_via_botfather(
    client,
    display_name: str,
    username: str,
    *,
    username_factory: Callable[[int], str] | None = None,
    max_username_attempts: int = 8,
) -> dict[str, str]:
    """
    Возвращает {token, username} после диалога с BotFather.
    При «username taken» повторяет ввод в том же диалоге (username_factory).
    """
    attempt = 0
    current = normalize_bot_username(username)

    async with client.conversation("BotFather", timeout=30) as conv:
        await conv.send_message("/newbot")
        await _wait_reply(conv)

        await conv.send_message(display_name[:64])
        reply = await _wait_reply(conv)
        text = reply.raw_text or ""

        if "invalid" in text.lower() and "username" not in text.lower():
            _raise_botfather_error(text, field="display_name")

        while attempt < max_username_attempts:
            await conv.send_message(current[:32])
            reply = await _wait_reply(conv)
            text = reply.raw_text or ""

            match = TOKEN_RE.search(text)
            if match:
                token = match.group(1)
                m_user = re.search(r"@([a-zA-Z0-9_]{5,32})", text)
                final_username = normalize_bot_username(m_user.group(1)) if m_user else current
                logger.info("Bot created @%s (attempt %s)", final_username, attempt + 1)
                return {"token": token, "username": final_username}

            if _is_username_taken_reply(text) or _is_username_invalid_reply(text):
                if username_factory and attempt + 1 < max_username_attempts:
                    attempt += 1
                    current = normalize_bot_username(username_factory(attempt))
                    logger.info("Username retry #%s: @%s", attempt + 1, current)
                    continue
                _raise_botfather_error(text, field="username", username=current)

            if "invalid" in text.lower() or "sorry" in text.lower():
                _raise_botfather_error(text, field="username", username=current)

        raise BadRequestError(
            f"Не удалось зарегистрировать бота после {max_username_attempts} попыток username."
        )


async def set_bot_name(client, username: str, display_name: str) -> None:
    name = (display_name or "").strip()[:64]
    if not name:
        return
    try:
        async with client.conversation("BotFather", timeout=20) as conv:
            await conv.send_message("/setname")
            await _wait_reply(conv)
            await conv.send_message(f"@{username.lstrip('@')}")
            await _wait_reply(conv)
            await conv.send_message(name)
            await _wait_reply(conv)
    except Exception as exc:
        logger.warning("setname failed for @%s: %s", username, exc)


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


async def set_bot_about(client, username: str, about: str) -> None:
    text = (about or "").strip()[:120]
    if not text:
        return
    try:
        async with client.conversation("BotFather", timeout=20) as conv:
            await conv.send_message("/setabouttext")
            await _wait_reply(conv)
            await conv.send_message(f"@{username.lstrip('@')}")
            await _wait_reply(conv)
            await conv.send_message(text)
            await _wait_reply(conv)
    except Exception as exc:
        logger.warning("setabouttext failed for @%s: %s", username, exc)


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
