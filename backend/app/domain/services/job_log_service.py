"""Логи выполнения creation_jobs."""
import json
from typing import Any, Optional

from app.infrastructure.database import repository as db


async def append_log(
    job_id: int,
    message: str,
    *,
    level: str = "info",
    context: Optional[dict[str, Any]] = None,
    progress_message: Optional[str] = None,
) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        INSERT INTO job_logs (job_id, level, message, context)
        VALUES ($1, $2, $3, $4::jsonb)
        RETURNING id, job_id, level, message, context, created_at
        """,
        job_id,
        level,
        message,
        json.dumps(context) if context else None,
    )

    if progress_message:
        await db.execute(
            """
            UPDATE creation_jobs
            SET progress_message = $2, updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            progress_message,
        )

    task_id = await db.fetch_val(
        "SELECT task_id FROM creation_jobs WHERE id = $1",
        job_id,
    )
    if task_id:
        from app.domain.services import task_service

        await task_service.append_log(
            int(task_id),
            message,
            level=level,
            context=context,
            progress_message=progress_message,
        )

    return _log_row(row)


async def list_logs(
    job_id: int,
    after_id: int = 0,
    limit: int = 200,
    *,
    min_level: str = "info",
) -> list[dict[str, Any]]:
    if min_level == "debug":
        level_clause = ""
        params: list[Any] = [job_id, after_id, limit]
    else:
        level_clause = "AND level != 'debug'"
        params = [job_id, after_id, limit]

    rows = await db.fetch_all(
        f"""
        SELECT id, job_id, level, message, context, created_at
        FROM job_logs
        WHERE job_id = $1 AND id > $2 {level_clause}
        ORDER BY id ASC
        LIMIT $3
        """,
        *params,
    )
    return [_log_row(r) for r in rows]


def _log_row(row: dict[str, Any]) -> dict[str, Any]:
    ctx = row.get("context")
    if isinstance(ctx, str):
        try:
            ctx = json.loads(ctx)
        except json.JSONDecodeError:
            pass
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "level": row["level"],
        "message": row["message"],
        "context": ctx,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }
