#!/bin/sh
# Restore a custom-format dump made by pg-backup.sh.
#
# Usage: pg-restore.sh [--force] <dump-file>
#   Refuses when the target database already holds user objects (tables, views,
#   sequences, user types in any non-system schema). With --force, objects that
#   are in the dump are dropped and recreated; objects not in the dump stay.
#   The restore runs in one transaction, so a failure leaves the target as it was.
#
# Environment: PGHOST, PGPORT (5432), PGUSER, PGDATABASE, PGPASSWORD_FILE.
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source-path=SCRIPTDIR
# shellcheck source=pg-common.sh
. "$script_dir/pg-common.sh"

force=0
dump=""
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -*)
      echo "usage: pg-restore.sh [--force] <dump-file>" >&2
      exit 2
      ;;
    *)
      if [ -n "$dump" ]; then
        echo "usage: pg-restore.sh [--force] <dump-file>" >&2
        exit 2
      fi
      dump="$arg"
      ;;
  esac
done
if [ -z "$dump" ]; then
  echo "usage: pg-restore.sh [--force] <dump-file>" >&2
  exit 2
fi
if [ ! -r "$dump" ]; then
  echo "pg-restore: cannot read dump file" >&2
  exit 1
fi

trap mq_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mq_setup_passfile

existing=$(psql -X -w -tA -d "$PGDATABASE" -c "
SELECT
  (SELECT count(*)
     FROM pg_catalog.pg_class c
     JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'v', 'm', 'S', 'f', 'p')
      AND n.nspname <> 'information_schema'
      AND n.nspname NOT LIKE 'pg\_%')
  +
  (SELECT count(*)
     FROM pg_catalog.pg_type t
     JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
     LEFT JOIN pg_catalog.pg_class c ON c.oid = t.typrelid
    WHERE (t.typtype IN ('e', 'd', 'r', 'm') OR (t.typtype = 'c' AND c.relkind = 'c'))
      AND n.nspname <> 'information_schema'
      AND n.nspname NOT LIKE 'pg\_%')")
if [ "$existing" -gt 0 ] && [ "$force" -ne 1 ]; then
  echo "pg-restore: target database already has $existing user object(s); use --force to overwrite" >&2
  exit 1
fi

if [ "$force" -eq 1 ]; then
  pg_restore -w --no-owner --no-privileges --exit-on-error --single-transaction \
    --clean --if-exists -d "$PGDATABASE" "$dump"
else
  pg_restore -w --no-owner --no-privileges --exit-on-error --single-transaction \
    -d "$PGDATABASE" "$dump"
fi

echo "row counts (schema.table count):"
psql -X -w -tA -d "$PGDATABASE" -c "
SELECT format('%I.%I', schemaname, tablename) || ' ' ||
  (xpath('/row/c/text()',
         query_to_xml(format('SELECT count(*) AS c FROM %I.%I', schemaname, tablename),
                      false, true, '')))[1]::text
FROM pg_catalog.pg_tables
WHERE schemaname = 'public'
ORDER BY tablename"
