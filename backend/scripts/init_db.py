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


def _sql_files() -> list[Path]:
    files = [_find_sql_path()]
    for name in (
        "migrate_job_logs.sql",
        "migrate_account_prep.sql",
        "migrate_prepared_accounts.sql",
        "migrate_campaign_optional.sql",
        "migrate_bot_promo.sql",
    ):
        for base in (_SCRIPT_DIR.parents[1], _SCRIPT_DIR.parent):
            migrate = base / "database" / name
            if migrate.is_file() and migrate not in files:
                files.append(migrate)
    return files


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
        for sql_path in _sql_files():
            await conn.execute(sql_path.read_text(encoding="utf-8"))
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
