# AGENTS.md

This file is the single source of truth for agent and contributor
instructions in this repository. `CLAUDE.md` intentionally contains only a
pointer here — do not duplicate guidance between the two files, or they will
drift apart.

---

## Project Overview

A modern web application for receiving, storing, and browsing
[Shoutrrr](https://containrrr.dev/shoutrrr/) notifications.

- Backend API: FastAPI (Python — see `backend/pyproject.toml` for the
  supported range; currently `>=3.12`, CI exercises 3.14)
- Database: PostgreSQL 17 in production, SQLite in the test harness
- ORM: SQLAlchemy 2.x (async)
- Migrations: Alembic (`backend/migrations/`)
- Authentication: OpenID Connect (OIDC), Keycloak as the reference provider
- Frontend: Next.js 16 (App Router) + React 19 + TypeScript 5.7 strict
- Internationalization: next-intl
- Package managers: `uv` (backend), `pnpm` (frontend, workspace-rooted)
- Containerization: Docker; reverse proxy via Nginx or Traefik

When generating code, documentation, tests, migrations, or configuration,
always follow the conventions defined in this document.

---

## Agent Mission Control & Terminal Commands

### Virtual environments — read this first

There are **two** venv locations, and which one you use depends on where you
run the command from. This trips people up constantly:

| Venv | Created by | Used for |
| --- | --- | --- |
| `backend/.venv` | local dev + the CI pytest/alembic jobs (`working-directory: backend`) | pytest, alembic, uvicorn, gunicorn, and ruff |
| `.venv` (repo root) | the CI ruff job only (a throwaway `python -m venv .venv` + `pip install ruff`) | ruff, in CI |

**Locally, only `backend/.venv` exists.** There is no root `.venv` unless you
create one yourself. So the ruff invocations below are written for the local
layout; CI's root-venv form is equivalent, not different guidance.

The simplest path is to skip the venv paths entirely and use the Makefile
targets (`make lint`, `make test`) — they wrap the exact CI commands.

### Backend (Python / uv)

All Python packages must be installed into the virtual environment, and all
backend scripts must be executed via that venv's binaries. Never invoke a
bare `pytest` / `ruff` / `alembic` that might resolve to a system install.

- Install dependencies: `cd backend && uv sync --extra test`
- Run local dev server: `cd backend && .venv/bin/uvicorn main:app --reload`
- Production (container) entrypoint:
  `cd backend && .venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app`
- Run tests: `cd backend && .venv/bin/pytest tests/ -v --tb=short`
- Lint: `backend/.venv/bin/ruff check backend/` (from the repo root)
- Format check:
  `backend/.venv/bin/ruff format --check backend/ --exclude backend/build/`

Note the ruff commands take a path **relative to the repo root**. Running
`cd backend && .venv/bin/ruff check backend/` fails with `E902 No such file
or directory` — after the `cd` there is no `backend/` to lint. From inside
`backend/`, use `.venv/bin/ruff check .`, or the `uv run` form that
`CONTRIBUTING.md` documents:

```bash
cd backend
uv run ruff check .            # lint
uv run ruff check --fix .      # lint + auto-fix
uv run ruff format .           # format in place
uv run ruff format --check .   # format check only (what CI runs)
```

A pre-commit hook that auto-formats and re-stages backend Python files ships
in `scripts/pre-commit`; see `CONTRIBUTING.md` for installation.

### Frontend (Node / pnpm)

The pnpm workspace is rooted at the **repository root** (`pnpm-workspace.yaml`
declares `packages: ["frontend"]`), so `pnpm-lock.yaml` and the dependency
`overrides` block live at the root, not in `frontend/`.

- Install dependencies: `pnpm install --frozen-lockfile` (from the repo root)
- Run local dev server: `cd frontend && pnpm dev`
- Build application: `cd frontend && pnpm build`
- Run tests: `cd frontend && pnpm test:run`
- Coverage: `cd frontend && pnpm test:cov`
- Lint: `cd frontend && pnpm lint`
- Type-check: `cd frontend && pnpm typecheck` (alias for `pnpm exec tsc --noEmit`)
- i18n parity: `cd frontend && pnpm i18n:check`

**Strict guardrail:** Never use `npm` or `yarn`. Never bypass `uv` for backend
package management. Always use the venv for backend execution, and strictly
match the CI lint/test commands.

### Security advisories and dependency overrides

Transitive vulnerabilities are resolved with a pinned `overrides` entry in the
root `pnpm-workspace.yaml`, each documented with the advisory ID and the reason
in the comment block directly above the `overrides:` key. Follow that pattern
when clearing a new Dependabot alert; if a patched version resolves naturally,
record that too (see the `sharp` note) rather than adding a redundant pin.

Expect a large `pnpm-lock.yaml` diff for even a one-line override: pnpm
rewrites peer-dependency keys whenever it re-resolves. Verify the real change
by diffing with the peer-key suffixes normalized out before assuming something
unintended moved.

---

## Workspace Layout

Agents must respect the following multi-surface codebase boundaries.

### Backend workspace (`backend/`)

```text
backend/
├── middleware/          # ASGI middleware (performance instrumentation)
├── migrations/          # Alembic environment + versions/ (NOT "alembic/")
├── plugins/             # Notification backends — one package per service
│   ├── base.py          # Plugin ABC
│   ├── registry.py      # Plugin discovery/registration
│   ├── discord/  gotify/  matrix/  ntfy/  pagerduty/  pushover/
│   └── slack/  splunk/  teams/  telegram/  webhook/
├── repositories/        # ALL database access lives here
├── routers/             # Thin FastAPI route handlers
├── services/            # Business logic
├── tests/               # pytest suite (+ tests/plugins/)
├── utils/               # sanitize, ssrf, templates, search parser/compiler
├── alembic.ini          # script_location = %(here)s/migrations
├── auth.py
├── config.py
├── database.py
├── logging_config.json
├── main.py
├── models.py
├── pyproject.toml
├── schemas.py
├── uv.lock
└── version.py
```

### Frontend workspace (`frontend/`)

```text
frontend/
├── app/
│   └── [locale]/        # ALL routes are nested under this locale segment
│       ├── about/  admin/  alerts/  log/  performance/  stats/
├── components/          # Feature components
│   └── ui/              # shadcn/ui primitives
├── hooks/
├── i18n/                # next-intl request.ts + routing.ts
├── lib/                 # api.ts (the ONLY data-access entrypoint), auth-context, utils
├── messages/            # en.json, no.json — app-level locale catalogs
├── plugins/             # Per-plugin config UI, mirrors the backend plugin set
│   ├── registry.tsx  types.ts
│   ├── discord/  gotify/  matrix/  ntfy/  pagerduty/  pushover/
│   └── slack/  splunk/  teams/  telegram/  webhook/
├── public/
├── scripts/             # i18n-report.mjs (backs `pnpm i18n:check`)
├── tests/               # Vitest suite — components/, lib/, setup.ts
├── types/               # messages.d.ts — compile-time i18n key typing
├── components.json
├── eslint.config.mjs
├── next.config.mjs
├── package.json
├── postcss.config.mjs
├── proxy.ts
├── tsconfig.json
└── vitest.config.ts
```

Repo-root files of note: `pnpm-workspace.yaml` (workspace + dependency
overrides), `pnpm-lock.yaml`, `Makefile`, `docker-compose.yml`,
`docker-entrypoint.sh`, `Dockerfile`.

---

## Code Generation Guardrails & Design Patterns

### 1. Backend & Async SQLAlchemy 2.x Standards

- Dependency Injection: Always use FastAPI `Depends()` for dependencies.
- Architecture Layering: Keep API route handlers thin. Business logic belongs in services; raw database access belongs exclusively in Repositories. Never place raw SQL or inline queries inside route handlers.
- Type Safety: Apply explicit Python type hints everywhere.
- Async Sessions: All database calls must use async sessions.
- Query Syntax: Use modern SQLAlchemy 2.x declarative models and explicit selection statements.
- Prefer composition over inheritance.
- Dialect portability: the test harness runs on SQLite while production is PostgreSQL. Do not hardcode a single dialect's constructs (e.g. importing `sqlalchemy.dialects.postgresql.insert` for `on_conflict_do_update`) inline in business logic — it silently becomes postgres-only and untestable. Encapsulate such writes in a Repository method that selects the right dialect's `insert` at runtime (via `session.get_bind().dialect.name`) so the path is exercised by tests. Keep these in repositories, never in route handlers.

```python
# PREFERRED SELECT PATTERN
stmt = select(User)
result = await session.execute(stmt)

# FORBIDDEN PATTERN (Do not generate)
# session.query(User)
```

Repositories encapsulate database operations:

```python
class UserRepository:
    async def get_by_id(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> User | None:
        ...
```

- Database Schema Rules:
  - Primary keys must be explicitly mapped as UUIDs defaulting to `uuid4`.
  - Enforce server-side timestamps, explicit foreign keys, and indexes for frequently queried columns.
  - Eager-load relations where appropriate to proactively eliminate N+1 query bugs.

```python
# Example Model Primary Key
id: Mapped[UUID] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid4,
)
```

### 2. Database Migrations (Alembic)

Migrations live in `backend/migrations/` (not `alembic/`); `alembic.ini` sets
`script_location = %(here)s/migrations`.

- Every schema modification requires a separate Alembic migration file.
- Never modify a migration that has shipped in a tagged release (it would
  diverge already-migrated databases). Migrations still in `[Unreleased]` may be
  corrected in place when that is cleaner than stacking a patch migration.
- Autogenerate migrations from changes to SQLAlchemy models, but review the
  generated script for consistency before final execution.
- Migrations are applied automatically by the application at container startup
  (`docker-entrypoint.sh` runs `alembic upgrade head` before the servers start).
  A release must NEVER require a manual migration step at deploy time.
- **CI enforces migration health.** The "Alembic migrations (PostgreSQL)" job
  runs `alembic upgrade head`, then `alembic check` for model/migration drift,
  then verifies a `downgrade` → re-`upgrade` round-trip. A model change without
  a matching migration fails `alembic check` even though every pytest test
  passes.
- **Defensive existence checks are mandatory.** `init_db()` builds fresh
  databases at *head* schema via `create_all()` but stamps *baseline*, so
  `alembic upgrade head` replays every post-baseline migration over an
  already-current schema (this is the `AUTO_MIGRATE=false` / out-of-band path).
  Guard every operation with `_has_table` / `_has_column` / index-existence
  helpers (see `4b9e0d21c6aa`) so a re-run is a no-op, never a
  DuplicateTable/DuplicateColumn crash.
- **Guard data migrations on the columns they actually read/write**, not a proxy
  column. A later migration can re-add a same-named column for an unrelated
  purpose and make a proxy guard misfire (this caused a real
  `create_all`-path crash).
- **Adding or narrowing a UNIQUE index/constraint must first de-duplicate
  existing data** in the same migration (aggregate/merge, then delete), or the
  index creation aborts startup with a `UniqueViolation` on real data. An empty
  test database will not reveal this.
- **Nullable columns in a UNIQUE index:** PostgreSQL treats NULLs as *distinct*,
  so `ON CONFLICT` upserts never match for NULL-keyed rows and rows accumulate.
  Keep nullable columns out of the conflict key, or use `NULLS NOT DISTINCT`.
- **Validate migrations against real PostgreSQL — the test suite does not.** The
  pytest harness uses SQLite and runs `create_all()`, so it never executes
  migration files. Before committing a migration, run it on a throwaway
  PostgreSQL on all three paths: (1) empty DB → `upgrade head` → `alembic check`
  (no drift); (2) `init_db()` (create_all + stamp baseline) → `upgrade head`;
  (3) seed representative *existing* data (including the duplicates/edge cases a
  new constraint must tolerate) → `upgrade head`. Confirm `downgrade base` →
  `upgrade head` round-trips.

### 3. API & Response Formatting

- REST routing style: `/api/v1/users`, `/api/v1/groups`, `/api/v1/projects`
- Serialization: All endpoints must validate inputs and outputs using Pydantic models. Never return raw SQLAlchemy ORM objects directly over the wire.
- Use Pydantic models for requests, responses, and configuration.
- Error schemas: Use structured JSON objects for errors coupled with accurate HTTP status codes:

```json
{ "detail": "Resource not found" }
```

### 4. Authentication & Keycloak OIDC Standards

- Flow: Enforce Authorization Code Flow with PKCE.
- Token Verification: The backend must explicitly validate JWT signatures, issuer, audience, and expiration. Never trust client-asserted roles without cryptographic validation.
- RBAC/Group Auth: Extract claims from the specified namespace (default: `realm_access.roles`). Authorization must be entirely role- or group-based. Avoid hardcoding granular string-permissions or using user ID/username-based access gates. Use Keycloak realm roles, client roles, and groups.
- Token Claims Structure:

```json
{
  "sub": "...",
  "preferred_username": "...",
  "email": "...",
  "realm_access": { "roles": ["admin"] }
}
```

- FastAPI dependency enforcement — these are the **actual** dependencies
  defined in `backend/auth.py`. There is no `get_current_user` or
  `require_role(...)`:

```python
current_user = Depends(get_current_user_from_session)
admin_user   = Depends(require_admin)
viewer_user  = Depends(require_viewer)
```

### 5. Frontend (Next.js 16 & TypeScript) Rules

- Plugin UI Guardrails: Test buttons in plugin config panels MUST be `size="sm"` and left-aligned below a `<Separator />` within a `<div className="flex items-center gap-4 py-3">`. They must use the primary variant (default), match the exact styling of the Save changes button, and report test states uniformly via a `<CheckCircle2 />` or `<XCircle />` coupled with `testSuccess` / `testFailed` localized text.
- Architecture: Enforce Next.js App Router conventions. Default to Server Components; explicitly mark Client Components using `'use client'` only when state hook interaction or client-specific APIs are required. All routes live under the `app/[locale]/` segment.
- TypeScript Strictness: `"strict": true` is non-negotiable. Never inject `any` types. Provide explicit function return types. Treat interfaces as the standard for defining contract/DTO objects.
- Data Access Layer: Direct `fetch` calls scattered through subcomponents are strictly forbidden. All data queries must go through a centralized client wrapper (`lib/api.ts`) managing centralized headers, errors, and silent token refresh logic.
- Client Security: Use OIDC Authorization Code Flow with PKCE via safe libraries (openid-client, oidc-client-ts, or NextAuth where appropriate). Never store access/refresh tokens inside localStorage. Ensure silent token refresh runs securely over HTTPS with HTTP-only cookies protected against CSRF vulnerabilities.
- Internationalization (i18n): All user-facing text is localized with next-intl. Never hardcode user-facing strings — resolve them via `useTranslations`/`getTranslations` and a message key. Every new key MUST be added to all locale files under `frontend/messages/` (currently `en.json` and `no.json`) at full key parity; `en.json` is the source of truth. Plugin strings live in `frontend/plugins/<id>/locales/<locale>.json`, namespaced `Plugin_<id>`. This applies to labels, placeholders, button text, toasts, errors, `aria-label`s, empty states, and dialog copy. Verify locale key parity before committing by running `pnpm i18n:check` from `frontend/` (fails on parity gaps and on `t()` references to undefined keys; `--all` adds advisory unused-key and hardcoded-string scans). Message keys are also typed at compile time via `frontend/types/messages.d.ts` — referencing an unknown key is a `tsc` error; when adding a plugin with its own `locales/en.json`, add a `Plugin_<id>: typeof import("../plugins/<id>/locales/en.json")` line there. See `TRANSLATING.md`.

---

## Testing & Quality Check Gates

Before considering a task finished, run the sweeps below. `make lint` and
`make test` run all of them in the same form CI does.

CI (`.github/workflows/lint.yml`) enforces six jobs: Backend (ruff), Backend
tests (pytest), Alembic migrations (PostgreSQL), Frontend (ESLint + tsc),
Frontend tests (vitest), and CodeQL.

### Backend testing target: min 80% coverage

- Frameworks: pytest, pytest-asyncio, and httpx.
- Coverage structure: unit tests for business services, integration tests for SQLAlchemy repositories, end-to-end API automation for endpoint validation.
- The harness runs on SQLite via `create_all()` — it does **not** execute
  migration files. See the Alembic section for what that misses.

### Frontend testing target

- Frameworks: Vitest with React Testing Library.
- Coverage structure: component isolated tests, hook operational tests, and simulated OIDC authentication flow checks.

---

## System Security & Environment Boundaries

Always validate all inputs, use parameterized SQL, escape untrusted content,
enforce HTTPS, and apply least privilege.

### Variables Management

Agents must use system environment variables instead of configuration constants. Never commit production credentials, access secrets, or raw keys into version control.

Required environment keys mapped within the project runtime:

```text
DATABASE_URL=postgresql+asyncpg://postgres:CHANGEME@localhost:5432/shoutrrr_logger
POSTGRES_PASSWORD=CHANGEME
OIDC_DISCOVERY_URL=
OIDC_CLIENT_ID=shoutrrr-logger
OIDC_CLIENT_SECRET=
APP_BASE_URL=http://localhost:4000
OIDC_ROLES_CLAIM=realm_access.roles
OIDC_ROLE_VIEWER=viewer
OIDC_ROLE_ADMIN=admin
OIDC_SCOPES=openid email profile roles
SECRET_KEY=
WORKERS=4
BACKEND_URL=http://localhost:9000
```

### Log Integrity

Logs generated by code must be structured formats containing a unique Request ID, User ID, Timestamp, and standard Log Level. Strict Guardrail: Never log user passwords, PII, tokens, or encryption secrets.

---

## Version Control & Workflow

### Git Commit Strategy

Agents must commit their changes frequently and granularly. Avoid monolithic, "massive" commits that encompass multiple unrelated features or fixes.
Follow these guidelines:

- Commit immediately after successfully implementing a single logical feature, fixing a bug, or completing a refactor.
- Ensure that `CHANGELOG.md` and `README.md` are updated in the same commit as the feature or fix they document. Whenever you make a new commit or changes, update `CHANGELOG.md` under the "Unreleased" section with the details of your modifications.
- Use Conventional Commits formatting for messages (e.g., `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).
- Run relevant tests and verify that the build passes before committing.
- You must run the ruff lint and format checks via the venv before every commit
  to enforce CI compliance — `make lint` is the shortest path; the explicit
  form is `backend/.venv/bin/ruff check backend/` and
  `backend/.venv/bin/ruff format --check backend/ --exclude backend/build/`
  from the repo root.
- Clean up throwaway scratch/debug artifacts once they've served their purpose — one-off probe scripts, ad-hoc `test_*.py` / `test*.js` files at the repo root, REPL dumps, etc. They must never be committed or left behind in the working tree. Only real, committed tests belong under `backend/tests/` and `frontend/tests/`. Verify the working tree is free of such debris before finishing a task.
