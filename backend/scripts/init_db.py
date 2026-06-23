"""Применяет database/init.sql к PostgreSQL (идемпотентно)."""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

# Локально: repo/database/init.sql — Docker: /app/database/init.sql
_SCRIPT_DIR = Path(__file__).resolve().parent


def _find_sql_path() -> Path:
    for base in (_SCRIPT_DIR.parents[1], _SCRIPT_DIR.parent):
        candidate = base / "database" / "init.sql"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("database/init.sql not found")


def _load_env() -> None:
    for env_path in (
        _SCRIPT_DIR.parents[1] / ".env",
        _SCRIPT_DIR.parent / ".env",
        Path("/app/.env"),
    ):
        if env_path.is_file():
            load_dotenv(env_path)


def _migration_files() -> list[Path]:
    """Миграции для уже существующих БД (ALTER, индексы)."""
    names = (
        "migrate_job_logs.sql",
        "migrate_account_prep.sql",
        "migrate_prepared_accounts.sql",
        "migrate_campaign_optional.sql",
        "migrate_bot_promo.sql",
        "migrate_bot_about.sql",
        "migrate_bot_link_mode.sql",
        "migrate_bot_welcome_button.sql",
        "migrate_ai_generations.sql",
        "migrate_campaign_default_texts.sql",
        "migrate_campaign_welcome_button_defaults.sql",
        "migrate_campaign_referral.sql",
        "migrate_creation_job_history.sql",
        "migrate_account_botfather_flood.sql",
        "migrate_job_account_ids.sql",
        "migrate_async_tasks.sql",
        "migrate_account_is_banned.sql",
        "migrate_job_mode_manual_multi.sql",
        "migrate_bot_telegram_sync.sql",
    )
    files: list[Path] = []
    for name in names:
        for base in (_SCRIPT_DIR.parents[1], _SCRIPT_DIR.parent):
            migrate = base / "database" / name
            if migrate.is_file() and migrate not in files:
                files.append(migrate)
    return files


def _sql_files() -> list[Path]:
    return [_find_sql_path(), *_migration_files()]


# Один процесс за раз: api + worker + prep-worker + bot-runner стартуют параллельно
_SCHEMA_ADVISORY_LOCK_KEY = 839204712


async def _execute_sql_file(conn, path: Path) -> None:
    await conn.execute(path.read_text(encoding="utf-8"))


async def apply_schema(
    *,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
) -> None:
    conn = await asyncpg.connect(
        host=host or os.getenv("DB_HOST", "localhost"),
        port=port or int(os.getenv("DB_PORT", "5432")),
        user=user or os.getenv("DB_USER", "postgres"),
        password=password if password is not None else os.getenv("DB_PASSWORD", ""),
        database=database or os.getenv("DB_NAME", "tg_bots"),
    )
    try:
        await conn.execute(f"SELECT pg_advisory_lock({_SCHEMA_ADVISORY_LOCK_KEY})")
        try:
            for sql_path in _sql_files():
                await _execute_sql_file(conn, sql_path)
        finally:
            await conn.execute(f"SELECT pg_advisory_unlock({_SCHEMA_ADVISORY_LOCK_KEY})")
    finally:
        await conn.close()


async def main() -> None:
    _load_env()
    try:
        await apply_schema()
    except Exception as exc:
        print(f"Database init failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print("Database schema applied successfully.")


if __name__ == "__main__":
    asyncio.run(main())
