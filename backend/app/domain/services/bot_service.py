"""CRUD ботов, AI-черновики, создание через BotFather."""
import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from app.config import Config
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)
from app.domain.services import (
    account_flood_service,
    account_service,
    bot_promo_service,
    campaign_service,
    referral_link_service,
    username_service,
)
from app.infrastructure.ai.provider import AIService, generate_image_bytes
from app.infrastructure.database import repository as db
from app.infrastructure.telegram.bot_api import telegram_bot_url, verify_bot_token
from app.infrastructure.telegram.botfather_client import (
    create_bot_via_botfather,
    delete_bot_via_botfather,
    set_bot_about,
    set_bot_description,
    set_bot_name,
    set_bot_photo,
)
from app.infrastructure.telegram.botfather_pacing import pace_botfather_op
from app.utils.crypto import decrypt_token, encrypt_token
from app.utils.telegram_username import build_username_from_keyword, normalize_bot_username
from app.infrastructure.telegram.session_loader import load_client_from_tdata

OnStepCallback = Callable[[str, str], Awaitable[None]]

CREATION_STEP_LABELS = {
    "username": "Подбор username",
    "botfather_create": "BotFather",
    "referral_fetch": "Реферальная ссылка",
    "links": "Ссылки",
    "avatar": "Аватар",
    "botfather_texts": "Тексты в BotFather",
    "db_save": "Сохранение",
}


def _wrap_creation_step_error(
    step_id: str,
    exc: Exception,
    *,
    botfather_created: bool = False,
    username: str | None = None,
) -> BadRequestError:
    label = CREATION_STEP_LABELS.get(step_id, step_id)
    if isinstance(exc, BadRequestError):
        details = dict(exc.details or {})
        details.setdefault("step", step_id)
        if botfather_created:
            details["botfather_created"] = True
        if username:
            details["username"] = username
        msg = exc.message
        if label not in msg:
            msg = f"{label}: {msg}"
        return BadRequestError(msg, details=details)
    details: dict[str, Any] = {"step": step_id}
    if botfather_created:
        details["botfather_created"] = True
    if username:
        details["username"] = username
    return BadRequestError(f"{label}: {exc}", details=details)


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _avatar_api_url(bot_id: int) -> str:
    return f"/api/v1/bots/{bot_id}/avatar"


def _save_avatar_file(campaign_id: int, username: str, data: bytes) -> Path:
    path = Config.AVATARS_DIR / str(campaign_id) / f"{username.lstrip('@')}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _bot_row(row: dict, *, include_welcome: bool = False) -> dict[str, Any]:
    bot_id = row["id"]
    link_mode = bot_promo_service.normalize_link_mode(row.get("link_mode"))
    target = row.get("target_url") or ""
    slug = row.get("redirect_slug")
    tracking_url = bot_promo_service.resolve_tracking_url(slug)
    public_link = bot_promo_service.resolve_public_link(link_mode, target, slug)
    out = {
        "id": bot_id,
        "campaign_id": row["campaign_id"],
        "telegram_account_id": row.get("telegram_account_id"),
        "keyword": row.get("keyword"),
        "username": row.get("username"),
        "display_name": row["display_name"],
        "description": row.get("description"),
        "about_text": row.get("about_text"),
        "has_avatar": bool(row.get("avatar_path")),
        "avatar_url": _avatar_api_url(bot_id) if row.get("avatar_path") else None,
        "status": row["status"],
        "has_token": bool(row.get("token_encrypted")),
        "telegram_url": telegram_bot_url(row.get("username")),
        "target_url": target or None,
        "link_mode": link_mode,
        "public_link": public_link,
        "tracking_url": tracking_url,
        "redirect_slug": slug,
        "click_count": int(row.get("click_count") or 0),
        "welcome_button_enabled": bool(row.get("welcome_button_enabled", True)),
        "welcome_button_text": bot_promo_service.welcome_button_label(
            row.get("welcome_button_text")
        ),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }
    if include_welcome:
        out["welcome_message"] = row.get("welcome_message")
    if row.get("campaign_title") is not None:
        out["campaign_title"] = row["campaign_title"]
    if row.get("account_label") is not None:
        out["account_label"] = row.get("account_label")
    if row.get("account_phone") is not None:
        out["account_phone"] = row.get("account_phone")
    return out


async def _apply_bot_avatar(
    client,
    campaign_id: int,
    username: str,
    *,
    avatar_bytes: Optional[bytes] = None,
    generate_avatar: bool = False,
    avatar_prompt: Optional[str] = None,
) -> Optional[Path]:
    """Сохраняет аватар на диск и загружает в BotFather."""
    path: Optional[Path] = None
    try:
        if avatar_bytes:
            path = _save_avatar_file(campaign_id, username, avatar_bytes)
        elif generate_avatar and avatar_prompt:
            img = await generate_image_bytes(avatar_prompt)
            path = _save_avatar_file(campaign_id, username, img)
        if path and path.is_file():
            await set_bot_photo(client, username, path)
            return path
    except Exception as exc:
        logger.warning("Avatar apply failed for @%s: %s", username, exc)
    return path if path and path.is_file() else None


