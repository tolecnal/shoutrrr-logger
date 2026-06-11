# AGENTS.md

## Project Overview

This project is a modern web application consisting of:

- Backend API: FastAPI (Python 3.13+) managed via uv
- Database: PostgreSQL 17
- ORM: SQLAlchemy 2.x (async) with Alembic migrations
- Authentication: OpenID Connect (OIDC) via Keycloak
- Frontend: Next.js 16 (App Router, Strict TypeScript) managed via pnpm
- API Communication: REST over HTTPS via centralized API client
- Containerization & Proxy: Docker with Gunicorn (Prod) / Nginx or Traefik

When acting as an agent generating code, documentation, tests, migrations, or configurations, you must strictly adhere to the layout and guardrails defined in this document.

---

## Agent Mission Control & Terminal Commands

Agents should execute operations using the following designated tools:

### Backend (Python/uv)

- Install dependencies: uv pip install -r pyproject.toml
- Run local dev server: uvicorn main:app --reload
- Run production container workflow: gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
- Run tests: pytest
- Linting/Formatting: ruff check or ruff format

### Frontend (Node/pnpm)

- Install dependencies: pnpm install
- Run local dev server: pnpm dev
- Build application: pnpm build
- Run tests: pnpm test
- Linting: pnpm lint

Strict Guardrail: Never use npm or yarn. Never bypass uv for backend package management.

---

## Workspace Layout

Agents must respect the following multi-surface codebase boundaries:

### Backend Workspace (/backend or root root-dependent files)

├── plugins/
│ └── splunk/
├── routers/
├── tests/
├── auth.py
├── config.py
├── database.py
├── main.py
├── models.py
├── pyproject.toml
├── schemas.py
├── uv.lock
└── version.py

### Frontend Workspace (/frontend or root-dependent app folder)

├── app/
│ ├── about/
│ ├── admin/
│ └── log/
├── components/
│ └── ui/
├── hooks/
├── lib/
├── plugins/
│ └── splunk/
├── public/
└── tests/
└── lib/
├── components.json
├── eslint.config.mjs
├── next.config.mjs
├── package.json
├── pnpm-lock.yaml
├── postcss.config.mjs
├── tsconfig.json
└── vitest.config.ts

---

## Code Generation Guardrails & Design Patterns

### 1. Backend & Async SQLAlchemy 2.x Standards

- Dependency Injection: Always use FastAPI Depends() for dependencies.
- Architecture Layering: Keep API route handlers thin. Business logic belongs in services; raw database access belongs exclusively in Repositories. Never place raw SQL or inline queries inside route handlers.
- Type Safety: Apply explicit Python type hints everywhere.
- Async Sessions: All database calls must use async sessions.
- Query Syntax: Use modern SQLAlchemy 2.x declarative models and explicit selection statements.

# PREFERRED SELECT PATTERN

stmt = select(User)
result = await session.execute(stmt)

# FORBIDDEN PATTERN (Do not generate)

# session.query(User)

- Database Schema Rules:
  - Primary keys must be explicitly mapped as UUIDs defaulting to uuid4.
  - Enforce server-side timestamps, explicit foreign keys, and indexes for frequently queried columns.
  - Eager-load relations where appropriate to proactively eliminate N+1 query bugs.

# Example Model Primary Key

id: Mapped[UUID] = mapped_column(
UUID(as_uuid=True),
primary_key=True,
default=uuid4,
)

### 2. Database Migrations (Alembic)

- Every schema modification requires a separate Alembic migration file.
- Never modify an existing, committed migration file.
- Autogenerate migrations from changes to SQLAlchemy models, but review the generated script for consistency before final execution.

### 3. API & Response Formatting

- REST Routing Style: /api/v1/users, /api/v1/groups, /api/v1/projects
- Serialization: All endpoints must validate inputs and outputs utilizing Pydantic models. Never return raw SQLAlchemy ORM objects directly over the wire.
- Error Schemas: Use structured JSON objects for errors coupled with accurate HTTP status codes:
  {
  "detail": "Resource not found"
  }

