# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.3.0] — 2026-06-09

### Added

- **Two-tier access tokens** — global tokens (admin-created, visible to all users in the log) and private tokens (user-created, scoped to the owner).
  - Admin panel creates global tokens only; the Owner field is removed from the create form (auto-assigned to the creating admin). Rows display a "Global" badge.
  - Users create and manage personal tokens from **Preferences → My Tokens**. The raw token value is shown in a reveal-once banner and never exposed again.
  - `max_private_tokens` application setting (default: 3, range: 0–50) enforced at creation time.
  - Notification log gains a **Scope** filter: **All** / **Global** / **My tokens** — applied server-side.
  - `POST /api/v1/me/tokens`, `GET /api/v1/me/tokens`, `PATCH /api/v1/me/tokens/{id}`, `DELETE /api/v1/me/tokens/{id}` endpoints for personal token management (viewer+ role).

- **API performance monitoring** — new admin-only `/performance` page showing request latency and error rates.
  - `PerformanceMiddleware` instruments every `/api/v1/*` request (excludes health, version, docs, auth, and the performance endpoint itself). Latency is persisted asynchronously via `asyncio.create_task` to avoid adding overhead.
  - `api_metric_logs` table stores path template, method, status code, duration in ms, and timestamp.
  - `GET /api/v1/admin/performance?window_hours=<1–168>` returns p50/p95/p99 latency, error rate, requests-per-hour time series, and per-endpoint breakdowns (PostgreSQL `PERCENTILE_CONT`).
  - Frontend `/performance` page: window selector (1 h / 6 h / 24 h / 48 h / 7 d), four summary cards, requests-per-hour area chart (Recharts), endpoint table with colour-coded latency and error-rate columns.

- **Admin-only statistics pages** — both `/stats` and `/performance` now redirect non-admin users to `/log`.

- **CI: tag-only Docker publishing** — all three pipelines (GitHub Actions `docker-publish.yml`, GitHub Actions `build-publish.yml`, GitLab CI `.gitlab-ci.yml`) no longer trigger Docker builds on branch pushes. Images are only built and published when a version tag (`v*.*.*`) is pushed.

### Changed

- `AccessToken` model gains an `is_global` column (`BOOLEAN NOT NULL DEFAULT TRUE`). Existing databases are migrated automatically via an idempotent `ALTER TABLE IF EXISTS … ADD COLUMN IF NOT EXISTS` in `init_db()`.
- Admin token create response no longer requires selecting an owner; the creating admin is used automatically.
- `GET /api/v1/notifications` gains a `scope` query parameter (`all` | `global` | `mine`). Default is `all`. For non-admin users `all` shows global + own private; for admins it shows everything.
- **Version strings are now derived from package manifests** — no more duplicate hardcoded constants. `backend/version.py` reads `APP_VERSION` from `pyproject.toml` at import time via stdlib `tomllib`; `frontend/lib/version.ts` exports `FRONTEND_VERSION` from `NEXT_PUBLIC_APP_VERSION`, injected at Next.js build time by `next.config.mjs` from `package.json`. Bumping either manifest is now sufficient to update the About page.

### Fixed

- Deprecated `HTTP_422_UNPROCESSABLE_ENTITY` constant replaced with `HTTP_422_UNPROCESSABLE_CONTENT` in `services/tokens.py`.

---

## [0.2.1] — 2026-06-09

### Added
- Browser favicon and Apple touch icon using the app's bell icon (cyan `#22d3ee` on dark background), generated via Next.js `ImageResponse` — no static image files required.

### Fixed
- HTML validation warning: search input in the notification log was missing `id` and `name` attributes.

---

## [0.2.0] — 2026-06-08

### Added
- **Time-range filter** on the notification log: preset windows (Last 15 min, 1 h, 3 h, 12 h, 24 h, 7 days) plus a custom date/time range picker. Filter is applied server-side via `after`/`before` query parameters.
- **Splunk plugin — drag-to-reorder field mappings**: rows can be reordered via HTML5 drag-and-drop. Visual drop-target highlight provided.
- **Splunk plugin — live payload preview**: a JSON block below the field mapping list shows exactly what will be sent to the HEC endpoint, updated in real time as mappings and metadata fields change.
- **Docker Hub documentation**: `DOCKER_HUB.md` with quick-start instructions, required environment variables, port reference, and tag strategy. Automatically synced to the Docker Hub repository description on every publish.
- **OCI image labels** baked into the Docker image (`org.opencontainers.image.*`): title, description, source URL, documentation URL, revision (git hash), created timestamp, and version.

### Changed
- **Plugin card UX**: clicking anywhere on the plugin card header now toggles the configuration panel. Previously only the small chevron button was clickable. Switch and Save button clicks are isolated so they do not accidentally toggle the panel.
- **Container logging**: gunicorn and uvicorn log output now uses a single unified format with timestamps (`[YYYY-MM-DD HH:MM:SS +0000] [PID] [LEVEL] message`). Previously gunicorn access log lines had no timestamp.
- **GitLab CI** aligned with the GitHub Actions workflows:
  - `build:gitlab` (automatic) publishes to the GitLab Container Registry on pushes to `main` and version tags.
  - `build:dockerhub` (manual trigger) publishes to Docker Hub; also pushes `DOCKER_HUB.md` as the repository description via the Docker Hub API.
  - Both jobs build multi-platform images (`linux/amd64`, `linux/arm64`) using QEMU + Docker Buildx with registry-based layer caching.
- **README** fully revised: accurate Keycloak setup instructions (roles come from the access token body — no UserInfo protocol mapper required), complete environment variable table (added `OIDC_SCOPES`, `BACKEND_URL`), development setup updated to use `uv`, troubleshooting section added.
- Next.js bumped to **16.2.7**, nginx base image to **1.31.1-trixie**.

### Fixed
- Splunk plugin `POST /admin/plugins/{id}/test` returned a `ResponseValidationError` because the endpoint declared `-> dict` but returned `None`. Now returns `{"detail": "..."}` as expected.
- About page was displaying version `1.0.0` instead of the actual application version.

---

## [0.1.0] — initial development

- FastAPI backend with PostgreSQL 17, SQLAlchemy 2.x async ORM, Alembic migrations.
- Next.js 16 frontend with App Router, TypeScript strict mode, shadcn/ui components.
- OpenID Connect authentication (Keycloak-first; any OIDC-compatible provider supported). Role-based access control: `viewer` and `admin` roles.
- Notification ingest endpoint (`POST /api/shoutrrr`) authenticated via opaque Bearer tokens.
- Notification log with search, pagination, and group-by-custom-field.
- Admin panel: user management, access token management, plugin management.
- Splunk HEC plugin with configurable field mappings.
- Plugin system with auto-discovery from `backend/plugins/`.
- Repository and service layers in the backend (routers are thin).
- nginx reverse proxy with TLS termination.
- Docker multi-stage build; GitHub Actions and GitLab CI/CD pipelines.
