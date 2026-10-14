# Deploy to Docker Swarm

Run the app, its Postgres database and a daily backup as three Swarm services behind
an nginx reverse proxy (SWAG). [deploy/math-quest.yml](../../deploy/math-quest.yml)
describes the three services in one place. Create them one at a time with
`docker service create`. Do not use `docker stack deploy`: it re-resolves every
image tag in the stack and restarts services you did not mean to touch.

Run the commands on a Swarm manager. Placeholders in angle brackets are yours to fill in:

| Placeholder | Meaning |
| --- | --- |
| `<db-node>` | Swarm node that holds the database volume |
| `<swag-overlay-cidr>` | Address range of the overlay network the proxy shares with the app |
| `<wan-target>` | Public address your existing DNS-only records point to |
| `<registry-image-tag>` | The exact image, `ghcr.io/<owner>/math-quest:sha-<12 chars>` |
| `<backups-path>` | Host directory for dumps (persistent storage) |
| `<scripts-path>` | Host directory holding the three scripts from `deploy/backup/` |

Images are tagged `sha-<12 chars>` after the commit. Never deploy `:latest`.

## 1. Create the secrets

Create each secret from a file or a pipe so the value is never echoed or left in
shell history. Four are needed:

- `mq_db_password`: the database password.
- `mq_database_url`: the full URL, `postgresql+asyncpg://mathquest:<password>@math-quest-db:5432/mathquest`.
- `mq_signup_word`: the grown-up's secret word that new players must enter.
- `mq_admin_password`: the admin password.

```sh
docker secret create mq_db_password ./db-password.txt
docker secret create mq_database_url ./database-url.txt
docker secret create mq_signup_word ./signup-word.txt
docker secret create mq_admin_password ./admin-password.txt
```

Delete the local files afterwards.

## 2. Create the network and label the database node

```sh
docker network create --driver overlay --attachable math-quest_net
docker node update --label-add math-quest.db=true <db-node>
```

The app also joins the overlay network the proxy uses (`swag_see_all` below). It
must already exist.

## 3. Create the database service

```sh
docker service create --name math-quest-db \
  --constraint 'node.labels.math-quest.db==true' \
  --network math-quest_net \
  --secret mq_db_password \
  --env POSTGRES_USER=mathquest \
  --env POSTGRES_DB=mathquest \
  --env POSTGRES_PASSWORD_FILE=/run/secrets/mq_db_password \
  --mount type=volume,source=math-quest-pgdata,target=/var/lib/postgresql/data \
  --restart-condition on-failure \
  --health-cmd 'pg_isready -U mathquest' \
  --health-interval 10s \
  postgres:16
```

Wait until the task is running and healthy:

```sh
docker service ps math-quest-db
```

## 4. Create the backup service and prove a dump

Put `pg-backup.sh`, `pg-restore.sh` and `pg-common.sh` from
[deploy/backup/](../../deploy/backup/README.md) in `<scripts-path>` (executable), and
create `<backups-path>` writable by the postgres user inside the image.

```sh
docker service create --name math-quest-backup \
  --network math-quest_net \
  --secret mq_db_password \
  --env PGHOST=math-quest-db \
  --env PGUSER=mathquest \
  --env PGDATABASE=mathquest \
  --env PGPASSWORD_FILE=/run/secrets/mq_db_password \
  --mount type=bind,source=<backups-path>,target=/backups \
  --mount type=bind,source=<scripts-path>,target=/scripts,readonly \
  --restart-condition on-failure \
  postgres:16 /scripts/pg-backup.sh
```

Take one dump now with a one-shot service, then check `<backups-path>` for a
`math-quest-<timestamp>.dump` file and remove the one-shot service:

```sh
docker service create --name math-quest-backup-once --restart-condition none \
  --network math-quest_net \
  --secret mq_db_password \
  --env PGHOST=math-quest-db \
  --env PGUSER=mathquest \
  --env PGDATABASE=mathquest \
  --env PGPASSWORD_FILE=/run/secrets/mq_db_password \
  --mount type=bind,source=<backups-path>,target=/backups \
  --mount type=bind,source=<scripts-path>,target=/scripts,readonly \
  postgres:16 /scripts/pg-backup.sh --once
docker service logs math-quest-backup-once
docker service rm math-quest-backup-once
```

Do not continue until a dump exists. The [backup README](../../deploy/backup/README.md)
lists the variables (`KEEP`, `BACKUP_AT`, `TZ`) and restore usage.

