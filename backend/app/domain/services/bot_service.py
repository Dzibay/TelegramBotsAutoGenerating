"""CRUD ботов, AI-черновики, создание через BotFather."""
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.domain.services import campaign_service
from app.infrastructure.ai.provider import AIService, generate_image_bytes
from app.infrastructure.database import repository as db
from app.infrastructure.telegram.botfather_client import (
    create_bot_via_botfather,
    set_bot_description,
    set_bot_photo,
)
from app.infrastructure.telegram.session_loader import load_client_from_tdata
from app.utils.crypto import encrypt_token


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
    keyword: Optional[str] = None,
) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    await _get_account_for_campaign(campaign_id, telegram_account_id)

    keywords = list(campaign["keywords"] or [])
    kw = (keyword or "").strip() or (keywords[0] if keywords else "бот")
    concept = {
        "keyword": kw,
        "display_name": f"{kw.title()} Bot",
        "description_hint": f"Помощник по теме {kw}",
        "username_hint": ("".join(c for c in kw.lower() if c.isalnum())[:12] or "tg") + "_bot",
    }

    ai = AIService()
    profile = await ai.refine_bot_profile(
        concept, campaign.get("niche_description"), campaign_id=campaign_id
    )
    display_name = profile.get("display_name", concept["display_name"])[:64]
    description = profile.get("description", "")[:512]
    username = profile.get("username", concept["username_hint"])[:32]
    welcome = await ai.generate_welcome_message(
        campaign["resource_url"],
        kw,
        display_name,
        0,
        campaign_id=campaign_id,
    )
    return {
        "campaign_id": campaign_id,
        "telegram_account_id": telegram_account_id,
        "keyword": kw,
        "display_name": display_name,
        "username": username,
        "description": description,
        "welcome_message": welcome,
        "avatar_prompt": profile.get("avatar_prompt", f"telegram bot icon {kw}"),
    }


async def create_bot(
    *,
    campaign_id: int,
    telegram_account_id: int,
    display_name: str,
    username: str,
    description: str,
    welcome_message: str,
    keyword: Optional[str] = None,
    create_via_botfather: bool = True,
    auto_start: bool = False,
) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    account = await _get_account_for_campaign(campaign_id, telegram_account_id)

    if account["bots_created"] >= account["max_bots_limit"]:
        raise ConflictError("На аккаунте достигнут лимит ботов")

    if account["status"] not in ("ready", "creating", "exhausted"):
        raise BadRequestError("Аккаунт не готов к созданию ботов")

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
                prompt = f"minimal telegram bot icon {keyword or display_name}"
                img = await generate_image_bytes(prompt)
                avatar_path = Config.AVATARS_DIR / str(campaign_id) / f"{final_username}.jpg"
                avatar_path.parent.mkdir(parents=True, exist_ok=True)
                avatar_path.write_bytes(img)
                await set_bot_photo(client, final_username, avatar_path)
            except Exception:
                avatar_path = None
            if description:
                await set_bot_description(client, final_username, description)

        status = "active" if auto_start and token else "stopped"
        if not create_via_botfather:
            raise BadRequestError("Создание только через BotFather (укажите create_via_botfather=true)")

        token_enc = encrypt_token(token) if token else None
        row = await db.fetch_one(
            """
            INSERT INTO bots (
                campaign_id, telegram_account_id, keyword, username, display_name,
                description, token_encrypted, avatar_path, welcome_message, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
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
    updates = []
    params: list[Any] = []
    for key in ("display_name", "description", "welcome_message", "keyword"):
        if fields.get(key) is not None:
            params.append(fields[key])
            updates.append(f"{key} = ${len(params)}")
    if not updates:
        return bot

    params.append(bot_id)
    row = await db.fetch_one(
        f"""
        UPDATE bots SET {', '.join(updates)}, updated_at = NOW()
        WHERE id = ${len(params)}
        RETURNING *
        """,
        *params,
    )
    return _bot_row(row, include_welcome=True)


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
