"""Промо-тексты «бот переехал», трекинг-ссылки и редирект."""
import secrets
from typing import Any, Optional
from urllib.parse import urlparse

from app.config import Config
from app.core.exceptions import BadRequestError, NotFoundError
from app.infrastructure.database import repository as db

MOVED_HEAD = "⚠️ Бот переехал!"

LINK_MODE_REDIRECT = "redirect"
LINK_MODE_DIRECT = "direct"


def normalize_link_mode(mode: str | None) -> str:
    m = (mode or LINK_MODE_REDIRECT).strip().lower()
    return LINK_MODE_DIRECT if m == LINK_MODE_DIRECT else LINK_MODE_REDIRECT


def resolve_public_link(
    link_mode: str,
    target_url: str,
    redirect_slug: str | None,
) -> str:
    """Ссылка, которую видит пользователь в текстах бота."""
    mode = normalize_link_mode(link_mode)
    if mode == LINK_MODE_DIRECT:
        return target_url
    if redirect_slug:
        return build_tracking_url(redirect_slug)
    return target_url


def resolve_tracking_url(redirect_slug: str | None) -> str | None:
    if not redirect_slug:
        return None
    return build_tracking_url(redirect_slug)


def prepare_bot_links(
    *,
    link_mode: str,
    target_url: str,
    redirect_slug: str | None = None,
    ensure_slug: bool = True,
) -> dict[str, Any]:
    mode = normalize_link_mode(link_mode)
    target = normalize_target_url(target_url)
    slug = redirect_slug
    if mode == LINK_MODE_REDIRECT and ensure_slug and not slug:
        slug = generate_redirect_slug()
    tracking_url = resolve_tracking_url(slug)
    public_link = resolve_public_link(mode, target, slug)
    return {
        "link_mode": mode,
        "target_url": target,
        "redirect_slug": slug,
        "tracking_url": tracking_url,
        "public_link": public_link,
    }


