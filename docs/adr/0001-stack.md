# 0001. Technology stack

- Status: accepted
- Date: 2026-10-13

## Context
math-quest needs to check free-form math answers, including form requirements such
as "lowest terms" or "factored", and to generate problems on demand from a skill
graph. It serves children on shared and low-end devices, stores minimal data, and
runs as a single small service on self-hosted infrastructure.

## Decision
- **Backend:** Python 3.13 with FastAPI and pydantic v2. Python gives access to
  SymPy for symbolic comparison, and FastAPI gives typed request validation.
- **Math engine:** SymPy 1.14 for algebra and equivalence. SymPy never sees raw
  learner input; the project's own parser produces an unevaluated tree first (see
  ADR 0002).
- **Database:** PostgreSQL 16 through async SQLAlchemy 2 and asyncpg, with Alembic
  migrations.
- **Credentials:** PINs, picture passwords and recovery words are stored as argon2
  hashes.
- **Frontend:** SvelteKit with Svelte 5 and TypeScript 6, built as a static
  single-page app with adapter-static. MathLive provides math input and emits LaTeX.
- **Tooling:** uv, ruff, pyright and import-linter on the backend; vitest,
  Playwright and dependency-cruiser on the frontend.
- **Delivery:** GitHub Actions for CI; one container image published to GHCR and
  tagged by commit, never `:latest`.

The backend and frontend each follow a layered layout with downward-only imports,
checked in CI.

## Alternatives rejected
- **TypeScript backend with a JavaScript CAS.** One language across the stack is
  attractive, but JavaScript algebra systems are far less capable than SymPy for
  the equivalence and simplification checks this game depends on.
- **Server-rendered pages instead of a single-page app.** The math input and the
  game map are interactive, and a static bundle is simpler to host and cache.
- **SQLite.** Simpler to operate, but the project expects concurrent writes from
  many sessions and wants a conventional migration and backup story.
- **Storing PINs with a fast hash.** A 4-digit PIN has very little entropy, so the
  hash is slow by design and attempts are rate limited per player, device and
  address.

## Consequences
Two toolchains to maintain, kept consistent by CI. SymPy is a heavy dependency, so
all checking work is bounded in input length and time. Static hosting of the
frontend keeps deployment to a single image.
