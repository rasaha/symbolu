#!/usr/bin/env bash
#
# Orchestrate the LIVE mobile↔backend integration test:
#   1. migrate a PostgreSQL database to head (a fresh DB when admin vars allow),
#   2. start the real FastAPI app with uvicorn,
#   3. wait for /v1/health,
#   4. run the production mobile API client against it (jest.integration.config.js),
#   5. always tear the server down.
#
# It FAILS (non-zero) if the DB or server never becomes ready — an unavailable
# backend must never read as a pass. Used locally and by dilchat-mobile-ci.
#
# Configuration (env):
#   PYTHON                 python interpreter for the backend (default: python3)
#   BACKEND_DIR            path to products/dilchat (default: ../ from mobile)
#   DILCHAT_DATABASE_URL   asyncpg URL the app + alembic use (required)
#   ADMIN_PSQL             optional psql base cmd for a fresh DB, e.g.
#                          "psql -h /tmp -p 5433 -U postgres -d postgres"
#   FRESH_DB_NAME          db to drop/create with ADMIN_PSQL (optional)
#   PORT                   uvicorn port (default: 8091)
set -euo pipefail

MOBILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
BACKEND_DIR="${BACKEND_DIR:-$(cd "$MOBILE_DIR/.." && pwd)}"
PORT="${PORT:-8091}"
RUN_ID="${DILCHAT_INTEGRATION_RUN_ID:-run$$}"

if [[ -z "${DILCHAT_DATABASE_URL:-}" ]]; then
  echo "run-integration: DILCHAT_DATABASE_URL is required" >&2
  exit 2
fi

# Optionally recreate a pristine database so the run starts clean.
if [[ -n "${ADMIN_PSQL:-}" && -n "${FRESH_DB_NAME:-}" ]]; then
  echo "run-integration: recreating database ${FRESH_DB_NAME}"
  ${ADMIN_PSQL} -c "DROP DATABASE IF EXISTS ${FRESH_DB_NAME};" >/dev/null
  ${ADMIN_PSQL} -c "CREATE DATABASE ${FRESH_DB_NAME};" >/dev/null
fi

echo "run-integration: alembic upgrade head"
( cd "$BACKEND_DIR" && DILCHAT_ENVIRONMENT="${DILCHAT_ENVIRONMENT:-test}" "$PYTHON" -m alembic upgrade head )

echo "run-integration: starting uvicorn on :${PORT}"
SERVER_LOG="$(mktemp)"
# `exec` so SERVER_PID is uvicorn itself, not a wrapping subshell — otherwise
# the cleanup trap kills only the subshell and an orphaned server keeps the
# port, poisoning the NEXT run (health passes, first DB call 500s on the old
# server's dead pool).
( cd "$BACKEND_DIR" && DILCHAT_ENVIRONMENT="${DILCHAT_ENVIRONMENT:-development}" \
  exec "$PYTHON" -m uvicorn ugence_dilchat.app:create_app --factory --host 127.0.0.1 --port "$PORT" \
  >"$SERVER_LOG" 2>&1 ) &
SERVER_PID=$!

cleanup() {
  echo "run-integration: stopping uvicorn (pid ${SERVER_PID})"
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

BASE="http://127.0.0.1:${PORT}"
echo "run-integration: waiting for ${BASE}/v1/health"
ready=0
for _ in $(seq 1 60); do
  if curl -fsS "${BASE}/v1/health" >/dev/null 2>&1; then ready=1; break; fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "run-integration: uvicorn exited early; log:" >&2; cat "$SERVER_LOG" >&2; exit 1
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "run-integration: backend did not become healthy in time; log:" >&2
  cat "$SERVER_LOG" >&2
  exit 1
fi

echo "run-integration: running live integration test"
cd "$MOBILE_DIR"
DILCHAT_INTEGRATION_BASE_URL="$BASE" DILCHAT_INTEGRATION_RUN_ID="$RUN_ID" \
  npx jest --config jest.integration.config.js --ci
