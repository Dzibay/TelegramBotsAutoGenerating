"""Создание бота через @BotFather (user-клиент Telethon)."""
import asyncio
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from telethon.errors.rpcerrorlist import FloodWaitError

from app.core.exceptions import BadRequestError
from app.core.logging import get_logger
from app.infrastructure.telegram.botfather_pacing import (
    max_server_flood_wait_sec,
    pace_before_conversation,
    throttle_pause_total_sec,
)
from app.utils.telegram_username import normalize_bot_username

logger = get_logger(__name__)

TOKEN_RE = re.compile(r"(\d{8,10}:[A-Za-z0-9_-]{30,})")
BOT_USER_RE = re.compile(r"@?([a-z][a-z0-9_]{2,28}bot)\b", re.IGNORECASE)
# BotFather троттлит на уровне приложения: «too many attempts ... try again in N seconds».
# Приходит обычным текстом (НЕ FloodWaitError), поэтому ловим отдельно.
TRY_AGAIN_RE = re.compile(r"try again in (\d+)\s*second", re.IGNORECASE)
_SKIP_BOT_USERNAMES = frozenset({"botfather"})


def _raise_flood_wait(seconds: int) -> None:
    sec = max(1, int(seconds))
    minutes, remainder = divmod(sec, 60)
    if minutes >= 1:
        hint = (
            f"Лимит Telegram: подождите {minutes} мин. {remainder} сек. "
            "перед следующей попыткой."
        )
    else:
        hint = f"Лимит Telegram: подождите {sec} сек. перед следующей попыткой."
    raise BadRequestError(
        hint,
        details={"wait_seconds": sec, "flood_wait": True},
    )


async def _handle_flood_wait(exc: FloodWaitError, *, context: str) -> None:
    from app.domain.services import account_flood_service

    wait = max(1, int(exc.seconds))
    logger.warning("Telegram FloodWait %s sec (%s)", wait, context)
    acc_id = account_flood_service.current_flood_account_id()
    if acc_id:
        await account_flood_service.record_flood_wait(acc_id, wait)
    if wait <= max_server_flood_wait_sec():
        await asyncio.sleep(wait + 1)
        # Не сбрасываем botfather_flood_until: пауза остаётся в БД до истечения
        # (важно при отмене задачи во время ожидания и перезапуске).
        return
    _raise_flood_wait(wait)


async def _conv_send(conv, text: str) -> None:
    preview = (text or "")[:48]
    while True:
        try:
            await conv.send_message(text)
            return
        except FloodWaitError as exc:
            await _handle_flood_wait(exc, context=f"send {preview!r}")


async def _conv_send_file(conv, path: Path) -> None:
    while True:
        try:
            await conv.send_file(path)
            return
        except FloodWaitError as exc:
            await _handle_flood_wait(exc, context=f"send_file {path.name!r}")


async def _prepare_botfather_chat(client) -> None:
    from app.domain.services.account_session_service import ensure_client_connected

    try:
        await ensure_client_connected(client)
    except Exception as exc:
        raise BadRequestError(
            f"Сессия Telegram отключена: {exc}. Повторите задачу или проверьте аккаунт."
        ) from exc
    try:
        await client.send_read_acknowledge("BotFather")
    except Exception as exc:
        logger.debug("BotFather read acknowledge: %s", exc)


def _abandon_pending_response(conv) -> None:
    """Убирает зависший future после timeout (иначе Telethon: InvalidStateError)."""
    target_id = conv._last_outgoing
    conv._pending_responses.pop(target_id, None)
    conv._pending_replies.pop(target_id, None)


def _abandon_all_pending(conv) -> None:
    for pending in (conv._pending_responses, conv._pending_replies, conv._pending_edits):
        for msg_id in list(pending):
            pending.pop(msg_id, None)


def _latest_incoming(conv):
    incoming = conv._incoming
    return incoming[-1] if incoming else None


async def _reset_botfather(conv) -> None:
    """Сбрасывает незавершённый диалог BotFather и очищает буфер сообщений."""
    await _conv_send(conv, "/cancel")
    try:
        await asyncio.wait_for(conv.get_response(), timeout=4.0)
    except (asyncio.TimeoutError, ValueError):
        _abandon_all_pending(conv)
    conv._incoming.clear()
    conv._response_indices.clear()
    conv._reply_indices.clear()


@asynccontextmanager
async def _botfather_conv(client, timeout: float = 60) -> AsyncIterator:
    await _prepare_botfather_chat(client)
    await pace_before_conversation()
    async with client.conversation("BotFather", timeout=timeout, total_timeout=180) as conv:
        await _reset_botfather(conv)
        yield conv


