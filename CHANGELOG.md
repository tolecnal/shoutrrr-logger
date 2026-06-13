# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **NQL Search**: Implemented an advanced JQL-style search query language (NQL) with full syntax validation.
- **NQL Compiler**: Added AST-based backend query compiler supporting Boolean logic (`AND`, `OR`, `NOT`) and nested grouping `()`.
- **Search UI**: Enhanced search bar with real-time syntax highlighting and inline syntax error validation.
- **Internationalization (i18n)**: Implemented full frontend translation support via `next-intl`. Added Norwegian (`no`) as a supported language.
- **Plugin Localization**: Frontend plugin configurations (`frontend/plugins/<plugin>/locales/`) are now fully localized and dynamically merged into the global messaging tree, including graceful fallbacks to API-provided plugin names and descriptions.
- **Locale Switcher**: Added a top-bar component to easily toggle the UI language.
- **UI Polish**: Added Lucide icons to all primary action buttons and application tabs (Admin Panel, Settings, User Preferences, Plugins) to ensure visual consistency and better UX.
- **Audit Log Syntax Highlighting**: Audit Log JSON details now render with `react-syntax-highlighter` (vs2015 theme) for improved readability.

### Changed

- **Next.js Proxy**: Renamed `frontend/middleware.ts` to `frontend/proxy.ts` to fix a Next.js 16+ deprecation warning.
- **Dependencies**: Bumped `pnpm` from `11.5.3` to `11.6.0` (managed via corepack).
- **Audit Log Terminology**: Renamed "Actor" to "Username" in the UI to be more precise for users.
- **Graceful Locale Fallbacks**: Visiting URLs with an unsupported or missing language code (e.g., `/es/log`) now dynamically intercepts the route in `proxy.ts` and safely redirects users to the English default to prevent 404 crashes.

### Fixed

- **NQL Lexer**: Fixed a bug where autocomplete suggestions such as `sender:` would render incorrectly as `ender:` due to greedy whitespace character exclusions swallowing the letter 's'.
- **NQL Lexer Editor**: Corrected cursor visual desynchronization that occurred while typing by perfectly matching the overlay text classes (especially monospace font configurations) with the active transparent input.
- **NQL Strict Validation**: The search parser now throws an explicit syntax error for unexpected characters (e.g., unclosed regex patterns like `/https`) rather than silently ignoring them, fulfilling the strict Jira-like search constraints.
- **Search Autocomplete Trigger**: Prevented the autocomplete suggestion dropdown from incorrectly hijacking the "Enter" key and opening suggestions when the search input is completely cleared (e.g. CTRL+A, Backspace).

## [0.8.0] — 2026-06-13

This release centers on **plugin configuration profiles**, **per-token external delivery control**, and **finer-grained notification deletion**, plus operational and security hardening (auto-applied migrations, RP-initiated logout). Note the API and migration changes called out below.

### Added

- **Plugin Configuration Profiles (per-user)**: Users can create multiple named configuration profiles per plugin (e.g. several Slack channels), shown as tabs under Preferences → My Plugins. Each profile has its own settings, routing rules, and enable toggle, and every enabled profile is dispatched independently through the routing engine. Profiles can be renamed, duplicated, deleted, and test-fired individually. A new *Max plugin profiles per user* admin setting caps profiles per plugin (default 5, 0 = unlimited; admins exempt).
- **Plugin Configuration Profiles (global/admin)**: Admin → Plugins now uses the same named-profile model — each global profile has its own settings, routing rules, enable toggle, and per-profile test button, with no cap for admins.
- **Per-Token External Delivery Policy**: Access tokens (global and personal) carry two independent toggles — **Allow plugins** and **Allow email alerts** — set by the token's creator, both on by default. When *Allow plugins* is off, no plugin forwards that token's notifications to third parties; when *Allow email alerts* is off, matching alert rules don't email them while the in-app alert is still created. Evaluated at ingestion and recorded in the audit log. Designed to extend (see `models.EXTERNAL_DELIVERY_CHANNELS`).
- **Admin Master Switch for User External Delivery**: A new *Allow external delivery for user tokens* admin setting (Settings → Access) acts as a kill switch — when disabled, notifications sent with users' private tokens are never forwarded to plugins or emailed regardless of each token's own toggles (in-app alerts and global/admin tokens unaffected). While off, a consistent amber warning appears across Preferences (My Tokens tab + token dialogs, Alert Rules, My Plugins).
- **Select & Delete Notifications**: The notification log supports Gmail-style multi-select — per-row checkboxes plus a header "select all on page" — with a **Delete selected** action (`POST /api/v1/notifications/delete`), alongside the existing filter-based bulk delete. Selection persists across pages within the same filter.
- **Automatic Database Migrations**: The container entrypoint now runs `alembic upgrade head` before starting the servers, so a schema-changing release can never serve requests against an un-migrated database (with retries while PostgreSQL starts up). Opt out with `AUTO_MIGRATE=false` to migrate out-of-band.

