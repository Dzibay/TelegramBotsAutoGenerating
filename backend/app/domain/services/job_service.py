import json
from typing import Any, Optional

from app.config import Config
from app.constants import ErrorMessages
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.services import campaign_service
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.database import repository as db


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _job_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "status": row["status"],
        "total_accounts": row["total_accounts"],
        "processed_accounts": row["processed_accounts"],
        "total_bots_created": row["total_bots_created"],
        "progress_message": row.get("progress_message"),
        "error_message": row.get("error_message"),
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
        "created_at": _iso(row.get("created_at")),
    }


async def start_creation_job(
    campaign_id: int,
    plans: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    if campaign["accounts_count"] < 1:
        raise ConflictError("Добавьте хотя бы один Telegram-аккаунт из пула подготовленных")

    ready_count = await db.fetch_val(
        """
        SELECT COUNT(*)::int FROM telegram_accounts
        WHERE campaign_id = $1 AND status IN ('ready', 'creating')
          AND tdata_path IS NOT NULL AND tdata_path != ''
        """,
        campaign_id,
    )
    if not ready_count:
        error_accounts = await db.fetch_all(
            """
            SELECT id, status, last_error FROM telegram_accounts
            WHERE campaign_id = $1
            """,
            campaign_id,
        )
        if error_accounts:
            sample = error_accounts[0]
            hint = sample.get("last_error") or sample.get("status")
            raise ConflictError(
                "Нет готовых аккаунтов для массового создания. "
                f"Откройте блок «Аккаунты» и нажмите «Проверить все». "
                f"Пример: аккаунт #{sample['id']} — {hint}"
            )
        raise ConflictError(
            "Нет готовых аккаунтов. Добавьте подготовленные аккаунты и нажмите «Проверить все»."
        )

    if not campaign.get("resource_url"):
        raise ConflictError(
            "Укажите ссылку на сервис в настройках кампании — "
            "она нужна для ссылок в ботах"
        )

    plan_list = plans or []
    if not plan_list and not campaign.get("keywords"):
        raise ConflictError(
            "Добавьте план ботов с ключевыми фразами на вкладке «Массово» "
            "или укажите ключевые слова в настройках кампании."
        )
    if plan_list:
        for p in plan_list:
            kw = (p.get("keyword") or "").strip()
            acc_id = p.get("telegram_account_id")
            if not acc_id or not kw:
                raise ConflictError("В плане каждый бот должен иметь аккаунт и ключевую фразу")

    running = await db.fetch_one(
        """
        SELECT id FROM creation_jobs
        WHERE campaign_id = $1 AND status IN ('queued', 'running')
        LIMIT 1
        """,
        campaign_id,
    )
    if running:
        raise ConflictError("Задача для этой кампании уже выполняется")

    if plan_list:
        account_ids = {int(p["telegram_account_id"]) for p in plan_list}
        total_accounts = len(account_ids)
        progress = f"В очереди: {len(plan_list)} бот(ов) по плану"
    else:
        total_accounts = await db.fetch_val(
            "SELECT COUNT(*)::int FROM telegram_accounts WHERE campaign_id = $1",
            campaign_id,
        )
        progress = "В очереди"

    row = await db.fetch_one(
        """
        INSERT INTO creation_jobs (campaign_id, status, total_accounts, progress_message)
        VALUES ($1, 'queued', $2, $3)
        RETURNING *
        """,
        campaign_id,
        total_accounts or 0,
        progress,
    )

    await db.execute(
        "UPDATE campaigns SET status = 'queued', updated_at = NOW() WHERE id = $1",
        campaign_id,
    )

    redis = get_redis()
    if not redis:
        await db.execute(
            """
            UPDATE creation_jobs SET status = 'failed', error_message = $2, updated_at = NOW()
            WHERE id = $1
            """,
            row["id"],
            "Redis недоступен — worker не получит задачу",
        )
        raise ConflictError("Redis недоступен. Запустите redis или docker compose up redis")
    payload: dict[str, Any] = {"job_id": row["id"], "campaign_id": campaign_id}
    if plan_list:
        payload["plans"] = plan_list
    await redis.lpush(Config.REDIS_JOB_QUEUE, json.dumps(payload))

    return _job_row(row)


async def get_active_job(campaign_id: int) -> dict[str, Any] | None:
    row = await db.fetch_one(
        """
        SELECT * FROM creation_jobs
        WHERE campaign_id = $1
        ORDER BY id DESC
        LIMIT 1
        """,
        campaign_id,
    )
    return _job_row(row) if row else None


async def get_job(job_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError(ErrorMessages.JOB_NOT_FOUND)
    return _job_row(row)
