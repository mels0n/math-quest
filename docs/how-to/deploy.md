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
| `<edge-subnet>` | Subnet of the dedicated edge network (step 2), a /28 or /27. Must not overlap your LAN or `ADMIN_ALLOWED_CIDRS` |
| `<proxy-service>` | Name of the reverse proxy's Swarm service |
| `<wan-target>` | Public address your existing DNS-only records point to |
| `<registry-image-tag>` | The exact image, `ghcr.io/<owner>/math-quest:sha-<12 chars>` |
| `<backups-path>` | Host directory for dumps (persistent storage) |
| `<scripts-path>` | Host directory holding the three scripts from `deploy/backup/` |

Images are tagged `sha-<12 chars>` after the commit. Never deploy `:latest`.

## 1. Create the secrets

Create each secret from a file or a pipe so the value is never echoed or left in
shell history. Four are needed:

- `mq_db_password`: the database password.
- `mq_database_url`: the full URL, `postgresql+asyncpg://mathquest:<password>@math-quest-db:5432/mathquest`. Percent-encode the password in the URL if it has characters such as `@`, `/`, `:` or `%`.
- `mq_signup_word`: the grown-up's secret word that new players must enter.
- `mq_admin_password`: the admin password (optional, see below). Use at least 16 characters (the app refuses to start with a shorter one) and preferably 24 or more random characters from a password manager. Logins are capped at 10 per client address and 30 across all clients per 10 minutes, so the length of the password is the main defence, not the cap.

```sh
docker secret create mq_db_password ./db-password.txt
docker secret create mq_database_url ./database-url.txt
docker secret create mq_signup_word ./signup-word.txt
docker secret create mq_admin_password ./admin-password.txt
```

The admin secret is optional. Without it (leave out the secret, the
`ADMIN_PASSWORD_FILE` variable and its `--secret` flag in step 5) the admin area is
disabled and every `/api/admin` route answers 404. With it, a secret that is missing
or empty stops the app from starting.

Delete the local files afterwards.

## 2. Create the networks and label the database node

```sh
docker network create --driver overlay math-quest_net
docker network create --driver overlay --subnet <edge-subnet> math-quest_edge
docker node update --label-add math-quest.db=true <db-node>
```

`math-quest_edge` is a dedicated network that holds only the proxy and the app. Do not
make it attachable, and attach nothing else to it. Attach the proxy once:

```sh
docker service update --network-add math-quest_edge <proxy-service>
```

This restarts the proxy task, so expect a short interruption of every site it serves.

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
[deploy/backup/](../../deploy/backup/README.md) in `<scripts-path>`, and
create `<backups-path>` writable by the container's user (root in this image). Dumps are created mode 600. The scripts are run as `sh /scripts/...`, so they need no
executable bit.

`<backups-path>` and `<scripts-path>` are host paths, so the backup service must run on
a node where both exist. The commands below pin it to the database node with the same
label; use a different constraint if the paths live on another node.

```sh
docker service create --name math-quest-backup \
  --constraint 'node.labels.math-quest.db==true' \
  --network math-quest_net \
  --secret mq_db_password \
  --env PGHOST=math-quest-db \
  --env PGUSER=mathquest \
  --env PGDATABASE=mathquest \
  --env PGPASSWORD_FILE=/run/secrets/mq_db_password \
  --mount type=bind,source=<backups-path>,target=/backups \
  --mount type=bind,source=<scripts-path>,target=/scripts,readonly \
  --restart-condition on-failure \
  postgres:16 sh /scripts/pg-backup.sh
```

Take one dump now with a one-shot service, then check `<backups-path>` for a
`math-quest-<timestamp>.dump` file and remove the one-shot service:

```sh
docker service create --name math-quest-backup-once --restart-condition none \
  --constraint 'node.labels.math-quest.db==true' \
  --network math-quest_net \
  --secret mq_db_password \
  --env PGHOST=math-quest-db \
  --env PGUSER=mathquest \
  --env PGDATABASE=mathquest \
  --env PGPASSWORD_FILE=/run/secrets/mq_db_password \
  --mount type=bind,source=<backups-path>,target=/backups \
  --mount type=bind,source=<scripts-path>,target=/scripts,readonly \
  postgres:16 sh /scripts/pg-backup.sh --once
docker service logs math-quest-backup-once
docker service rm math-quest-backup-once
```

Do not continue until a dump exists. The [backup README](../../deploy/backup/README.md)
lists the variables (`KEEP`, `BACKUP_AT`, `TZ`, `RETRY_SECONDS`, `RETRY_MAX`) and restore usage.

## 5. Create the app service

The image must be public, or log in to the registry on the manager first
(`docker login`) and add `--with-registry-auth` to the `docker service create`
command below.