### Changed

- **User Plugins API**: `/api/v1/user-plugins` responses are now profile-based (plugin metadata + a `profiles` array), with per-profile CRUD under `/api/v1/user-plugins/{plugin}/profiles/...`. The old `PATCH /api/v1/user-plugins/{plugin}` endpoint is **removed**.
- **Admin Plugins API**: now profile-based under `/api/v1/admin/plugins/{plugin}/profiles/...`; `PATCH /admin/plugins/{id}` only accepts `allow_user_configs`, and the old `POST /admin/plugins/{id}/test` endpoint is **replaced** by per-profile tests. Existing global plugin configs are migrated into a "Default" profile automatically.
- **Personal Token Update API**: `PATCH /api/v1/me/tokens/{id}` now takes a JSON body instead of query parameters (consistent with the admin token endpoint) and accepts the new delivery flags.
- **Personal Token Creation UX**: Creating a personal token now uses a "+ Create token" button that opens a dialog (name, optional expiry, delivery toggles), matching the admin flow.

### Fixed

- **Logout Didn't End the SSO Session (account switching)**: Logging out only cleared the app's own session cookie, leaving the IdP's SSO session alive — so in a shared browser the next login was silently completed as the previous user. Logout now performs **RP-initiated logout** (redirects to the IdP's `end_session_endpoint` with `id_token_hint`, then back to the app), and login sends `prompt=login` so the IdP always re-authenticates. Requires the app's post-logout redirect URI to be registered with the provider (documented for Keycloak).
- **Unreachable Admin Settings**: Three registered settings were never wired into the Admin → Settings UI — *Max plugin profiles per user*, *Enable alert states (Ack/Resolve)*, and *Test rule preview limit* — and are now editable.
- **User Plugin Test Button**: "Send test notification" in Preferences → My Plugins called the admin-only endpoint (always 403 for viewers, and tested the global config); it now runs through the user's selected profile.
- **Checkbox Visibility**: The shared checkbox was nearly invisible unchecked, especially in dark mode; it now has a clearly visible border in both themes.

### Security

- **Notification Delete Permissions**: Deletion is governed by a permission model narrower than viewing — admins may delete anything they can see, but viewers may only delete notifications from **their own private tokens**, never global or other users' (even though they can see global ones). Enforced server-side for both selected-delete and filter-based bulk delete; previously a viewer's bulk delete could remove global notifications it could see.
- **esbuild Advisory (dev dependency)**: Pinned `esbuild` to `^0.28.1` via a pnpm override to clear a Windows-only path-traversal in esbuild's dev server, pulled in transitively through `vitest`. The app never runs esbuild's dev server, so exposure was nil, but the override removes the advisory.
## [0.7.5] — 2026-06-12

### Added

