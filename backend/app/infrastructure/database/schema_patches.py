"""Идемпотентные патчи схемы при старте приложения."""
from app.core.logging import get_logger
from app.infrastructure.database import repository as db

logger = get_logger(__name__)

_SCHEMA_PATCH_LOCK_KEY = 839204713

_JOB_MODE_CHECK = """
    CHECK (job_mode IS NULL OR job_mode IN ('manual', 'manual_multi', 'planned', 'auto'))
"""


async def ensure_creation_jobs_job_mode_check() -> None:
    """Разрешает job_mode = manual_multi (мультиаккаунтное создание)."""
    existing = await db.fetch_val(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'creation_jobs'::regclass
          AND conname = 'creation_jobs_job_mode_check'
        """
    )
    if existing and "manual_multi" in str(existing):
        return

    await db.execute(
        "ALTER TABLE creation_jobs DROP CONSTRAINT IF EXISTS creation_jobs_job_mode_check"
    )
    await db.execute(
        f"""
        ALTER TABLE creation_jobs
        ADD CONSTRAINT creation_jobs_job_mode_check
        {_JOB_MODE_CHECK}
        """
    )
    logger.info("Applied creation_jobs.job_mode constraint (manual_multi enabled)")


async def apply_startup_schema_patches() -> None:
    await db.execute(f"SELECT pg_advisory_lock({_SCHEMA_PATCH_LOCK_KEY})")
    try:
        await ensure_creation_jobs_job_mode_check()
    finally:
        await db.execute(f"SELECT pg_advisory_unlock({_SCHEMA_PATCH_LOCK_KEY})")
