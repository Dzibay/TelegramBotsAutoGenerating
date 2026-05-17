"""Нормализация username бота под правила Telegram / BotFather."""
import re
import secrets

# 5–32 символа, латиница/цифры/_, начинается с буквы, заканчивается на bot
BOT_USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,28}bot$")


def normalize_bot_username(raw: str) -> str:
    """
    Приводит строку к допустимому username бота.
    Убирает кириллицу и спецсимволы, гарантирует суффикс bot и длину 5–32.
    """
    s = (raw or "").lower().strip().lstrip("@")
    s = re.sub(r"[^a-z0-9_]", "", s)

    if not s or not s[0].isalpha():
        s = "tg" + s

    if not s.endswith("bot"):
        suffix = "_bot" if not s.endswith("_") else "bot"
        max_base = 32 - len(suffix)
        s = (s[:max_base] if len(s) > max_base else s) + suffix

    if len(s) < 5:
        s = f"tg{secrets.token_hex(2)}_bot"

    if len(s) > 32:
        s = s[:29] + "bot"

    s = re.sub(r"_+", "_", s).strip("_")
    if not s.endswith("bot"):
        s = "tgapp_bot"

    if not BOT_USERNAME_RE.match(s):
        s = f"tg_{secrets.token_hex(3)}_bot"[:32]
        if not s.endswith("bot"):
            s = s[:29] + "bot"

    return s[:32]
