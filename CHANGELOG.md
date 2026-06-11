# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **Slack Plugin**: Added a new bundled Slack plugin that can post notifications directly to Slack via an Incoming Webhook URL.
- **User Plugin Configs**: Users can now configure their own plugin integrations from User Preferences if the admin permits it. This allows users to receive notifications to their personal Slack/Teams/etc based on routing rules, completely separate from the global system plugins.
- **Plugin Routing Rules**: Plugins can now have custom outbound routing rules defined at both the global and user levels. A notification must match the severity, tags, token ID, or sender criteria for it to be routed to that plugin.
- **Server-Sent Events (SSE)**: The notification log now uses SSE to stream real-time updates directly to the UI, eliminating the need for periodic polling or manual refreshing.
- **Time Formatting**: Timestamps on the notifications page now intelligently format themselves. If a notification is from today, only the time is shown. For older notifications, the date is included.
- **Audit Logging**: Added audit log capture for updates to User Plugin Configurations.
- **Alert System**: Users can now define personal Alert Rules to highlight specific notifications and optionally receive email alerts via SMTP. Includes testing tools, a draft editor, and a template engine for customizing alert emails.
- **Alerts Navigation**: Added an "Alerts" item to the main sidebar with an unread badge for quick access to triggered visual alerts.
- **SSRF Mitigation**: Implemented robust Server-Side Request Forgery (SSRF) validation for outbound plugin requests. Webhook URLs (like Slack and Splunk) are now resolved via `socket.getaddrinfo` and validated against a strict denylist to block requests to private, loopback, or reserved IP address spaces.

### Added

- **Admin toggle for private access tokens**: new `private_tokens_enabled` setting (default: enabled), configurable from **Admin → Settings**. When disabled, users can no longer create new private tokens from **Preferences → My Tokens**, and existing private tokens are rejected (`403`) for notification ingestion. Global tokens are unaffected.
- **"Test this token" dialog**: the Admin → Access Tokens page and Preferences → My Tokens now have a "Test" action that opens a dialog with copy-paste examples (curl, PowerShell, Python, PHP, wget, and the shoutrrr generic URL scheme) for sending a notification with that token.
- **README**: added PowerShell, Python (`requests`), PHP, and wget examples to the "Sending notifications" section, alongside the existing curl example.

### Security

- **Notification access control**: `GET /api/v1/notifications/{id}` and `PATCH /api/v1/notifications/{id}/state` now enforce the same global/own-private visibility rules as the notification list, instead of allowing any authenticated viewer to read or change the state of any notification by ID.
- **Alert email access control**: `POST /api/v1/alerts/test-email` and `POST /api/v1/alerts/preview-template` no longer allow an arbitrary `notification_id` to pull another user's private-token notification content into a templated email.
- **Routing rules access control**: non-admin users can no longer read, update, or delete global routing rules by ID via `/api/v1/routing-rules/{id}` (they remain visible read-only via the rules list, as before).
- **Rate limiting**: the per-token ingestion rate limit (`rate_limit_per_minute`) now counts deduplicated (repeated-fingerprint) notifications via `last_received_at`, closing a bypass where identical notifications sent faster than the dedup window would stop counting toward the limit once their original `received_at` aged out of the window.
- **SSRF validation bypass**: outbound webhook SSRF checks (Slack/Splunk plugins) are now disabled only via the dedicated `SSRF_VALIDATION_DISABLED` setting (test suites only), and log a warning when active. Previously this was tied to `ENVIRONMENT=test`, which also silently skipped production secret-strength checks if left set in a real deployment.
- **Alert email templates**: `email_alert_template` and the admin "preview template" endpoint now use a restricted formatter that only allows simple `{name}` substitutions, rejecting attribute/index access (e.g. `{title.__class__}`) that `str.format()` would otherwise evaluate.
- **Notification ingestion**: `severity`/`level` and `tags` from `/shoutrrr` payloads are now length-validated (`severity` ≤ 32 chars, each tag ≤ 64 chars), returning `400` instead of an unhandled database error for oversized values.
- **Alert rule names**: `AlertRule.name` can no longer contain CR/LF characters (rejected with `422`), and is sanitized again before being used in the alert email `Subject` header.
- Routing rule evaluation errors for one plugin's user-configured rules (e.g. malformed JSON) no longer abort dispatch for the remaining plugins.
- **Alert email HTML sanitization**: HTML produced by `markdown.markdown()` for alert/test/preview emails is now sanitized (script/iframe/event-handler attributes and `javascript:` links stripped) before being sent, preventing stored HTML injection via untrusted notification `title`/`message` content.
- **SSRF DNS-rebinding/TOCTOU fix**: outbound Slack/Splunk plugin requests now resolve and re-validate the destination hostname against the SSRF denylist at connection time and pin the connection to that resolved IP, closing a gap where `validate_url_for_ssrf`'s lookup and the actual outbound request could resolve to different addresses (e.g. via DNS rebinding).
- **OIDC login**: the access token's role claims are now verified against the identity provider's JWKS (signature, issuer, expiration) instead of being decoded without signature verification.

