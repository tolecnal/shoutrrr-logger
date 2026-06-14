# CLAUDE.md

## Project Overview

This project is a modern web application consisting of:

- Backend API: FastAPI (Python 3.13+)
- Database: PostgreSQL 17
- ORM: SQLAlchemy 2.x (async)
- Authentication: OpenID Connect (OIDC)
- Identity Provider: Keycloak
- Frontend: Next.js 16
- Package Manager: pnpm
- API Communication: REST over HTTPS
- Containerization: Docker
- Reverse Proxy: Nginx or Traefik

When generating code, documentation, tests, migrations, or configuration, always follow the conventions defined in this document.

---

# Architecture

## Backend

The FastAPI backend is responsible for:

- Business logic
- Authentication and authorization
- Database access
- Background tasks
- Audit logging
- REST API endpoints

### Backend Directory Layout

```text
├── plugins
│   └── splunk
├── routers/
|-- tests/
├── auth.py
├── config.py
├── database.py
├── main.py
├── models.py
├── pyproject.toml
├── schemas.py
├── uv.lock
└── version.py
```

### Design Principles

- Use dependency injection via FastAPI Depends.
- Keep API routes thin.
- Place business logic in services.
- Place database access in repositories.
- Never place SQL queries directly inside route handlers.
- Prefer composition over inheritance.
- Use type hints everywhere.
- Use uv for Python package Management
- uvicorn for running locally
- use gunicorn for production (Docker Containerization)

---

# Database Standards

## PostgreSQL

Version: PostgreSQL 17

### Rules

- Use SQLAlchemy 2.x style syntax.
- Use async database sessions.
- Use UUID primary keys.
- Use server-side timestamps where possible.
- Use explicit foreign key constraints.
- Use database indexes for frequently queried columns.
- Avoid N+1 queries.
- Use eager loading when appropriate.

### Example Primary Key

```python
id: Mapped[UUID] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid4,
)
```

### Migrations

Use Alembic.

Rules:

- Every schema change requires a migration.
- Never modify existing migrations.
- Generate migrations from model changes.
- Review generated migrations before committing.
- Migrations are applied automatically by the application at container
  startup (docker-entrypoint.sh runs `alembic upgrade head`). A release must
  NEVER require a manual migration step at deploy time.

---

# SQLAlchemy Standards

Use SQLAlchemy 2.x declarative models.

Preferred pattern:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID]
    username: Mapped[str]
