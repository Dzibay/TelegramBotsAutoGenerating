"""Фоновое обслуживание: reaper зависших статусов."""
from __future__ import annotations

from app.core.logging import get_logger
from app.infrastructure.database import repository as db

logger = get_logger(__name__)

SYNC_STALE_MINUTES = 10
JOB_STALE_MINUTES = 30
TASK_STALE_MINUTES = 30


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
          AND task_id IS NULL
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


async def reap_stale_async_tasks() -> int:
    """Вернуть зависшие running-задачи в очередь (не трогать уже завершённые jobs)."""
    from app.domain.services import task_service

    rows = await db.fetch_all(
        """
        SELECT id FROM async_tasks
        WHERE status = 'running'
          AND COALESCE(heartbeat_at, updated_at) < NOW() - ($1 * INTERVAL '1 minute')
        """,
        TASK_STALE_MINUTES,
    )
    if not rows:
        return 0

    requeued = 0
    for row in rows:
        task_id = int(row["id"])
        job = await db.fetch_one(
            "SELECT status FROM creation_jobs WHERE task_id = $1",
            task_id,
        )
        if job and job["status"] in ("completed", "failed", "cancelled"):
            await db.execute(
                """
                UPDATE async_tasks
                SET status = $2,
                    progress_message = 'Синхронизировано с задачей создания',
                    finished_at = COALESCE(finished_at, NOW()),
                    claimed_by = NULL,
                    updated_at = NOW()
                WHERE id = $1
                """,
                task_id,
                job["status"],
            )
            continue

        await db.execute(
            """
            UPDATE async_tasks
            SET status = 'queued',
                claimed_by = NULL,
                progress_message = 'Возвращено в очередь после перезапуска worker',
                heartbeat_at = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
        )
        await db.execute(
            """
            UPDATE creation_jobs
            SET status = 'queued',
                progress_message = 'Возвращено в очередь после перезапуска worker',
                started_at = NULL,
                finished_at = NULL,
                updated_at = NOW()
            WHERE task_id = $1 AND status = 'running'
            """,
            task_id,
        )
        await task_service.signal_task(task_id)
        requeued += 1

    if requeued:
        logger.warning("Requeued %s stale async task(s)", requeued)
    return requeued


async def run_maintenance_cycle() -> None:
    await reap_stale_telegram_sync()
    await reap_stale_creation_jobs()
    await reap_stale_async_tasks()
    from app.domain.services.account_session_service import reap_stale_cached_sessions

    await reap_stale_cached_sessions()
