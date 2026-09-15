# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Ztech Sales - single image serving the API and the compiled interface from
# the same origin, so session cookies and CSRF protection apply to every
# request with no cross-origin configuration at all.
#
# The same image runs the web process and the outbox worker; the command
# decides which. There is one image per release, never one per client: client
# differences are supplied entirely through the environment.
# ---------------------------------------------------------------------------

# --- Stage 1: compile the interface ----------------------------------------
FROM node:22-bookworm-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# --- Stage 2: resolve Python dependencies from the lockfile ----------------
FROM python:3.12-slim-bookworm AS python-deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv

WORKDIR /app
# Dependencies are installed from uv.lock with --frozen, so a build can never
# silently resolve a different version than the one that was tested.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev


# --- Stage 3: runtime ------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/*

# The application never runs as root.
RUN groupadd --system --gid 1001 ztech \
    && useradd --system --uid 1001 --gid ztech --create-home ztech

WORKDIR /app

COPY --from=python-deps /app/.venv /app/.venv
COPY backend/ /app/
COPY --from=frontend /build/dist /app/frontend-dist

# Private attachment storage lives outside anything the web server publishes.
RUN mkdir -p /var/lib/ztech-sales/private /app/staticfiles \
    && chown -R ztech:ztech /var/lib/ztech-sales /app/staticfiles

# Collected at build time so the running container needs no write access to it.
RUN DJANGO_SECRET_KEY=build-only \
    DJANGO_ALLOWED_HOSTS=localhost \
    DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost \
    ATTACHMENT_SCANNER=none \
    python manage.py collectstatic --noinput --clear

COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER ztech
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/system/health/ || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["web"]
