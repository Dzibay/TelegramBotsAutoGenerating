"""Нормализация и генерация уникальных username ботов (транслит + суффиксы)."""
import re
import secrets
from typing import Optional

# 5–32 символа, латиница/цифры/_, начинается с буквы, заканчивается на bot
BOT_USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,28}bot$")

# Транслитерация RU → LAT (компактная, для коротких username)
_RU_MAP: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sh",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def transliterate_ru(text: str) -> str:
    """Транслитерация кириллицы; латиница и цифры сохраняются."""
    if not text:
        return ""
    out: list[str] = []
    for ch in text.lower():
        if ch in _RU_MAP:
            out.append(_RU_MAP[ch])
        elif ch.isascii() and (ch.isalnum() or ch in " _-"):
            out.append(ch)
    return "".join(out)


def _slugify_latin(text: str, max_len: int = 18) -> str:
    s = transliterate_ru(text).lower()
    s = s.replace("-", "_").replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or not s[0].isalpha():
        s = "tg" + s
    return s[:max_len].strip("_") or "tg"


def normalize_bot_username(raw: str) -> str:
    """Приводит строку к допустимому username бота (с транслитом кириллицы)."""
    s = (raw or "").strip().lstrip("@")
    if re.search(r"[а-яё]", s, re.IGNORECASE):
        s = _slugify_latin(s, max_len=22)
    else:
        s = s.lower()
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


def build_username_from_keyword(
    keyword: str,
    *,
    variant: int = 0,
    campaign_id: Optional[int] = None,
    unique_token: Optional[str] = None,
) -> str:
    """
    Строит username из ключевого слова (транслит) + уникальный суффикс.
    variant>0 добавляет цифры/hex для коллизий.
    """
    base = _slugify_latin(keyword or "bot", max_len=16)
    suffix_parts: list[str] = []

    if variant > 0 and campaign_id is not None:
        suffix_parts.append(str(campaign_id % 100000))
    if variant > 0 or unique_token:
        suffix_parts.append(unique_token or secrets.token_hex(2))
    if variant > 2:
        suffix_parts.append(str(variant))

    if suffix_parts:
        tail = "_".join(suffix_parts)
        max_base = 32 - len(tail) - 4  # _bot
        base = base[: max(3, max_base)]
        raw = f"{base}_{tail}_bot"
    else:
        raw = f"{base}_bot"

    return normalize_bot_username(raw)


def username_variants(
    keyword: str,
    *,
    preferred: Optional[str] = None,
    campaign_id: Optional[int] = None,
    max_variants: int = 12,
) -> list[str]:
    """Список кандидатов username от более «чистого» к более уникальному."""
    seen: set[str] = set()
    out: list[str] = []

    def add(raw: str) -> None:
        u = normalize_bot_username(raw)
        key = u.lower()
        if key not in seen:
            seen.add(key)
            out.append(u)

    if preferred:
        add(preferred)
    add(build_username_from_keyword(keyword, variant=0, campaign_id=campaign_id))
    for i in range(1, max_variants):
        add(
            build_username_from_keyword(
                keyword,
                variant=i,
                campaign_id=campaign_id,
                unique_token=secrets.token_hex(2),
            )
        )
    return out
