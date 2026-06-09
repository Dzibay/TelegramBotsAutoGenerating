from pathlib import Path
from typing import Any

from app.config import Config
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.services import campaign_service
from app.infrastructure.database import repository as db

logger = get_logger(__name__)


def _tdata_path_valid(tdata_path: str | None) -> bool:
    from app.domain.services.account_health import tdata_exists

    return tdata_exists(tdata_path)


_STATUS_HINTS = {
    "pending": "аккаунт ещё не активирован — перепривяжите из пула подготовленных",
    "error": "ошибка на аккаунте — проверьте подготовку tdata",
    "disabled": "аккаунт отключён",
    "exhausted": "достигнут лимит ботов на этом аккаунте",
}


async def ensure_ready_for_bot_creation(account: dict[str, Any]) -> dict[str, Any]:
    """
    Проверяет, что аккаунт можно использовать для BotFather.
    При pending/error и валидном tdata — автоматически переводит в ready.
    """
    account_id = account["id"]
    status = account.get("status") or "pending"
    bots_created = int(account.get("bots_created") or 0)
    max_limit = int(account.get("max_bots_limit") or 20)
    tdata_ok = _tdata_path_valid(account.get("tdata_path"))

    if bots_created >= max_limit:
        raise ConflictError(
            f"На аккаунте достигнут лимит ботов ({bots_created}/{max_limit})"
        )

    if status in ("ready", "creating"):
        if not tdata_ok:
            raise BadRequestError(
                "Файлы tdata аккаунта не найдены на сервере. "
                "Удалите аккаунт из кампании и добавьте снова из пула подготовленных."
            )
        return account

    if status == "exhausted" and bots_created < max_limit:
        row = await db.fetch_one(
            """
            UPDATE telegram_accounts
            SET status = 'ready', updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            account_id,
        )
        logger.info("Account id=%s: exhausted -> ready (есть слоты для ботов)", account_id)
        return row

    if status in ("pending", "error") and tdata_ok:
        row = await db.fetch_one(
            """
            UPDATE telegram_accounts
            SET status = 'ready', last_error = NULL, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            account_id,
        )
        logger.info("Account id=%s: %s -> ready (tdata на месте)", account_id, status)
        return row

    hint = _STATUS_HINTS.get(status, "неизвестный статус")
    last_err = account.get("last_error") or ""
    extra = f" Ошибка: {last_err}" if last_err else ""
    if status in ("pending", "error") and not tdata_ok:
        raise BadRequestError(
            f"Аккаунт не готов (статус: {status}). Нет файлов tdata на сервере. "
            f"Добавьте аккаунт из раздела «Подготовка аккаунтов» в кампанию.{extra}"
        )
    raise BadRequestError(
        f"Аккаунт не готов к созданию ботов (статус: {status}). {hint}.{extra}"
    )


async def list_accounts(campaign_id: int) -> list[dict[str, Any]]:
    from app.domain.services.account_health import _serialize_account

    await campaign_service.get_campaign(campaign_id)
    rows = await db.fetch_all(
        """
        SELECT ta.id, ta.campaign_id, ta.label, ta.phone, ta.status, ta.max_bots_limit,
               ta.bots_created, ta.last_error, ta.prepared_account_id, ta.tdata_path,
               ta.created_at,
               (SELECT COUNT(*)::int FROM bots b WHERE b.telegram_account_id = ta.id) AS bots_in_db
        FROM telegram_accounts ta
        WHERE ta.campaign_id = $1
        ORDER BY ta.created_at
        """,
        campaign_id,
    )
    return [_serialize_account(r) for r in rows]


async def _get_campaign_account(campaign_id: int, account_id: int) -> dict[str, Any]:
    row = await db.fetch_one(
        "SELECT * FROM telegram_accounts WHERE id = $1 AND campaign_id = $2",
        account_id,
        campaign_id,
    )
    if not row:
        raise NotFoundError("Аккаунт не найден в этой кампании")
    return row


async def _load_account_client(campaign_id: int, account_id: int, account: dict[str, Any]):
    from app.core.exceptions import BadRequestError
    from app.infrastructure.telegram.session_loader import load_client_from_tdata

    if not Config.TELEGRAM_API_ID or not Config.TELEGRAM_API_HASH:
        raise BadRequestError(
            "На сервере не заданы TELEGRAM_API_ID и TELEGRAM_API_HASH (my.telegram.org)"
        )
    if not _tdata_path_valid(account.get("tdata_path")):
        raise BadRequestError("Файлы tdata аккаунта не найдены на сервере")

    session_file = Config.STORAGE_ROOT / "sessions" / str(campaign_id) / f"{account_id}.session"
    return await load_client_from_tdata(Path(account["tdata_path"]), session_file)


async def sync_bots_created_count(account_id: int, telegram_bots_count: int) -> None:
    """Синхронизирует счётчик ботов с фактическим числом в Telegram."""
    await db.execute(
        """
        UPDATE telegram_accounts
        SET bots_created = $2,
            status = CASE
                WHEN $2 >= max_bots_limit THEN 'exhausted'
                WHEN status = 'exhausted' AND $2 < max_bots_limit THEN 'ready'
                ELSE status
            END,
            updated_at = NOW()
        WHERE id = $1
        """,
        account_id,
        max(0, int(telegram_bots_count)),
    )


