"""Проверка готовности Telegram-аккаунтов кампании."""
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.domain.services import campaign_service
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

    hints: list[str] = []
    if not has_tdata:
        hints.append("Нет файлов tdata на сервере — удалите и добавьте из пула подготовленных")
    elif status == "pending":
        hints.append("Нажмите «Проверить» — подтвердить сессию Telegram")
    elif status == "error":
        err = row.get("last_error") or "неизвестная ошибка"
        hints.append(f"Ошибка: {err}. Нажмите «Проверить» снова")
    elif status == "exhausted" and bots >= limit:
        hints.append("Достигнут лимит ботов на аккаунте")
    elif status == "ready" and has_tdata:
        hints.append("Готов к созданию ботов")
    elif status == "creating":
        hints.append("Идёт создание ботов")

    return {
        "tdata_on_disk": has_tdata,
        "can_create_bots": can_create,
        "health_hint": " ".join(hints) if hints else "",
    }


def _serialize_account(row: dict[str, Any], extra: Optional[dict] = None) -> dict[str, Any]:
    caps = account_capabilities(row)
    out = {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "label": row.get("label"),
        "phone": row.get("phone"),
        "status": row["status"],
        "max_bots_limit": row["max_bots_limit"],
        "bots_created": row["bots_created"],
        "last_error": row.get("last_error"),
        "prepared_account_id": row.get("prepared_account_id"),
        "tdata_on_disk": caps["tdata_on_disk"],
        "can_create_bots": caps["can_create_bots"],
        "health_hint": caps["health_hint"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }
    if extra:
        out.update(extra)
    return out


async def verify_account(campaign_id: int, account_id: int) -> dict[str, Any]:
    row = await db.fetch_one(
        "SELECT * FROM telegram_accounts WHERE id = $1 AND campaign_id = $2",
        account_id,
        campaign_id,
    )
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
        row = await db.fetch_one("SELECT * FROM telegram_accounts WHERE id = $1", account_id)
        return _serialize_account(
            row,
            {
                "verified": False,
                "verify_message": "Файлы tdata отсутствуют. Удалите аккаунт и добавьте снова из подготовленных.",
            },
        )

    client = None
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
        row = await db.fetch_one("SELECT * FROM telegram_accounts WHERE id = $1", account_id)
        msg = f"Сессия OK"
        if phone:
            msg += f" ({phone})"
        if username:
            msg += f" @{username}"
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
        row = await db.fetch_one("SELECT * FROM telegram_accounts WHERE id = $1", account_id)
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
