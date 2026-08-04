#!/usr/bin/env bash
# Start a throwaway local PostgreSQL 16 cluster for development/tests.
# Runs as an unprivileged user (PostgreSQL refuses to run as root).
# NOT a production deployment manifest — local development only.
set -euo pipefail

PGBIN="${PGBIN:-/usr/lib/postgresql/16/bin}"
PGDATA="${PGDATA:-/tmp/dilchat_pgdata}"
PGPORT="${PGPORT:-5433}"
SOCKDIR="${SOCKDIR:-/tmp}"

if [ ! -d "$PGDATA/base" ]; then
  "$PGBIN/initdb" -D "$PGDATA" -U postgres --auth=trust -E UTF8
fi
"$PGBIN/pg_ctl" -D "$PGDATA" -o "-p $PGPORT -k $SOCKDIR" -l "$PGDATA/server.log" start
sleep 1
for db in dilchat_dev dilchat_test; do
  "$PGBIN/psql" -h "$SOCKDIR" -p "$PGPORT" -U postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 || \
    "$PGBIN/createdb" -h "$SOCKDIR" -p "$PGPORT" -U postgres "$db"
done
echo "PostgreSQL up on $SOCKDIR:$PGPORT (databases: dilchat_dev, dilchat_test)"
echo "export DILCHAT_DATABASE_URL='postgresql+asyncpg://postgres@/dilchat_dev?host=$SOCKDIR&port=$PGPORT'"