```

Avoid:

```python
session.query(User)
```

Use:

```python
stmt = select(User)
result = await session.execute(stmt)
```

Repositories should encapsulate database operations.

Example:

```python
class UserRepository:
    async def get_by_id(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> User | None:
        ...
```

---

# API Standards

## REST Design

Use:

```text
/api/v1/users
/api/v1/groups
/api/v1/projects
```

### Response Models

All endpoints should return Pydantic models.

Never return ORM objects directly.

### Validation

Use Pydantic models for:

- Requests
- Responses
- Configuration

### Error Handling

Use structured responses:

```json
{
  "detail": "Resource not found"
}
```

Use appropriate HTTP status codes.

---

# Authentication

## OIDC

Authentication is handled through OpenID Connect.

Preferred Identity Provider:

Keycloak

### Requirements

- Authorization Code Flow with PKCE
- JWT access tokens
- Refresh tokens
- Role-based access control (RBAC)
- Group-based authorization support

### Backend Validation

The FastAPI backend must:

- Validate JWT signatures
- Validate issuer
- Validate audience
- Validate expiration
- Extract roles from token claims

Never trust client-provided role information.

### Expected Claims

```json
{
  "sub": "...",
  "preferred_username": "...",
  "email": "...",
  "realm_access": {
    "roles": ["admin"]
  }
}
```

### Authorization Pattern

Use dependencies:

```python
current_user = Depends(get_current_user)
```

and

```python
Depends(require_role("admin"))
```

---

# Keycloak Standards

Assume Keycloak is the default OIDC provider.

Use:

- Realm roles
- Client roles
- Groups

Avoid:

- Hardcoded permissions
- Username-based authorization

All authorization should be role or group based.

---

# Frontend

## Next.js

Version: Next.js 16

### Requirements

- App Router
- Server Components by default
- Client Components only when necessary
- TypeScript strict mode
- Plugin UI Guardrails: Test buttons in plugin config panels MUST be `size="sm"` and left-aligned below a `<Separator />` within a `<div className="flex items-center gap-4 py-3">`. They must use the primary variant (default), match the exact styling of the Save changes button, and report test states uniformly via a `<CheckCircle2 />` or `<XCircle />` coupled with `testSuccess` / `testFailed` localized text.

### Directory Layout

```text
├── app
│   ├── about
│   ├── admin
│   └── log
├── components
│   └── ui
├── hooks
├── lib
├── plugins
│   └── splunk
├── public
└── tests
|    └── lib
├── components.json
├── eslint.config.mjs
├── next.config.mjs
├── package.json
├── pnpm-lock.yaml
├── postcss.config.mjs
├── tsconfig.json
└── vitest.config.ts
```

## Internationalization (i18n)

All user-facing text is localized with **next-intl**. This is a hard
requirement for every change that adds or edits UI strings:

- Never hardcode user-facing strings in components. Use `useTranslations`
  (client) or `getTranslations` (server) and reference a message key.
- Add each new key to **every** locale file in `frontend/messages/`
  (currently `en.json` and `no.json`). The catalogs must stay at full key
  parity — no missing or extra keys between locales. `en.json` is the source
  of truth; translate the others.
- Plugin-specific strings live in that plugin's
  `frontend/plugins/<id>/locales/<locale>.json` and are namespaced as
  `Plugin_<id>`.
- This covers everything a user can read: labels, placeholders, button text,
  toasts, error messages, `aria-label`s, empty states, and dialog copy.
- Verify locale key parity before committing. Run `pnpm i18n:check` (from
  `frontend/`) — it fails on parity gaps and on `t()` references to undefined
  keys. `pnpm i18n:check --all` adds advisory unused-key and hardcoded-string
  scans. See `TRANSLATING.md`.
- next-intl message keys are typed at compile time via
  `frontend/types/messages.d.ts` (referencing an unknown key is a `tsc` error).
  When adding a plugin with its own `locales/en.json`, add a
  `Plugin_<id>: typeof import("../plugins/<id>/locales/en.json")` line there or
  its `t()` calls won't type-check.

---

# Frontend Data Access

Use a dedicated API client.

Example:

```typescript
lib / api.ts;
```

Do not perform direct fetch calls throughout the application.

Centralize:

- Authentication
- Error handling
- Retry logic

---

# Authentication in Frontend

Use OIDC Authorization Code Flow with PKCE.

Preferred libraries:

- openid-client
- oidc-client-ts
- NextAuth when appropriate

Requirements:

- Silent token refresh
- Secure cookie storage
- CSRF protection

Never store tokens in localStorage.

---

# TypeScript Standards

Enable:

```json
{
  "strict": true
}
```

Requirements:

- No any types
- Explicit return types
- Shared DTOs where possible
- Prefer interfaces for API contracts

---

# Package Management

Use pnpm exclusively for frontend and uv for backend.

Commands:

```bash
pnpm install --frozen-lockfile
pnpm dev
pnpm build
pnpm test:run
pnpm lint
pnpm exec tsc --noEmit
```

Never use:

```bash
npm install
yarn
```

---

# Testing

## Backend

Use:

- pytest (`pytest tests/ -v --tb=short`)
- pytest-asyncio
- httpx
- ruff (`ruff check backend/` and `ruff format --check backend/ --exclude backend/build/`)

**Crucial Constraint**: All Python packages must be installed within the virtual environment (`.venv`), and all backend scripts/tools must be executed using the `.venv` binaries (e.g., `.venv/bin/pytest`, `.venv/bin/ruff`).

Requirements:

- Unit tests for services
- Integration tests for repositories
- API tests for endpoints

Target:

- Minimum 80% coverage

---

## Frontend

Use:

- Vitest
- eslint
- React Testing Library

Requirements:

- Component tests
- Hook tests
- Authentication flow tests

---

# Security

## General

Security is a priority.

Always:

- Validate all inputs
- Use parameterized SQL
- Escape untrusted content
- Enforce HTTPS
- Apply least privilege

Never:

- Log passwords
- Log tokens
- Store secrets in code
- Commit credentials

---

## Secrets

Use environment variables.

Examples:

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

Never hardcode secrets.

---

# Logging

Use structured logging.

Include:

- Request ID
- User ID
- Timestamp
- Log level

Avoid logging sensitive information.

---

# Code Generation Rules

When generating backend code:

- Use async functions
- Use SQLAlchemy 2.x
- Use dependency injection
- Use Pydantic models
- Add type hints

When generating frontend code:

- Use TypeScript
- Use App Router conventions
- Use server components unless interaction is required
- Use pnpm-compatible workflows
- Localize every user-facing string via next-intl; add keys to all locale
  files at full parity (see Internationalization)

When generating authentication code:

- Assume Keycloak OIDC
- Use Authorization Code Flow with PKCE
- Validate JWTs correctly
- Enforce RBAC

When generating database code:

- Assume PostgreSQL 17
- Assume Alembic migrations
- Assume UUID primary keys

Always prefer maintainable, production-ready implementations over simplified examples.

---

# Version Control & Workflow

When committing code, you must adhere to the following workflow:

- Run relevant tests and verify that the build passes before committing.
- You must execute `ruff check backend/` and `ruff format --check backend/ --exclude backend/build/` via the `.venv` to enforce CI linting compliance before every commit.
- Clean up throwaway scratch/debug artifacts once they've served their
  purpose — one-off probe scripts, ad-hoc `test_*.py` / `test*.js` files at
  the repo root, REPL dumps, etc. They must never be committed or left
  behind in the working tree. Only real, committed tests belong under
  `backend/tests/` and `frontend/tests/`.
