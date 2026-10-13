# math-quest

## What this is
An adaptive math game for kids, roughly kindergarten through algebra. Each child
picks their own path across a map of math regions. The game finds their level,
teaches new ideas as they unlock them, and brings old skills back for review. It
collects no personal data: players have a nickname and a PIN or picture password,
nothing else.

The backend is a FastAPI service with a SymPy-based problem engine and answer
checker. The frontend is a SvelteKit single-page app with MathLive for math input.

## Run locally
Requirements: Python 3.13+ with [uv](https://docs.astral.sh/uv/), Node 24, Docker.

```bash
docker compose -f compose.dev.yml up -d   # Postgres 16 for development and tests

cd backend
uv sync
uv run pytest

cd ../frontend
npm ci
npm run dev
```

Checks run in CI and can be run locally:

- Backend (in `backend/`): `uv run ruff check`, `uv run pyright`, `uv run lint-imports`, `uv run pytest`
- Frontend (in `frontend/`): `npm run check`, `npm run depcruise`, `npm test`, `npm run build`

## Deploy
Pushes and pull requests run the CI workflow in `.github/workflows/ci.yml`
(lint, typecheck, import-boundary checks, tests, build). The application ships as a
single container image tagged with the commit (`sha-<12 chars>`), never `:latest`.

## Where secrets live
Configuration comes from environment variables read in one place,
`mathquest.shared.config`. Local values go in a gitignored `.env` file. In deployment, the database password
and admin credential are supplied as container secrets. The Postgres credentials
in `compose.dev.yml` are for local development only.
