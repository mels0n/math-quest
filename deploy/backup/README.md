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
| `TZ` | `America/Chicago` | Time zone for `BACKUP_AT` |

## Run the backup

Run as a long-lived service. It sleeps until the next `BACKUP_AT`, dumps,
prunes, and repeats:

```sh
sh /opt/backup/pg-backup.sh
```

Take a single dump and exit (useful for a manual backup or a test):

```sh
sh /opt/backup/pg-backup.sh --once
```

A dump is written to `math-quest-YYYYMMDD-HHMMSS.dump.partial` and renamed to
`.dump` only after `pg_dump` succeeds. On failure the partial file is removed,
the error goes to stderr and the script exits non-zero, so a container
orchestrator restarts it. Stale `.partial` files from an interrupted run are removed at startup. Dumps are created mode 600. Pruning only touches files named `math-quest-YYYYMMDD-HHMMSS.dump`, so hand-named copies are never counted or removed. Timestamps use the `TZ` zone.

## Restore

1. Stop the application so nothing writes during the restore.
2. Point the same environment variables at the target database. For a fresh
   database, create it first (`createdb`).
3. Restore. The interface is environment variables plus the dump path:

   ```sh
   sh /opt/backup/pg-restore.sh /backups/math-quest-YYYYMMDD-HHMMSS.dump
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
sh /opt/backup/pg-restore.sh /backups/math-quest-YYYYMMDD-HHMMSS.dump
```

Restores use `--no-owner --no-privileges --exit-on-error`, so the restored
objects belong to `PGUSER` and any error aborts the restore.

## Tests

`backend/tests/ops/test_backup_scripts.py` runs both scripts against throwaway
databases on the test server (`TEST_DATABASE_URL`). It is skipped when the
PostgreSQL client tools are not installed.
