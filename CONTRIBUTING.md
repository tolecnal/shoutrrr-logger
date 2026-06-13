# Contributing to shoutrrr-logger

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). For
security vulnerabilities, please follow the [security policy](SECURITY.md)
instead of opening a public issue.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | ≥ 3.12 | [python.org](https://www.python.org/downloads/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | ≥ 22 | [nodejs.org](https://nodejs.org/) |
| pnpm | 10.x | `npm install -g pnpm` |
| Docker + Compose | latest | [docs.docker.com](https://docs.docker.com/get-docker/) |
| ruff | latest | `pip install ruff` or `uv tool install ruff` |

---

## Running the full stack with Docker

The fastest way to get everything running:

```bash
cp .env.example .env          # fill in OIDC_CLIENT_SECRET and SECRET_KEY at minimum
docker compose up --build
```

The app is then available at `http://localhost:4000`.

---

## Backend (FastAPI)

### Setup

```bash
cd backend
uv sync --extra test          # install runtime + test dependencies into a managed venv
cp ../.env.example .env       # or point DATABASE_URL at a local PostgreSQL instance
```

### Running locally

```bash
uv run uvicorn main:app --reload --port 9000
```

The API is served at `http://localhost:9000`. Interactive docs are at `/api/docs`.

### Tests

```bash
uv run pytest                 # all tests
uv run pytest -x              # stop on first failure
uv run pytest --cov=. --cov-report=term-missing   # with coverage
```

### Linting and formatting

```bash
uv run ruff check .           # lint
uv run ruff check --fix .     # lint + auto-fix
uv run ruff format .          # format in place
uv run ruff format --check .  # format check only (what CI runs)
```

CI requires **both** `ruff check` and `ruff format --check` to pass with zero errors on `backend/` (excluding `backend/build/`).

---

## Frontend (Next.js)

### Setup

```bash
cd frontend
pnpm install
```

### Running locally

```bash
pnpm dev                      # starts on http://localhost:4000
```

Set `NEXT_PUBLIC_BACKEND_URL` (or `BACKEND_URL` in `.env`) to point at the running backend.

### Tests

```bash
pnpm test                     # watch mode
pnpm test:run                 # single run
pnpm test:cov                 # with coverage
```

### Linting and type-checking

```bash
pnpm lint                     # ESLint
pnpm exec tsc --noEmit        # TypeScript strict check
```

### Internationalization (i18n)

All user-facing text must be localized with `next-intl`. Never hardcode strings in the UI.

```bash
pnpm i18n:check               # Verify locale key parity across en.json and no.json
```

See `TRANSLATING.md` and `AGENTS.md` for more details on translating the application and writing plugins.

---

## Git hooks

A pre-commit hook that auto-formats and auto-fixes staged backend Python files is included in `scripts/pre-commit`. Install it once:

```bash
cp scripts/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook finds `ruff` by checking (in order):

1. `ruff` on `$PATH`
2. `~/.local/bin/ruff` (uv / pipx install)
3. `~/.local/share/nvim/mason/bin/ruff` (Neovim Mason)

If none of those exist it prints a warning and skips formatting rather than blocking the commit.

---

## Environment variables

Copy `.env.example` to `.env` and fill in the required values:

```text
# Database
DATABASE_URL=postgresql+asyncpg://postgres:CHANGEME@localhost:5432/shoutrrr_logger
POSTGRES_PASSWORD=CHANGEME

# OpenID Connect (Keycloak or any OIDC provider)
OIDC_DISCOVERY_URL=http://localhost:8080/realms/master/.well-known/openid-configuration
OIDC_CLIENT_ID=shoutrrr-logger
OIDC_CLIENT_SECRET=          # required
OIDC_SCOPES=openid email profile roles
OIDC_ROLES_CLAIM=realm_access.roles
OIDC_ROLE_VIEWER=viewer
OIDC_ROLE_ADMIN=admin

# Application
SECRET_KEY=                   # required — generate with: python -c "import secrets; print(secrets.token_hex(32))"
APP_BASE_URL=http://localhost:4000
BACKEND_URL=http://localhost:9000
WORKERS=4
```

---

## Project structure

```
.
├── backend/                  # FastAPI application
│   ├── repositories/         # Database access layer
│   ├── services/             # Business logic layer
│   ├── routers/              # HTTP route handlers (thin)
│   ├── plugins/              # Plugin system (Splunk, …)
│   ├── tests/                # pytest test suite
│   ├── main.py               # Application entry point
│   ├── models.py             # SQLAlchemy ORM models
│   ├── schemas.py            # Pydantic request/response schemas
│   └── pyproject.toml
├── frontend/                 # Next.js application
│   ├── app/                  # App Router pages
│   ├── components/           # React components
│   ├── lib/                  # API client, types, utilities
│   └── package.json
├── scripts/                  # Developer tooling scripts
│   └── pre-commit            # Git pre-commit hook (ruff format + fix)
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

---

## Pull requests

- Keep PRs focused — one concern per PR.
- All CI checks must pass (lint, format, type-check, tests).
- Backend: follow the repository → service → router layering defined in `AGENTS.md`.
- Frontend: use TypeScript strict mode; no `any` types.
- New endpoints need at least a basic pytest test.
