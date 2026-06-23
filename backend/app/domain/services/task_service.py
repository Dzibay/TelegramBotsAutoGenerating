"""Единый durable-реестр фоновых задач.

PostgreSQL хранит состояние и используется для claim/account gating.
Redis используется только как wakeup-сигнал для worker'ов.
"""
from __future__ import annotations

import json
import socket
from typing import Any

from app.config import Config
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.database import repository as db

logger = get_logger(__name__)

ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")
TASK_TYPE_CREATION = "creation"
TASK_TYPE_BOT_SYNC = "bot_telegram_sync"

_LOG_LEVELS = frozenset({"debug", "info", "warn", "error", "success"})


def _normalize_log_level(level: str) -> str:
    lvl = (level or "info").lower().strip()
    return lvl if lvl in _LOG_LEVELS else "info"


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _task_row(row: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return {}
    account_ids = row.get("account_ids") or []
    payload = _json(row.get("payload")) or {}
    result = _json(row.get("result"))
    return {
        "id": row["id"],
        "task_type": row["task_type"],
        "status": row["status"],
        "priority": row.get("priority", 100),
        "campaign_id": row.get("campaign_id"),
        "campaign_title": row.get("campaign_title"),
        "bot_id": row.get("bot_id"),
        "bot_username": row.get("bot_username"),
        "bot_display_name": row.get("bot_display_name"),
        "creation_job_id": row.get("creation_job_id"),
        "account_ids": [int(x) for x in account_ids if x is not None],
        "dedupe_key": row.get("dedupe_key"),
        "payload": payload,
        "result": result,
        "progress_message": row.get("progress_message"),
        "error_message": row.get("error_message"),
        "claimed_by": row.get("claimed_by"),
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
        "heartbeat_at": _iso(row.get("heartbeat_at")),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


def _log_row(row: dict[str, Any]) -> dict[str, Any]:
    ctx = _json(row.get("context"))
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "level": row["level"],
        "message": row["message"],
        "context": ctx,
        "created_at": _iso(row.get("created_at")),
    }


async def signal_task(task_id: int) -> None:
    """Разбудить worker. Если Redis временно недоступен, задача остаётся queued в БД."""
    redis = get_redis()
    if not redis:
        logger.warning("Redis unavailable; task %s remains queued in DB", task_id)
        return
    payload = json.dumps({"task_id": int(task_id)}, ensure_ascii=False)
    await redis.lpush(Config.REDIS_TASK_QUEUE, payload)


async def enqueue_task(
    *,
    task_type: str,
    payload: dict[str, Any],
    campaign_id: int | None = None,
    bot_id: int | None = None,
    creation_job_id: int | None = None,
    account_ids: list[int] | set[int] | None = None,
    dedupe_key: str | None = None,
    priority: int = 100,
    progress_message: str | None = None,
    conn=None,
    signal: bool = True,
) -> dict[str, Any]:
    accounts = sorted({int(x) for x in (account_ids or []) if x is not None})

    if dedupe_key:
        select_sql = """
            SELECT t.*, c.title AS campaign_title, b.username AS bot_username,
                   b.display_name AS bot_display_name
            FROM async_tasks t
            LEFT JOIN campaigns c ON c.id = t.campaign_id
            LEFT JOIN bots b ON b.id = t.bot_id
            WHERE t.dedupe_key = $1 AND t.status IN ('queued', 'running')
            ORDER BY t.id DESC
            LIMIT 1
        """
        existing = (
            await db.tx_fetch_one(conn, select_sql, dedupe_key)
            if conn is not None
            else await db.fetch_one(select_sql, dedupe_key)
        )
        if existing:
            if signal:
                await signal_task(int(existing["id"]))
            return _task_row(existing)

    insert_sql = """
        INSERT INTO async_tasks (
            task_type, status, priority, campaign_id, bot_id, creation_job_id,
            account_ids, dedupe_key, payload, progress_message
        )
        VALUES ($1, 'queued', $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
        RETURNING *
    """
    args = (
        task_type,
        int(priority),
        campaign_id,
        bot_id,
        creation_job_id,
        accounts,
        dedupe_key,
        json.dumps(payload, ensure_ascii=False),
        progress_message,
    )
    row = (
        await db.tx_fetch_one(conn, insert_sql, *args)
        if conn is not None
        else await db.fetch_one(insert_sql, *args)
    )
    if signal:
        await signal_task(int(row["id"]))
    return _task_row(row)


async def append_log(
    task_id: int,
    message: str,
    *,
    level: str = "info",
    context: dict[str, Any] | None = None,
    progress_message: str | None = None,
) -> dict[str, Any]:
    level = _normalize_log_level(level)
    row = await db.fetch_one(
        """
        INSERT INTO task_logs (task_id, level, message, context)
        VALUES ($1, $2, $3, $4::jsonb)
        RETURNING id, task_id, level, message, context, created_at
        """,
        task_id,
        level,
        message,
        json.dumps(context, ensure_ascii=False) if context else None,
    )
    if progress_message is not None:
        await db.execute(
            """
            UPDATE async_tasks
            SET progress_message = $2, updated_at = NOW(), heartbeat_at = NOW()
            WHERE id = $1
            """,
            task_id,
            progress_message,
        )
    return _log_row(row)


async def list_logs(
    task_id: int,
    after_id: int = 0,
    limit: int = 200,
    *,
    min_level: str = "info",
) -> list[dict[str, Any]]:
    level_clause = "" if min_level == "debug" else "AND level != 'debug'"
    rows = await db.fetch_all(
        f"""
        SELECT id, task_id, level, message, context, created_at
        FROM task_logs
        WHERE task_id = $1 AND id > $2 {level_clause}
        ORDER BY id ASC
        LIMIT $3
        """,
        task_id,
        after_id,
        max(1, min(limit, 500)),
    )
    return [_log_row(r) for r in rows]


async def get_task(task_id: int) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT t.*, c.title AS campaign_title, b.username AS bot_username,
               b.display_name AS bot_display_name
        FROM async_tasks t
        LEFT JOIN campaigns c ON c.id = t.campaign_id
        LEFT JOIN bots b ON b.id = t.bot_id
        WHERE t.id = $1
        """,
        task_id,
    )
    if not row:
        raise NotFoundError("Задача не найдена")
    return _task_row(row)


async def list_tasks(
    *,
    active_only: bool = False,
    campaign_id: int | None = None,
    bot_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses = []
    args: list[Any] = []
    if active_only:
        clauses.append("t.status IN ('queued', 'running')")
    if campaign_id is not None:
        args.append(campaign_id)
        clauses.append(f"t.campaign_id = ${len(args)}")
    if bot_id is not None:
        args.append(bot_id)
        clauses.append(f"t.bot_id = ${len(args)}")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    args.extend([max(1, min(limit, 200)), max(0, offset)])
    rows = await db.fetch_all(
        f"""
        SELECT t.*, c.title AS campaign_title, b.username AS bot_username,
               b.display_name AS bot_display_name
        FROM async_tasks t
        LEFT JOIN campaigns c ON c.id = t.campaign_id
        LEFT JOIN bots b ON b.id = t.bot_id
        {where}
        ORDER BY
            CASE t.status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
            t.priority ASC,
            t.id DESC
        LIMIT ${len(args) - 1} OFFSET ${len(args)}
        """,
        *args,
    )
    return [_task_row(r) for r in rows]


async def active_count() -> int:
    return int(
        await db.fetch_val(
            "SELECT COUNT(*)::int FROM async_tasks WHERE status IN ('queued', 'running')"
        )
        or 0
    )


async def signal_queued_tasks(*, limit: int = 15) -> None:
    """Разбудить worker для задач в очереди (после завершения блокирующей задачи)."""
    rows = await db.fetch_all(
        """
        SELECT id FROM async_tasks
        WHERE status = 'queued'
        ORDER BY priority ASC, id ASC
        LIMIT $1
        """,
        max(1, min(limit, 50)),
    )
    for row in rows:
        await signal_task(int(row["id"]))


async def _effective_account_ids(conn, task: dict[str, Any]) -> list[int]:
    """account_ids из async_tasks или, если пусто, из связанного creation_jobs."""
    ids = {int(x) for x in (task.get("account_ids") or []) if x is not None}
    if ids:
        return sorted(ids)
    job_id = task.get("creation_job_id")
    if not job_id:
        return []
    row = await conn.fetchrow(
        """
        SELECT account_ids, telegram_account_id
        FROM creation_jobs
        WHERE id = $1
        """,
        int(job_id),
    )
    if not row:
        return []
    for x in row["account_ids"] or []:
        if x is not None:
            ids.add(int(x))
    if row.get("telegram_account_id"):
        ids.add(int(row["telegram_account_id"]))
    return sorted(ids)


async def _other_task_account_ids(conn, other: dict[str, Any]) -> list[int]:
    ids = {int(x) for x in (other.get("account_ids") or []) if x is not None}
    if ids:
        return sorted(ids)
    job_id = other.get("creation_job_id")
    if not job_id:
        return []
    row = await conn.fetchrow(
        """
        SELECT account_ids, telegram_account_id
        FROM creation_jobs
        WHERE id = $1
        """,
        int(job_id),
    )
    if not row:
        return []
    for x in row["account_ids"] or []:
        if x is not None:
            ids.add(int(x))
    if row.get("telegram_account_id"):
        ids.add(int(row["telegram_account_id"]))
    return sorted(ids)


async def _has_running_conflict(conn, task: dict[str, Any]) -> bool:
    account_ids = await _effective_account_ids(conn, task)
    payload = _json(task.get("payload")) or {}
    exclusive = bool(payload.get("exclusive_campaign"))
    campaign_id = task.get("campaign_id")

    others = await conn.fetch(
        """
        SELECT * FROM async_tasks
        WHERE status = 'running' AND id != $1
        """,
        int(task["id"]),
    )
    for other in others:
        other_payload = _json(other.get("payload")) or {}
        other_exclusive = bool(other_payload.get("exclusive_campaign"))
        if (
            campaign_id is not None
            and other.get("campaign_id") == campaign_id
            and (other_exclusive or exclusive)
        ):
            return True
        other_accounts = await _other_task_account_ids(conn, other)
        if account_ids and other_accounts and set(account_ids) & set(other_accounts):
            return True
    return False


async def _lock_task_scope(conn, task: dict[str, Any]) -> None:
    account_ids = await _effective_account_ids(conn, task)
    for account_id in account_ids:
        await conn.execute("SELECT pg_advisory_xact_lock($1)", 1_900_000_000 + account_id)
    payload = _json(task.get("payload")) or {}
    if payload.get("exclusive_campaign") and task.get("campaign_id"):
        await conn.execute("SELECT pg_advisory_xact_lock($1)", 1_800_000_000 + int(task["campaign_id"]))


async def claim_task(task_id: int | None = None, *, worker_id: str | None = None) -> dict[str, Any] | None:
    """Claim queued task if its accounts are free. Returns None when it should keep waiting."""
    worker = worker_id or socket.gethostname()
    async with db.transaction() as conn:
        if task_id is not None:
            rows = await db.tx_fetch_all(
                conn,
                """
                SELECT * FROM async_tasks
                WHERE id = $1 AND status = 'queued'
                FOR UPDATE SKIP LOCKED
                """,
                task_id,
            )
        else:
            rows = await db.tx_fetch_all(
                conn,
                """
                SELECT * FROM async_tasks
                WHERE status = 'queued'
                ORDER BY priority ASC, id ASC
                LIMIT 10
                FOR UPDATE SKIP LOCKED
                """,
            )

        for row in rows:
            resolved_accounts = await _effective_account_ids(conn, row)
            if resolved_accounts and not row.get("account_ids"):
                await conn.execute(
                    """
                    UPDATE async_tasks
                    SET account_ids = $2, updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                    resolved_accounts,
                )
                row = {**row, "account_ids": resolved_accounts}
            await _lock_task_scope(conn, row)
            if await _has_running_conflict(conn, row):
                await db.tx_execute(
                    conn,
                    """
                    UPDATE async_tasks
                    SET progress_message = COALESCE(progress_message, 'Ожидает свободный аккаунт'),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                )
                continue

            claimed = await db.tx_fetch_one(
                conn,
                """
                UPDATE async_tasks
                SET status = 'running',
                    claimed_by = $2,
                    started_at = COALESCE(started_at, NOW()),
                    heartbeat_at = NOW(),
                    updated_at = NOW(),
                    progress_message = COALESCE(progress_message, 'Старт')
                WHERE id = $1 AND status = 'queued'
                RETURNING *
                """,
                row["id"],
                worker,
            )
            if claimed:
                return _task_row(claimed)
    return None


async def heartbeat(task_id: int, *, progress_message: str | None = None) -> None:
    await db.execute(
        """
        UPDATE async_tasks
        SET heartbeat_at = NOW(),
            updated_at = NOW(),
            progress_message = COALESCE($2, progress_message)
        WHERE id = $1 AND status = 'running'
        """,
        task_id,
        progress_message,
    )


async def complete_task(
    task_id: int,
    *,
    result: dict[str, Any] | None = None,
    progress_message: str = "Готово",
) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        UPDATE async_tasks
        SET status = 'completed',
            result = COALESCE($2::jsonb, result),
            progress_message = $3,
            error_message = NULL,
            finished_at = NOW(),
            heartbeat_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        task_id,
        json.dumps(result, ensure_ascii=False) if result is not None else None,
        progress_message,
    )
    await signal_queued_tasks()
    return _task_row(row)


async def fail_task(task_id: int, error: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        UPDATE async_tasks
        SET status = 'failed',
            error_message = $2,
            result = COALESCE($3::jsonb, result),
            progress_message = 'Ошибка',
            finished_at = NOW(),
            heartbeat_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        task_id,
        error[:1000],
        json.dumps(context, ensure_ascii=False) if context else None,
    )
    await append_log(task_id, f"Ошибка: {error}", level="error")
    await signal_queued_tasks()
    return _task_row(row)


async def cancel_task(task_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM async_tasks WHERE id = $1", task_id)
    if not row:
        raise NotFoundError("Задача не найдена")
    if row["status"] not in ACTIVE_STATUSES:
        raise ConflictError("Задача уже завершена и не может быть отменена")

    updated = await db.fetch_one(
        """
        UPDATE async_tasks
        SET status = 'cancelled',
            progress_message = 'Отменено пользователем',
            finished_at = NOW(),
            heartbeat_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        task_id,
    )
    creation_job_id = row.get("creation_job_id")
    if creation_job_id:
        from app.domain.services import job_service

        try:
            await job_service.cancel_job(int(creation_job_id))
        except ConflictError:
            pass
    if row.get("task_type") == TASK_TYPE_BOT_SYNC and row.get("bot_id"):
        await db.execute(
            """
            UPDATE bots
            SET telegram_sync_status = 'failed',
                botfather_error = 'Синхронизация отменена пользователем',
                updated_at = NOW()
            WHERE id = $1 AND telegram_sync_status IN ('pending', 'syncing')
            """,
            row["bot_id"],
        )
    await append_log(task_id, "Задача отменена пользователем", level="warn")
    await signal_queued_tasks()
    return _task_row(updated)


