"""Проверка готовности Telegram-аккаунтов кампании."""
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.domain.services import campaign_service
from app.domain.services.account_session_service import account_lock
from app.infrastructure.database import repository as db
from app.infrastructure.telegram.session_loader import load_client_from_tdata

logger = get_logger(__name__)


def tdata_exists(tdata_path: str | None) -> bool:
    if not tdata_path or not str(tdata_path).strip():
        return False
    p = Path(tdata_path)
    if not p.is_dir():
        return False
    try:
        from app.infrastructure.telegram.session_loader import find_tdata_folder

        find_tdata_folder(p)
        return True
    except FileNotFoundError:
        return False


def account_capabilities(row: dict[str, Any]) -> dict[str, Any]:
    """Быстрая оценка без подключения к Telegram."""
    status = row.get("status") or "pending"
    bots = int(row.get("bots_created") or 0)
    limit = int(row.get("max_bots_limit") or 20)
    has_tdata = tdata_exists(row.get("tdata_path"))

    can_create = (
        has_tdata
        and bots < limit
        and status in ("ready", "creating", "pending", "error", "exhausted")
        and status != "disabled"
    )
    if status == "exhausted" and bots >= limit:
        can_create = False

    if row.get("is_banned"):
        can_create = False

    hints: list[str] = []
    if row.get("is_banned"):
        hints.append("Аккаунт забанен — создание ботов недоступно")
    if not has_tdata:
        hints.append("Нет файлов сессии — уберите аккаунт и добавьте заново из подготовленных")
    elif status == "pending":
        hints.append("Нажмите «Проверить», чтобы подтвердить вход в Telegram")
    elif status == "error":
        err = row.get("last_error") or "неизвестная ошибка"
        hints.append(f"Ошибка: {err}. Нажмите «Проверить» снова")
    elif status == "exhausted" and bots >= limit:
        hints.append("Достигнут лимит ботов на аккаунте")
    elif status == "ready" and has_tdata and not row.get("is_banned"):
        hints.append("Готов к созданию ботов")
    elif status == "creating":
        hints.append("Идёт создание ботов")

    flood_remaining = 0
    until = row.get("botfather_flood_until")
    if until:
        from datetime import datetime, timezone

        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        flood_remaining = max(0, int((until - datetime.now(timezone.utc)).total_seconds()))
        if flood_remaining > 0:
            from app.domain.services.account_flood_service import format_flood_wait_human

            hints.append(
                f"Лимит BotFather: подождите ещё {format_flood_wait_human(flood_remaining)}"
            )

    return {
        "tdata_on_disk": has_tdata,
        "can_create_bots": can_create,
        "health_hint": " ".join(hints) if hints else "",
        "botfather_flood_remaining_sec": flood_remaining,
    }


