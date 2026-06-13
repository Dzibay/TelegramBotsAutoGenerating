from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.domain.services import campaign_service
from app.infrastructure.database import repository as db
from app.infrastructure.telegram.session_loader import find_tdata_folder
from app.utils.tdata_storage import copy_tdata_tree


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _row(row: dict) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row.get("label"),
        "phone": row.get("phone"),
        "username": row.get("username"),
        "status": row["status"],
        "is_banned": bool(row.get("is_banned")),
        "source_prep_account_id": row.get("source_prep_account_id"),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


async def register_from_prep_account(prep_account: dict) -> dict[str, Any]:
    """Сохраняет успешно подготовленный аккаунт в общий пул."""
    prep_id = prep_account["id"]
    existing = await db.fetch_one(
        """
        SELECT * FROM prepared_accounts
        WHERE source_prep_account_id = $1
        """,
        prep_id,
    )
    if existing:
        if existing["status"] == "disabled":
            await db.execute(
                """
                UPDATE prepared_accounts
                SET status = 'available', updated_at = NOW()
                WHERE id = $1
                """,
                existing["id"],
            )
            existing = await db.fetch_one(
                "SELECT * FROM prepared_accounts WHERE id = $1", existing["id"]
            )
        return _row(existing)

    src = Path(prep_account["tdata_path"])
    if not src.is_dir():
        raise ValueError(f"tdata не найден: {src}")
    find_tdata_folder(src)

    row = await db.fetch_one(
        """
        INSERT INTO prepared_accounts (
            source_prep_account_id, label, tdata_path, phone, username, status
        )
        VALUES ($1, $2, '', $3, $4, 'available')
        RETURNING *
        """,
        prep_id,
        prep_account.get("label"),
        prep_account.get("phone"),
        prep_account.get("username"),
    )
    pool_id = row["id"]
    dest = Config.PREPARED_TDATA_DIR / str(pool_id)
    copy_tdata_tree(src, dest)

    updated = await db.fetch_one(
        """
        UPDATE prepared_accounts
        SET tdata_path = $2, updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        pool_id,
        str(dest),
    )
    return _row(updated)


async def list_prepared_accounts(*, available_only: bool = False) -> list[dict[str, Any]]:
    if available_only:
        rows = await db.fetch_all(
            """
            SELECT * FROM prepared_accounts
            WHERE status = 'available' AND is_banned = FALSE
            ORDER BY created_at DESC
            """
        )
    else:
        rows = await db.fetch_all(
            "SELECT * FROM prepared_accounts ORDER BY created_at DESC LIMIT 200"
        )
    return [_row(r) for r in rows]


async def get_prepared_account(prepared_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM prepared_accounts WHERE id = $1", prepared_id)
    if not row:
        raise NotFoundError("Подготовленный аккаунт не найден")
    return _row(row)


async def update_prepared_account(
    prepared_id: int,
    *,
    label: str | None = None,
    is_banned: bool | None = None,
    patch_label: bool = False,
    patch_banned: bool = False,
) -> dict[str, Any]:
    await get_prepared_account(prepared_id)
    row = await db.fetch_one("SELECT * FROM prepared_accounts WHERE id = $1", prepared_id)
    if not row:
        raise NotFoundError("Подготовленный аккаунт не найден")

    next_label = row.get("label")
    if patch_label:
        next_label = (label or "").strip() or None

    next_banned = row.get("is_banned") or False
    if patch_banned:
        next_banned = bool(is_banned)

    updated = await db.fetch_one(
        """
        UPDATE prepared_accounts
        SET label = $2, is_banned = $3, updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        prepared_id,
        next_label,
        next_banned,
    )

    if patch_banned:
        await db.execute(
            """
            UPDATE telegram_accounts
            SET is_banned = $2, updated_at = NOW()
            WHERE prepared_account_id = $1
            """,
            prepared_id,
            next_banned,
        )

    return _row(updated)


async def update_prepared_account_label(prepared_id: int, label: str | None) -> dict[str, Any]:
    return await update_prepared_account(
        prepared_id,
        label=label,
        patch_label=True,
    )


async def attach_to_campaign(campaign_id: int, prepared_ids: list[int]) -> list[dict[str, Any]]:
    if not prepared_ids:
        raise BadRequestError("Выберите хотя бы один подготовленный аккаунт")

    await campaign_service.get_campaign(campaign_id)
    unique_ids = list(dict.fromkeys(prepared_ids))
    results: list[dict[str, Any]] = []

    for prepared_id in unique_ids:
        prepared = await db.fetch_one(
            "SELECT * FROM prepared_accounts WHERE id = $1 FOR UPDATE",
            prepared_id,
        )
        if not prepared:
            raise NotFoundError(f"Аккаунт #{prepared_id} не найден в пуле")
        if prepared["status"] != "available":
            raise ConflictError(
                f"Аккаунт {(prepared.get('label') or '').strip() or prepared_id} "
                f"уже используется (статус: {prepared['status']})"
            )
        if prepared.get("is_banned"):
            raise BadRequestError(
                f"Аккаунт {(prepared.get('label') or '').strip() or prepared_id} "
                "забанен и не может быть добавлен в кампанию"
            )

        src = Path(prepared["tdata_path"])
        if not src.is_dir():
            raise BadRequestError(f"Файлы tdata аккаунта #{prepared_id} отсутствуют на диске")

        row = await db.fetch_one(
            """
            INSERT INTO telegram_accounts (
                campaign_id, prepared_account_id, label, phone, tdata_path, status, is_banned
            )
            VALUES ($1, $2, $3, $4, '', 'pending', $5)
            RETURNING id
            """,
            campaign_id,
            prepared_id,
            prepared.get("label"),
            prepared.get("phone"),
            bool(prepared.get("is_banned")),
        )
        account_id = row["id"]
        dest = Config.TDATA_DIR / str(campaign_id) / str(account_id)
        copy_tdata_tree(src, dest)

        await db.execute(
            """
            UPDATE telegram_accounts
            SET tdata_path = $2, status = 'ready', updated_at = NOW()
            WHERE id = $1
            """,
            account_id,
            str(dest),
        )
        await db.execute(
            """
            UPDATE prepared_accounts
            SET status = 'in_use', updated_at = NOW()
            WHERE id = $1
            """,
            prepared_id,
        )

        acc = await db.fetch_one(
            """
            SELECT id, campaign_id, label, status, max_bots_limit, bots_created,
                   prepared_account_id, created_at
            FROM telegram_accounts WHERE id = $1
            """,
            account_id,
        )
        results.append(
            {
                "id": acc["id"],
                "campaign_id": acc["campaign_id"],
                "label": acc.get("label"),
                "status": acc["status"],
                "max_bots_limit": acc["max_bots_limit"],
                "bots_created": acc["bots_created"],
                "prepared_account_id": acc.get("prepared_account_id"),
                "created_at": _iso(acc.get("created_at")),
            }
        )

    return results
