#!/bin/sh
# Restore a custom-format dump made by pg-backup.sh.
#
# Usage: pg-restore.sh [--force] <dump-file>
#   Refuses when the target database has any table in schema public. With
#   --force the existing objects in the dump are dropped and recreated.
#
# Environment: PGHOST, PGPORT (5432), PGUSER, PGDATABASE, PGPASSWORD_FILE.
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
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
trap 'exit 143' INT TERM
mq_setup_passfile

existing=$(psql -X -w -tA -d "$PGDATABASE" \
  -c "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
if [ "$existing" -gt 0 ] && [ "$force" -ne 1 ]; then
  echo "pg-restore: target database has $existing table(s) in schema public; use --force to overwrite" >&2
  exit 1
fi

if [ "$force" -eq 1 ]; then
  pg_restore -w --no-owner --no-privileges --exit-on-error --clean --if-exists \
    -d "$PGDATABASE" "$dump"
else
  pg_restore -w --no-owner --no-privileges --exit-on-error -d "$PGDATABASE" "$dump"
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
