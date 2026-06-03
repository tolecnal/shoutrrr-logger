# ============================================================
# Stage 1 – Build the Next.js frontend
# ============================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend

# Enable corepack so it reads packageManager from package.json automatically
RUN corepack enable

# Copy dependency manifests first — corepack will activate the pinned pnpm
# version declared in package.json's "packageManager" field
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install deps. --frozen-lockfile enforces lockfile integrity; the fallback
# catches the rare case where the lockfile is slightly out of sync after a
# shadcn component add without a manual `pnpm install` run.
RUN corepack prepare --activate \
    && pnpm install --frozen-lockfile \
    || pnpm install --no-frozen-lockfile

# Copy the rest of the frontend source
COPY frontend/ ./

# Build – output a standalone bundle for minimal image size
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN pnpm build

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

# Build wheels into a dedicated directory for clean copying
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir=/wheels \
        "fastapi[standard]>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "gunicorn>=23.0.0" \
        "asyncpg>=0.30.0" \
        "sqlalchemy[asyncio]>=2.0.0" \
        "alembic>=1.14.0" \
        "python-jose[cryptography]>=3.3.0" \
        "httpx>=0.28.0" \
        "python-multipart>=0.0.20" \
        "pydantic-settings>=2.7.0"

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

# Install Python packages from pre-built wheels (no compiler needed)
COPY --from=python-deps /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels

# ---- Backend ----
WORKDIR /app/backend
COPY backend/ ./

# ---- Frontend (Next.js standalone) ----
WORKDIR /app/frontend
COPY --from=frontend-builder /build/frontend/.next/standalone ./
COPY --from=frontend-builder /build/frontend/.next/static ./.next/static
# Trailing slash on source turns this into a "copy contents if dir exists" –
# Docker will not error if public/ is empty, but the .gitkeep ensures it exists.
COPY --from=frontend-builder /build/frontend/public/ ./public/

# ---- Entrypoint ----
WORKDIR /app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 4000 9000

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

ENTRYPOINT ["./docker-entrypoint.sh"]
