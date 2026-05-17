"""CRUD ботов, AI-черновики, создание через BotFather."""
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)
from app.domain.services import account_service, bot_promo_service, campaign_service
from app.infrastructure.ai.provider import AIService, generate_image_bytes
from app.infrastructure.database import repository as db
from app.infrastructure.telegram.bot_api import telegram_bot_url, verify_bot_token
from app.infrastructure.telegram.botfather_client import (
    create_bot_via_botfather,
    set_bot_about,
    set_bot_description,
    set_bot_photo,
)
from app.utils.crypto import decrypt_token, encrypt_token
from app.infrastructure.telegram.session_loader import load_client_from_tdata


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _bot_row(row: dict, *, include_welcome: bool = False) -> dict[str, Any]:
    out = {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "telegram_account_id": row.get("telegram_account_id"),
        "keyword": row.get("keyword"),
        "username": row.get("username"),
        "display_name": row["display_name"],
        "description": row.get("description"),
        "status": row["status"],
        "has_token": bool(row.get("token_encrypted")),
        "telegram_url": telegram_bot_url(row.get("username")),
        "target_url": row.get("target_url"),
        "tracking_url": bot_promo_service.build_tracking_url(row["redirect_slug"])
        if row.get("redirect_slug")
        else None,
        "redirect_slug": row.get("redirect_slug"),
        "click_count": int(row.get("click_count") or 0),
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
        ORDER BY c.title, ta.id NULLS LAST, b.created_at DESC
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
) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    await _get_account_for_campaign(campaign_id, telegram_account_id)
    target = bot_promo_service.normalize_target_url(target_url)
    slug = redirect_slug or bot_promo_service.generate_redirect_slug()
    tracking_url = bot_promo_service.build_tracking_url(slug)

    keywords = list(campaign["keywords"] or [])
    kw = (keyword or "").strip() or (keywords[0] if keywords else "бот")
    concept = {
        "keyword": kw,
        "display_name": f"{kw.title()} Bot",
        "description_hint": f"Бот переехал — {kw}",
        "username_hint": ("".join(c for c in kw.lower() if c.isalnum())[:12] or "tg") + "_bot",
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
        profile = {
            "display_name": concept["display_name"],
            "username": concept["username_hint"],
            "description": concept["description_hint"],
        }
        ai_fallback = True

    display_name = profile.get("display_name", concept["display_name"])[:64]
    username = profile.get("username", concept["username_hint"])[:32]

    promo = bot_promo_service.build_promo_texts(
        tracking_url=tracking_url,
        display_name=display_name,
        keyword=kw,
    )
    ai_desc = profile.get("description", "")[:512]
    description = bot_promo_service.embed_tracking_in_description(
        ai_desc or promo["description"], tracking_url, target
    )
    try:
        welcome = await ai.generate_welcome_message(
            tracking_url,
            kw,
            display_name,
            0,
            campaign_id=campaign_id,
            moved_notice=True,
        )
        welcome = bot_promo_service.embed_tracking_in_welcome(welcome, tracking_url, target)
        if not welcome.strip() or welcome.strip() == f"👉 {tracking_url}":
            welcome = promo["welcome_message"]
            ai_fallback = True
    except Exception as exc:
        if Config.AI_FALLBACK_ON_ERROR:
            logger.warning("AI welcome failed: %s — template", exc)
            welcome = promo["welcome_message"]
            ai_fallback = True
        else:
            raise

    return {
        "campaign_id": campaign_id,
        "telegram_account_id": telegram_account_id,
        "target_url": target,
        "redirect_slug": slug,
        "tracking_url": tracking_url,
        "keyword": kw,
        "display_name": display_name,
        "username": username,
        "description": description,
        "welcome_message": welcome,
        "about_text": promo["about_text"],
        "avatar_prompt": profile.get("avatar_prompt", promo["avatar_prompt"]),
        "ai_fallback": ai_fallback,
        "ai_hint": (
            "Тексты из шаблонов (AI недоступен). Проверьте GROQ_API_KEY в .env."
            if ai_fallback
            else None
        ),
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
    keyword: Optional[str] = None,
    redirect_slug: Optional[str] = None,
    create_via_botfather: bool = True,
    auto_start: bool = False,
) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    account = await _get_account_for_campaign(campaign_id, telegram_account_id)
    account = await account_service.ensure_ready_for_bot_creation(account)

    target = bot_promo_service.normalize_target_url(target_url)
    slug = redirect_slug or bot_promo_service.generate_redirect_slug()
    tracking_url = bot_promo_service.build_tracking_url(slug)
    description = bot_promo_service.embed_tracking_in_description(description, tracking_url, target)
    welcome_message = bot_promo_service.embed_tracking_in_welcome(
        welcome_message, tracking_url, target
    )
    promo = bot_promo_service.build_promo_texts(
        tracking_url=tracking_url,
        display_name=display_name,
        keyword=keyword or "",
    )
    about_text = promo["about_text"]

    token = None
    final_username = username.lower().strip().lstrip("@")
    avatar_path = None
    client = None

    try:
        if create_via_botfather:
            session_file = (
                Config.STORAGE_ROOT / "sessions" / str(campaign_id) / f"{telegram_account_id}.session"
            )
            client, _ = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
            result = await create_bot_via_botfather(client, display_name, final_username)
            token = result["token"]
            final_username = result["username"]
            try:
                prompt = promo.get("avatar_prompt") or f"telegram bot banner icon {keyword or display_name}"
                img = await generate_image_bytes(prompt)
                avatar_path = Config.AVATARS_DIR / str(campaign_id) / f"{final_username}.jpg"
                avatar_path.parent.mkdir(parents=True, exist_ok=True)
                avatar_path.write_bytes(img)
                await set_bot_photo(client, final_username, avatar_path)
            except Exception:
                avatar_path = None
            await set_bot_description(client, final_username, description)
            await set_bot_about(client, final_username, about_text)

        status = "active" if auto_start and token else "stopped"
        if not create_via_botfather:
            raise BadRequestError("Создание только через BotFather (укажите create_via_botfather=true)")

        token_enc = encrypt_token(token) if token else None
        row = await db.fetch_one(
            """
            INSERT INTO bots (
                campaign_id, telegram_account_id, keyword, username, display_name,
                description, token_encrypted, avatar_path, welcome_message,
                target_url, redirect_slug, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            campaign_id,
            telegram_account_id,
            keyword,
            final_username,
            display_name[:64],
            description[:512] if description else None,
            token_enc,
            str(avatar_path) if avatar_path else None,
            welcome_message,
            target,
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
        if client:
            await client.disconnect()


async def update_bot(bot_id: int, **fields: Any) -> dict[str, Any]:
    bot = await get_bot(bot_id)
    row_data = await db.fetch_one("SELECT * FROM bots WHERE id = $1", bot_id)
    tracking_url = (
        bot_promo_service.build_tracking_url(row_data["redirect_slug"])
        if row_data.get("redirect_slug")
        else None
    )
    target = row_data.get("target_url")

    if fields.get("target_url") is not None:
        target = bot_promo_service.normalize_target_url(fields["target_url"])
        fields["target_url"] = target

    if fields.get("target_url") and not row_data.get("redirect_slug"):
        slug = bot_promo_service.generate_redirect_slug()
        await db.execute(
            "UPDATE bots SET redirect_slug = $1, updated_at = NOW() WHERE id = $2",
            slug,
            bot_id,
        )
        row_data["redirect_slug"] = slug
        tracking_url = bot_promo_service.build_tracking_url(slug)

    if tracking_url:
        if fields.get("description") is not None:
            fields["description"] = bot_promo_service.embed_tracking_in_description(
                fields["description"], tracking_url, target
            )
        if fields.get("welcome_message") is not None:
            fields["welcome_message"] = bot_promo_service.embed_tracking_in_welcome(
                fields["welcome_message"], tracking_url, target
            )

    updates = []
    params: list[Any] = []
    for key in ("display_name", "target_url", "description", "welcome_message", "keyword"):
        if fields.get(key) is not None:
            params.append(fields[key])
            updates.append(f"{key} = ${len(params)}")
    if not updates and not fields.get("sync_botfather"):
        return bot

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

    if fields.get("sync_botfather") and row.get("token_encrypted"):
        await _sync_botfather_promo(bot_id, row)

    return _bot_row(row, include_welcome=True)


async def _sync_botfather_promo(bot_id: int, row: dict) -> None:
    """Обновить описание и about в BotFather."""
    from app.infrastructure.telegram.session_loader import load_client_from_tdata

    account = await db.fetch_one(
        "SELECT * FROM telegram_accounts WHERE id = $1",
        row.get("telegram_account_id"),
    )
    if not account or not row.get("username"):
        return

    tracking_url = bot_promo_service.build_tracking_url(row["redirect_slug"])
    promo = bot_promo_service.build_promo_texts(
        tracking_url=tracking_url,
        display_name=row["display_name"],
        keyword=row.get("keyword") or "",
    )
    description = row.get("description") or promo["description"]
    about = promo["about_text"]
    client = None
    try:
        session_file = (
            Config.STORAGE_ROOT
            / "sessions"
            / str(row["campaign_id"])
            / f"{account['id']}.session"
        )
        client, _ = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
        await set_bot_description(client, row["username"], description)
        await set_bot_about(client, row["username"], about)
        if row.get("avatar_path"):
            await set_bot_photo(client, row["username"], Path(row["avatar_path"]))
    finally:
        if client:
            await client.disconnect()


async def delete_bot(bot_id: int) -> None:
    row = await db.fetch_one(
        "SELECT id, telegram_account_id, status FROM bots WHERE id = $1", bot_id
    )
    if not row:
        raise NotFoundError("Бот не найден")

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