### Fixed

- Corrected the packed-integer value of the retention-loop advisory lock key (`_RETENTION_LOCK_KEY`) so it matches its documented "sh_rt" encoding (cosmetic — the lock only needs to be a stable constant).

### Changed

- **Settings validation**: the **Statistics window** (`stats_window_days`) can no longer be set higher than **Retention period** (`retention_days`) or **API metrics retention** (`api_metrics_retention_days`) when either is non-zero, preventing `/stats` and `/performance` from silently showing incomplete data for windows that exceed the retained data.
- Error responses from the settings API (and other endpoints) now surface their `detail` message directly in toast notifications instead of raw JSON.
- **API Performance UI**: Added real-time text search and full column sorting (asc/desc) to the Endpoint Breakdown table. Refined the visual styling of the summary stat cards so they don't look incorrectly "selected".
- **CI**: bumped GitHub Actions in the lint and Docker publish workflows to Node.js 24-compatible major versions (`actions/checkout@v5`, `docker/build-push-action@v7`, `docker/login-action@v4`, `docker/metadata-action@v6`, `docker/setup-buildx-action@v4`, `docker/setup-qemu-action@v4`, `peter-evans/dockerhub-description@v5`), ahead of GitHub's Node 20 runner deprecation.
- **CI & Workflows**: Enforced isolated Python virtual environments (`.venv`) and exact command parity (`ruff`, `pytest`) across GitLab CI, GitHub Actions, and developer documentation (`AGENTS.md` and `CLAUDE.md`).
- **Frontend build**: added `onlyBuiltDependencies` (esbuild, sharp, unrs-resolver) to `pnpm-workspace.yaml` so pnpm no longer skips the install scripts these packages need.

## [0.5.0] — 2026-06-10

### Added

- **Automatic retention for API performance metrics and audit logs**, alongside the existing notification retention sweep. New settings `api_metrics_retention_days` (default 30) and `audit_log_retention_days` (default 365), configurable from **Admin → Settings**; set either to `0` to keep records forever.

### Changed

- **Database performance review**: indexing and query fixes for ingestion under load and large data volumes.
  - Bearer-token verification (`POST /api/v1/shoutrrr` and other token-authenticated endpoints) now does an O(1) indexed lookup by `token_hash` instead of loading every active token and comparing hashes one by one. New unique index `ix_access_tokens_token_hash`.
  - Notification search (`message`/`title`/`sender_name` `ILIKE` filter) now has trigram (`pg_trgm`) GIN indexes on all three columns (`ix_notifications_title_gin`, `ix_notifications_sender_name_gin`), matching the existing `message` index, so searches on large tables avoid sequential scans.
  - `GET /api/v1/admin/stats` "top senders" now respects the configured stats window instead of scanning the entire `notifications` table unfiltered.
  - New composite index `ix_access_tokens_user_global` on `(user_id, is_global)` speeds up per-user token listing/limit checks.
  - Removed a redundant duplicate unique index on `users.sub` (`uq_users_sub`), keeping a single unique index (`ix_users_sub`).
  - All changes applied automatically via idempotent `CREATE INDEX IF NOT EXISTS` / `DROP CONSTRAINT IF EXISTS` statements in `init_db()`.
