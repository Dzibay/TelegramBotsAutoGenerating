"""
Worker: обработка очереди creation_jobs и bot_sync (Redis).

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
from app.domain.services import bot_service, job_log_service, job_service, maintenance_service
from app.infrastructure.cache.redis_client import blocking_pop_any, close_redis, get_redis, init_redis
from app.infrastructure.database.pool import close_pool, init_pool

init_logging()
logger = get_logger(__name__)

_semaphore = asyncio.Semaphore(Config.WORKER_CONCURRENCY)
_active_tasks: set[asyncio.Task] = set()
_shutdown = asyncio.Event()
_DEFER_SEC = 8
_MAINT_INTERVAL_SEC = 120


async def _maintenance_loop() -> None:
    while not _shutdown.is_set():
        try:
            await maintenance_service.run_maintenance_cycle()
        except Exception as exc:
            logger.exception("Maintenance cycle failed: %s", exc)
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=_MAINT_INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass


def _account_ids_from_payload(data: dict) -> tuple[set[int], bool]:
    mode = data.get("mode")
    if mode == "single":
        spec = data.get("spec") or {}
        return {int(spec["telegram_account_id"])}, False
    if mode == "batch_create":
        specs = data.get("specs") or []
        return {int(s["telegram_account_id"]) for s in specs}, False
    if mode in ("manual", "manual_multi"):
        plans = data.get("manual_plans") or []
        return {int(p["telegram_account_id"]) for p in plans if p.get("telegram_account_id")}, False
    return set(), True


async def _defer_job_payload(data: dict) -> None:
    job_id = data.get("job_id")
    if job_id:
        await job_log_service.append_log(
            int(job_id),
            f"Аккаунты заняты — повтор через {_DEFER_SEC} сек.",
            level="warn",
        )
    await asyncio.sleep(_DEFER_SEC)
    redis = get_redis()
    if redis:
        await redis.lpush(Config.REDIS_JOB_QUEUE, json.dumps(data, ensure_ascii=False))


async def process_botfather_sync(payload: dict) -> None:
    bot_id = int(payload["bot_id"])
    await bot_service.run_botfather_sync(
        bot_id,
        generate_avatar=bool(payload.get("generate_avatar")),
        upload_avatar=bool(payload.get("upload_avatar")),
    )


async def process_job(
    job_id: int,
    campaign_id: int,
    plans: list | None = None,
    manual_plans: list | None = None,
    manual_multi: bool = False,
    *,
    single_spec: dict | None = None,
    avatar_path: str | None = None,
    batch_specs: list | None = None,
) -> None:
    from app.infrastructure.database import repository as db

    async with _semaphore:
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
                manual_multi=manual_multi,
                batch_specs=batch_specs,
            )
            if single_spec is not None:
                await pipeline.run_single(single_spec, avatar_path=avatar_path)
            else:
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
            await job_service.sync_campaign_status(campaign_id)


async def _run_job_payload(data: dict) -> None:
    job_id = int(data["job_id"])
    campaign_id = int(data["campaign_id"])
    mode = data.get("mode")
    if mode == "single":
        await process_job(
            job_id,
            campaign_id,
            single_spec=data.get("spec") or {},
            avatar_path=data.get("avatar_path"),
        )
        return
    if mode == "batch_create":
        await process_job(
            job_id,
            campaign_id,
            batch_specs=data.get("specs") or [],
        )
        return
    manual_plans = data.get("manual_plans") if mode in ("manual", "manual_multi") else None
    plans = None if manual_plans else data.get("plans")
    manual_multi = mode == "manual_multi"
    await process_job(
        job_id,
        campaign_id,
        plans=plans,
        manual_plans=manual_plans,
        manual_multi=manual_multi,
    )


async def _dispatch_creation_job(data: dict) -> None:
    job_id = int(data["job_id"])
    campaign_id = int(data["campaign_id"])
    account_ids, is_auto = _account_ids_from_payload(data)
    available = await job_service.verify_job_accounts_available(
        job_id,
        campaign_id,
        account_ids,
        is_auto=is_auto,
    )
    if not available:
        await _defer_job_payload(data)
        return

    task = asyncio.create_task(_run_job_payload(data))
    _active_tasks.add(task)

    def _on_done(t: asyncio.Task, jid=job_id, cid=campaign_id) -> None:
        _active_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is None:
            return
        logger.exception("Ошибка обработки задачи %s: %s", jid, exc)

    task.add_done_callback(_on_done)


async def worker_loop() -> None:
    queues = [Config.REDIS_JOB_QUEUE, Config.REDIS_BOT_SYNC_QUEUE]
    logger.info(
        "Worker слушает очереди %s (concurrency=%s)",
        ", ".join(queues),
        Config.WORKER_CONCURRENCY,
    )
    while not _shutdown.is_set():
        _active_tasks.difference_update({t for t in _active_tasks if t.done()})

        item = await blocking_pop_any(queues, timeout=2)
        if not item:
            continue
        queue_name, payload = item
        job_id = campaign_id = None
        try:
            data = json.loads(payload)
            if queue_name == Config.REDIS_BOT_SYNC_QUEUE or data.get("type") == "botfather_sync":
                await process_botfather_sync(data)
                continue

            job_id = int(data["job_id"])
            campaign_id = int(data["campaign_id"])
            await _dispatch_creation_job(data)
        except Exception as exc:
            logger.exception("Ошибка постановки задачи: %s", exc)
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
                await job_service.sync_campaign_status(campaign_id)


async def main() -> None:
    Config.validate()
    await init_pool()
    await init_redis(Config.REDIS_URL)
    maint_task = asyncio.create_task(_maintenance_loop())
    try:
        await worker_loop()
    finally:
        _shutdown.set()
        maint_task.cancel()
        try:
            await maint_task
        except asyncio.CancelledError:
            pass
        if _active_tasks:
            logger.info("Ожидание %s активных задач…", len(_active_tasks))
            await asyncio.gather(*_active_tasks, return_exceptions=True)
        await close_pool()
        await close_redis()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
