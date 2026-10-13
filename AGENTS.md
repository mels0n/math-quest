# Contributing to math-quest

How to build, check and navigate the code.

## Build, test, lint

Backend (run in `backend/`; needs Python 3.13+ and uv):

- Install: `uv sync`
- Test: `uv run pytest` (database tests need `docker compose -f compose.dev.yml up -d`)
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
    engine/     pure problem engine (types, skill graph, generators, checker, mastery)
  content/      skill packs and word lists
  migrations/   Alembic revisions
  tests/
frontend/
  src/routes/   thin SvelteKit routes; import only from pages
  src/app, pages, widgets, features, entities, shared
docs/           tutorials, how-to, reference, explanation, adr
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

## Decisions

Architecture decisions are numbered records in `docs/adr/`. Read the relevant one
before proposing an approach it may already have rejected.
