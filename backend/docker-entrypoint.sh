#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL…"
python scripts/wait_for_postgres.py

if [ "${SKIP_DB_INIT:-0}" = "1" ]; then
  echo "==> Skipping database schema (SKIP_DB_INIT=1)"
else
  echo "==> Applying database schema (init.sql)…"
  python scripts/init_db.py
fi

echo "==> Starting: $*"
exec "$@"