```sh
docker service create --name math-quest \
  --network math-quest_net \
  --network math-quest_edge \
  --secret mq_database_url \
  --secret mq_signup_word \
  --secret mq_admin_password \
  --env DATABASE_URL_FILE=/run/secrets/mq_database_url \
  --env INITIAL_SIGNUP_WORD_FILE=/run/secrets/mq_signup_word \
  --env ADMIN_PASSWORD_FILE=/run/secrets/mq_admin_password \
  --env TRUSTED_PROXIES=<edge-subnet> \
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

- Set `TRUSTED_PROXIES` to the dedicated edge subnet (`<edge-subnet>`). Every address
  on that network can only be the proxy, the app, or Docker's own gateway and
  virtual addresses, so the range survives proxy task restarts and admits no
  neighbouring containers. Do not point it at a shared proxy network: any container
  there could then forge `X-Forwarded-For`.
- The proxy must see real client source addresses. Publish its ports in host mode
  (`mode=host`) so Swarm's ingress does not source-NAT connections to an internal
  address. Behind NAT every client looks like the same internal address, so the app
  cannot tell the LAN from the internet and admin is judged by an address you did
  not intend.
- Check the proxy's own nginx `real_ip` settings. If it trusts private ranges
  (`set_real_ip_from`), it can believe a client-supplied `X-Forwarded-For`. The
  shipped config sets the header from the proxy's real TCP peer
  (`$realip_remote_addr`), so the app only ever sees an address the proxy observed.
- A range that covers the LAN your admin browser sits on makes the app treat your
  browser as a proxy, and admin requests then get 404.
- A trusted proxy that sends no `X-Forwarded-For` also gets 404 on admin routes. The
  SWAG `proxy.conf` include sets it.
- Left empty, `X-Forwarded-For` is ignored and every client looks like the proxy,
  which collapses rate limits and lockouts into one shared bucket. Admin routes then
  return 404 for everyone behind the proxy, because their requests carry
  `X-Forwarded-For` from an untrusted peer.

`/api/admin` answers only to clients inside `ADMIN_ALLOWED_CIDRS`, default
`192.168.0.0/16,127.0.0.1/32,::1/128`. Set the variable (comma-separated) if your LAN
differs. Everyone else gets an ordinary 404 before the password is checked. The
reasoning is in [ADR-0009](../adr/0009-lan-only-admin.md); client identity is in
[ADR-0006](../adr/0006-client-identity-and-rate-limits.md).

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

Then check that a forged forwarding header does not open admin, over both IPv4 and
IPv6. Both must print `404`:

```sh
curl -4 -s -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: 192.168.1.10' https://math.<your-domain>/api/admin/me
curl -6 -s -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: 192.168.1.10' https://math.<your-domain>/api/admin/me
```

Run the `-6` line only if you published an AAAA record. Without one curl prints
`000`, which is expected. If a line that can connect prints anything else, stop: the proxy is passing a client-supplied header
through or hiding real source addresses. See "Trusted proxies and admin access".

Then sign up with a throwaway account, play a few problems, and delete the account
from the admin screen on the LAN. Check that `docker service logs math-quest` shows
real client addresses, not the proxy's. Rerun this whole step, including the
log check, after any proxy restart.

## 9. Rehearse a restore

Prove a dump restores before you need one. Restore the newest dump into a throwaway
database with a one-shot service, then drop it:

```sh
docker service create --name math-quest-restore-test --restart-condition none \
  --constraint 'node.labels.math-quest.db==true' \
  --network math-quest_net \
  --secret mq_db_password \
  --env PGHOST=math-quest-db \
  --env PGUSER=mathquest \
  --env PGDATABASE=mq_restore_test \
  --env PGPASSWORD_FILE=/run/secrets/mq_db_password \
  --mount type=bind,source=<backups-path>,target=/backups,readonly \
  --mount type=bind,source=<scripts-path>,target=/scripts,readonly \
  postgres:16 sh -c 'export PGPASSWORD="$(cat /run/secrets/mq_db_password)"; PGDATABASE=mathquest createdb mq_restore_test && sh /scripts/pg-restore.sh "$(ls -t /backups/math-quest-*.dump | head -n 1)"; PGDATABASE=mathquest dropdb mq_restore_test'
docker service logs math-quest-restore-test
docker service rm math-quest-restore-test
```

Print the live row counts to compare with the restore output:

```sh
docker service create --name math-quest-counts --restart-condition none   --network math-quest_net   --secret mq_db_password   --env PGHOST=math-quest-db   --env PGUSER=mathquest   --env PGDATABASE=mathquest   postgres:16 sh -c 'export PGPASSWORD="$(cat /run/secrets/mq_db_password)"; psql -X -tA -c "SELECT format('"'"'%I.%I'"'"', schemaname, tablename) || '"'"' '"'"' || (xpath('"'"'/row/c/text()'"'"', query_to_xml(format('"'"'SELECT count(*) AS c FROM %I.%I'"'"', schemaname, tablename), false, true, '"'"''"'"')))[1]::text FROM pg_catalog.pg_tables WHERE schemaname = '"'"'public'"'"' ORDER BY tablename"'
docker service logs math-quest-counts
docker service rm math-quest-counts
```

## Update the app later

Deploy a new commit by changing only the image on the running service:

```sh
docker service update --image <registry-image-tag> math-quest
```

`--update-order stop-first` replaces the single replica without running two at once.
The image runs `alembic upgrade head` on start, so a release's database migrations are
applied when its first task starts.

## Roll back, or roll forward

- **A release without a migration:** if the new task fails its health check, roll back
  right away:

  ```sh
  docker service rollback math-quest
  ```

- **A release with a migration:** once the migration has run, the previous image cannot
  start (Alembic cannot find the database's revision), so `docker service rollback` does
  not help. Fix the problem and deploy a new commit (roll forward). To go back anyway,
  first run `alembic downgrade <previous revision>` with the new image, in a one-off
  container or service that uses the same image and the database secret, and only then roll
  the service back. A downgrade can drop data added by the migration, so take a dump first
  (step 4).
- **A release that adds skills** must not be rolled back once learners have played them:
  their progress, reviews and open problems name skills the older image does not know. The
  app ignores a stored review or problem for a skill missing from its pack rather than
  failing, but the learner's progress on that skill is invisible until the skill returns.
  Roll forward instead.
