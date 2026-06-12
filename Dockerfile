# syntax=docker/dockerfile:1

# ============================================================
# Stage 1 – Build the Next.js frontend
# ============================================================
FROM node:24-alpine AS frontend-builder

# `frontend/` is a member of the pnpm workspace rooted here — install MUST
# run from the workspace root. Installing from frontend/ alone makes pnpm
# treat it as a standalone project: it ignores pnpm-workspace.yaml (and the
# `overrides` pin that keeps postcss off the vulnerable 8.4.x line bundled by
# next/autoprefixer, GHSA-qx2v-qp2m-jg93) and ends up resolving against
# frontend/'s own stale, untested lockfile instead of the real one.
WORKDIR /build

# Enable corepack so it reads packageManager from package.json automatically
RUN corepack enable

# Copy workspace manifests first — this layer is cached independently of
# source changes. corepack activates the pinned pnpm version declared in
# the workspace root package.json's "packageManager" field.
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend/package.json frontend/

# Install deps. --frozen-lockfile enforces lockfile integrity; the fallback
# catches the rare case where the lockfile is slightly out of sync after a
# shadcn component add without a manual `pnpm install` run. The cache mount
# persists pnpm's content-addressable store across builds so unchanged
# dependencies are linked from cache instead of re-downloaded.
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    corepack prepare --activate \
    && pnpm install --frozen-lockfile \
    || pnpm install --no-frozen-lockfile

# Copy the rest of the frontend source
COPY frontend/ frontend/

# Build – output a standalone bundle for minimal image size
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN pnpm --filter frontend build

# ============================================================
# Stage 2 – Python dependency wheel cache
# ============================================================
FROM python:3.14-slim AS python-deps

WORKDIR /build

# Install build tools needed to compile some wheels (bcrypt, asyncpg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./

# Build wheels into a dedicated directory for clean copying. The dependency
# list is read from pyproject.toml's [project] dependencies — the single
# source of truth — instead of being duplicated here. The cache mount
# persists pip's download/build cache across builds so unchanged dependencies
# don't get re-downloaded and re-compiled every time.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && python -c 'import tomllib, pathlib; deps = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]; pathlib.Path("requirements.txt").write_text("\n".join(deps))' \
    && echo "==> runtime dependencies:" && cat requirements.txt \
    && pip wheel --wheel-dir=/wheels -r requirements.txt

# ============================================================
# Stage 3 – Final runtime image
# ============================================================
FROM python:3.14-slim AS runtime

# Minimal system runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    nodejs \
    # curl for health-checks
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user. Both servers bind unprivileged ports (4000/9000)
# and only log to stdout, so nothing needs root at runtime.
RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

# Install Python packages from pre-built wheels (no compiler needed)
COPY --from=python-deps /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels

# Build-time version metadata — injected by docker-compose automatically:
#   GIT_HASH: ${GIT_HASH} resolved in the shell before compose passes it in
#   BUILD_TIME: ${BUILD_TIME} same
# Or pass explicitly with plain docker build:
#   docker build --build-arg GIT_HASH=$(git rev-parse --short HEAD) .
ARG GIT_HASH=dev
ARG BUILD_TIME=
ARG APP_VERSION=dev

LABEL org.opencontainers.image.title="shoutrrr-logger" \
      org.opencontainers.image.description="Self-hosted notification logging service for shoutrrr" \
      org.opencontainers.image.url="https://github.com/tolecnal/shoutrrr-logger" \
      org.opencontainers.image.source="https://github.com/tolecnal/shoutrrr-logger" \
      org.opencontainers.image.documentation="https://github.com/tolecnal/shoutrrr-logger#readme" \
      org.opencontainers.image.revision="${GIT_HASH}" \
      org.opencontainers.image.created="${BUILD_TIME}" \
      org.opencontainers.image.version="${APP_VERSION}"

# ---- Backend ----
WORKDIR /app/backend
COPY --chown=app:app backend/ ./

# Generate _version_meta.py so version.py can import it at runtime.
RUN RESOLVED_HASH="${GIT_HASH:-dev}" \
    && BUILD_TIME_VAL="${BUILD_TIME:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}" \
    && printf 'BUILD_GIT_HASH = "%s"\nBUILD_TIME = "%s"\n' "${RESOLVED_HASH}" "${BUILD_TIME_VAL}" \
       > _version_meta.py \
    && chown app:app _version_meta.py \
    && echo "==> version metadata:" && cat _version_meta.py

# ---- Frontend (Next.js standalone) ----
# Building from the pnpm workspace root (see frontend-builder above) makes
# Next.js emit the standalone bundle mirroring the workspace layout —
# server.js lands at .next/standalone/frontend/server.js with a hoisted
# node_modules as its sibling, not at the standalone root. Copy the whole
# tree into /app so that relative structure (and Node's module resolution
# walk-up) is preserved, landing server.js at /app/frontend/server.js.
WORKDIR /app
COPY --from=frontend-builder --chown=app:app /build/frontend/.next/standalone ./
COPY --from=frontend-builder --chown=app:app /build/frontend/.next/static ./frontend/.next/static
# Trailing slash on source turns this into a "copy contents if dir exists" –
# Docker will not error if public/ is empty, but the .gitkeep ensures it exists.
COPY --from=frontend-builder --chown=app:app /build/frontend/public/ ./frontend/public/

# Next.js writes its image-optimization/ISR cache here at runtime, and
# gunicorn's control server creates /app/.gunicorn (app's home directory).
RUN mkdir -p /app/frontend/.next/cache \
    && chown app:app /app /app/frontend/.next/cache

# ---- Entrypoint ----
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 4000 9000

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

USER app

ENTRYPOINT ["./docker-entrypoint.sh"]