async def retry_task(task_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM async_tasks WHERE id = $1", task_id)
    if not row:
        raise NotFoundError("Задача не найдена")
    if row["status"] not in TERMINAL_STATUSES:
        raise ConflictError("Задача ещё активна")
    if row["status"] == "completed":
        raise BadRequestError("Успешно завершённую задачу нельзя повторить")

    updated = await db.fetch_one(
        """
        UPDATE async_tasks
        SET status = 'queued',
            progress_message = 'В очереди на повтор',
            error_message = NULL,
            claimed_by = NULL,
            started_at = NULL,
            finished_at = NULL,
            heartbeat_at = NULL,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        task_id,
    )
    if row.get("creation_job_id"):
        await db.execute(
            """
            UPDATE creation_jobs
            SET status = 'queued',
                progress_message = 'В очереди на повтор',
                error_message = NULL,
                started_at = NULL,
                finished_at = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            row["creation_job_id"],
        )
    if row.get("task_type") == TASK_TYPE_BOT_SYNC and row.get("bot_id"):
        await db.execute(
            """
            UPDATE bots
            SET telegram_sync_status = 'pending',
                botfather_error = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            row["bot_id"],
        )
    await append_log(task_id, "Задача поставлена на повтор", level="info")
    await signal_task(task_id)
    return _task_row(updated)