async def _wait_reply(conv, timeout: float = 45.0):
    target_id = conv._last_outgoing
    try:
        await asyncio.wait_for(conv.get_response(), timeout=timeout)
    except ValueError as exc:
        _abandon_pending_response(conv)
        if "Too many incoming messages" not in str(exc):
            raise
        reply = _latest_incoming(conv)
        if not reply:
            raise BadRequestError(
                "BotFather прислал несколько ответов сразу. Подождите минуту и повторите."
            ) from exc
        conv._response_indices[target_id] = len(conv._incoming)
        return reply
    except asyncio.TimeoutError:
        _abandon_pending_response(conv)
        raise BadRequestError(
            "BotFather не ответил вовремя. Попробуйте ещё раз.",
            details={
                "flood_wait": True,
                "wait_seconds": throttle_pause_total_sec(0),
            },
        )

    reply = _latest_incoming(conv)
    if not reply:
        raise BadRequestError("BotFather не ответил. Попробуйте ещё раз.")
    conv._response_indices[target_id] = len(conv._incoming)
    return reply


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


def _is_cannot_create_now_reply(text: str) -> bool:
    """BotFather: аккаунт ограничен — создание ботов недоступно."""
    low = (text or "").lower()
    if "cannot create new bots" in low or "can't create new bots" in low:
        return True
    restricted_markers = (
        "your account is limited",
        "account is limited",
        "account was limited",
        "limited and can't",
        "your account was blocked",
        "account was blocked",
        "blocked by telegram",
        "banned from creating",
    )
    return any(marker in low for marker in restricted_markers)


def _is_botfather_menu_reply(text: str) -> bool:
    """Меню помощи BotFather. В середине диалога значит, что ввод не принят."""
    low = (text or "").lower()
    return "i can help you create and manage telegram bots" in low


def _raise_botfather_blocked() -> None:
    raise BadRequestError(
        "BotFather заблокировал создание ботов на этом аккаунте "
        "(«you cannot create new bots at this time»). "
        "Разблокировка — через @SpamBot, либо используйте другой аккаунт.",
        details={"botfather_blocked": True},
    )


def _is_too_many_bots_reply(text: str) -> bool:
    """BotFather: «you can't add more than 20 bots» — достигнут лимит аккаунта."""
    low = (text or "").lower()
    return "more than" in low and "bots" in low


def _raise_bots_limit() -> None:
    raise BadRequestError(
        "Достигнут лимит Telegram: на аккаунте уже 20 ботов. "
        "Удалите лишних ботов или используйте другой аккаунт.",
        details={"bots_limit_reached": True},
    )


def _check_botfather_throttle(text: str) -> None:
    """
    «Sorry, too many attempts. Please try again in N seconds.» — троттлинг BotFather.
    Короткие паузы ждём здесь же, длинные отдаём наверх через wait_seconds.
    """
    match = TRY_AGAIN_RE.search(text or "")
    if not match:
        return
    wait = max(1, int(match.group(1)))
    logger.warning("BotFather throttle: try again in %s sec", wait)
    _raise_flood_wait(wait)


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

    async with _botfather_conv(client) as conv:
        await _conv_send(conv, "/newbot")
        reply = await _wait_reply(conv)
        intro = reply.raw_text or ""
        _check_botfather_throttle(intro)
        if _is_too_many_bots_reply(intro):
            _raise_bots_limit()
        if _is_cannot_create_now_reply(intro):
            _raise_botfather_blocked()
        if _is_botfather_menu_reply(intro):
            raise BadRequestError(
                "BotFather не принял /newbot (вернул меню). Повторите позже или "
                "используйте другой аккаунт."
            )

        await _conv_send(conv, display_name[:64])
        reply = await _wait_reply(conv)
        text = reply.raw_text or ""

        if _is_cannot_create_now_reply(text):
            _raise_botfather_blocked()
        if _is_botfather_menu_reply(text):
            raise BadRequestError(
                "BotFather прервал создание (вернул меню вместо запроса username). "
                "Возможно, аккаунт ограничен — проверьте @SpamBot."
            )
        if "invalid" in text.lower() and "username" not in text.lower():
            _raise_botfather_error(text, field="display_name")

        while attempt < max_username_attempts:
            await _conv_send(conv, current[:32])
            reply = await _wait_reply(conv)
            text = reply.raw_text or ""

            match = TOKEN_RE.search(text)
            if match:
                token = match.group(1)
                m_user = re.search(r"@([a-zA-Z0-9_]{5,32})", text)
                final_username = normalize_bot_username(m_user.group(1)) if m_user else current
                logger.info("Bot created @%s (attempt %s)", final_username, attempt + 1)
                return {"token": token, "username": final_username}

            _check_botfather_throttle(text)
            if _is_too_many_bots_reply(text):
                _raise_bots_limit()
            if _is_cannot_create_now_reply(text):
                _raise_botfather_blocked()
            if _is_botfather_menu_reply(text):
                raise BadRequestError(
                    "BotFather не принял username (вернул меню). Создание прервано — "
                    "возможно, аккаунт ограничен. Проверьте @SpamBot."
                )

            if _is_username_taken_reply(text) or _is_username_invalid_reply(text):
                if username_factory and attempt + 1 < max_username_attempts:
                    attempt += 1
                    current = normalize_bot_username(username_factory(attempt))
                    logger.info("Username retry #%s: @%s", attempt + 1, current)
                    continue
                _raise_botfather_error(text, field="username", username=current)

            # Любой иной ответ не ожидался — не зацикливаемся на повторной отправке.
            _raise_botfather_error(text, field="username", username=current)

        raise BadRequestError(
            f"Не удалось зарегистрировать бота после {max_username_attempts} попыток username."
        )


