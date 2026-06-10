"""
Worker: обработка очереди creation_jobs (Redis).

Запуск: python -m app.workers.creation_worker
"""
import asyncio
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from app.config import Config
from app.core.logging import get_logger, init_logging
from app.domain.services.creation_pipeline import CreationPipeline
from app.domain.services import job_log_service
from app.infrastructure.cache.redis_client import close_redis, get_redis, init_redis
from app.infrastructure.database.pool import close_pool, init_pool

init_logging()
logger = get_logger(__name__)


async def process_job(
    job_id: int,
    campaign_id: int,
    plans: list | None = None,
    manual_plans: list | None = None,
) -> None:
    from app.infrastructure.database import repository as db

    existing = await db.fetch_one(
        "SELECT status FROM creation_jobs WHERE id = $1",
        job_id,
    )
    if not existing:
        logger.warning("Job %s not found in DB", job_id)
        return
    if existing["status"] == "cancelled":
        await job_log_service.append_log(
            job_id,
            "Задача была отменена до старта worker",
            level="warn",
        )
        return

    await db.execute(
        """
        UPDATE creation_jobs
        SET status = 'running', started_at = NOW(), progress_message = 'Старт', updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
    )
    await db.execute(
        "UPDATE campaigns SET status = 'running', updated_at = NOW() WHERE id = $1",
        campaign_id,
    )
    await job_log_service.append_log(job_id, "Задача запущена", progress_message="Старт")

    try:
        pipeline = CreationPipeline(
            job_id,
            campaign_id,
            plans=plans,
            manual_plans=manual_plans,
        )
        await pipeline.run()
    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        await job_log_service.append_log(job_id, f"Критическая ошибка: {exc}", level="error")
        await db.execute(
            """
            UPDATE creation_jobs
            SET status = 'failed',
                error_message = $2,
                finished_at = NOW(),
                progress_message = 'Ошибка',
                updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            str(exc)[:1000],
        )
        await db.execute(
            "UPDATE campaigns SET status = 'failed', updated_at = NOW() WHERE id = $1",
            campaign_id,
        )


async def worker_loop() -> None:
    redis = get_redis()
    if not redis:
        logger.error("Redis не настроен — worker не может работать")
        return

    logger.info("Worker слушает очередь %s", Config.REDIS_JOB_QUEUE)
    while True:
        item = await redis.brpop(Config.REDIS_JOB_QUEUE, timeout=5)
        if not item:
            continue
        _, payload = item
        job_id = campaign_id = None
        try:
            data = json.loads(payload)
            job_id = int(data["job_id"])
            campaign_id = int(data["campaign_id"])
            manual_plans = data.get("manual_plans") if data.get("mode") == "manual" else None
            plans = None if manual_plans else data.get("plans")
            await process_job(
                job_id,
                campaign_id,
                plans=plans,
                manual_plans=manual_plans,
            )
        except Exception as exc:
            logger.exception("Ошибка обработки задачи: %s", exc)
            if job_id and campaign_id:
                from app.infrastructure.database import repository as db

                await job_log_service.append_log(
                    job_id, f"Сбой worker: {exc}", level="error"
                )
                await db.execute(
                    """
                    UPDATE creation_jobs
                    SET status = 'failed', error_message = $2, finished_at = NOW(), updated_at = NOW()
                    WHERE id = $1 AND status = 'running'
                    """,
                    job_id,
                    str(exc)[:1000],
                )


async def main() -> None:
    Config.validate()
    await init_pool()
    await init_redis(Config.REDIS_URL)
    try:
        await worker_loop()
    finally:
        await close_pool()
        await close_redis()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