- **Cursor (keyset) pagination** for `GET /api/v1/notifications` and `GET /api/v1/admin/audit-logs`, replacing `OFFSET`-based pagination so deep pages on large tables stay an indexed range scan instead of an ever-growing skip.
  - **Breaking API change**: both endpoints now accept an opaque `cursor` query parameter instead of `page`, and return `{ items, total, page_size, pages, next_cursor }` instead of `{ items, total, page, page_size, pages }`. Pass the previous response's `next_cursor` to fetch the next page; `next_cursor` is `null` on the last page.
  - The notification log and admin audit log UIs now use Prev/Next cursor-based navigation.
- **Configurable database connection pool**: new `DB_POOL_SIZE` (default `5`) and `DB_MAX_OVERFLOW` (default `5`) environment variables control the SQLAlchemy async engine pool size per worker process (previously hardcoded to 10/20). Total connections to PostgreSQL are approximately `WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW)`.
- **Single retention-loop owner across gunicorn workers**: each worker previously started its own hourly retention loop, risking concurrent purges of the same rows. Workers now race for a PostgreSQL session-level advisory lock at startup; only the winner runs `_retention_loop`. Self-healing — if that worker is recycled, the lock is released and another worker takes over. No-op (always "leader") on SQLite for local dev/tests.
- **Notification log pagination moved to the toolbar**: "Page X of Y" and the Prev/Next controls now sit next to the total/visible count at the top of the notification log, so they stay visible regardless of table scroll position (previously shown only in a footer below the table).

### Fixed

- **Preferences dialog**: the dialog no longer changes size when switching between the Display, Tag Rules, and My Tokens tabs (now a fixed height with internal scrolling per tab).
- **Preferences dialog — Tag Rules**: rule rows now wrap onto multiple lines instead of clipping labels (tag name, "Exclude" toggle, color, pattern count) when there isn't enough horizontal space.
- **Preferences dialog — Tag Rules**: the color picker is now wide enough to show full color names (e.g. "yellow", "magenta") without clipping.

---

## [0.4.0] — 2026-06-10

### Added

- **Light and dark theme support** — the app previously rendered dark-only; it now supports Light, Dark, and System (follows OS preference) modes.
  - New **Theme** selector in **Preferences → Display**, persisted in `localStorage` via `next-themes`.
  - A new light color palette is defined alongside the existing dark palette; the active theme is applied via a `.dark` class on `<html>` with no flash on load.
  - Charts, status badges, and other previously hardcoded dark-mode colors now adapt to the active theme.

- **Admin audit log** — every admin action (user/token/settings/plugin create, update, delete) is now recorded.
  - New `audit_logs` table: actor (user id + username snapshot), action (`user.create`, `token.update`, `plugin.update`, etc.), target type/id, a redacted JSON `details` snapshot, IP address, and timestamp.
  - Sensitive fields (anything matching `token`, `secret`, `password`, `passwd`, `key`, `hec`, or `auth`) are masked as `***REDACTED***` before being stored — plugin secrets (e.g. Splunk HEC token/URL) and raw access tokens never appear in audit details.
  - `GET /api/v1/admin/audit-logs` (admin-only) supports `action`, `actor_user_id`, `after`, `before`, `page`, and `page_size` filters.
  - New **Admin → Audit Log** tab: paginated table (Time, Actor, Action, Target, IP) with an action filter and an expandable details view.

- **Ingestion rate limiting** for `POST /api/v1/shoutrrr`, enforced via a DB-backed sliding window over the `notifications` table (accurate across multiple gunicorn workers, no new infra).
  - New global setting `rate_limit_per_minute` (default `0` = unlimited, range 0–10000) configurable from **Admin → Settings**.
  - Admin-only per-token override `rate_limit_override`: `null` = inherit the global setting, `0` = explicitly unlimited, `>0` = a custom per-minute limit for that token.
  - Requests over the limit receive `429 Too Many Requests` with a `Retry-After: 60` header.
  - **Admin → Access Tokens** gains a "Rate limit" column and an edit (pencil) action to rename a token or set/clear its rate-limit override; the create-token dialog offers the same control.

### Changed

- `AccessToken` model gains a nullable `rate_limit_override` integer column. `notifications` gains a composite index on `(token_id, received_at)` to keep the rate-limit lookup cheap. Both are applied automatically via idempotent `ALTER TABLE IF EXISTS … ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` in `init_db()`.

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
