#!/bin/sh
# Shared connection setup for pg-backup.sh and pg-restore.sh. Sourced, not executed.
#
# Reads PGHOST, PGPORT (default 5432), PGUSER, PGDATABASE and PGPASSWORD_FILE.
# The password is copied into a private temporary PGPASSFILE so it never appears
# on a command line or in the environment of the child processes.

: "${PGHOST:?PGHOST is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
PGPORT="${PGPORT:-5432}"
export PGHOST PGPORT PGUSER PGDATABASE

mq_tmpdir=""

mq_cleanup() {
  if [ -n "$mq_tmpdir" ]; then
    rm -rf "$mq_tmpdir"
  fi
}

mq_setup_passfile() {
  unset PGPASSWORD
  if [ -z "${PGPASSWORD_FILE:-}" ]; then
    unset PGPASSFILE
    return 0
  fi
  if [ ! -r "$PGPASSWORD_FILE" ]; then
    echo "cannot read PGPASSWORD_FILE" >&2
    return 1
  fi
  umask 077
  mq_tmpdir=$(mktemp -d)
  PGPASSFILE="$mq_tmpdir/pgpass"
  export PGPASSFILE
  # Backslash and colon are the pgpass escape characters.
  mq_pw=$(head -n 1 "$PGPASSWORD_FILE" | tr -d '\r\n' | sed -e 's/\\/\\\\/g' -e 's/:/\\:/g')
  printf '*:*:*:%s:%s\n' "$PGUSER" "$mq_pw" > "$PGPASSFILE"
  unset mq_pw
  chmod 600 "$PGPASSFILE"
}