async def get_bot_avatar_path(bot_id: int) -> Path:
    row = await db.fetch_one("SELECT avatar_path FROM bots WHERE id = $1", bot_id)
    if not row or not row.get("avatar_path"):
        raise NotFoundError("Аватар не задан")
    path = Path(row["avatar_path"])
    if not path.is_file():
        raise NotFoundError("Файл аватара не найден")
    return path


async def generate_avatar_preview(
    *,
    prompt: Optional[str] = None,
    keyword: Optional[str] = None,
) -> bytes:
    text = (prompt or "").strip() or f"Telegram bot icon, theme {keyword or 'app'}, flat modern"
    return await generate_image_bytes(text)


async def _get_account_for_campaign(campaign_id: int, account_id: int) -> dict:
    row = await db.fetch_one(
        """
        SELECT * FROM telegram_accounts
        WHERE id = $1 AND campaign_id = $2
        """,
        account_id,
        campaign_id,
    )
    if not row:
        raise NotFoundError("Аккаунт не найден в этой кампании")
    return row


async def list_bots(
    *,
    campaign_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if campaign_id is not None:
        params.append(campaign_id)
        clauses.append(f"b.campaign_id = ${len(params)}")
    if status:
        params.append(status)
        clauses.append(f"b.status = ${len(params)}")

    rows = await db.fetch_all(
        f"""
        SELECT b.*, c.title AS campaign_title,
               ta.label AS account_label, ta.phone AS account_phone
        FROM bots b
        JOIN campaigns c ON c.id = b.campaign_id
        LEFT JOIN telegram_accounts ta ON ta.id = b.telegram_account_id
        WHERE {' AND '.join(clauses)}
        ORDER BY b.created_at DESC, b.id DESC
        """,
        *params,
    )
    return [_bot_row(r) for r in rows]


async def list_bots_grouped() -> list[dict[str, Any]]:
    bots = await list_bots()
    campaigns: dict[int, dict] = {}
    for b in bots:
        cid = b["campaign_id"]
        if cid not in campaigns:
            campaigns[cid] = {
                "campaign_id": cid,
                "campaign_title": b.get("campaign_title", f"#{cid}"),
                "accounts": {},
            }
        acc_id = b.get("telegram_account_id") or 0
        acc_key = str(acc_id)
        if acc_key not in campaigns[cid]["accounts"]:
            campaigns[cid]["accounts"][acc_key] = {
                "telegram_account_id": acc_id or None,
                "account_label": b.get("account_label"),
                "account_phone": b.get("account_phone"),
                "bots": [],
            }
        campaigns[cid]["accounts"][acc_key]["bots"].append(b)

    result = []
    for camp in campaigns.values():
        camp["accounts"] = list(camp["accounts"].values())
        result.append(camp)
    return result


async def get_bot(bot_id: int) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT b.*, c.title AS campaign_title,
               ta.label AS account_label, ta.phone AS account_phone
        FROM bots b
        JOIN campaigns c ON c.id = b.campaign_id
        LEFT JOIN telegram_accounts ta ON ta.id = b.telegram_account_id
        WHERE b.id = $1
        """,
        bot_id,
    )
    if not row:
        raise NotFoundError("Бот не найден")
    return _bot_row(row, include_welcome=True)


async def generate_bot_draft(
    campaign_id: int,
    telegram_account_id: int,
    target_url: str,
    keyword: Optional[str] = None,
    redirect_slug: Optional[str] = None,
    link_mode: str = bot_promo_service.LINK_MODE_REDIRECT,
) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    await _get_account_for_campaign(campaign_id, telegram_account_id)
    use_referral = referral_link_service.is_referral_configured(campaign)
    if use_referral:
        public_link = referral_link_service.referral_preview_link()
        target = public_link
        slug = None
        tracking_url = None
        mode = bot_promo_service.LINK_MODE_DIRECT
    else:
        links = bot_promo_service.prepare_bot_links(
            link_mode=link_mode,
            target_url=target_url,
            redirect_slug=redirect_slug,
        )
        target = links["target_url"]
        slug = links["redirect_slug"]
        tracking_url = links["tracking_url"]
        public_link = links["public_link"]
        mode = links["link_mode"]

    kw = (keyword or "").strip()
    if not kw:
        raise BadRequestError(
            "Укажите ключевую фразу — она нужна только для генерации текстов нейросетью."
        )
    concept = {
        "keyword": kw,
        "display_name": f"{kw.title()} Bot",
        "description_hint": f"Бот переехал — {kw}",
        "username_hint": build_username_from_keyword(kw, campaign_id=campaign_id),
    }

    ai = AIService()
    ai_fallback = False
    try:
        profile = await ai.refine_bot_profile(
            concept, campaign.get("niche_description"), campaign_id=campaign_id
        )
    except (BadRequestError, Exception) as exc:
        if not Config.AI_FALLBACK_ON_ERROR:
            raise
        msg = getattr(exc, "message", str(exc))
        logger.warning("AI draft profile failed: %s — using templates", msg)
        hint = concept["description_hint"]
        profile = {
            "display_name": concept["display_name"],
            "username": concept["username_hint"],
            "description": hint,
            "about_text": (hint[:120] if hint else f"Бот — {kw}")[:120],
        }
        ai_fallback = True

    display_name = profile.get("display_name", concept["display_name"])[:64]
    username = await username_service.allocate_unique_username(
        kw,
        preferred=profile.get("username") or concept.get("username_hint"),
        campaign_id=campaign_id,
    )

    texts = bot_promo_service.finalize_bot_texts(
        description=profile.get("description", ""),
        about_text=profile.get("about_text", ""),
        welcome_message=None,
        public_link=public_link,
        link_mode=mode,
        target_url=target,
        tracking_url=tracking_url,
        display_name=display_name,
        keyword=kw,
        use_promo_welcome=False,
        campaign_defaults=bot_promo_service.campaign_text_defaults(campaign),
    )
    description = texts["description"] or ""
    about_draft = texts["about_text"] or ""
    promo = bot_promo_service.build_promo_texts(
        public_link=public_link,
        display_name=display_name,
        keyword=kw,
        link_mode=mode,
    )
    try:
        welcome = await ai.generate_welcome_message(
            public_link,
            kw,
            display_name,
            0,
            campaign_id=campaign_id,
            moved_notice=True,
        )
        welcome = bot_promo_service.embed_link_in_welcome(
            welcome,
            public_link,
            link_mode=mode,
            target_url=target,
            tracking_url=tracking_url,
        )
        if not welcome.strip():
            defaults = bot_promo_service.campaign_text_defaults(campaign)
            if defaults.get("welcome_message"):
                welcome = bot_promo_service.embed_link_in_welcome(
                    defaults["welcome_message"],
                    public_link,
                    link_mode=mode,
                    target_url=target,
                    tracking_url=tracking_url,
                )
            else:
                welcome = promo["welcome_message"]
            ai_fallback = True
    except Exception as exc:
        if Config.AI_FALLBACK_ON_ERROR:
            logger.warning("AI welcome failed: %s — template", exc)
            defaults = bot_promo_service.campaign_text_defaults(campaign)
            if defaults.get("welcome_message"):
                welcome = bot_promo_service.embed_link_in_welcome(
                    defaults["welcome_message"],
                    public_link,
                    link_mode=mode,
                    target_url=target,
                    tracking_url=tracking_url,
                )
            else:
                welcome = promo["welcome_message"]
            ai_fallback = True
        else:
            raise

    defaults = bot_promo_service.campaign_text_defaults(campaign)
    return {
        "campaign_id": campaign_id,
        "telegram_account_id": telegram_account_id,
        "target_url": target,
        "link_mode": mode,
        "public_link": public_link,
        "redirect_slug": slug,
        "tracking_url": tracking_url,
        "keyword": kw,
        "display_name": display_name,
        "username": username,
        "description": description,
        "welcome_message": welcome,
        "about_text": about_draft,
        "welcome_button_enabled": defaults["welcome_button_enabled"],
        "welcome_button_text": defaults["welcome_button_text"],
        "avatar_prompt": profile.get("avatar_prompt", promo["avatar_prompt"]),
        "ai_fallback": ai_fallback,
        "ai_hint": (
            "Тексты из шаблонов (AI недоступен). Проверьте GROQ_API_KEY в .env."
            if ai_fallback
            else None
        ),
        "referral_pending": use_referral,
    }


async def create_bot(
    *,
    campaign_id: int,
    telegram_account_id: int,
    target_url: str,
    display_name: str,
    username: str,
    description: str,
    welcome_message: str,
    about_text: str = "",
    welcome_button_enabled: bool = True,
    welcome_button_text: str = bot_promo_service.WELCOME_BUTTON_TEXT_DEFAULT,
    keyword: Optional[str] = None,
    redirect_slug: Optional[str] = None,
    link_mode: str = bot_promo_service.LINK_MODE_REDIRECT,
    create_via_botfather: bool = True,
    auto_start: bool = False,
    avatar_bytes: Optional[bytes] = None,
    generate_avatar: bool = True,
    telethon_client=None,
    use_referral_api: bool | None = None,
    on_step: OnStepCallback | None = None,
) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    account = await _get_account_for_campaign(campaign_id, telegram_account_id)
    account = await account_service.ensure_ready_for_bot_creation(account)

    kw_for_user = (keyword or "").strip() or display_name
    desc_input = description
    welcome_input = welcome_message
    about_input = about_text

    token = None
    avatar_path = None
    client = telethon_client
    owns_client = client is None
    target = ""
    slug = None
    tracking_url = None
    public_link = ""
    mode = bot_promo_service.normalize_link_mode(link_mode)
    about_final = ""
    promo: dict[str, str] = {}
    final_username = normalize_bot_username(username)
    botfather_created = False

    async def _step(msg: str, step_id: str = "") -> None:
        if on_step:
            await on_step(msg, step_id)

    use_referral = (
        use_referral_api
        if use_referral_api is not None
        else referral_link_service.is_referral_configured(campaign)
    )

    flood_ctx = None
    try:
        if create_via_botfather:
            flood_ctx = account_flood_service.set_flood_account_context(telegram_account_id)
            if owns_client:
                session_file = (
                    Config.STORAGE_ROOT / "sessions" / str(campaign_id) / f"{telegram_account_id}.session"
                )
                client, _ = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
            async def _notify_saved_flood(msg: str) -> None:
                await _step(msg, "botfather_wait")

            await account_flood_service.wait_for_flood_clear_simple(
                telegram_account_id,
                on_message=_notify_saved_flood,
            )
            requested_username = normalize_bot_username(username)
            await _step(f"Подбор username (запрошен @{requested_username})…", "username")
            final_username = await username_service.allocate_unique_username(
                kw_for_user,
                preferred=username,
                campaign_id=campaign_id,
                telethon_client=client,
            )
            if final_username != requested_username:
                await _step(
                    f"Username @{final_username} (запрошен был @{requested_username})",
                    "username",
                )
            reserved = await username_service.get_reserved_usernames()
            username_factory = username_service.make_username_factory(
                kw_for_user,
                preferred=final_username,
                campaign_id=campaign_id,
                reserved=reserved,
            )
            await _step(f"BotFather: создание @{final_username}…", "botfather_create")
            try:
                result = await create_bot_via_botfather(
                    client,
                    display_name,
                    final_username,
                    username_factory=username_factory,
                )
            except asyncio.InvalidStateError as exc:
                logger.warning("BotFather conversation race: %s", exc)
                raise BadRequestError(
                    "Сбой диалога с BotFather. Подождите минуту и создайте бота снова.",
                    details={"step": "botfather_create"},
                ) from exc
            except BadRequestError as exc:
                await account_flood_service.record_flood_from_details(
                    telegram_account_id,
                    exc.details,
                )
                raise _wrap_creation_step_error("botfather_create", exc, username=final_username)
            except Exception as exc:
                raise _wrap_creation_step_error("botfather_create", exc, username=final_username)
            token = result["token"]
            final_username = result["username"]
            botfather_created = True
            await _step(f"BotFather: бот создан @{final_username}", "botfather_create")
            await pace_botfather_op()

            if use_referral:
                await _step(f"Запрос реферальной ссылки для @{final_username}…", "referral_fetch")
            else:
                await _step("Подготовка ссылок из настроек партии…", "links")
            try:
                links = await referral_link_service.resolve_bot_links(
                    campaign,
                    username=final_username,
                    target_url=target_url,
                    link_mode=link_mode,
                    redirect_slug=redirect_slug,
                    use_referral_api=use_referral,
                )
            except BadRequestError as exc:
                raise _wrap_creation_step_error(
                    "referral_fetch" if use_referral else "links",
                    exc,
                    botfather_created=True,
                    username=final_username,
                )
            target = links["target_url"]
            slug = links["redirect_slug"]
            tracking_url = links["tracking_url"]
            public_link = links["public_link"]
            mode = links["link_mode"]
            link_preview = public_link[:72] + ("…" if len(public_link) > 72 else "")
            await _step(f"Ссылки готовы: {link_preview}", "links")

            texts = bot_promo_service.finalize_bot_texts(
                description=desc_input,
                about_text=about_input,
                welcome_message=welcome_input,
                public_link=public_link,
                link_mode=mode,
                target_url=target,
                tracking_url=tracking_url,
                display_name=display_name,
                keyword=keyword or "",
                campaign_defaults=bot_promo_service.campaign_text_defaults(campaign),
            )
            description = texts["description"] or ""
            welcome_message = texts["welcome_message"] or ""
            about_final = texts["about_text"] or ""
            promo = bot_promo_service.build_promo_texts(
                public_link=public_link,
                display_name=display_name,
                keyword=kw_for_user,
                link_mode=mode,
            )

            await _step("Установка аватара…", "avatar")
            try:
                avatar_path = await _apply_bot_avatar(
                    client,
                    campaign_id,
                    final_username,
                    avatar_bytes=avatar_bytes,
                    generate_avatar=generate_avatar and not avatar_bytes,
                    avatar_prompt=promo.get("avatar_prompt")
                    or f"telegram bot banner icon {keyword or display_name}",
                )
            except Exception as exc:
                raise _wrap_creation_step_error(
                    "avatar",
                    exc,
                    botfather_created=True,
                    username=final_username,
                )
            await pace_botfather_op()
            await _step("Описание и About в BotFather…", "botfather_texts")
            try:
                await set_bot_description(
                    client,
                    final_username,
                    bot_promo_service.apply_link_placeholder(description, public_link),
                )
                await pace_botfather_op()
                await set_bot_about(
                    client,
                    final_username,
                    bot_promo_service.apply_link_placeholder(about_final, public_link),
                )
            except Exception as exc:
                raise _wrap_creation_step_error(
                    "botfather_texts",
                    exc,
                    botfather_created=True,
                    username=final_username,
                )
        else:
            links = await referral_link_service.resolve_bot_links(
                campaign,
                target_url=target_url,
                link_mode=link_mode,
                redirect_slug=redirect_slug,
                use_referral_api=use_referral,
            )
            target = links["target_url"]
            slug = links["redirect_slug"]
            tracking_url = links["tracking_url"]
            public_link = links["public_link"]
            mode = links["link_mode"]
            texts = bot_promo_service.finalize_bot_texts(
                description=desc_input,
                about_text=about_input,
                welcome_message=welcome_input,
                public_link=public_link,
                link_mode=mode,
                target_url=target,
                tracking_url=tracking_url,
                display_name=display_name,
                keyword=keyword or "",
                campaign_defaults=bot_promo_service.campaign_text_defaults(campaign),
            )
            description = texts["description"] or ""
            welcome_message = texts["welcome_message"] or ""
            about_final = texts["about_text"] or ""

        status = "active" if auto_start and token else "stopped"
        if not create_via_botfather:
            raise BadRequestError("Создание только через BotFather (укажите create_via_botfather=true)")

        await _step("Сохранение бота в базу…", "db_save")
        token_enc = encrypt_token(token) if token else None
        row = await db.fetch_one(
            """
            INSERT INTO bots (
                campaign_id, telegram_account_id, keyword, username, display_name,
                description, about_text, token_encrypted, avatar_path, welcome_message,
                welcome_button_enabled, welcome_button_text,
                target_url, link_mode, redirect_slug, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            RETURNING *
            """,
            campaign_id,
            telegram_account_id,
            keyword,
            final_username,
            display_name[:64],
            description[:512] if description else None,
            about_final or None,
            token_enc,
            str(avatar_path) if avatar_path else None,
            welcome_message,
            welcome_button_enabled,
            bot_promo_service.welcome_button_label(welcome_button_text),
            target,
            mode,
            slug,
            status,
        )
        await db.execute(
            """
            UPDATE telegram_accounts
            SET bots_created = bots_created + 1,
                status = CASE
                    WHEN bots_created + 1 >= max_bots_limit THEN 'exhausted'
                    ELSE 'ready'
                END,
                updated_at = NOW()
            WHERE id = $1
            """,
            telegram_account_id,
        )
        return _bot_row(row, include_welcome=True)
    finally:
        if flood_ctx is not None:
            account_flood_service.reset_flood_account_context(flood_ctx)
        if owns_client and client:
            await client.disconnect()


async def create_bots_batch(specs: list[dict[str, Any]]) -> dict[str, Any]:
    """Последовательное создание ботов (после предпросмотра в UI)."""
    created: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for i, spec in enumerate(specs):
        try:
            bot = await create_bot(**spec)
            created.append(bot)
        except Exception as exc:
            err = getattr(exc, "message", None) or str(exc)
            errors.append({"index": i, "keyword": spec.get("keyword"), "error": err[:300]})
    return {
        "created_count": len(created),
        "failed_count": len(errors),
        "bots": created,
        "errors": errors,
    }


async def save_bot_avatar(bot_id: int, avatar_bytes: bytes) -> dict[str, Any]:
    """Сохраняет аватар на диск и в БД без обращения к BotFather."""
    if len(avatar_bytes) > 5 * 1024 * 1024:
        raise BadRequestError("Аватар не больше 5 МБ")
    row = await db.fetch_one("SELECT * FROM bots WHERE id = $1", bot_id)
    if not row or not row.get("username"):
        raise BadRequestError("У бота нет username для сохранения аватара")
    path = _save_avatar_file(row["campaign_id"], row["username"], avatar_bytes)
    row = await db.fetch_one(
        "UPDATE bots SET avatar_path = $2, updated_at = NOW() WHERE id = $1 RETURNING *",
        bot_id,
        str(path),
    )
    return _bot_row(row)


async def update_bot(bot_id: int, **fields: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    bot = await get_bot(bot_id)
    row_data = await db.fetch_one("SELECT * FROM bots WHERE id = $1", bot_id)
    sync_botfather = bool(fields.pop("sync_botfather", False))
    force_avatar_sync = bool(fields.pop("force_avatar_sync", False))

    link_mode = bot_promo_service.normalize_link_mode(
        fields.get("link_mode") if fields.get("link_mode") is not None else row_data.get("link_mode")
    )
    target = fields.get("target_url") if fields.get("target_url") is not None else row_data.get("target_url")
    slug = row_data.get("redirect_slug")

    if fields.get("target_url") is not None:
        target = bot_promo_service.normalize_target_url(fields["target_url"])
        fields["target_url"] = target

    if link_mode == bot_promo_service.LINK_MODE_REDIRECT and target and not slug:
        slug = bot_promo_service.generate_redirect_slug()
        await db.execute(
            "UPDATE bots SET redirect_slug = $1, updated_at = NOW() WHERE id = $2",
            slug,
            bot_id,
        )
        row_data["redirect_slug"] = slug

    tracking_url = bot_promo_service.resolve_tracking_url(slug)
    public_link = bot_promo_service.resolve_public_link(link_mode, target or "", slug)

    if fields.get("link_mode") is not None:
        fields["link_mode"] = link_mode

    needs_reembed = fields.get("link_mode") is not None or fields.get("target_url") is not None
    if fields.get("welcome_button_text") is not None:
        fields["welcome_button_text"] = bot_promo_service.welcome_button_label(
            fields["welcome_button_text"]
        )

    if needs_reembed or any(fields.get(k) is not None for k in ("description", "welcome_message", "about_text")):
        campaign = await campaign_service.get_campaign(bot["campaign_id"])
        texts = bot_promo_service.finalize_bot_texts(
            description=fields.get("description")
            if fields.get("description") is not None
            else row_data.get("description"),
            about_text=fields.get("about_text")
            if fields.get("about_text") is not None
            else row_data.get("about_text"),
            welcome_message=fields.get("welcome_message")
            if fields.get("welcome_message") is not None
            else row_data.get("welcome_message"),
            public_link=public_link,
            link_mode=link_mode,
            target_url=target or "",
            tracking_url=tracking_url,
            display_name=fields.get("display_name")
            if fields.get("display_name") is not None
            else row_data.get("display_name") or "",
            keyword=row_data.get("keyword") or "",
            campaign_defaults=bot_promo_service.campaign_text_defaults(campaign),
        )
        for k, v in texts.items():
            if v is not None:
                fields[k] = v

    updates = []
    params: list[Any] = []
    for key in (
        "display_name",
        "target_url",
        "link_mode",
        "description",
        "about_text",
        "welcome_message",
        "welcome_button_enabled",
        "welcome_button_text",
        "keyword",
    ):
        if fields.get(key) is not None:
            params.append(fields[key])
            updates.append(f"{key} = ${len(params)}")
    avatar_bytes = fields.pop("avatar_bytes", None)
    generate_avatar = fields.pop("generate_avatar", False)

    if not updates and not sync_botfather and not avatar_bytes and not generate_avatar:
        return bot, None

    row = row_data
    if updates:
        params.append(bot_id)
        row = await db.fetch_one(
            f"""
            UPDATE bots SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = ${len(params)}
            RETURNING *
            """,
            *params,
        )

    if (avatar_bytes or generate_avatar) and row.get("username"):
        if sync_botfather:
            if avatar_bytes:
                path = _save_avatar_file(row["campaign_id"], row["username"], avatar_bytes)
                row = await db.fetch_one(
                    "UPDATE bots SET avatar_path = $2, updated_at = NOW() WHERE id = $1 RETURNING *",
                    bot_id,
                    str(path),
                )
        else:
            account = await db.fetch_one(
                "SELECT * FROM telegram_accounts WHERE id = $1",
                row.get("telegram_account_id"),
            )
            if account:
                client = None
                try:
                    session_file = (
                        Config.STORAGE_ROOT
                        / "sessions"
                        / str(row["campaign_id"])
                        / f"{account['id']}.session"
                    )
                    client, _ = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
                    pl = bot_promo_service.resolve_public_link(
                        row.get("link_mode") or bot_promo_service.LINK_MODE_REDIRECT,
                        row.get("target_url") or "",
                        row.get("redirect_slug"),
                    )
                    promo = bot_promo_service.build_promo_texts(
                        public_link=pl,
                        display_name=row["display_name"],
                        keyword=row.get("keyword") or "",
                    )
                    path = await _apply_bot_avatar(
                        client,
                        row["campaign_id"],
                        row["username"],
                        avatar_bytes=avatar_bytes,
                        generate_avatar=generate_avatar and not avatar_bytes,
                        avatar_prompt=promo.get("avatar_prompt"),
                    )
                    if path:
                        row = await db.fetch_one(
                            "UPDATE bots SET avatar_path = $2, updated_at = NOW() WHERE id = $1 RETURNING *",
                            bot_id,
                            str(path),
                        )
                finally:
                    if client:
                        await client.disconnect()

    sync_job: dict[str, Any] | None = None
    if sync_botfather:
        if not row.get("token_encrypted"):
            raise BadRequestError(
                "Синхронизация с Telegram недоступна: у бота нет токена BotFather"
            )
        sync_job = {
            "generate_avatar": generate_avatar,
            "upload_avatar": bool(avatar_bytes) or force_avatar_sync,
        }

    return _bot_row(row, include_welcome=True), sync_job


async def run_botfather_sync(
    bot_id: int,
    *,
    generate_avatar: bool = False,
    upload_avatar: bool = False,
) -> None:
    """Фоновая синхронизация профиля бота с BotFather (после быстрого сохранения в БД)."""
    row = await db.fetch_one("SELECT * FROM bots WHERE id = $1", bot_id)
    if not row or not row.get("token_encrypted"):
        logger.warning("Skip BotFather sync bot_id=%s: no row or token", bot_id)
        return
    try:
        await _sync_botfather_promo(
            bot_id,
            row,
            generate_avatar=generate_avatar,
            upload_avatar=upload_avatar,
        )
        logger.info("BotFather sync completed bot_id=%s @%s", bot_id, row.get("username"))
    except Exception:
        logger.exception("BotFather sync failed bot_id=%s @%s", bot_id, row.get("username"))


async def _sync_botfather_promo(
    bot_id: int,
    row: dict,
    *,
    generate_avatar: bool = False,
    upload_avatar: bool = False,
) -> None:
    """Обновить имя, описание, about и аватар в BotFather."""
    account = await db.fetch_one(
        "SELECT * FROM telegram_accounts WHERE id = $1",
        row.get("telegram_account_id"),
    )
    if not account or not row.get("username"):
        raise BadRequestError("Не найден Telegram-аккаунт или username бота для синхронизации")

    link_mode = bot_promo_service.normalize_link_mode(row.get("link_mode"))
    public_link = bot_promo_service.resolve_public_link(
        link_mode, row.get("target_url") or "", row.get("redirect_slug")
    )
    promo = bot_promo_service.build_promo_texts(
        public_link=public_link,
        display_name=row["display_name"],
        keyword=row.get("keyword") or "",
        link_mode=link_mode,
    )
    description = bot_promo_service.apply_link_placeholder(
        row.get("description") or promo["description"],
        public_link,
    )
    about = bot_promo_service.apply_link_placeholder(
        (row.get("about_text") or promo["about_text"])[:120],
        public_link,
    )
    client = None
    try:
        session_file = (
            Config.STORAGE_ROOT
            / "sessions"
            / str(row["campaign_id"])
            / f"{account['id']}.session"
        )
        try:
            client, _ = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            raise BadRequestError(str(exc)) from exc
        await set_bot_name(client, row["username"], row["display_name"])
        await set_bot_description(client, row["username"], description)
        await set_bot_about(client, row["username"], about)
        if generate_avatar:
            path = await _apply_bot_avatar(
                client,
                row["campaign_id"],
                row["username"],
                generate_avatar=True,
                avatar_prompt=promo.get("avatar_prompt"),
            )
            if path:
                await db.execute(
                    "UPDATE bots SET avatar_path = $2, updated_at = NOW() WHERE id = $1",
                    bot_id,
                    str(path),
                )
        elif upload_avatar and row.get("avatar_path"):
            await set_bot_photo(client, row["username"], Path(row["avatar_path"]))
    finally:
        if client:
            await client.disconnect()


async def cleanup_bots_for_phone(phone: str) -> int:
    """Удаляет записи ботов из БД для всех telegram_accounts с этим номером."""
    if not phone or not str(phone).strip():
        return 0
    accounts = await db.fetch_all(
        "SELECT id FROM telegram_accounts WHERE phone = $1",
        str(phone).strip(),
    )
    total = 0
    for acc in accounts:
        count_row = await db.fetch_one(
            "SELECT COUNT(*)::int AS c FROM bots WHERE telegram_account_id = $1",
            acc["id"],
        )
        n = int(count_row["c"] if count_row else 0)
        if n:
            await db.execute("DELETE FROM bots WHERE telegram_account_id = $1", acc["id"])
            await db.execute(
                """
                UPDATE telegram_accounts
                SET bots_created = 0,
                    status = CASE
                        WHEN status = 'exhausted' THEN 'ready'
                        ELSE status
                    END,
                    updated_at = NOW()
                WHERE id = $1
                """,
                acc["id"],
            )
            total += n
    return total


async def _delete_bot_from_telegram(
    *,
    campaign_id: int,
    account_id: int,
    username: str,
) -> None:
    account = await db.fetch_one(
        "SELECT * FROM telegram_accounts WHERE id = $1 AND campaign_id = $2",
        account_id,
        campaign_id,
    )
    if not account or not account.get("tdata_path"):
        raise BadRequestError(
            "Файлы tdata аккаунта не найдены — невозможно удалить бота в Telegram"
        )

    client = None
    try:
        session_file = (
            Config.STORAGE_ROOT / "sessions" / str(campaign_id) / f"{account_id}.session"
        )
        client, _ = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
        await delete_bot_via_botfather(client, username)
    finally:
        if client:
            await client.disconnect()


async def delete_bot(bot_id: int) -> None:
    row = await db.fetch_one(
        """
        SELECT id, campaign_id, telegram_account_id, username
        FROM bots WHERE id = $1
        """,
        bot_id,
    )
    if not row:
        raise NotFoundError("Бот не найден")

    username = (row.get("username") or "").strip()
    account_id = row.get("telegram_account_id")
    if username and account_id:
        await _delete_bot_from_telegram(
            campaign_id=row["campaign_id"],
            account_id=account_id,
            username=username,
        )

    await db.execute("DELETE FROM bots WHERE id = $1", bot_id)
    if row.get("telegram_account_id"):
        await db.execute(
            """
            UPDATE telegram_accounts
            SET bots_created = GREATEST(0, bots_created - 1),
                status = CASE
                    WHEN bots_created - 1 < max_bots_limit THEN 'ready'
                    ELSE status
                END,
                updated_at = NOW()
            WHERE id = $1
            """,
            row["telegram_account_id"],
        )


async def verify_bot(bot_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM bots WHERE id = $1", bot_id)
    if not row:
        raise NotFoundError("Бот не найден")

    out: dict[str, Any] = {
        "bot_id": bot_id,
        "username": row.get("username"),
        "telegram_url": telegram_bot_url(row.get("username")),
        "tracking_url": bot_promo_service.build_tracking_url(row["redirect_slug"])
        if row.get("redirect_slug")
        else None,
        "click_count": int(row.get("click_count") or 0),
        "local_status": row.get("status"),
        "has_token": bool(row.get("token_encrypted")),
        "verified": False,
        "telegram": None,
        "polling_hint": None,
    }

    if not row.get("token_encrypted"):
        out["message"] = "У бота нет токена — создайте через BotFather"
        return out

    token = decrypt_token(row["token_encrypted"])
    tg = await verify_bot_token(token)
    out["verified"] = True
    out["telegram"] = tg
    if tg.get("username") and tg["username"] != row.get("username"):
        await db.execute(
            "UPDATE bots SET username = $2, updated_at = NOW() WHERE id = $1",
            bot_id,
            tg["username"],
        )
        out["username"] = tg["username"]
        out["telegram_url"] = tg.get("telegram_url")

    if row.get("status") == "active":
        out["polling_hint"] = (
            "Бот помечен как активный — bot-runner подхватит polling в течение минуты"
        )
        out["message"] = "Токен валиден. Откройте ссылку в Telegram и отправьте /start для проверки ответа."
    else:
        out["polling_hint"] = "Запустите бота в панели, чтобы он отвечал на сообщения на сервере."
        out["message"] = "Токен валиден в Telegram. Для ответов на сервере нажмите «Запустить»."

    return out


async def set_bot_status(bot_id: int, status: str) -> dict[str, Any]:
    if status not in ("active", "stopped"):
        raise BadRequestError("Статус: active или stopped")

    row = await db.fetch_one("SELECT * FROM bots WHERE id = $1", bot_id)
    if not row:
        raise NotFoundError("Бот не найден")
    if status == "active" and not row.get("token_encrypted"):
        raise BadRequestError("У бота нет токена — создайте через BotFather")

    updated = await db.fetch_one(
        """
        UPDATE bots SET status = $2, updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        bot_id,
        status,
    )
    return _bot_row(updated, include_welcome=True)
