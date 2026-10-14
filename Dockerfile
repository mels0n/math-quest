# syntax=docker/dockerfile:1

FROM node:24-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --frozen --no-dev

FROM python:3.13-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONTENT_DIR=/app/content \
    STATIC_DIR=/app/static \
    DATABASE_URL_FILE=/run/secrets/mq_database_url \
    INITIAL_SIGNUP_WORD_FILE=/run/secrets/mq_signup_word
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin mathquest
WORKDIR /app
COPY --from=backend /app/.venv ./.venv
COPY --from=backend /app/src ./src
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/content ./content
COPY --from=frontend /build/build ./static
USER mathquest
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn mathquest.app.main:create_app --factory --host 0.0.0.0 --port 8000 --no-proxy-headers"]