def _is_set_field_success(text: str) -> bool:
    low = (text or "").lower()
    return any(
        p in low
        for p in (
            "success",
            "updated",
            "done!",
            "done.",
            "new description",
            "new about",
            "new name",
            "profile photo updated",
            "photo updated",
            "успешно",
            "обновлен",
        )
    )


def _is_unchanged_field_reply(text: str) -> bool:
    """BotFather отклоняет повторную отправку того же текста — для sync это нормально."""
    low = (text or "").lower()
    return any(
        p in low
        for p in (
            "unchanged",
            "not modified",
            "has not changed",
            "nothing has changed",
            "you haven't changed",
            "choose a different",
            "please choose",
            "please modify",
            "change something",
            "already set",
            "same description",
            "same about",
            "не изменил",
            "не изменено",
            "не изменён",
            "не изменен",
            "выберите другой",
            "выберите другое",
            "ничего не изменил",
        )
    )


def _validate_set_field_reply(text: str, *, field: str, username: str = "") -> None:
    _check_botfather_throttle(text)
    if _is_set_field_success(text) or _is_unchanged_field_reply(text):
        return
    _raise_botfather_error(text, field=field, username=username)


async def set_bot_name(client, username: str, display_name: str) -> None:
    name = (display_name or "").strip()[:64]
    if not name:
        return
    try:
        async with _botfather_conv(client, timeout=20) as conv:
            await _conv_send(conv, "/setname")
            await _wait_reply(conv)
            await _conv_send(conv, f"@{username.lstrip('@')}")
            await _wait_reply(conv)
            await _conv_send(conv, name)
            reply = await _wait_reply(conv)
            _validate_set_field_reply(reply.raw_text or "", field="display_name", username=username)
    except BadRequestError:
        raise
    except Exception as exc:
        logger.warning("setname failed for @%s: %s", username, exc)
        raise BadRequestError(f"Не удалось обновить имя бота в Telegram: {exc}") from exc


async def set_bot_description(client, username: str, description: str) -> None:
    try:
        async with _botfather_conv(client, timeout=20) as conv:
            await _conv_send(conv, "/setdescription")
            await _wait_reply(conv)
            await _conv_send(conv, f"@{username.lstrip('@')}")
            await _wait_reply(conv)
            await _conv_send(conv, description[:512])
            reply = await _wait_reply(conv)
            _validate_set_field_reply(reply.raw_text or "", field="description", username=username)
    except BadRequestError:
        raise
    except Exception as exc:
        logger.warning("setdescription failed for @%s: %s", username, exc)
        raise BadRequestError(f"Не удалось обновить описание бота в Telegram: {exc}") from exc


async def set_bot_about(client, username: str, about: str) -> None:
    text = (about or "").strip()[:120]
    if not text:
        return
    try:
        async with _botfather_conv(client, timeout=20) as conv:
            await _conv_send(conv, "/setabouttext")
            await _wait_reply(conv)
            await _conv_send(conv, f"@{username.lstrip('@')}")
            await _wait_reply(conv)
            await _conv_send(conv, text)
            reply = await _wait_reply(conv)
            _validate_set_field_reply(reply.raw_text or "", field="about", username=username)
    except BadRequestError:
        raise
    except Exception as exc:
        logger.warning("setabouttext failed for @%s: %s", username, exc)
        raise BadRequestError(f"Не удалось обновить «О боте» в Telegram: {exc}") from exc


