#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL…"
python scripts/wait_for_postgres.py

echo "==> Applying database schema (init.sql)…"
python scripts/init_db.py

echo "==> Starting: $*"
exec "$@"
