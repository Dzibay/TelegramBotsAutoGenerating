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
BOT_USER_RE = re.compile(r"@?([a-z][a-z0-9_]{2,28}bot)\b", re.IGNORECASE)
_SKIP_BOT_USERNAMES = frozenset({"botfather"})


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


def _is_delete_success(text: str) -> bool:
    low = (text or "").lower()
    return any(
        p in low
        for p in (
            "success",
            "deleted",
            "done.",
            " was deleted",
            "has been deleted",
            "удалён",
            "удален",
        )
    )


def _is_bot_not_found(text: str) -> bool:
    low = (text or "").lower()
    return any(
        p in low
        for p in (
            "not found",
            "no bot",
            "can't find",
            "cannot find",
            "does not exist",
            "не найден",
            "unknown bot",
        )
    )


async def _try_confirm_delete(conv, reply, username: str) -> str:
    """Подтверждение удаления: кнопка, повтор username или Yes."""
    uname = username.lstrip("@")

    if reply.buttons:
        for row in reply.buttons:
            for btn in row:
                label = (getattr(btn, "text", None) or str(btn)).lower()
                if "delete" in label or "удал" in label:
                    try:
                        await reply.click(text=btn.text)
                        confirm = await _wait_reply(conv)
                        return confirm.raw_text or ""
                    except Exception as exc:
                        logger.debug("click delete button failed: %s", exc)

    text = (reply.raw_text or "").lower()
    if "confirm" in text or "sure" in text or "yes" in text or "удал" in text:
        for candidate in (f"@{uname}", uname, "Yes"):
            await conv.send_message(candidate)
            confirm = await _wait_reply(conv)
            body = confirm.raw_text or ""
            if _is_delete_success(body) or _is_bot_not_found(body):
                return body

    return text


def _extract_bot_usernames_from_reply(reply) -> list[str]:
    text = reply.raw_text or ""
    found: list[str] = []
    for match in BOT_USER_RE.finditer(text):
        name = normalize_bot_username(match.group(1))
        if name and name not in _SKIP_BOT_USERNAMES:
            found.append(name)
    if reply.buttons:
        for row in reply.buttons:
            for btn in row:
                label = getattr(btn, "text", None) or str(btn)
                for match in BOT_USER_RE.finditer(label):
                    name = normalize_bot_username(match.group(1))
                    if name and name not in _SKIP_BOT_USERNAMES:
                        found.append(name)
    return list(dict.fromkeys(found))


def _is_no_bots_reply(text: str) -> bool:
    low = (text or "").lower()
    return any(
        p in low
        for p in (
            "no bots",
            "don't have any bots",
            "you have no",
            "you do not have",
            "нет ботов",
            "no bot yet",
        )
    )


def _has_next_page(reply) -> bool:
    if not reply.buttons:
        return False
    for row in reply.buttons:
        for btn in row:
            label = (getattr(btn, "text", None) or str(btn)).strip()
            if label in (">", "»", ">>", "Next", "Далее"):
                return True
    return False


async def list_bots_via_botfather(client) -> list[str]:
    """Список username ботов аккаунта через /mybots."""
    found: list[str] = []
    seen_pages: set[int] = set()

    async with client.conversation("BotFather", timeout=30) as conv:
        await conv.send_message("/mybots")
        reply = await _wait_reply(conv)

        if _is_no_bots_reply(reply.raw_text or ""):
            return []

        while True:
            found.extend(_extract_bot_usernames_from_reply(reply))
            found = list(dict.fromkeys(found))

            if not _has_next_page(reply) or reply.id in seen_pages:
                break
            seen_pages.add(reply.id)
            try:
                for label in (">", "»", ">>", "Next", "Далее"):
                    try:
                        await reply.click(text=label)
                        break
                    except Exception:
                        continue
                else:
                    break
                reply = await _wait_reply(conv)
            except Exception as exc:
                logger.debug("mybots pagination failed: %s", exc)
                break

    return found


async def delete_all_bots_via_botfather(client, *, max_rounds: int = 25) -> int:
    """
    Удаляет всех ботов аккаунта в BotFather.
    Возвращает число успешно удалённых.
    """
    deleted = 0
    for _ in range(max_rounds):
        bots = await list_bots_via_botfather(client)
        if not bots:
            break
        round_deleted = 0
        for username in bots:
            try:
                await delete_bot_via_botfather(client, username)
                deleted += 1
                round_deleted += 1
            except BadRequestError as exc:
                logger.warning("delete @%s skipped: %s", username, exc)
            await asyncio.sleep(1.0)
        if round_deleted == 0:
            break
    return deleted


async def delete_bot_via_botfather(client, username: str) -> None:
    """
    Удаляет бота через /deletebot в BotFather.
    Если бот уже отсутствует в аккаунте — считается успехом.
    """
    uname = normalize_bot_username(username)
    if not uname:
        raise BadRequestError("У бота нет username для удаления в Telegram")

    async with client.conversation("BotFather", timeout=30) as conv:
        await conv.send_message("/deletebot")
        await _wait_reply(conv)

        await conv.send_message(f"@{uname}")
        reply = await _wait_reply(conv)
        text = reply.raw_text or ""

        if _is_delete_success(text):
            logger.info("Bot @%s deleted via BotFather", uname)
            return
        if _is_bot_not_found(text):
            logger.info("Bot @%s already absent in BotFather", uname)
            return

        low = text.lower()
        if "are you sure" in low or "confirm" in low or reply.buttons:
            text = await _try_confirm_delete(conv, reply, uname)
            if _is_delete_success(text) or _is_bot_not_found(text):
                logger.info("Bot @%s deleted via BotFather (confirmed)", uname)
                return

        if "invalid" in low and "bot" in low:
            raise BadRequestError(f"BotFather не нашёл бота @{uname}")

        raise BadRequestError(f"BotFather не подтвердил удаление @{uname}: {text[:200]}")


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
