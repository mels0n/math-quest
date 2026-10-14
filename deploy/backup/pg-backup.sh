#!/bin/sh
# Scheduled PostgreSQL backup.
#
# Usage: pg-backup.sh [--once]
#   (default)  loop: dump at start if the newest dump is older than 25 hours,
#              then sleep until each BACKUP_AT in TZ, dump, prune, repeat. A
#              failed dump is retried after RETRY_SECONDS, up to RETRY_MAX
#              attempts, then waits for the next slot. The loop never exits on
#              a dump failure.
#   --once     take a single dump, prune, and exit (non-zero on failure)
#
# Environment: PGHOST, PGPORT (5432), PGUSER, PGDATABASE, PGPASSWORD_FILE,
#   BACKUP_DIR (/backups), KEEP (14), BACKUP_AT (03:15), TZ (UTC),
#   RETRY_SECONDS (900), RETRY_MAX (4).
# Needs GNU date (the official postgres image has it). Dumps are created mode 600.
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source-path=SCRIPTDIR
# shellcheck source=pg-common.sh
. "$script_dir/pg-common.sh"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP="${KEEP:-14}"
BACKUP_AT="${BACKUP_AT:-03:15}"
RETRY_SECONDS="${RETRY_SECONDS:-900}"
RETRY_MAX="${RETRY_MAX:-4}"
TZ="${TZ:-UTC}"
export TZ
umask 077

log() {
  printf '%s pg-backup: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

warn() {
  printf '%s pg-backup: error: %s
' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
}

die() {
  printf '%s pg-backup: error: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
  exit 1
}

case "$KEEP" in
  '' | *[!0-9]* | 0*) die "KEEP must be a positive integer without leading zeros" ;;
esac
case "$RETRY_SECONDS" in
  '' | *[!0-9]* | 0*) die "RETRY_SECONDS must be a positive integer without leading zeros" ;;
esac
case "$RETRY_MAX" in
  '' | *[!0-9]* | 0*) die "RETRY_MAX must be a positive integer without leading zeros" ;;
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
child=""
on_exit() {
  if [ -n "$child" ]; then
    kill "$child" 2> /dev/null || true
    wait "$child" 2> /dev/null || true
  fi
  if [ -n "$partial" ]; then
    rm -f -- "$partial"
  fi
  mq_cleanup
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mq_setup_passfile
if [ ! -d "$BACKUP_DIR" ] || [ ! -w "$BACKUP_DIR" ]; then
  die "BACKUP_DIR is not a writable directory"
fi

# Dump files are named math-quest-YYYYMMDD-HHMMSS.dump; nothing else matches.
prune() {
  total=0
  for f in "$BACKUP_DIR"/math-quest-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].dump; do
    if [ -e "$f" ]; then
      total=$((total + 1))
    fi
  done
  pruned=0
  excess=$((total - KEEP))
  if [ "$excess" -gt 0 ]; then
    # Timestamped names sort oldest first.
    for f in "$BACKUP_DIR"/math-quest-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].dump; do
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
  pg_dump -w -Fc -f "$partial" -d "$PGDATABASE" &
  child=$!
  if ! wait "$child"; then
    child=""
    rm -f -- "$partial"
    partial=""
    warn "pg_dump failed"
    return 1
  fi
  child=""
  sync "$partial" 2> /dev/null || sync
  if ! mv -- "$partial" "$final"; then
    rm -f -- "$partial"
    partial=""
    warn "could not move the finished dump into place"
    return 1
  fi
  partial=""
  if ! size=$(wc -c < "$final" | tr -d ' '); then
    warn "could not read the size of $(basename -- "$final")"
    return 1
  fi
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

# A partial file left by a killed run is never a usable dump. Recent ones may
# belong to a run in progress, so only files older than 6 hours are removed.
find "$BACKUP_DIR" -maxdepth 1 -name 'math-quest-*.dump.partial' -mmin +360 -exec rm -f {} +

if [ "$mode" = once ]; then
  run_backup || exit 1
  exit 0
fi

# Sleep without blocking signal handling.
nap() {
  sleep "$1" &
  child=$!
  wait "$child" || true
  child=""
}

# Dump, retrying after a failure. Gives up after RETRY_MAX attempts; the caller
# then waits for the next slot.
backup_with_retry() {
  attempt=1
  while ! run_backup; do
    if [ "$attempt" -ge "$RETRY_MAX" ]; then
      log "giving up after ${attempt} attempts, waiting for the next slot"
      return 0
    fi
    log "retrying in ${RETRY_SECONDS}s (attempt ${attempt} of ${RETRY_MAX} failed)"
    nap "$RETRY_SECONDS"
    attempt=$((attempt + 1))
  done
}

# Catch up: a restart across the slot would otherwise skip a whole day.
if [ -z "$(find "$BACKUP_DIR" -maxdepth 1 -name 'math-quest-*.dump' -mmin -1500 | head -n 1)" ]; then
  log "no dump newer than 25 hours, dumping now"
  backup_with_retry
fi

while :; do
  wait_s=$(seconds_until_next)
  log "next dump in ${wait_s}s (${BACKUP_AT} ${TZ})"
  nap "$wait_s"
  backup_with_retry
done