- **Security Policy**: Added `SECURITY.md` with private vulnerability reporting channels (GitHub advisories / email), scope, and the project's deployment security model.
- **Code of Conduct**: Added `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1).
- **PostgreSQL Tuning**: The docker-compose postgres service now ships workload-aligned settings (shared buffers, effective cache size, work/maintenance memory, SSD cost model, faster autovacuum for retention churn, WAL compression) — all overridable via new optional `PG_*` environment variables. Defaults target a 2 GB host; `.env.example` documents recommended values for 4 GB / 8 GB. Also sets `shm_size: 128mb` per the official postgres image recommendation.
- **Metrics Write Optimization**: The per-request API metric insert now uses `SET LOCAL synchronous_commit TO off`, removing a WAL fsync from every API request. Scoped to the telemetry transaction only — notification, audit, and alert writes remain fully durable.

### Fixed

- **Monitoring Token Dialog Overflow**: The "Token Created" dialog shown after creating a monitoring token was too narrow for its content — the usage example inlined the full raw token in a non-wrapping code element. The dialog now matches the access-token dialog width and references the token instead of duplicating it.

## [0.7.4] — 2026-06-12

### Security

- **OIDC Login CSRF & PKCE**: The callback now *rejects* requests whose `state` fails signature/expiry verification or whose nonce doesn't match the new browser-bound `oidc_nonce` cookie (previously a forged or missing state silently fell back and the login still completed). The login flow also implements PKCE (RFC 7636, S256), so an intercepted authorization code cannot be redeemed without the browser-bound verifier cookie.
- **SMTP TLS Enforcement**: Alert emails no longer fall back to plaintext authentication when STARTTLS fails or is stripped by a MITM — sending credentials now *requires* an encrypted connection, and certificates are validated via `ssl.create_default_context()` on both STARTTLS and implicit-TLS (465) paths. Unauthenticated internal relays without TLS keep working, with a logged warning.
- **CSV Formula Injection**: Notification exports neutralize cells beginning with `=`, `+`, `-`, `@`, tab, or CR so attacker-supplied notification content cannot execute as spreadsheet formulas when the export is opened in Excel/LibreOffice/Sheets.
- **Spoofable Source IPs**: The ingestion endpoint and audit logger no longer trust the client-controlled left-most `X-Forwarded-For` entry; the real client IP is taken from nginx's authoritative `X-Real-IP`, falling back to the right-most XFF hop, then the socket peer.
- **Bulk Delete Auditing**: `DELETE /api/v1/notifications` now writes a `notification.bulk_delete` audit-log entry recording the actor, filters, deleted count, and client IP.
- **Security Headers**: The bundled nginx config now sends `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **Non-root Container**: The Docker image now runs both servers as an unprivileged `app` user (uid 999) instead of root.
- **SECRET_KEY Strength**: Production startup now requires `SECRET_KEY` to be at least 32 characters (RFC 7518 §3.2 minimum for HMAC-SHA256), not merely different from the default.
- **POST-only Logout**: `/api/auth/logout` no longer accepts GET, closing a cross-site forced-logout vector (SameSite=Lax cookies are sent on top-level navigations). The frontend now logs out via a POST from the API client.
- **OIDC Audience Validation (opt-in)**: New `OIDC_VERIFY_AUDIENCE` / `OIDC_AUDIENCE` settings enforce the `aud` claim of OIDC access tokens for providers with a properly configured audience mapper. Off by default for Keycloak compatibility.
- **Metrics Endpoint Guard (opt-in)**: New `METRICS_TOKEN` setting requires `Authorization: Bearer <token>` on `GET /metrics` for deployments that expose the backend port directly. Empty (default) keeps the endpoint open, which is safe behind the bundled nginx.
- **Narrower TLS Mounts**: docker-compose now bind-mounts only this site's certificate and key into the nginx container instead of all of `/etc/ssl/certs` and `/etc/ssl/private` (which handed the container every private key on the host).
- **CI Supply Chain**: The third-party `peter-evans/dockerhub-description` action is now pinned to a commit SHA instead of a mutable tag.

### Changed

- **Token Update API**: `PATCH /api/v1/admin/tokens/{id}` now takes a JSON body (`AccessTokenUpdate`) instead of query parameters, so token names no longer appear in proxy/access logs via the query string.
- **SSE Backpressure**: Per-subscriber SSE queues are now bounded (100 entries, drop-oldest) so a stalled client connection can no longer grow memory indefinitely.
- **Docker Build**: The backend dependency wheel list is now derived from `backend/pyproject.toml` at build time instead of being hand-duplicated in the Dockerfile.

