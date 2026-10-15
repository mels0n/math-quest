# Contributing to math-quest

How to build, check and navigate the code.

## Build, test, lint

Backend (run in `backend/`; needs Python 3.13+ and uv):

- Install: `uv sync`
- Test: `uv run pytest` (database tests need `docker compose -f compose.dev.yml up -d` and
  `export TEST_DATABASE_URL=postgresql+asyncpg://mathquest:mathquest@localhost:5432/mathquest`)
- Lint: `uv run ruff check`
- Types: `uv run pyright`
- Import boundaries: `uv run lint-imports`

Frontend (run in `frontend/`; needs Node 24):

- Install: `npm ci`
- Types: `npm run check`
- Layer rules: `npm run depcruise`
- Unit tests: `npm test`
- Build: `npm run build`
- End-to-end: `npm run test:e2e`

## Layout

```
backend/
  src/mathquest/
    app/        application factory and wiring
    api/        HTTP routes and the single error-to-HTTP mapping
    features/   use cases (accounts, play)
    entities/   database models and per-entity data access
    shared/     config, database, errors, logging
    engine/     pure problem engine (types, skill graph, generators, checker, mastery,
                content pack loader, templates, word problems, bank items)
  content/      content packs (skills, world, teaching text, word problems, bank items),
                word-problem slot lists and account word lists
  migrations/   Alembic revisions
  tests/
frontend/
  src/routes/   thin SvelteKit routes; import only from pages
  src/app, pages, widgets, features, entities, shared
docs/           Diátaxis layout (adr/ today; see docs/README.md)
```

Imports point downward only.

- Backend: `api -> features -> entities -> shared`. `engine` imports nothing from
  those four. Enforced by import-linter.
- Frontend: `app -> pages -> widgets -> features -> entities -> shared`, and slices
  are imported through their `index.ts`. Enforced by dependency-cruiser.

Both checks fail CI.

## Conventions

- Validate every inbound payload with a pydantic model before using it.
- Database rows never leave the data layer; map them to response models.
- Environment variables and secret files are read only in `mathquest.shared.config`.
- Domain errors are typed and mapped to HTTP responses in `mathquest.api.errors`.
- Learner input is parsed only by the checker's LaTeX parser. Never `eval`,
  `sympify` or `parse_expr` on it.
- Text shown to children uses no em dashes.
- Container images are tagged `sha-<12 chars>`, never `:latest`.

## Deployment settings

- `COOKIE_SECURE` (default true): sets the `Secure` flag on the session and device cookies.
- `DEV_EXPOSE_ANSWERS` (default false): test-only; returns answers to the client. The app refuses to start with it set while `COOKIE_SECURE` is true.
- `TRUSTED_PROXIES`: comma-separated IPs or CIDRs of the reverse proxy in front of the
  app. The client address comes from the socket peer. Only when the peer is in this
  list is the right-most address in `X-Forwarded-For` that is not itself a trusted
  proxy used instead. Production sets it to the dedicated edge network the app shares only
  with the proxy (for example `10.0.250.0/28`). Left empty, `X-Forwarded-For`
  is ignored and every request is attributed to the proxy's address, which collapses
  per-client rate limits and lockouts into one.
- `ADMIN_PASSWORD_FILE`: path to a file holding the admin password (optional). Unset,
  the admin area is disabled and every `/api/admin` route answers 404. Set to a missing
  or empty file, or a password shorter than 16 characters, boot fails.
- `ADMIN_ALLOWED_CIDRS`: comma-separated networks allowed to reach `/api/admin`
  (default `192.168.0.0/16,127.0.0.1/32,::1/128`). Other clients get a 404 before the
  password is checked ([ADR-0009](docs/adr/0009-lan-only-admin.md)).
- Rate limits are counted in process, so the app must run as a single replica.

## Decisions

Architecture decisions are numbered records in `docs/adr/`. Read the relevant one
before proposing an approach it may already have rejected.
