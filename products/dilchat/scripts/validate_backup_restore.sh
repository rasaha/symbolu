#!/usr/bin/env bash
#
# Backup/restore validation (production-readiness round PR-A).
#
# Proves that a pg_dump of a migrated DilChat database restores into a second
# database and that the restored copy matches the source on:
#   1. the Alembic version stamp,
#   2. the set of public tables,
#   3. per-table row counts.
#
# The dump uses the custom format (-Fc) so the same artifact drives selective
# or full restores. Restore SHOULD target a database in the SAME cluster (or a
# cluster where the dilchat_* roles already exist): DilChat GRANTs and RLS
# policies reference those roles, and pg_restore fails without them (see the
# operations runbook, docs/DILCHAT_OPERATIONS_RUNBOOK.md).
#
# Usage:
#   SOURCE_URL=postgresql://user:pw@host:5432/dilchat \
#   RESTORE_URL=postgresql://user:pw@host:5432/dilchat_restore_validate \
#     scripts/validate_backup_restore.sh
#
# RESTORE_URL must point at an EXISTING, EMPTY, DISPOSABLE database; anything
# in it is clobbered. The script refuses non-disposable-looking names (must
# contain "validate", "test", "ci", or "scratch"; override DILCHAT_RESTORE_I_KNOW=1).
set -euo pipefail

SOURCE_URL="${SOURCE_URL:?SOURCE_URL is required (plain postgresql:// URL of the source database)}"
RESTORE_URL="${RESTORE_URL:?RESTORE_URL is required (plain postgresql:// URL of a DISPOSABLE target database)}"

RDB="${RESTORE_URL##*/}"; RDB="${RDB%%\?*}"
if [[ "${DILCHAT_RESTORE_I_KNOW:-0}" != "1" ]] \
   && ! [[ "$RDB" == *validate* || "$RDB" == *test* || "$RDB" == *ci* || "$RDB" == *scratch* ]]; then
  echo "validate-backup-restore: REFUSED — '$RDB' does not look disposable" >&2
  exit 2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
DUMP="$WORK/dilchat.dump"

echo "validate-backup-restore: pg_dump (custom format)"
pg_dump --format=custom --no-owner --file="$DUMP" "$SOURCE_URL"
test -s "$DUMP"
echo "  dump: $(wc -c < "$DUMP") bytes"

echo "validate-backup-restore: pg_restore into target"
pg_restore --no-owner --dbname="$RESTORE_URL" "$DUMP"

snapshot() {
  # Alembic stamp + exact per-table row counts, one deterministic text blob.
  psql "$1" -X -q -t -A -c "select 'alembic:' || version_num from alembic_version order by 1"
  psql "$1" -X -q -t -A -c "
    select string_agg(format('count:%s:%s', tab, cnt), E'\n' order by tab)
    from (
      select c.relname as tab,
             (xpath('/row/cnt/text()',
                    query_to_xml(format('select count(*) as cnt from %I.%I',
                                        n.nspname, c.relname), false, true, '')))[1]::text as cnt
      from pg_class c join pg_namespace n on n.oid = c.relnamespace
      where n.nspname = 'public' and c.relkind = 'r'
    ) t"
}

echo "validate-backup-restore: comparing source and restored copies"
SRC_STATE="$(snapshot "$SOURCE_URL")"
DST_STATE="$(snapshot "$RESTORE_URL")"
if [[ "$SRC_STATE" != "$DST_STATE" ]]; then
  echo "validate-backup-restore: FAIL — restored state differs from source" >&2
  diff <(echo "$SRC_STATE") <(echo "$DST_STATE") >&2 || true
  exit 1
fi
echo "$SRC_STATE" | grep -q '^alembic:' || { echo "FAIL: no alembic stamp found" >&2; exit 1; }

echo "validate-backup-restore: OK (alembic stamp, table set, and row counts match)"
