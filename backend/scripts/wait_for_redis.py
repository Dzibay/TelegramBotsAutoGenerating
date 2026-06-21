"""Ожидание готовности Redis перед стартом API/worker."""
import os
import sys
import time
from pathlib import Path

import redis
from dotenv import load_dotenv

_SCRIPT_DIR = Path(__file__).resolve().parent


def _load_env() -> None:
    for env_path in (_SCRIPT_DIR.parents[1] / ".env", _SCRIPT_DIR.parent / ".env"):
        if env_path.is_file():
            load_dotenv(env_path)


def wait_for_redis(
    *,
    max_attempts: int | None = None,
    delay_sec: float | None = None,
) -> None:
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        print("Redis URL not set, skipping wait")
        return

    attempts = max_attempts or int(os.getenv("REDIS_WAIT_MAX_ATTEMPTS", "30"))
    delay = delay_sec or float(os.getenv("REDIS_WAIT_DELAY_SEC", "2"))

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        client = None
        try:
            client = redis.from_url(url, decode_responses=True, socket_connect_timeout=5)
            client.ping()
            print("Redis ready")
            return
        except Exception as exc:
            last_error = exc
            print(
                f"Waiting for Redis ({attempt}/{attempts})…",
                file=sys.stderr,
            )
            time.sleep(delay)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    print(f"Redis not ready: {last_error}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    _load_env()
    wait_for_redis()


if __name__ == "__main__":
    main()
