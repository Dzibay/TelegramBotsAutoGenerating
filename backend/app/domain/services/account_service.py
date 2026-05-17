import shutil
import zipfile
from pathlib import Path
from typing import Any

from app.config import Config
from app.constants import ErrorMessages
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)
from app.domain.services import campaign_service
from app.infrastructure.database import repository as db


async def add_tdata_archives_batch(
    campaign_id: int, archive_paths: list[tuple[Path, str | None]]
) -> list[dict[str, Any]]:
    results = []
    for path, label in archive_paths:
        results.append(await add_tdata_archive(campaign_id, path, label))
    return results


async def add_tdata_archive(campaign_id: int, archive_path: Path, label: str | None = None) -> dict[str, Any]:
    await campaign_service.get_campaign(campaign_id)

    if not zipfile.is_zipfile(archive_path):
        raise BadRequestError("Ожидается ZIP-архив с папкой tdata")

    row = await db.fetch_one(
        """
        INSERT INTO telegram_accounts (campaign_id, label, tdata_path, status)
        VALUES ($1, $2, '', 'pending')
        RETURNING id, campaign_id, label, status, max_bots_limit, bots_created, created_at
        """,
        campaign_id,
        label,
    )
    account_id = row["id"]
    dest = Config.TDATA_DIR / str(campaign_id) / str(account_id)
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(dest)

    if not any(dest.rglob("tdata")) and not (dest / "tdata").exists():
        shutil.rmtree(dest, ignore_errors=True)
        await db.execute("DELETE FROM telegram_accounts WHERE id = $1", account_id)
        raise BadRequestError("В архиве не найдена папка tdata")

    await db.execute(
        """
        UPDATE telegram_accounts
        SET tdata_path = $2, status = 'ready', updated_at = NOW()
        WHERE id = $1
        """,
        account_id,
        str(dest),
    )

    updated = await db.fetch_one(
        "SELECT id, campaign_id, label, status, max_bots_limit, bots_created, tdata_path, created_at FROM telegram_accounts WHERE id = $1",
        account_id,
    )
    return {
        "id": updated["id"],
        "campaign_id": updated["campaign_id"],
        "label": updated.get("label"),
        "status": updated["status"],
        "max_bots_limit": updated["max_bots_limit"],
        "bots_created": updated["bots_created"],
        "created_at": updated["created_at"].isoformat() if updated.get("created_at") else None,
    }


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
        SELECT id, campaign_id, label, phone, status, max_bots_limit, bots_created,
               last_error, prepared_account_id, tdata_path, created_at
        FROM telegram_accounts
        WHERE campaign_id = $1
        ORDER BY created_at
        """,
        campaign_id,
    )
    return [_serialize_account(r) for r in rows]


async def remove_from_campaign(campaign_id: int, account_id: int) -> None:
    import shutil

    row = await db.fetch_one(
        "SELECT * FROM telegram_accounts WHERE id = $1 AND campaign_id = $2",
        account_id,
        campaign_id,
    )
    if not row:
        raise NotFoundError("Аккаунт не найден в кампании")

    bots_count = await db.fetch_val(
        "SELECT COUNT(*)::int FROM bots WHERE telegram_account_id = $1",
        account_id,
    )
    if bots_count and int(bots_count) > 0:
        raise BadRequestError(
            f"На аккаунте есть {bots_count} бот(ов). Сначала удалите ботов, затем уберите аккаунт."
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