### Fixed

- **Routing Rules Admin Check**: Admin detection in the routing-rules API compared the internal role enum against the *configurable OIDC role name*, silently demoting admins to per-user rule scope when `OIDC_ROLE_ADMIN` was customized. It now checks the internal role enum directly.
- **Test-Email Diagnostics**: SMTP test failures are logged with full tracebacks through the structured logger (instead of `traceback.print_exc()` to stderr) and return a 502 with a concise error summary.

### Removed

- **`fix_db.py`**: Obsolete one-off data-fix script (predates the Alembic baseline where `last_received_at` is NOT NULL).

## [0.7.3] — 2026-06-12

### Security

- **OIDC Open Redirects**: Fixed multiple instances of Open Redirect vulnerabilities flagged by CodeQL in both the OIDC login initiation and callback flows by tightening relative path verification and breaking taint chains.
- **OIDC State Integrity**: Refactored the OIDC post-login redirection architecture to eliminate the short-lived `oidc_redirect` cookie. The redirect target is now bundled alongside the CSRF nonce inside a cryptographically signed JSON Web Token (JWT) passed via the OIDC `state` parameter, completely resolving CodeQL "Cookie Injection" / HTTP Response Splitting alerts and providing tamper-proof state.
- **XSS Prevention**: Fixed incomplete JSON string escaping in the Generic Webhook live payload preview generator that failed to escape literal backslash characters.
- **CI Least Privilege**: Explicitly set default `permissions: { contents: read }` across all GitHub Actions workflows to prevent privilege escalation via `GITHUB_TOKEN`.

## [0.7.2] — 2026-06-12

### Added

- **SSRF Whitelist**: Added a new `SSRF_ALLOWED_HOSTNAMES` environment variable. This accepts a comma-separated list of hostnames or IPs that are explicitly permitted for outbound plugin requests (like Webhooks or Splunk), even if they resolve to a private, loopback, or reserved IP address. This is critical for self-hosted instances that need to route notifications to internal services on the same LAN without completely disabling SSRF protection.

### Changed

- **Node.js**: Bumped Dockerfile and CI pipelines to use the current LTS version, Node.js 24 ("Jod").
- **Frontend Dependencies**: Updated core libraries including Next.js 16, React 19, Recharts v3 (with corresponding component upgrades), Zod, Vitest, and Lucide React.
- **Backend Dependencies**: Updated core Python dependencies including `starlette` (1.3.1), `pydantic-core` (2.47.0), and `ruff` (0.15.17).

## [0.7.1] — 2026-06-11

### Added

- **Database migrations**: Added Alembic configuration (`backend/alembic.ini`, `backend/migrations/`) with a baseline migration matching the current schema. Existing databases are stamped at this baseline automatically on startup; future schema changes ship as Alembic migrations.
- **CI**: a new workflow job applies Alembic migrations to a fresh PostgreSQL database, runs `alembic check` to catch model/migration drift, and verifies `alembic downgrade base` / `upgrade head` round-trip cleanly. Added to both GitHub and GitLab CI workflows.
- **Generic Webhook Config UI**: The generic webhook plugin now has a fully featured configuration panel in the user preferences, supporting custom HTTP methods, headers, a payload template, a TLS verification toggle, and a syntax-highlighted live payload preview.
- **Syntax Highlighting**: Splunk HEC and Generic Webhook plugin live payload previews now feature full JSON syntax highlighting.

### Fixed

- **Monitoring health counters**: `/api/v1/monitoring/health` always reported `alerts_unread` and `alerts_email_pending` as `0` due to a Python `not <Column>` expression being evaluated before query construction. Both counters now reflect actual data.
- **Email alert digests**: the background email digest loop never sent any emails, for the same `not <Column>` reason — it could never find unsent alerts. Email digests now send correctly.
- **Log noise**: every `HTTPException` (including normal 401/403/404/422 responses) was logged at `ERROR` level with a full traceback by the `get_db` dependency. Only unexpected errors and 5xx responses are now logged as errors.
- **Alembic Downgrade**: The `userrole` enum type is now explicitly dropped during `alembic downgrade base` to prevent a `DuplicateObjectError` on subsequent `upgrade head` operations.

