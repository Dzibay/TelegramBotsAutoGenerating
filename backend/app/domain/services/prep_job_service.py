import json
from typing import Any, Optional

from app.config import Config
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.services import prep_account_service, prep_log_service
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.database import repository as db


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _job_row(row: dict) -> dict[str, Any]:
    opts = row.get("options") or {}
    if isinstance(opts, str):
        opts = json.loads(opts)
    return {
        "id": row["id"],
        "status": row["status"],
        "options": opts,
        "total_accounts": row["total_accounts"],
        "processed_accounts": row["processed_accounts"],
        "succeeded_accounts": row["succeeded_accounts"],
        "progress_message": row.get("progress_message"),
        "error_message": row.get("error_message"),
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
        "created_at": _iso(row.get("created_at")),
    }


async def create_prep_job(
    options: dict[str, Any],
    archive_paths: list[tuple[Any, str | None]],
    *,
    new_password: str | None = None,
    current_password: str | None = None,
    password_hint: str = "",
    auto_start: bool = True,
) -> dict[str, Any]:
    if not archive_paths:
        raise ConflictError("Загрузите хотя бы один ZIP с tdata")

    if options.get("change_password") and not new_password:
        raise ConflictError("Укажите новый облачный пароль для смены")

    row = await db.fetch_one(
        """
        INSERT INTO account_prep_jobs (status, options, total_accounts, progress_message)
        VALUES ('queued', $1::jsonb, $2, 'Ожидает запуска')
        RETURNING *
        """,
        json.dumps(options),
        len(archive_paths),
    )
    job_id = row["id"]

    accounts = await prep_account_service.save_tdata_archives(job_id, archive_paths)
    await prep_log_service.append_log(
        job_id,
        f"Загружено аккаунтов: {len(accounts)}",
        progress_message="Готово к запуску",
    )

    job = _job_row(row)
    job["accounts"] = accounts

    if auto_start:
        job = await start_prep_job(
            job_id,
            new_password=new_password,
            current_password=current_password,
            password_hint=password_hint,
        )
        job["accounts"] = accounts

    return job


async def start_prep_job(
    job_id: int,
    *,
    new_password: str | None = None,
    current_password: str | None = None,
    password_hint: str = "",
) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM account_prep_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError("Задача подготовки не найдена")

    if row["status"] == "running":
        raise ConflictError("Задача уже выполняется")

    redis = get_redis()
    if not redis:
        raise ConflictError("Redis недоступен")

    payload = {
        "job_id": job_id,
        "new_password": new_password,
        "current_password": current_password,
        "password_hint": password_hint or "",
    }
    await redis.lpush(Config.REDIS_PREP_QUEUE, json.dumps(payload))

    await db.execute(
        """
        UPDATE account_prep_jobs
        SET status = 'queued', progress_message = 'В очереди', updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
    )
    await prep_log_service.append_log(job_id, "Задача поставлена в очередь")

    updated = await db.fetch_one("SELECT * FROM account_prep_jobs WHERE id = $1", job_id)
    return _job_row(updated)


async def get_prep_job(job_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM account_prep_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError("Задача подготовки не найдена")
    return _job_row(row)


async def list_prep_jobs() -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        "SELECT * FROM account_prep_jobs ORDER BY created_at DESC LIMIT 50"
    )
    return [_job_row(r) for r in rows]


async def list_prep_accounts(job_id: int) -> list[dict]:
    rows = await db.fetch_all(
        """
        SELECT id, job_id, label, phone, username, status, steps_done, last_error, created_at
        FROM account_prep_accounts
        WHERE job_id = $1
        ORDER BY id
        """,
        job_id,
    )
    result = []
    for r in rows:
        steps = r.get("steps_done") or []
        if isinstance(steps, str):
            steps = json.loads(steps)
        result.append(
            {
                "id": r["id"],
                "job_id": r["job_id"],
                "label": r.get("label"),
                "phone": r.get("phone"),
                "username": r.get("username"),
                "status": r["status"],
                "steps_done": steps,
                "last_error": r.get("last_error"),
                "created_at": _iso(r.get("created_at")),
            }
        )
    return result
