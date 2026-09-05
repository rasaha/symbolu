#!/usr/bin/env bash
#
# Migration-cycle validation (production-readiness round PR-A).
#
# Proves, against a REAL PostgreSQL database, that the committed Alembic
# history: (1) upgrades base -> head, (2) has exactly one head, (3) downgrades
# head -> base, and (4) re-upgrades to head. This is the same cycle CI runs
# (dilchat-ci.yml, PostgreSQL job); this script gives operators the identical
# check locally and against pre-production databases.
#
# DESTRUCTIVE by design: the downgrade drops every table. Point it ONLY at a
# disposable validation database — never at one holding data you keep. The
# script refuses to run unless the target database name contains "validate",
# "test", "ci", or "scratch" (override with DILCHAT_CYCLE_I_KNOW=1).
#
# Usage:
#   DILCHAT_DATABASE_URL=postgresql+asyncpg://user:pw@host:5432/dilchat_validate \
#     scripts/validate_migration_cycle.sh
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"

URL="${DILCHAT_DATABASE_URL:?DILCHAT_DATABASE_URL is required (asyncpg URL of a DISPOSABLE database)}"
DBNAME="${URL##*/}"; DBNAME="${DBNAME%%\?*}"
if [[ "${DILCHAT_CYCLE_I_KNOW:-0}" != "1" ]] \
   && ! [[ "$DBNAME" == *validate* || "$DBNAME" == *test* || "$DBNAME" == *ci* || "$DBNAME" == *scratch* ]]; then
  echo "validate-migration-cycle: REFUSED — '$DBNAME' does not look disposable" >&2
  echo "(name it *validate*/*test*/*ci*/*scratch*, or set DILCHAT_CYCLE_I_KNOW=1)" >&2
  exit 2
fi

echo "validate-migration-cycle: upgrade base -> head"
alembic upgrade head

echo "validate-migration-cycle: exactly one head"
count=$(alembic heads | grep -c '(head)')
test "$count" -eq 1 || { echo "FAIL: $count alembic heads" >&2; exit 1; }

echo "validate-migration-cycle: downgrade head -> base"
alembic downgrade base

echo "validate-migration-cycle: re-upgrade base -> head"
alembic upgrade head

echo "validate-migration-cycle: OK (upgrade / single head / downgrade / re-upgrade)"
