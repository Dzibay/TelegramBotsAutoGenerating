"""
Worker: подготовка аккаунтов (безопасность).

Запуск: python -m app.workers.prep_worker
"""
import asyncio
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from app.config import Config
from app.core.logging import get_logger, init_logging
from app.domain.services.prep_pipeline import AccountPrepPipeline
from app.domain.services import prep_log_service
from app.infrastructure.cache.redis_client import blocking_pop, close_redis, init_redis
from app.infrastructure.database.pool import close_pool, init_pool

init_logging()
logger = get_logger(__name__)


async def process_prep_job(payload: dict) -> None:
    job_id = int(payload["job_id"])
    pipeline = AccountPrepPipeline(
        job_id,
        new_password=payload.get("new_password"),
        current_password=payload.get("current_password"),
        password_hint=payload.get("password_hint") or "",
    )
    try:
        await pipeline.run()
    except Exception as exc:
        logger.exception("Prep job %s failed: %s", job_id, exc)
        await prep_log_service.append_log(job_id, f"Критическая ошибка: {exc}", level="error")
        from app.infrastructure.database import repository as db

        await db.execute(
            """
            UPDATE account_prep_jobs
            SET status = 'failed', error_message = $2, finished_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            str(exc)[:1000],
        )


async def worker_loop() -> None:
    logger.info("Prep worker слушает %s", Config.REDIS_PREP_QUEUE)
    while True:
        item = await blocking_pop(Config.REDIS_PREP_QUEUE, timeout=5)
        if not item:
            continue
        try:
            payload = json.loads(item[1])
            await process_prep_job(payload)
        except Exception as exc:
            logger.exception("Prep queue error: %s", exc)


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
