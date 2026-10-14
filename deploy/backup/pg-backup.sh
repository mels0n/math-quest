#!/bin/sh
# Scheduled PostgreSQL backup.
#
# Usage: pg-backup.sh [--once]
#   (default)  loop: sleep until the next BACKUP_AT in TZ, dump, prune, repeat
#   --once     take a single dump, prune, and exit
#
# Environment: PGHOST, PGPORT (5432), PGUSER, PGDATABASE, PGPASSWORD_FILE,
#   BACKUP_DIR (/backups), KEEP (14), BACKUP_AT (03:15), TZ (America/Chicago).
# Needs GNU date (the official postgres image has it).
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=pg-common.sh
. "$script_dir/pg-common.sh"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP="${KEEP:-14}"
BACKUP_AT="${BACKUP_AT:-03:15}"
TZ="${TZ:-America/Chicago}"
export TZ

log() {
  printf '%s pg-backup: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

die() {
  printf '%s pg-backup: error: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
  exit 1
}

case "$KEEP" in
  '' | *[!0-9]* | 0) die "KEEP must be a positive integer" ;;
esac
case "$BACKUP_AT" in
  [0-1][0-9]:[0-5][0-9] | 2[0-3]:[0-5][0-9]) ;;
  *) die "BACKUP_AT must be HH:MM (24 hour)" ;;
esac

mode=loop
case "${1:-}" in
  '') ;;
  --once) mode=once ;;
  *)
    echo "usage: pg-backup.sh [--once]" >&2
    exit 2
    ;;
esac

partial=""
sleeper=""
on_exit() {
  if [ -n "$partial" ]; then
    rm -f "$partial"
  fi
  if [ -n "$sleeper" ]; then
    kill "$sleeper" 2> /dev/null || true
  fi
  mq_cleanup
}
trap on_exit EXIT
trap 'exit 143' INT TERM

mq_setup_passfile
[ -d "$BACKUP_DIR" ] && [ -w "$BACKUP_DIR" ] || die "BACKUP_DIR is not a writable directory"

prune() {
  total=0
  for f in "$BACKUP_DIR"/math-quest-*.dump; do
    if [ -e "$f" ]; then
      total=$((total + 1))
    fi
  done
  pruned=0
  excess=$((total - KEEP))
  if [ "$excess" -gt 0 ]; then
    # Timestamped names sort oldest first.
    for f in "$BACKUP_DIR"/math-quest-*.dump; do
      [ "$pruned" -lt "$excess" ] || break
      rm -f -- "$f"
      pruned=$((pruned + 1))
    done
  fi
}

run_backup() {
  stamp=$(date +%Y%m%d-%H%M%S)
  final="$BACKUP_DIR/math-quest-$stamp.dump"
  partial="$final.partial"
  log "dump started: $PGDATABASE"
  if ! pg_dump -w -Fc -f "$partial" -d "$PGDATABASE"; then
    rm -f "$partial"
    partial=""
    die "pg_dump failed"
  fi
  sync "$partial" 2> /dev/null || sync
  mv -- "$partial" "$final"
  partial=""
  size=$(wc -c < "$final" | tr -d ' ')
  prune
  log "dump finished: $(basename -- "$final") ${size} bytes, pruned ${pruned}, kept up to ${KEEP}"
}

seconds_until_next() {
  now=$(date +%s)
  target=$(date -d "today $BACKUP_AT" +%s)
  if [ "$target" -le "$now" ]; then
    target=$(date -d "tomorrow $BACKUP_AT" +%s)
  fi
  echo $((target - now))
}

if [ "$mode" = once ]; then
  run_backup
  exit 0
fi

while :; do
  wait_s=$(seconds_until_next)
  log "next dump in ${wait_s}s (${BACKUP_AT} ${TZ})"
  sleep "$wait_s" &
  sleeper=$!
  wait "$sleeper" || true
  sleeper=""
  run_backup
done
