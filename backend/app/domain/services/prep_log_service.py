from typing import Optional

from app.infrastructure.database import repository as db


async def append_log(
    job_id: int,
    message: str,
    *,
    level: str = "info",
    account_id: Optional[int] = None,
    progress_message: Optional[str] = None,
) -> None:
    await db.execute(
        """
        INSERT INTO account_prep_logs (job_id, account_id, level, message)
        VALUES ($1, $2, $3, $4)
        """,
        job_id,
        account_id,
        level,
        message,
    )
    if progress_message:
        await db.execute(
            """
            UPDATE account_prep_jobs
            SET progress_message = $2, updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            progress_message,
        )


async def list_logs(job_id: int, after_id: int = 0, limit: int = 300) -> list[dict]:
    rows = await db.fetch_all(
        """
        SELECT id, job_id, account_id, level, message, created_at
        FROM account_prep_logs
        WHERE job_id = $1 AND id > $2
        ORDER BY id ASC
        LIMIT $3
        """,
        job_id,
        after_id,
        limit,
    )
    return [
        {
            "id": r["id"],
            "job_id": r["job_id"],
            "account_id": r.get("account_id"),
            "level": r["level"],
            "message": r["message"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]