def _serialize_account(row: dict[str, Any], extra: Optional[dict] = None) -> dict[str, Any]:
    caps = account_capabilities(row)
    bots_in_db = int(row.get("bots_in_db") or 0)
    bots_created = int(row.get("bots_created") or 0)
    out = {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "label": row.get("label"),
        "phone": row.get("phone"),
        "status": row["status"],
        "max_bots_limit": row["max_bots_limit"],
        "bots_created": bots_created,
        "bots_in_db": bots_in_db,
        "bots_in_telegram": bots_created,
        "last_error": row.get("last_error"),
        "prepared_account_id": row.get("prepared_account_id"),
        "is_banned": bool(row.get("is_banned")),
        "tdata_on_disk": caps["tdata_on_disk"],
        "can_create_bots": caps["can_create_bots"],
        "health_hint": caps["health_hint"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "botfather_flood_until": (
            row["botfather_flood_until"].isoformat() if row.get("botfather_flood_until") else None
        ),
        "botfather_flood_remaining_sec": caps.get("botfather_flood_remaining_sec", 0),
    }
    if bots_in_db != bots_created:
        out["health_hint"] = (
            (out["health_hint"] + " ").strip()
            + f"В Telegram: {bots_created}, в кампании: {bots_in_db}. "
            "Нажмите «Показать ботов» для актуального списка."
        ).strip()
    if extra:
        out.update(extra)
    return out


async def _fetch_account_row(account_id: int, campaign_id: int | None = None) -> dict[str, Any] | None:
    if campaign_id is not None:
        return await db.fetch_one(
            """
            SELECT ta.*,
                   (SELECT COUNT(*)::int FROM bots b WHERE b.telegram_account_id = ta.id) AS bots_in_db
            FROM telegram_accounts ta
            WHERE ta.id = $1 AND ta.campaign_id = $2
            """,
            account_id,
            campaign_id,
        )
    return await db.fetch_one(
        """
        SELECT ta.*,
               (SELECT COUNT(*)::int FROM bots b WHERE b.telegram_account_id = ta.id) AS bots_in_db
        FROM telegram_accounts ta
        WHERE ta.id = $1
        """,
        account_id,
    )


async def verify_account(campaign_id: int, account_id: int) -> dict[str, Any]:
    row = await _fetch_account_row(account_id, campaign_id)
    if not row:
        raise NotFoundError("Аккаунт не найден в этой кампании")

    if not Config.TELEGRAM_API_ID or not Config.TELEGRAM_API_HASH:
        raise BadRequestError(
            "На сервере не заданы TELEGRAM_API_ID и TELEGRAM_API_HASH (my.telegram.org)"
        )

    if not tdata_exists(row.get("tdata_path")):
        await db.execute(
            """
            UPDATE telegram_accounts
            SET status = 'error',
                last_error = 'Файлы tdata не найдены на сервере',
                updated_at = NOW()
            WHERE id = $1
            """,
            account_id,
        )
        row = await _fetch_account_row(account_id)
        return _serialize_account(
            row,
            {
                "verified": False,
                "verify_message": "Файлы сессии не найдены. Уберите аккаунт и добавьте снова из подготовленных.",
            },
        )

    client = None
    async with account_lock(account_id):
        try:
            session_file = (
                Config.STORAGE_ROOT / "sessions" / str(campaign_id) / f"{account_id}.session"
            )
            client, me = await load_client_from_tdata(Path(row["tdata_path"]), session_file)
            phone = getattr(me, "phone", None) or str(getattr(me, "id", ""))
            username = getattr(me, "username", None)

            await db.execute(
                """
                UPDATE telegram_accounts
                SET status = 'ready',
                    phone = $2,
                    last_error = NULL,
                    updated_at = NOW()
                WHERE id = $1
                """,
                account_id,
                phone,
            )
            row = await _fetch_account_row(account_id)
            msg = "Сессия OK"
            if phone:
                msg += f" ({phone})"
            if username:
                msg += f" @{username}"

            from app.domain.services.account_service import sync_bots_created_count
            from app.infrastructure.telegram.botfather_client import list_bots_via_botfather

            try:
                tg_bots = await list_bots_via_botfather(client)
                await sync_bots_created_count(account_id, len(tg_bots))
                row = await _fetch_account_row(account_id)
                msg += f" · ботов в Telegram: {len(tg_bots)}"
            except Exception as sync_exc:
                logger.warning("Bot count sync on verify id=%s: %s", account_id, sync_exc)

            return _serialize_account(row, {"verified": True, "verify_message": msg})
        except Exception as exc:
            err = str(exc)[:500]
            logger.warning("Verify account id=%s failed: %s", account_id, err)
            await db.execute(
                """
                UPDATE telegram_accounts
                SET status = 'error', last_error = $2, updated_at = NOW()
                WHERE id = $1
                """,
                account_id,
                err,
            )
            row = await _fetch_account_row(account_id)
            return _serialize_account(
                row,
                {"verified": False, "verify_message": f"Проверка не пройдена: {err}"},
            )
        finally:
            if client:
                await client.disconnect()


async def verify_all_accounts(campaign_id: int) -> dict[str, Any]:
    await campaign_service.get_campaign(campaign_id)
    rows = await db.fetch_all(
        "SELECT id FROM telegram_accounts WHERE campaign_id = $1 ORDER BY id",
        campaign_id,
    )
    results = []
    ok = 0
    for r in rows:
        item = await verify_account(campaign_id, r["id"])
        results.append(item)
        if item.get("verified"):
            ok += 1
    return {
        "total": len(results),
        "verified_ok": ok,
        "verified_failed": len(results) - ok,
        "accounts": results,
    }
