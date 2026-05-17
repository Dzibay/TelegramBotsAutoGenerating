import shutil
import zipfile
from pathlib import Path
from typing import Any

from app.config import Config
from app.constants import ErrorMessages
from app.core.exceptions import BadRequestError, NotFoundError
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


async def list_accounts(campaign_id: int) -> list[dict[str, Any]]:
    await campaign_service.get_campaign(campaign_id)
    rows = await db.fetch_all(
        """
        SELECT id, campaign_id, label, status, max_bots_limit, bots_created, last_error, created_at
        FROM telegram_accounts
        WHERE campaign_id = $1
        ORDER BY created_at
        """,
        campaign_id,
    )
    return [
        {
            "id": r["id"],
            "campaign_id": r["campaign_id"],
            "label": r.get("label"),
            "status": r["status"],
            "max_bots_limit": r["max_bots_limit"],
            "bots_created": r["bots_created"],
            "last_error": r.get("last_error"),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]