async def list_account_bots(campaign_id: int, account_id: int) -> dict[str, Any]:
    """
    Список ботов аккаунта из BotFather (/mybots) с пометкой, есть ли бот в приложении.
    Обновляет bots_created по фактическому числу в Telegram.
    """
    from app.infrastructure.telegram.botfather_client import list_bots_via_botfather
    from app.utils.telegram_username import normalize_bot_username

    await campaign_service.get_campaign(campaign_id)
    account = await _get_campaign_account(campaign_id, account_id)

    client = None
    try:
        client, _ = await _load_account_client(campaign_id, account_id, account)
        telegram_usernames = await list_bots_via_botfather(client)
    finally:
        if client:
            await client.disconnect()

    db_rows = await db.fetch_all(
        """
        SELECT id, username, display_name, status
        FROM bots
        WHERE telegram_account_id = $1
        """,
        account_id,
    )
    db_by_username: dict[str, dict[str, Any]] = {}
    for row in db_rows:
        uname = normalize_bot_username(row.get("username") or "")
        if uname:
            db_by_username[uname] = row

    telegram_set = set(telegram_usernames)
    bots: list[dict[str, Any]] = []

    for username in telegram_usernames:
        db_row = db_by_username.get(username)
        bots.append(
            {
                "username": username,
                "in_telegram": True,
                "in_app": db_row is not None,
                "bot_id": db_row["id"] if db_row else None,
                "display_name": db_row.get("display_name") if db_row else None,
                "status": db_row.get("status") if db_row else None,
            }
        )

    for username, db_row in db_by_username.items():
        if username not in telegram_set:
            bots.append(
                {
                    "username": username,
                    "in_telegram": False,
                    "in_app": True,
                    "bot_id": db_row["id"],
                    "display_name": db_row.get("display_name"),
                    "status": db_row.get("status"),
                }
            )

    await sync_bots_created_count(account_id, len(telegram_usernames))

    account = await db.fetch_one("SELECT * FROM telegram_accounts WHERE id = $1", account_id)
    return {
        "account_id": account_id,
        "telegram_bots_count": len(telegram_usernames),
        "bots_in_app": len(db_rows),
        "bots_created": account["bots_created"],
        "max_bots_limit": account["max_bots_limit"],
        "bots": bots,
    }


async def delete_account_bot(
    campaign_id: int, account_id: int, username: str
) -> dict[str, Any]:
    """Удаляет бота в BotFather; при наличии в БД — удаляет запись и синхронизирует счётчик."""
    from app.infrastructure.telegram.botfather_client import (
        delete_bot_via_botfather,
        list_bots_via_botfather,
    )
    from app.utils.telegram_username import normalize_bot_username

    await campaign_service.get_campaign(campaign_id)
    account = await _get_campaign_account(campaign_id, account_id)
    uname = normalize_bot_username(username)
    if not uname:
        raise BadRequestError("Некорректный username бота")

    db_row = await db.fetch_one(
        """
        SELECT id FROM bots
        WHERE telegram_account_id = $1
          AND LOWER(REPLACE(username, '@', '')) = LOWER($2)
        """,
        account_id,
        uname,
    )

    client = None
    try:
        client, _ = await _load_account_client(campaign_id, account_id, account)
        await delete_bot_via_botfather(client, uname)
        remaining = await list_bots_via_botfather(client)
    finally:
        if client:
            await client.disconnect()

    if db_row:
        await db.execute("DELETE FROM bots WHERE id = $1", db_row["id"])

    await sync_bots_created_count(account_id, len(remaining))

    account = await db.fetch_one("SELECT * FROM telegram_accounts WHERE id = $1", account_id)
    return {
        "username": uname,
        "deleted_from_telegram": True,
        "deleted_from_app": db_row is not None,
        "telegram_bots_count": len(remaining),
        "bots_created": account["bots_created"],
        "max_bots_limit": account["max_bots_limit"],
    }


async def remove_from_campaign(campaign_id: int, account_id: int) -> None:
    import shutil

    row = await db.fetch_one(
        "SELECT * FROM telegram_accounts WHERE id = $1 AND campaign_id = $2",
        account_id,
        campaign_id,
    )
    if not row:
        raise NotFoundError("Аккаунт не найден в кампании")

    if int(row.get("bots_created") or 0) > 0:
        raise BadRequestError(
            f"На аккаунте есть {row['bots_created']} бот(ов) в Telegram. "
            "Сначала удалите всех ботов (кнопка «Показать ботов» в карточке аккаунта), затем уберите аккаунт."
        )
    bots_in_db = await db.fetch_val(
        "SELECT COUNT(*)::int FROM bots WHERE telegram_account_id = $1",
        account_id,
    )
    if bots_in_db and int(bots_in_db) > 0:
        raise BadRequestError(
            f"В кампании остались записи о {bots_in_db} бот(ах). Удалите их, затем уберите аккаунт."
        )

    prepared_id = row.get("prepared_account_id")
    tdata_path = row.get("tdata_path")

    await db.execute("DELETE FROM telegram_accounts WHERE id = $1", account_id)

    if prepared_id:
        await db.execute(
            """
            UPDATE prepared_accounts
            SET status = 'available', updated_at = NOW()
            WHERE id = $1
            """,
            prepared_id,
        )

    if tdata_path:
        p = Path(tdata_path)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