### 4. Authentication & Keycloak OIDC Standards

- Flow: Enforce Authorization Code Flow with PKCE.
- Token Verification: The backend must explicitly validate JWT signatures, issuer, audience, and expiration. Never trust client-asserted roles without cryptographic validation.
- RBAC/Group Auth: Extract claims from the specified namespace (default: realm_access.roles). Authorization must be entirely role- or group-based. Avoid hardcoding granular string-permissions or using user ID/username-based access gates.
- Token Claims Structure:
  {
  "sub": "...",
  "preferred_username": "...",
  "email": "...",
  "realm_access": {
  "roles": ["admin"]
  }
  }
- FastAPI Dependency Enforcement:
  current_user = Depends(get_current_user)
  admin_user = Depends(require_role("admin"))

### 5. Frontend (Next.js 16 & TypeScript) Rules

- Architecture: Enforce Next.js App Router conventions. Default to Server Components; explicitly mark Client Components using 'use client' only when state hook interaction or client-specific APIs are required.
- TypeScript Strictness: "strict": true is non-negotiable. Never inject any types. Provide explicit function return types. Treat interfaces as the standard for defining contract/DTO objects.
- Data Access Layer: Direct fetch calls scattered through subcomponents are strictly forbidden. All data queries must go through a centralized client wrapper (lib/api.ts) managing centralized headers, errors, and silent token refresh logic.
- Client Security: Use OIDC Authorization Code Flow with PKCE via safe libraries (openid-client, oidc-client-ts). Never store access/refresh tokens inside localStorage. Ensure silent token refresh runs securely over HTTPS with HTTP-only cookies protected against CSRF vulnerabilities.

---

## Testing & Quality Check Gates

Before considering a task finished, the agent should run test sweeps ensuring code satisfies coverage targets:

### Backend Testing Target: Min 80% Coverage

- Frameworks: pytest, pytest-asyncio, and httpx.
- Coverage Structure: Unit tests for business services, Integration tests for SQLAlchemy repositories, End-to-end API automation for endpoint validation.

### Frontend Testing Target

- Frameworks: Vitest with React Testing Library.
- Coverage Structure: Component isolated tests, hook operational tests, and simulated OIDC authentication flow checks.

---

## System Security & Environment Boundaries

### Variables Management

Agents must use system environment variables instead of configuration constants. Never commit production credentials, access secrets, or raw keys into version control.

Required environment keys mapped within the project runtime:
DATABASE_URL=postgresql+asyncpg://postgres:CHANGEME@localhost:5432/shoutrrr_logger
POSTGRES_PASSWORD=CHANGEME
OIDC_DISCOVERY_URL=
OIDC_CLIENT_ID=shoutrrr-logger
OIDC_CLIENT_SECRET=
APP_BASE_URL=<http://localhost:4000>
OIDC_ROLES_CLAIM=realm_access.roles
OIDC_ROLE_VIEWER=viewer
OIDC_ROLE_ADMIN=admin
OIDC_SCOPES=openid email profile roles
SECRET_KEY=
WORKERS=4
BACKEND_URL=<http://localhost:9000>

### Log Integrity

Logs generated by code must be structured formats containing a unique Request ID, User ID, Timestamp, and standard Log Level. Strict Guardrail: Never log user passwords, PII, tokens, or encryption secrets.

---

## Version Control & Workflow

### Git Commit Strategy

Agents must commit their changes frequently and granularly. Avoid monolithic, "massive" commits that encompass multiple unrelated features or fixes.
Follow these guidelines:
- Commit immediately after successfully implementing a single logical feature, fixing a bug, or completing a refactor.
- Ensure that `CHANGELOG.md` and `README.md` are updated in the same commit as the feature or fix they document.
- Use Conventional Commits formatting for messages (e.g., `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).
- Run relevant tests and verify that the build passes before committing.
