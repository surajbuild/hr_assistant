#!/bin/sh
# ---------------------------------------------------------------------------
# docker/backend-entrypoint.sh
# ---------------------------------------------------------------------------
# Container entrypoint for the FastAPI backend (see Dockerfile / docker-compose.yml).
#
#   1. Wait until MySQL (DATABASE_URL) accepts connections.
#   2. Apply migrations:            alembic upgrade head
#   3. Optional demo seed:          SEED_DEMO_DATA=true runs scripts/seed_db.py, but ONLY
#                                   when the employees AND users tables are empty.
#                                   seed_db.py resets demo rows when run, so it must never
#                                   run against a database that already holds data.
#   4. exec the CMD (default: uvicorn app.main:app --host 0.0.0.0 --port 8000, one worker,
#      no --reload; the login/chat rate limiter is in-memory, so keep a single worker).
#
# Must keep LF line endings (the Dockerfile also strips CR as a safety net).
# ---------------------------------------------------------------------------
set -eu

cd /app

if [ -z "${DATABASE_URL:-}" ]; then
    echo "[entrypoint] ERROR: DATABASE_URL is not set." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 1. Wait for the database
# ---------------------------------------------------------------------------
DB_WAIT_SECONDS="${DB_WAIT_SECONDS:-120}"
echo "[entrypoint] Waiting for the database (up to ${DB_WAIT_SECONDS}s)..."
python - <<'PY'
import os
import sys
import time

from sqlalchemy import create_engine, text

deadline = time.monotonic() + int(os.environ.get("DB_WAIT_SECONDS", "120"))
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
last_error = None
while time.monotonic() < deadline:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[entrypoint] Database is reachable.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - any connection error means "not ready yet"
        last_error = exc
        time.sleep(2)
print(f"[entrypoint] ERROR: database not reachable: {type(last_error).__name__}", file=sys.stderr)
sys.exit(1)
PY

# ---------------------------------------------------------------------------
# 2. Migrations
# ---------------------------------------------------------------------------
echo "[entrypoint] Running alembic upgrade head..."
alembic upgrade head

# ---------------------------------------------------------------------------
# 3. Optional first-run demo seed (never on a non-empty database)
# ---------------------------------------------------------------------------
case "$(printf '%s' "${SEED_DEMO_DATA:-false}" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes)
        if python - <<'PY'
import os
import sys

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    employees = conn.execute(text("SELECT COUNT(*) FROM employees")).scalar_one()
    users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
print(f"[entrypoint] employees={employees} users={users}")
# exit 0 -> database is empty -> seed
sys.exit(0 if int(employees) == 0 and int(users) == 0 else 1)
PY
        then
            echo "[entrypoint] Empty database and SEED_DEMO_DATA=true -> seeding demo data..."
            python scripts/seed_db.py
        else
            echo "[entrypoint] Database already has data -> skipping demo seed."
        fi
        ;;
    *)
        echo "[entrypoint] SEED_DEMO_DATA is not true -> skipping demo seed."
        ;;
esac

# ---------------------------------------------------------------------------
# 4. Start the server (or whatever command was passed)
# ---------------------------------------------------------------------------
echo "[entrypoint] Starting: $*"
exec "$@"
