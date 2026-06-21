"""Фоновое обслуживание: reaper зависших статусов."""
from __future__ import annotations

from app.core.logging import get_logger
from app.infrastructure.database import repository as db

logger = get_logger(__name__)

SYNC_STALE_MINUTES = 10
JOB_STALE_MINUTES = 30


async def reap_stale_telegram_sync() -> int:
    """Сбросить ботов, застрявших в pending/syncing после рестарта API."""
    result = await db.execute(
        """
        UPDATE bots
        SET telegram_sync_status = 'failed',
            botfather_error = COALESCE(
                NULLIF(botfather_error, ''),
                'Синхронизация прервана (таймаут или перезапуск сервера). Повторите «Обновить в Telegram».'
            ),
            updated_at = NOW()
        WHERE telegram_sync_status IN ('pending', 'syncing')
          AND updated_at < NOW() - ($1 * INTERVAL '1 minute')
        """,
        SYNC_STALE_MINUTES,
    )
    count = int(result.split()[-1]) if result else 0
    if count:
        logger.warning("Reaped %s stale telegram_sync bot(s)", count)
    return count


async def reap_stale_creation_jobs() -> int:
    """Пометить зависшие running-задачи как failed и освободить аккаунты."""
    rows = await db.fetch_all(
        """
        SELECT id, campaign_id FROM creation_jobs
        WHERE status = 'running'
          AND updated_at < NOW() - ($1 * INTERVAL '1 minute')
        """,
        JOB_STALE_MINUTES,
    )
    if not rows:
        return 0

    for row in rows:
        job_id = int(row["id"])
        campaign_id = int(row["campaign_id"])
        await db.execute(
            """
            UPDATE creation_jobs
            SET status = 'failed',
                error_message = 'Задача зависла (таймаут worker или перезапуск)',
                finished_at = NOW(),
                progress_message = 'Ошибка: таймаут',
                updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
        )
        await db.execute(
            """
            UPDATE telegram_accounts
            SET status = CASE
                WHEN bots_created >= max_bots_limit THEN 'exhausted'
                ELSE 'ready'
            END,
            updated_at = NOW()
            WHERE campaign_id = $1 AND status = 'creating'
            """,
            campaign_id,
        )
        from app.domain.services import job_service

        await job_service.sync_campaign_status(campaign_id)
        logger.warning("Reaped stale creation_job id=%s campaign=%s", job_id, campaign_id)
    return len(rows)


async def run_maintenance_cycle() -> None:
    await reap_stale_telegram_sync()
    await reap_stale_creation_jobs()
    from app.domain.services.account_session_service import reap_stale_cached_sessions

    await reap_stale_cached_sessions()
