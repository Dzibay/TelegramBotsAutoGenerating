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


async def start_creation_job(campaign_id: int) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    if campaign["accounts_count"] < 1:
        raise ConflictError("Добавьте хотя бы один Telegram-аккаунт (tdata)")

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

    total_accounts = await db.fetch_val(
        "SELECT COUNT(*)::int FROM telegram_accounts WHERE campaign_id = $1",
        campaign_id,
    )

    row = await db.fetch_one(
        """
        INSERT INTO creation_jobs (campaign_id, status, total_accounts, progress_message)
        VALUES ($1, 'queued', $2, 'В очереди')
        RETURNING *
        """,
        campaign_id,
        total_accounts or 0,
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
    await redis.lpush(Config.REDIS_JOB_QUEUE, json.dumps({"job_id": row["id"], "campaign_id": campaign_id}))

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
