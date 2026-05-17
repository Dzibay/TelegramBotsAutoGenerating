"""Ожидание готовности PostgreSQL перед init_db."""
import asyncio
import os
import sys
import time

import asyncpg
from dotenv import load_dotenv
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent


def _load_env() -> None:
    for env_path in (_SCRIPT_DIR.parents[1] / ".env", _SCRIPT_DIR.parent / ".env"):
        if env_path.is_file():
            load_dotenv(env_path)


async def wait_for_postgres(
    *,
    max_attempts: int | None = None,
    delay_sec: float | None = None,
) -> None:
    attempts = max_attempts or int(os.getenv("DB_WAIT_MAX_ATTEMPTS", "30"))
    delay = delay_sec or float(os.getenv("DB_WAIT_DELAY_SEC", "2"))

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "tg_bots")

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            conn = await asyncpg.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                timeout=5,
            )
            await conn.close()
            print(f"PostgreSQL ready ({host}:{port}/{database})")
            return
        except Exception as exc:
            last_error = exc
            print(
                f"Waiting for PostgreSQL ({attempt}/{attempts}) at {host}:{port}…",
                file=sys.stderr,
            )
            await asyncio.sleep(delay)

    print(f"PostgreSQL not ready: {last_error}", file=sys.stderr)
    sys.exit(1)


async def main() -> None:
    _load_env()
    await wait_for_postgres()


if __name__ == "__main__":
    asyncio.run(main())
