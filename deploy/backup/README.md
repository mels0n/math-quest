# Database backup and restore

Two POSIX shell scripts for PostgreSQL 16, meant to run in the official
`postgres:16` image (they need `pg_dump`, `pg_restore`, `psql` and GNU `date`).

- `pg-backup.sh` takes a daily `pg_dump -Fc` and keeps the newest N dumps.
- `pg-restore.sh` restores one dump into a database and prints row counts.
- `pg-common.sh` is sourced by both. It builds a private, mode 600 password
  file from `PGPASSWORD_FILE`, so the password is never on a command line or in
  the environment, and removes it on exit.

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `PGHOST` | required | Database host |
| `PGPORT` | `5432` | Database port |
| `PGUSER` | required | Database role |
| `PGDATABASE` | required | Database to dump or restore into |
| `PGPASSWORD_FILE` | unset | Path to a file holding the password (for example a Docker secret). If unset, `PGPASSFILE` and `PGPASSWORD` from the environment are used as usual. |
| `BACKUP_DIR` | `/backups` | Where dumps are written (a persistent volume) |
| `KEEP` | `14` | Number of newest `math-quest-*.dump` files to keep |
| `BACKUP_AT` | `03:15` | Daily run time, `HH:MM` 24 hour |
| `TZ` | `UTC` | Time zone for `BACKUP_AT` |
| `RETRY_SECONDS` | `900` | Wait before retrying a failed dump (loop mode) |
| `RETRY_MAX` | `4` | Attempts per slot before waiting for the next `BACKUP_AT` (loop mode) |

## Run the backup

Run as a long-lived service. At start, if no `math-quest-*.dump` is newer than
25 hours, it dumps immediately (so a restart across the slot does not skip a
day). Then it sleeps until each `BACKUP_AT`, dumps, prunes, and repeats. A
failed dump does not stop the service: it is retried after `RETRY_SECONDS`, up
to `RETRY_MAX` attempts, then the service waits for the next slot:

```sh
sh /scripts/pg-backup.sh
```

Take a single dump and exit (useful for a manual backup or a test):

```sh
sh /scripts/pg-backup.sh --once
```

A dump is written to `math-quest-YYYYMMDD-HHMMSS.dump.partial` and renamed to
`.dump` only after `pg_dump` succeeds. On failure the partial file is removed and
`pg_dump failed` goes to stderr. If the finished dump cannot be renamed, the
partial file is removed too and `could not move the finished dump into place` goes
to stderr. Either way the run counts as failed. With `--once` the script then exits non-zero;
in loop mode it retries as described above. Invalid settings (`KEEP`,
`BACKUP_AT`, `RETRY_SECONDS`, `RETRY_MAX`, an unwritable `BACKUP_DIR`) make
either mode exit non-zero at start. Stale `.partial` files from an interrupted run are removed at startup. Dumps are created mode 600. Pruning only touches files named `math-quest-YYYYMMDD-HHMMSS.dump`, so hand-named copies are never counted or removed. Timestamps use the `TZ` zone.

## Restore

1. Stop the application so nothing writes during the restore.
2. Point the same environment variables at the target database. For a fresh
   database, create it first (`createdb`).
3. Restore. The interface is environment variables plus the dump path:

   ```sh
   sh /scripts/pg-restore.sh /backups/math-quest-YYYYMMDD-HHMMSS.dump
   ```

   The script refuses if the target already holds user objects (tables, views,
   sequences or user types in any non-system schema). The restore runs in a
   single transaction, so a failed restore leaves the target untouched.
4. Check the printed row counts against what you expect, then start the
   application.

### Overwriting a populated database

`--force` drops and recreates only the objects that are present in the dump.
Anything else already in the database stays. For a full rollback, drop and
recreate the database first, then restore without `--force`:

```sh
dropdb -h <db-host> -U <db-admin-user> <database>
createdb -h <db-host> -U <db-admin-user> -O <app-role> <database>
sh /scripts/pg-restore.sh /backups/math-quest-YYYYMMDD-HHMMSS.dump
```

A dump taken from an older schema cannot be restored with `--force` over a
newer schema. Use the drop and create path above.

Restores use `--no-owner --no-privileges --exit-on-error`, so the restored
objects belong to `PGUSER` and any error aborts the restore.

## Tests

`backend/tests/ops/test_backup_scripts.py` runs both scripts against throwaway
databases on the test server (`TEST_DATABASE_URL`). It is skipped when the
PostgreSQL client tools are not installed.
