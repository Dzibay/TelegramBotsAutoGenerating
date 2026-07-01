"""Чтение публичного профиля чужого бота для копирования (user-клиент Telethon)."""
from dataclasses import dataclass

from telethon import utils
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import BotInfo, User

from app.core.exceptions import BadRequestError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SourceBotProfile:
    """Данные, скопированные с исходного бота."""

    name: str
    about: str
    description: str
    photo_bytes: bytes | None = None
    desc_media_bytes: bytes | None = None
    desc_media_ext: str = ""  # ".jpg" / ".gif" / ".mp4"; "" — медиа нет


async def fetch_source_bot_profile(client, source_username: str) -> SourceBotProfile:
    """
    Скачивает name, about, description, аватар и медиа описания исходного бота.
    Пустые поля возвращаются как есть (копируем как есть).
    """
    uname = (source_username or "").strip().lstrip("@")
    if not uname:
        raise BadRequestError("Не указан username исходного бота")

    try:
        bot: User = await client.get_entity(uname)
    except Exception as exc:
        raise BadRequestError(f"Не удалось найти @{uname} в Telegram: {exc}") from exc

    if not getattr(bot, "bot", False):
        raise BadRequestError(f"@{uname} — не бот, копирование невозможно")

    try:
        full = await client(GetFullUserRequest(bot))
    except Exception as exc:
        raise BadRequestError(f"Не удалось прочитать профиль @{uname}: {exc}") from exc

    full_user = full.full_user
    bot_info: BotInfo | None = getattr(full_user, "bot_info", None)

    name = " ".join(filter(None, [bot.first_name, bot.last_name])) or ""
    about = full_user.about or ""
    description = (bot_info.description if bot_info else "") or ""

    photo_bytes: bytes | None = None
    try:
        photo_bytes = await client.download_profile_photo(bot, file=bytes)
    except Exception as exc:
        logger.warning("Аватар @%s не скачался: %s", uname, exc)

    desc_media_bytes: bytes | None = None
    desc_media_ext = ""
    desc_media = bot_info and (bot_info.description_document or bot_info.description_photo)
    if desc_media:
        try:
            desc_media_bytes = await client.download_media(desc_media, file=bytes)
            desc_media_ext = utils.get_extension(desc_media) or ""
        except Exception as exc:
            logger.warning("Медиа описания @%s не скачалось: %s", uname, exc)

    logger.info(
        "Профиль @%s скопирован: name=%s about=%s desc=%s photo=%s desc_media=%s%s",
        uname,
        bool(name),
        bool(about),
        bool(description),
        bool(photo_bytes),
        bool(desc_media_bytes),
        f" ({desc_media_ext})" if desc_media_ext else "",
    )
    return SourceBotProfile(
        name=name,
        about=about,
        description=description,
        photo_bytes=photo_bytes,
        desc_media_bytes=desc_media_bytes,
        desc_media_ext=desc_media_ext,
    )