## 5. Create the app service

```sh
docker service create --name math-quest \
  --network math-quest_net \
  --network swag_see_all \
  --secret mq_database_url \
  --secret mq_signup_word \
  --secret mq_admin_password \
  --env DATABASE_URL_FILE=/run/secrets/mq_database_url \
  --env INITIAL_SIGNUP_WORD_FILE=/run/secrets/mq_signup_word \
  --env ADMIN_PASSWORD_FILE=/run/secrets/mq_admin_password \
  --env TRUSTED_PROXIES=<swag-overlay-cidr> \
  --env COOKIE_SECURE=true \
  --replicas 1 \
  --update-order stop-first \
  --restart-condition on-failure \
  <registry-image-tag>
```

Keep it at one replica: rate limits are counted in process
([ADR-0006](../adr/0006-client-identity-and-rate-limits.md)). The container runs as
uid 10001, applies database migrations on start, and is healthy once `/api/health`
answers. Check the logs for the migrations:

```sh
docker service logs math-quest
```

### Trusted proxies and admin access

The app trusts `X-Forwarded-For` only from the addresses in `TRUSTED_PROXIES`.

- Name only the proxy itself: its overlay address, or the narrow range holding it.
- A range that covers the LAN your admin browser sits on makes the app treat your
  browser as a proxy, and admin requests then get 404.
- A trusted proxy that sends no `X-Forwarded-For` also gets 404 on admin routes. The
  SWAG `proxy.conf` include sets it.
- Left empty, `X-Forwarded-For` is ignored and every client looks like the proxy,
  which collapses rate limits and lockouts into one shared bucket.

`/api/admin` answers only to clients inside `ADMIN_ALLOWED_CIDRS`, default
`192.168.0.0/16,127.0.0.1/32,::1/128`. Set the variable (comma-separated) if your LAN
differs. Everyone else gets an ordinary 404 before the password is checked. The
reasoning is in [ADR-0006](../adr/0006-client-identity-and-rate-limits.md) and
[ADR-0007](../adr/0007-account-credentials-and-lockouts.md).

## 6. Add the proxy configuration

Copy [deploy/swag/math.subdomain.conf](../../deploy/swag/math.subdomain.conf) into the
SWAG proxy-confs directory, then test and reload nginx inside the SWAG container:

```sh
docker exec <swag-container> nginx -t
docker exec <swag-container> nginx -s reload
```

## 7. Add the DNS record

Create a DNS-only `A` record for `math.<your-domain>` pointing at `<wan-target>`. If
your LAN resolver has a wildcard for the domain, local clients already resolve it.

## 8. Smoke test

From outside your network:

```sh
curl -fsS https://math.<your-domain>/api/health
curl -s -o /dev/null -w '%{http_code}\n' https://math.<your-domain>/api/admin/me
```

The first returns 200 with a JSON body. The second must print `404`.

Then sign up with a throwaway account, play a few problems, and delete the account
from the admin screen on the LAN. Check that `docker service logs math-quest` shows
real client addresses, not the proxy's.

## 9. Rehearse a restore

Prove a dump restores before you need one. Restore the newest dump into a throwaway
database with a one-shot service, then drop it:

```sh
docker service create --name math-quest-restore-test --restart-condition none \
  --network math-quest_net \
  --secret mq_db_password \
  --env PGHOST=math-quest-db \
  --env PGUSER=mathquest \
  --env PGDATABASE=mq_restore_test \
  --env PGPASSWORD_FILE=/run/secrets/mq_db_password \
  --mount type=bind,source=<backups-path>,target=/backups,readonly \
  --mount type=bind,source=<scripts-path>,target=/scripts,readonly \
  postgres:16 sh -c 'PGDATABASE=mathquest createdb mq_restore_test && /scripts/pg-restore.sh "$(ls -t /backups/math-quest-*.dump | head -n 1)"; PGDATABASE=mathquest dropdb mq_restore_test'
docker service logs math-quest-restore-test
docker service rm math-quest-restore-test
```

Compare the printed row counts with the live database.

## Update the app later

Deploy a new commit by changing only the image on the running service:

```sh
docker service update --image <registry-image-tag> math-quest
```

`--update-order stop-first` replaces the single replica without running two at once,
and migrations run on start. If the new task fails its health check, roll back:

```sh
docker service rollback math-quest
```