def _is_delete_success(text: str) -> bool:
    low = (text or "").lower()
    return any(
        p in low
        for p in (
            "success",
            "deleted",
            "done!",
            "done.",
            "the bot is gone",
            "bot is gone",
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


_DELETE_CONFIRM_PHRASE = "Yes, I am totally sure."


async def _try_confirm_delete(conv, reply, username: str) -> str:
    """Подтверждение удаления: кнопка, фраза BotFather, username или Yes."""
    uname = username.lstrip("@")
    last_body = reply.raw_text or ""

    if reply.buttons:
        for row in reply.buttons:
            for btn in row:
                label = (getattr(btn, "text", None) or str(btn)).lower()
                if "delete" in label or "удал" in label:
                    try:
                        await reply.click(text=btn.text)
                        confirm = await _wait_reply(conv)
                        last_body = confirm.raw_text or ""
                        if _is_delete_success(last_body) or _is_bot_not_found(last_body):
                            return last_body
                    except Exception as exc:
                        logger.debug("click delete button failed: %s", exc)

    text = (reply.raw_text or "").lower()
    needs_exact_phrase = (
        "totally sure" in text
        or "confirmation text exactly" in text
        or _DELETE_CONFIRM_PHRASE.lower() in text
    )
    candidates: list[str] = []
    if needs_exact_phrase:
        candidates.append(_DELETE_CONFIRM_PHRASE)
    elif "confirm" in text or "sure" in text or "yes" in text or "удал" in text:
        candidates.extend((f"@{uname}", uname, "Yes", _DELETE_CONFIRM_PHRASE))

    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        await _conv_send(conv, candidate)
        confirm = await _wait_reply(conv)
        last_body = confirm.raw_text or ""
        if _is_delete_success(last_body) or _is_bot_not_found(last_body):
            return last_body

    return last_body


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

    async with _botfather_conv(client, timeout=30) as conv:
        await _conv_send(conv, "/mybots")
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

    async with _botfather_conv(client, timeout=30) as conv:
        await _conv_send(conv, "/deletebot")
        await _wait_reply(conv)

        await _conv_send(conv, f"@{uname}")
        reply = await _wait_reply(conv)
        text = reply.raw_text or ""

        if _is_delete_success(text):
            logger.info("Bot @%s deleted via BotFather", uname)
            return
        if _is_bot_not_found(text):
            logger.info("Bot @%s already absent in BotFather", uname)
            return

        low = text.lower()
        if (
            "are you sure" in low
            or "totally sure" in low
            or "confirmation text exactly" in low
            or "confirm" in low
            or reply.buttons
        ):
            text = await _try_confirm_delete(conv, reply, uname)
            if _is_delete_success(text) or _is_bot_not_found(text):
                logger.info("Bot @%s deleted via BotFather (confirmed)", uname)
                return
            retry_low = (text or "").lower()
            if "confirmation text exactly" in retry_low or "totally sure" in retry_low:
                await _conv_send(conv, _DELETE_CONFIRM_PHRASE)
                text = (await _wait_reply(conv)).raw_text or ""
                if _is_delete_success(text) or _is_bot_not_found(text):
                    logger.info("Bot @%s deleted via BotFather (exact confirm)", uname)
                    return

        if "invalid" in low and "bot" in low:
            raise BadRequestError(f"BotFather не нашёл бота @{uname}")

        raise BadRequestError(f"BotFather не подтвердил удаление @{uname}: {text[:200]}")


async def set_bot_photo(client, username: str, image_path: Path) -> None:
    path = Path(image_path)
    if not path.is_file():
        return
    try:
        async with _botfather_conv(client, timeout=30) as conv:
            await _conv_send(conv, "/setuserpic")
            await _wait_reply(conv)
            await _conv_send(conv, f"@{username.lstrip('@')}")
            await _wait_reply(conv)
            await _conv_send_file(conv, path)
            reply = await _wait_reply(conv)
            _validate_set_field_reply(reply.raw_text or "", field="photo", username=username)
    except BadRequestError:
        raise
    except Exception as exc:
        logger.warning("setuserpic failed for @%s: %s", username, exc)
        raise BadRequestError(f"Не удалось обновить аватар бота в Telegram: {exc}") from exc