def embed_bot_texts(
    *,
    description: str | None = None,
    welcome_message: str | None = None,
    about_text: str | None = None,
    public_link: str,
    link_mode: str,
    target_url: str,
    tracking_url: str | None,
) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    if description is not None:
        out["description"] = embed_link_in_description(
            description,
            public_link,
            link_mode=link_mode,
            target_url=target_url,
            tracking_url=tracking_url,
        )
    if welcome_message is not None:
        out["welcome_message"] = embed_link_in_welcome(
            welcome_message,
            public_link,
            link_mode=link_mode,
            target_url=target_url,
            tracking_url=tracking_url,
        )
    if about_text is not None:
        out["about_text"] = embed_link_in_about(
            about_text,
            public_link,
            link_mode=link_mode,
            target_url=target_url,
            tracking_url=tracking_url,
        )
    return out


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
    public_link: str,
    display_name: str,
    keyword: str = "",
    link_mode: str = LINK_MODE_REDIRECT,
) -> dict[str, str]:
    """Описание, about и welcome с публичной ссылкой (трекинг или прямая)."""
    kw = keyword or display_name
    link = public_link
    description = (
        f"{MOVED_HEAD}\n\n"
        f"Мы переехали на новый сервис «{display_name}».\n"
        f"Актуальная версия и все материалы — по ссылке:\n"
        f"👉 {link}\n\n"
        f"Тема: {kw}."
    )[:512]

    about = (f"Переехали! Новый сервис: {link}")[:120]

    welcome = (
        f"{MOVED_HEAD}\n\n"
        f"Привет! Раньше вы пользовались ботом «{display_name}».\n\n"
        f"Мы переехали — перейдите по ссылке, чтобы открыть актуальную версию:\n"
        f"👉 {link}\n\n"
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


def _swap_legacy_links(text: str, public_link: str, target_url: Optional[str], tracking_url: Optional[str]) -> str:
    out = text or ""
    if tracking_url and tracking_url != public_link and tracking_url in out:
        out = out.replace(tracking_url, public_link)
    if target_url and target_url != public_link and target_url in out:
        out = out.replace(target_url, public_link)
    return out


def embed_link_in_about(
    text: str,
    public_link: str,
    *,
    link_mode: str = LINK_MODE_REDIRECT,
    target_url: Optional[str] = None,
    tracking_url: Optional[str] = None,
) -> str:
    out = _swap_legacy_links((text or "").strip(), public_link, target_url, tracking_url)[:120]
    if not out:
        return out
    if public_link not in out:
        extra = f" {public_link}"
        out = (out + extra)[:120] if len(out) + len(extra) <= 120 else out
    return out


def embed_link_in_welcome(
    text: str,
    public_link: str,
    *,
    link_mode: str = LINK_MODE_REDIRECT,
    target_url: Optional[str] = None,
    tracking_url: Optional[str] = None,
) -> str:
    """Добавляет ссылку в пользовательский текст. Пустая строка не меняется."""
    out = _swap_legacy_links((text or "").strip(), public_link, target_url, tracking_url)
    if not out:
        return ""
    if public_link not in out:
        out = f"{out}\n\n👉 {public_link}"
    return out[:2000]


def embed_link_in_description(
    text: str,
    public_link: str,
    *,
    link_mode: str = LINK_MODE_REDIRECT,
    target_url: Optional[str] = None,
    tracking_url: Optional[str] = None,
) -> str:
    """Добавляет ссылку в пользовательский текст. Пустая строка не меняется."""
    out = _swap_legacy_links((text or "").strip(), public_link, target_url, tracking_url)
    if not out:
        return ""
    if public_link not in out:
        out = f"{out}\n\n👉 {public_link}"
    return out[:512]


def finalize_bot_texts(
    *,
    description: str | None,
    about_text: str | None,
    welcome_message: str | None,
    public_link: str,
    link_mode: str,
    target_url: str,
    tracking_url: str | None,
    display_name: str = "",
    keyword: str = "",
    use_promo_welcome: bool = True,
) -> dict[str, str | None]:
    """Собирает финальные тексты: пустые поля → шаблон promo, свои → только вставка ссылки."""
    promo = build_promo_texts(
        public_link=public_link,
        display_name=display_name,
        keyword=keyword,
        link_mode=link_mode,
    )
    desc_trim = (description or "").strip()
    about_trim = (about_text or "").strip()
    welcome_trim = (welcome_message or "").strip()

    if not desc_trim:
        final_desc = promo["description"]
    else:
        final_desc = embed_link_in_description(
            desc_trim,
            public_link,
            link_mode=link_mode,
            target_url=target_url,
            tracking_url=tracking_url,
        )

    if not about_trim:
        final_about = promo["about_text"]
    else:
        final_about = embed_link_in_about(
            about_trim,
            public_link,
            link_mode=link_mode,
            target_url=target_url,
            tracking_url=tracking_url,
        )

    if welcome_message is None and not use_promo_welcome:
        final_welcome = None
    elif not welcome_trim:
        final_welcome = promo["welcome_message"] if use_promo_welcome else None
    else:
        final_welcome = embed_link_in_welcome(
            welcome_trim,
            public_link,
            link_mode=link_mode,
            target_url=target_url,
            tracking_url=tracking_url,
        )

    return {
        "description": final_desc,
        "about_text": final_about,
        "welcome_message": final_welcome,
    }


# Обратная совместимость
def embed_tracking_in_about(text: str, tracking_url: str, target_url: Optional[str] = None) -> str:
    return embed_link_in_about(
        text, tracking_url, link_mode=LINK_MODE_REDIRECT, target_url=target_url, tracking_url=tracking_url
    )


def embed_tracking_in_welcome(text: str, tracking_url: str, target_url: Optional[str] = None) -> str:
    return embed_link_in_welcome(
        text, tracking_url, link_mode=LINK_MODE_REDIRECT, target_url=target_url, tracking_url=tracking_url
    )


def embed_tracking_in_description(text: str, tracking_url: str, target_url: Optional[str] = None) -> str:
    return embed_link_in_description(
        text, tracking_url, link_mode=LINK_MODE_REDIRECT, target_url=target_url, tracking_url=tracking_url
    )


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