### Changed

- **Advanced Search hardening**: `message:/regex/`, `title:/regex/`, etc. now reject invalid or excessively long (>200 character) regex patterns with a `422` response before they reach PostgreSQL, and search/export/bulk-delete queries are now bounded by a configurable statement timeout (`SEARCH_STATEMENT_TIMEOUT_MS`, default 5000ms) on PostgreSQL.
- **Renamed "Tag Rules" to "Labels"**: the content-based classification rules in Preferences (badges shown on notifications matching a regex pattern) are now called "Labels" to avoid confusion with the unrelated, ingestion-time `tags` field on notifications. This remains a client-side (localStorage) preference; existing rules are migrated automatically to the new storage key.

## [0.7.0] — 2026-06-11

### Added

- **External Monitoring**: Added dedicated monitoring tokens and a `/api/v1/monitoring/health` endpoint intended for use by external monitoring tools (e.g. Icinga2, Nagios). Exposes unread alerts, user counts, database status, and pending email digests.
- **Monitoring Tokens UI**: Added a "Monitoring" tab in the Admin panel to manage these separate, read-only system tokens.
- **Monitoring Documentation**: Added a `MONITORING.md` guide to the root of the project with configuration instructions for Nagios and Icinga2.

### Changed

- Replaced `secrets.token_urlsafe` with `secrets.token_hex` for generating access tokens to eliminate hyphens and underscores, preventing double-click truncation when copying tokens from the UI.

## [0.6.0] — 2026-06-11

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
- **Admin toggle for private access tokens**: new `private_tokens_enabled` setting (default: enabled), configurable from **Admin → Settings**. When disabled, users can no longer create new private tokens from **Preferences → My Tokens**, and existing private tokens are rejected (`403`) for notification ingestion. Global tokens are unaffected.
- **"Test this token" dialog**: the Admin → Access Tokens page and Preferences → My Tokens now have a "Test" action that opens a dialog with syntax-highlighted, copy-paste examples (curl, PowerShell, Python, PHP, wget, and the shoutrrr generic URL scheme) for sending a notification with that token.
- **README**: added PowerShell, Python (`requests`), PHP, and wget examples to the "Sending notifications" section, alongside the existing curl example.
- **Advanced Search Syntax**: The notification log search now natively supports complex queries directly in the search bar. You can target specific fields (`title:`, `message:`, `sender:`, `severity:`, `tag:`), use wildcards (`sender:app*`), regular expressions (`message:/regex/`), exact phrases (`"quoted string"`), and relative/absolute time ranges (`after:1h`, `before:2024-01-01`).
- **Search Auto-complete**: Typing in the search bar now provides a rich, keyboard-navigable auto-complete dropdown for senders, tags, severities, and search keys, fully caching available filters to prevent database strain.
- **Alerts page**: clicking an alert now opens its details in a modal dialog (close with `Esc` or the close button) instead of an inline panel. Added "Mark as read" / "Mark as unread" (shortcut `R`) and "Next unread" (shortcut `N`) buttons to step through unread alerts, closing the dialog once none remain.

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
- **Audit log redaction**: settings-change entries (`{"old": ..., "new": ...}`) now have sensitive values redacted in *both* the old and new value, including when nested inside change-tracking objects. Previously only flat `{key: "value"}` shapes were redacted, so updating `smtp_password` logged its plaintext value in the audit log.
- **Settings API secret masking**: `GET /settings` and `GET /admin/settings` no longer return `smtp_password` in plaintext to any viewer or admin. The value is masked with a placeholder; submitting the placeholder back leaves the stored secret unchanged (an empty string still clears it), and "Test SMTP Settings" substitutes the real stored password when the placeholder is submitted.

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
