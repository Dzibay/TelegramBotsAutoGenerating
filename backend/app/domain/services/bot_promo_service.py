"""Промо-тексты «бот переехал», трекинг-ссылки и редирект."""
import secrets
from typing import Any, Optional
from urllib.parse import urlparse

from app.config import Config
from app.core.exceptions import BadRequestError, NotFoundError
from app.infrastructure.database import repository as db

MOVED_HEAD = "⚠️ Бот переехал!"


def normalize_target_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        raise BadRequestError("Укажите ссылку на рекламируемый сервис")
    if not u.startswith(("http://", "https://")):
        u = f"https://{u}"
    parsed = urlparse(u)
    if not parsed.netloc:
        raise BadRequestError("Некорректная ссылка на сервис")
    return u


def generate_redirect_slug() -> str:
    return secrets.token_urlsafe(8).rstrip("=").replace("-", "x")[:12]


def build_tracking_url(slug: str) -> str:
    base = (Config.PUBLIC_SITE_URL or Config.FRONTEND_URL or "").rstrip("/")
    return f"{base}/go/{slug}"


def build_promo_texts(
    *,
    tracking_url: str,
    display_name: str,
    keyword: str = "",
) -> dict[str, str]:
    """Описание, about и welcome — только с трекинг-ссылкой (не сырой target)."""
    kw = keyword or display_name
    description = (
        f"{MOVED_HEAD}\n\n"
        f"Мы переехали на новый сервис «{display_name}».\n"
        f"Актуальная версия и все материалы — по ссылке:\n"
        f"👉 {tracking_url}\n\n"
        f"Тема: {kw}."
    )[:512]

    about = (
        f"Переехали! Новый сервис: {tracking_url}"
    )[:120]

    welcome = (
        f"{MOVED_HEAD}\n\n"
        f"Привет! Раньше вы пользовались ботом «{display_name}».\n\n"
        f"Мы переехали — перейдите по ссылке, чтобы открыть актуальную версию:\n"
        f"👉 {tracking_url}\n\n"
        f"Нажмите /start, если ссылка не открылась — она продублирована выше."
    )[:2000]

    avatar_prompt = (
        f"Telegram bot profile banner icon, modern flat design, "
        f"theme {kw}, visual hint 'we moved to new platform', vibrant, no text"
    )

    return {
        "description": description,
        "about_text": about,
        "welcome_message": welcome,
        "avatar_prompt": avatar_prompt,
    }


def embed_tracking_in_welcome(text: str, tracking_url: str, target_url: Optional[str] = None) -> str:
    out = (text or "").strip()
    if target_url and target_url in out:
        out = out.replace(target_url, tracking_url)
    if MOVED_HEAD not in out:
        out = f"{MOVED_HEAD}\n\n{out}".strip() if out else MOVED_HEAD
    if tracking_url not in out:
        out = f"{out}\n\n👉 {tracking_url}"
    return out[:2000]


def embed_tracking_in_description(text: str, tracking_url: str, target_url: Optional[str] = None) -> str:
    out = (text or "").strip()
    if target_url and target_url in out:
        out = out.replace(target_url, tracking_url)
    if MOVED_HEAD not in out:
        out = f"{MOVED_HEAD}\n\n{out}".strip()
    if tracking_url not in out:
        out = f"{out}\n\n👉 {tracking_url}"
    return out[:512]


async def record_click(slug: str) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT id, target_url, click_count
        FROM bots
        WHERE redirect_slug = $1 AND target_url IS NOT NULL
        """,
        slug,
    )
    if not row:
        raise NotFoundError("Ссылка не найдена")

    updated = await db.fetch_one(
        """
        UPDATE bots
        SET click_count = click_count + 1, updated_at = NOW()
        WHERE id = $1
        RETURNING click_count
        """,
        row["id"],
    )
    return {
        "bot_id": row["id"],
        "target_url": row["target_url"],
        "click_count": updated["click_count"] if updated else row["click_count"] + 1,
    }
