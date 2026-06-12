# shoutrrr-logger

A self-hosted notification logging service for [shoutrrr](https://containrrr.dev/shoutrrr/). It exposes an HTTP endpoint that accepts notifications from shoutrrr, stores them in PostgreSQL 17, and provides a web UI for searching, browsing, filtering, and managing them.

**Stack:** FastAPI (Python 3.14) · Next.js 16 · PostgreSQL 17 · OpenID Connect · Docker  
**Version:** 0.6.0

---

## Table of contents

- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [OpenID Connect setup](#openid-connect-setup)
  - [How role resolution works](#how-role-resolution-works)
  - [Keycloak](#keycloak-recommended)
  - [Other OIDC providers](#other-oidc-providers)
  - [First-admin bootstrap](#first-admin-bootstrap)
  - [Troubleshooting role claims](#troubleshooting-role-claims)
- [Sending notifications](#sending-notifications)
  - [Rate limiting](#rate-limiting)
- [Watchtower integration](#watchtower-integration)
- [Advanced Search](#advanced-search)
- [User roles](#user-roles)
- [Preferences](#preferences)
- [Alerts](#alerts)
- [Access tokens](#access-tokens)
- [Admin settings](#admin-settings)
- [Audit log](#audit-log)
- [Plugins](#plugins)
- [API reference](#api-reference)
- [Development setup](#development-setup)
  - [Database migrations](#database-migrations)
- [Building the Docker image](#building-the-docker-image)
- [Reverse proxy (nginx)](#reverse-proxy-nginx)

---

## Architecture

```
browser
  │
  ▼
nginx  :443 (TLS termination) / :80 (→ 443 redirect)
  │
  ├── /api/* ──▶  FastAPI  :9000  ──▶  PostgreSQL 17
  │
  └── /*     ──▶  Next.js  :4000
```

`docker-compose` runs nginx as the **only** service published to the host. It terminates TLS and routes `/api/*` to the FastAPI backend and everything else to the Next.js frontend. The `app` (frontend + backend) and `postgres` containers are reachable only over the internal compose network — they are not exposed to the host.

The `app` container runs both processes: Next.js on port 4000 and FastAPI under Gunicorn/Uvicorn on port 9000. The Next.js server also rewrites `/api/*` to the backend, which is useful when running the frontend directly during development without nginx.

Gunicorn runs multiple Uvicorn workers (default: 4, controlled by `WORKERS`).

---

## Quick start

### Prerequisites

- Docker 24+ with Compose v2
- An OIDC provider (Keycloak, Auth0, Authentik, …) — see [OpenID Connect setup](#openid-connect-setup)
- A TLS certificate and private key for your public hostname — see [Reverse proxy](#reverse-proxy-nginx)

### 1. Clone and configure

```bash
git clone https://github.com/yourorg/shoutrrr-logger.git
cd shoutrrr-logger
cp .env.example .env
```

Edit `.env`. The minimum required values are:

```dotenv
POSTGRES_PASSWORD=<strong-random-password>
SECRET_KEY=<output of: openssl rand -hex 32>
OIDC_DISCOVERY_URL=<your provider's /.well-known/openid-configuration URL>
OIDC_CLIENT_SECRET=<from your OIDC provider>
NGINX_SERVER_NAME=shoutrrr-logger.example.com
APP_BASE_URL=https://shoutrrr-logger.example.com
```

### 2. Place TLS material

Put your certificate and private key on the Docker host at:

```
/etc/ssl/certs/<NGINX_SERVER_NAME>.crt
/etc/ssl/private/<NGINX_SERVER_NAME>.key
```

The filenames must match `NGINX_SERVER_NAME` exactly — the nginx config references them by that name.

### 3. Start

```bash
docker compose up -d
```

On first boot the database schema is created automatically.

### 4. Open

Navigate to **https://\<NGINX_SERVER_NAME\>**. You will be redirected to your OIDC provider to sign in. See [First-admin bootstrap](#first-admin-bootstrap) if this is a fresh deployment.

---

## Environment variables

All variables are read from `.env` (or from the process environment). The `.env.example` file documents every option with inline comments.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://postgres:postgres@localhost:5432/shoutrrr_logger` | Full async SQLAlchemy DSN. In docker-compose this is assembled automatically from the `POSTGRES_*` vars. |
| `POSTGRES_DB` | yes | `shoutrrr_logger` | Database name (docker-compose only). |
| `POSTGRES_USER` | yes | `shoutrrr` | Database user (docker-compose only). |
| `POSTGRES_PASSWORD` | **yes** | _(none)_ | Database password. Also used to build `DATABASE_URL` in docker-compose. |
| `SECRET_KEY` | **yes** | `change-me-in-production` | Signs session JWTs. Generate with `openssl rand -hex 32`. |
| `OIDC_DISCOVERY_URL` | **yes** | _(Keycloak localhost)_ | Full URL to the provider's `/.well-known/openid-configuration`. |
| `OIDC_CLIENT_ID` | yes | `shoutrrr-logger` | Client / app ID registered with your OIDC provider. |
| `OIDC_CLIENT_SECRET` | **yes** | _(empty)_ | Client secret from your OIDC provider (confidential client). |
| `APP_BASE_URL` | **yes** | `http://localhost:4000` | Public URL the browser uses to reach the app. Used to build the OIDC redirect URI. Must match the redirect URI registered with your provider. Behind the bundled nginx this is `https://<NGINX_SERVER_NAME>` (no port). |
| `NGINX_SERVER_NAME` | **yes** | `shoutrrr-logger.example.com` | Public hostname nginx serves. Used as `server_name` and to locate the TLS cert/key files. |
| `OIDC_SCOPES` | no | `openid email profile roles` | Space-separated OAuth2 scopes requested at login. The `roles` scope is required for Keycloak to include role claims in tokens. Adjust for other providers if needed. |
| `OIDC_ROLES_CLAIM` | no | `realm_access.roles` | Dot-separated path into the token claims that resolves to a list of role strings. Use `roles` for flat-claim providers (Auth0, Authentik, Entra). |
| `OIDC_ROLE_VIEWER` | no | `viewer` | The role string that grants read-only access. |
| `OIDC_ROLE_ADMIN` | no | `admin` | The role string that grants full admin access. |
| `OIDC_VERIFY_AUDIENCE` | no | `false` | Validate the `aud` claim of OIDC access tokens. Off by default because Keycloak issues access tokens with `aud: "account"` unless an audience mapper is configured for the client. |
| `OIDC_AUDIENCE` | no | _(empty)_ | Expected `aud` value when `OIDC_VERIFY_AUDIENCE=true`. Falls back to `OIDC_CLIENT_ID` when empty. |
| `METRICS_TOKEN` | no | _(empty)_ | Optional bearer token protecting the Prometheus `GET /metrics` endpoint. Empty = unauthenticated, which is safe behind the bundled nginx (it never routes `/metrics` to the backend); set it if you expose the backend port directly. |
| `WORKERS` | no | `4` | Number of Gunicorn/Uvicorn worker processes. |
| `DB_POOL_SIZE` | no | `5` | SQLAlchemy connection pool size, *per worker*. Total connections ≈ `WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW)` — keep this under PostgreSQL's `max_connections` (default 100). |
| `DB_MAX_OVERFLOW` | no | `5` | Extra burst connections allowed beyond `DB_POOL_SIZE`, per worker. |
| `BACKEND_URL` | no | `http://localhost:9000` | Internal URL the Next.js server uses to reach FastAPI. Only change this if you run the two as separate services. |
| `SSRF_ALLOWED_HOSTNAMES` | no | _(empty)_ | Comma-separated list of hostnames or IPs explicitly permitted to bypass SSRF IP restriction. Useful for internal webhooks. |

The docker-compose PostgreSQL service is additionally tuned via optional `PG_*` variables (shared buffers, autovacuum, WAL, SSD cost model). Defaults target a 2 GB host; see [.env.example](.env.example) for the full list and recommended values for 4 GB / 8 GB hosts.

---

## OpenID Connect setup

shoutrrr-logger uses the **Authorization Code flow with PKCE (S256)**. The login flow also binds the OIDC `state` to the initiating browser via a signed nonce, so callbacks from other sessions are rejected. Any provider that publishes a standard OIDC discovery document (`/.well-known/openid-configuration`) works.

### How role resolution works

Understanding this section makes provider configuration much easier.

After the user authenticates, the backend:

1. Calls the provider's `token_endpoint` to exchange the authorization code for tokens.
2. Calls the `userinfo_endpoint` to fetch profile claims (`sub`, `email`, `preferred_username`, `name`).
3. **Decodes the access token body** (without signature re-verification — it was just issued by the provider) to read role claims. Keycloak and most other providers put role information in the token body rather than in the UserInfo response.
4. **Merges** the UserInfo response over the token body claims so that profile fields from UserInfo take precedence, but role claims from the token body are also available.
5. Resolves the user's role by checking, in order:
   - The path defined by `OIDC_ROLES_CLAIM` (default: `realm_access.roles`)
   - The Keycloak client-role fallback: `resource_access.<OIDC_CLIENT_ID>.roles`

**A user who has neither the viewer nor admin role is rejected at login with a diagnostic message** listing exactly which claim paths were checked and what was found — this message appears in the browser and in the backend log.

Users are **auto-provisioned** on first login. No pre-registration is required. The local user record (email, username, role) is re-synced from SSO claims on every login.

### Keycloak (recommended)

These steps assume Keycloak 22 or later. The screenshots path may differ slightly across minor versions but the concepts are identical.

#### Step 1 — Create a realm

In the Keycloak Admin Console, create a new realm (e.g. `shoutrrr`) or use an existing one. All subsequent steps are performed inside that realm.

#### Step 2 — Create a client

Go to **Clients → Create client**:

| Setting | Value |
|---|---|
| Client type | OpenID Connect |
| Client ID | `shoutrrr-logger` |
| Client authentication | **On** (makes this a confidential client) |
| Authentication flow | **Standard flow** only |

On the **Settings** tab that follows, set:

| Setting | Value |
|---|---|
| Valid redirect URIs | `https://<your-domain>/api/auth/callback` |
| Valid post logout redirect URIs | `https://<your-domain>/*` |
| Web origins | `https://<your-domain>` |

For local development, add a second redirect URI: `http://localhost:4000/api/auth/callback`

Click **Save**.

#### Step 3 — Copy the client secret

Go to **Clients → shoutrrr-logger → Credentials** and copy the **Client secret**. You will paste this into `OIDC_CLIENT_SECRET` in `.env`.

#### Step 4 — Create roles

You can use **realm roles** or **client roles** — pick one approach and use it consistently.

**Option A — Client roles (recommended)**

Go to **Clients → shoutrrr-logger → Roles → Create role** and create two roles: `viewer` and `admin`.

Client roles are automatically included in `resource_access.shoutrrr-logger.roles` in the access token when the `roles` scope is requested. The application checks this path as a built-in fallback — **no env var changes or additional mappers are required**.

**Option B — Realm roles**

Go to **Realm roles → Create role** and create two roles: `viewer` and `admin`.

Realm roles are automatically included in `realm_access.roles` in the access token when the `roles` scope is requested. This matches the default `OIDC_ROLES_CLAIM=realm_access.roles` — **no env var changes or additional mappers are required**.

> Both options work without any protocol mapper configuration, as long as `roles` is included in `OIDC_SCOPES` (it is by default). The built-in Keycloak `roles` scope maps both realm roles and client roles into the access token. The application reads claims from the token body, not only from the UserInfo endpoint.

#### Step 5 — Assign roles to users

Go to **Users → [select a user] → Role mappings → Assign role**.

- For **client roles**: filter by `shoutrrr-logger` in the client dropdown, then assign `viewer` or `admin`.
- For **realm roles**: assign `viewer` or `admin` from the realm role list.

#### Step 6 — Verify the `roles` scope is assigned to the client

Go to **Clients → shoutrrr-logger → Client scopes** and confirm that `roles` appears in the assigned scopes list (it is included by default when you create a new client). If it is missing, click **Add client scope**, select `roles`, and add it as a **Default** scope.

This scope is what causes Keycloak to embed role claims in the access token. Without it, `realm_access.roles` and `resource_access.<client>.roles` will not appear in the token and login will fail with a "no recognised role" error.

#### Step 7 — Configure `.env`

```dotenv
OIDC_DISCOVERY_URL=https://keycloak.example.com/realms/shoutrrr/.well-known/openid-configuration
OIDC_CLIENT_ID=shoutrrr-logger
OIDC_CLIENT_SECRET=<paste the secret from Step 3>
APP_BASE_URL=https://shoutrrr-logger.example.com

# The defaults below already match Keycloak — only change them if you
# customised the role names or used a non-standard claim path.
# OIDC_SCOPES=openid email profile roles
# OIDC_ROLES_CLAIM=realm_access.roles
# OIDC_ROLE_VIEWER=viewer
# OIDC_ROLE_ADMIN=admin
```

#### When would I need a protocol mapper?

The `roles` scope covers most setups. You only need to add a custom protocol mapper if:

- You renamed `realm_access.roles` to a custom path and need it in the UserInfo response rather than just the token body.
- Your Keycloak version (older than 19) does not include the built-in `roles` scope.
- You are using a non-standard role claim structure.

To add a mapper: **Clients → shoutrrr-logger → Client scopes → shoutrrr-logger-dedicated → Add mapper → By configuration → User Realm Role**. Set *Token Claim Name* to `realm_access.roles`, enable *Add to access token* and *Add to userinfo*, and update `OIDC_ROLES_CLAIM` in `.env` to match.

---

### Other OIDC providers

The application works with any OIDC provider. You need the discovery URL and a way to include a roles/groups claim in the token.

| Provider | `OIDC_DISCOVERY_URL` | `OIDC_ROLES_CLAIM` | Notes |
|---|---|---|---|
| Auth0 | `https://<tenant>.auth0.com/.well-known/openid-configuration` | `roles` | Add a custom action that sets `event.accessToken.setCustomClaim("roles", [...])`. |
| Authentik | `https://authentik.example.com/application/o/<slug>/.well-known/openid-configuration` | `roles` | Use a Scope Mapping with `return {"roles": [g.name for g in request.user.ak_groups()]}`. |
| Dex | `https://dex.example.com/.well-known/openid-configuration` | depends | Map groups to a custom claim via your Dex connector config; set `OIDC_ROLES_CLAIM` to match. |
| Okta | `https://<tenant>.okta.com/oauth2/default/.well-known/openid-configuration` | `groups` | Add a Groups claim to the authorization server policy; set `OIDC_ROLES_CLAIM=groups`. |
| Microsoft Entra ID | `https://login.microsoftonline.com/<tenant>/v2.0/.well-known/openid-configuration` | `roles` | Configure App Roles in the app registration and assign them to users. |
| Google | `https://accounts.google.com/.well-known/openid-configuration` | N/A | Google has no built-in roles. Use Authentik or Dex as a federation layer in front of Google. |

**The redirect URI to register with your provider:**

```
<APP_BASE_URL>/api/auth/callback
```

For example: `https://shoutrrr-logger.example.com/api/auth/callback`

This value must match exactly — no trailing slash.

---

### First-admin bootstrap

Because roles come entirely from the SSO provider, getting your first admin is straightforward:

1. Create the `admin` role in your SSO provider (see the Keycloak steps above).
2. Assign that role to your own user account in the SSO provider.
3. Log in to shoutrrr-logger. Your account will be auto-provisioned with the admin role on first login.

No bootstrap configuration is required in shoutrrr-logger itself.

---

### Troubleshooting role claims

**Check what the provider actually returns**

Decode the access token at [jwt.io](https://jwt.io) and look for the claim path you configured in `OIDC_ROLES_CLAIM`. Also call the UserInfo endpoint directly:

```bash
curl -H "Authorization: Bearer <your-access-token>" <OIDC_USERINFO_ENDPOINT>
```

The diagnostic message shown at login failure also lists exactly which paths were checked and what was found — check the backend log (`docker compose logs app`) or your browser for this message.

**Common issues with Keycloak**

| Symptom | Likely cause | Fix |
|---|---|---|
| "No recognised role" — `realm_access` is missing | `roles` scope not assigned to the client | Add the built-in `roles` scope (Step 6) |
| "No recognised role" — roles list is present but wrong values | Role names differ from `OIDC_ROLE_VIEWER` / `OIDC_ROLE_ADMIN` | Set the env vars to match the exact strings in Keycloak |
| "No recognised role" — `resource_access` but not `realm_access` | Using client roles but `OIDC_ROLES_CLAIM=realm_access.roles` | The application falls back to `resource_access` automatically; confirm `roles` scope is assigned |
| Login loop / redirect error | `APP_BASE_URL` does not match the registered redirect URI | Update both `APP_BASE_URL` in `.env` and the Valid Redirect URI in Keycloak to the same value |

**Emergency SQL access** — if you cannot fix the SSO role mapping immediately and need admin access now:

```sql
UPDATE users SET role = 'admin' WHERE sub = 'your-oidc-sub-here';
```

This change is overwritten on the user's next login once the SSO role is correct.

---

## Sending notifications

The notification ingest endpoint accepts `POST` requests with a Bearer token:

```
POST /api/v1/shoutrrr
Authorization: Bearer <access-token>
Content-Type: application/json
```

**JSON body:**

```json
{
  "message": "Deployment succeeded",
  "title": "CI/CD"
}
```

Any additional JSON fields are stored verbatim and accessible as `custom_fields` in the log viewer and plugins.

**Creating an access token:**

- **Global token** (shared): log in as an admin, go to **Admin → Access Tokens**, create a token, and copy the raw value — it is shown **only once**.
- **Personal token** (private): go to **Preferences → My Tokens**, create a token, and copy the raw value — also shown **only once**.

**curl example:**

```bash
curl -X POST https://shoutrrr-logger.example.com/api/v1/shoutrrr \
  -H "Authorization: Bearer <your-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Backup completed", "title": "Backup job"}'
```

**PowerShell example:**

```powershell
Invoke-RestMethod -Method Post -Uri "https://shoutrrr-logger.example.com/api/v1/shoutrrr" `
  -Headers @{ Authorization = "Bearer <your-access-token>" } `
  -ContentType "application/json" `
  -Body (@{ message = "Backup completed"; title = "Backup job" } | ConvertTo-Json)
```

**Python example (requests):**

```python
import requests

requests.post(
    "https://shoutrrr-logger.example.com/api/v1/shoutrrr",
    headers={"Authorization": "Bearer <your-access-token>"},
    json={"message": "Backup completed", "title": "Backup job"},
)
```

**PHP example:**

```php
$ch = curl_init("https://shoutrrr-logger.example.com/api/v1/shoutrrr");
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "Authorization: Bearer <your-access-token>",
    "Content-Type: application/json",
]);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    "message" => "Backup completed",
    "title" => "Backup job",
]));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_exec($ch);
curl_close($ch);
```

**wget example:**

```bash
wget -q -O- --method=POST \
  --header="Authorization: Bearer <your-access-token>" \
  --header="Content-Type: application/json" \
  --body-data='{"message": "Backup completed", "title": "Backup job"}' \
  https://shoutrrr-logger.example.com/api/v1/shoutrrr
```

**shoutrrr generic URL scheme:**

shoutrrr's `generic` service forwards to arbitrary HTTP endpoints. Pass the Bearer token via the `@Authorization` header parameter:

```
generic+https://shoutrrr-logger.example.com/api/v1/shoutrrr?@Authorization=Bearer+YOUR_TOKEN
```

The `+` is URL-encoded space — shoutrrr decodes this before sending the header, so the server receives `Authorization: Bearer YOUR_TOKEN` correctly.

### Rate limiting

Ingestion can be rate-limited per access token. The default **Notification rate limit** ([Admin settings](#admin-settings)) is `0` (unlimited). Admins can also set a per-token override in **Admin → Access Tokens**: leave it unset to inherit the global limit, set it to `0` to make that token explicitly unlimited, or set a custom requests-per-minute value.

Requests over the limit receive `429 Too Many Requests` with a `Retry-After: 60` header.

---

## Watchtower integration

[Watchtower](https://containrrr.dev/watchtower/) uses shoutrrr internally for all its notifications. Point it at shoutrrr-logger using the `generic` scheme and a Bearer token.

### URL format

```
generic+https://shoutrrr-logger.example.com/api/v1/shoutrrr?@Authorization=Bearer+YOUR_TOKEN
```

> Behind the bundled nginx reverse proxy, port 9000 is **not** reachable from outside the Docker host — always send through the public HTTPS URL (port 443). For Watchtower running in the same compose stack, see [Same host / compose stack](#same-host--compose-stack) below.

### docker run

```bash
docker run -d \
  --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e WATCHTOWER_NOTIFICATION_URL="generic+https://shoutrrr-logger.example.com/api/v1/shoutrrr?@Authorization=Bearer+YOUR_TOKEN" \
  -e WATCHTOWER_NOTIFICATION_REPORT="true" \
  nickfedor/watchtower
```

### docker-compose (separate host)

```yaml
services:
  watchtower:
    image: nickfedor/watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      WATCHTOWER_NOTIFICATION_URL: "generic+https://shoutrrr-logger.example.com/api/v1/shoutrrr?@Authorization=Bearer+YOUR_TOKEN"
      WATCHTOWER_NOTIFICATION_REPORT: "true"
      WATCHTOWER_POLL_INTERVAL: "86400"   # optional: check every 24 h
```

### Same host / compose stack

If Watchtower runs in the same compose stack as shoutrrr-logger, use the internal service name and port — no TLS needed on the Docker-internal network:

```yaml
services:
  watchtower:
    image: nickfedor/watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      WATCHTOWER_NOTIFICATION_URL: "generic+http://app:9000/api/v1/shoutrrr?@Authorization=Bearer+YOUR_TOKEN&disabletls=Yes"
      WATCHTOWER_NOTIFICATION_REPORT: "true"
    depends_on:
      - app
```

### TLS trust errors with self-signed certificates

If nginx is serving a self-signed or private-CA certificate and Watchtower runs on a **different host**, you may see:

```
x509: certificate signed by unknown authority
```

This is Watchtower's Go HTTP client refusing to trust a certificate that isn't in its system trust store. Options:

- **Use a publicly-trusted certificate** (recommended) — Let's Encrypt if the host is publicly reachable, or your organisation's internal CA. Fixes this for all external clients without per-client configuration.
- **Mount the certificate into the Watchtower container** and point Go at it via `SSL_CERT_FILE`:

  ```yaml
  services:
    watchtower:
      image: nickfedor/watchtower
      volumes:
        - /var/run/docker.sock:/var/run/docker.sock
        - /etc/ssl/certs/shoutrrr-logger.example.com.crt:/certs/shoutrrr-logger.crt:ro
      environment:
        SSL_CERT_FILE: /certs/shoutrrr-logger.crt
        WATCHTOWER_NOTIFICATION_URL: "generic+https://shoutrrr-logger.example.com/api/v1/shoutrrr?@Authorization=Bearer+YOUR_TOKEN"
  ```

  Note: `SSL_CERT_FILE` **replaces** Go's default trust store entirely. If Watchtower also pulls from private registries over TLS, concatenate the system CA bundle and your certificate into a single PEM file and mount that instead.

- **Run on the same compose stack** and use the internal HTTP URL — bypasses TLS entirely.

### Notification report format

With `WATCHTOWER_NOTIFICATION_REPORT=true`, Watchtower sends a structured summary after each update run:

```
3 Scanned, 2 Updated, 0 Failed
- myapp (myimage:latest): abc123 updated to def456
- otherapp (otherapp:stable): up to date
```

Without the flag it sends individual log lines as separate notifications. Both formats are stored verbatim and fully searchable.

---

## Advanced Search

The notification log features a powerful search bar with auto-complete and advanced query syntax.

- **Field Targeting**: Prefix terms with a field name to restrict searches: `title:`, `message:`, `sender:`, `severity:`, or `tag:`.
- **Exact Phrases**: Use quotes to match exact phrases: `"database timeout"`.
- **Wildcards**: Use `*` to match any characters, and `?` for a single character (e.g. `sender:app*`).
- **Regular Expressions**: Enclose queries in forward slashes to execute regex searches: `message:/timeout|disconnect/`.
- **Time Filters**: Filter by relative time (`after:1h`, `before:2d`) or absolute dates (`after:2024-01-01`).
- **Free-text**: Any terms without prefixes search across the title, message, and sender name simultaneously.

Queries can be mixed and matched: `severity:error tag:prod /timeout/ after:1h`

---

## User roles

| Role | Access |
|---|---|
| `viewer` | `/log` — browse, search, and inspect notifications; **Preferences → My Tokens** to create personal tokens |
| `admin` | `/log` + `/admin` — manage users, access tokens, plugins, and settings; `/stats` and `/performance` dashboards |

**Roles are controlled entirely by your SSO provider.** On every login the backend re-reads the role claim from the merged token/UserInfo claims and syncs it to the local user record. There is no role management inside shoutrrr-logger — the Admin → Users page is read-only with respect to roles.

To grant or revoke a role: assign or remove the `viewer` / `admin` role (or the custom names configured via `OIDC_ROLE_VIEWER` / `OIDC_ROLE_ADMIN`) in your SSO provider. The change takes effect on the user's next login.

A user who has neither role is refused at login with a diagnostic message.

---

## Preferences

Every signed-in user can open **Preferences** (gear icon in the top bar) to customize their own view. Preferences are stored in the browser (`localStorage`) and are per-user, per-device.

- **Display** — theme (Light / Dark / System) and time format (locale-aware, 12-hour, or 24-hour).
- **Labels** — highlight notifications whose message or title match a pattern with a chosen color, optionally excluding matches from the log entirely.
- **Alert rules** — configure conditions (e.g. matching tags, severity, or message patterns) to trigger visual alerts in the UI, and optionally receive customized email notifications via SMTP.
- **My Tokens** — create and manage personal access tokens (see [Access tokens](#access-tokens)).
- **Plugins** — configure your own plugin settings, like a personal Slack webhook URL, with custom routing rules.

---

## Alerts

The **Alerts** page (sidebar, with an unread-count badge) lists notifications that matched one of your alert rules. Clicking an alert opens its full details in a modal dialog.

From the dialog you can:

- **Mark as read / Mark as unread** — toggle the alert's read state (shortcut: `R`).
- **Next unread** — jump straight to the next unread alert in the list (shortcut: `N`). If there are no more unread alerts, the dialog closes.

Keyboard shortcuts are active whenever the dialog is open and no modifier key (Ctrl/Cmd/Alt) is held.

---

## Access tokens

Access tokens are opaque bearer tokens used to authenticate ingest requests to `POST /api/v1/shoutrrr`. They are stored as HMAC-SHA256 hashes — the plaintext is shown only once at creation time.

### Global tokens (admin-managed)

Created in **Admin → Access Tokens**. Global tokens are visible to all users — any notification received through a global token appears in every user's log view. Global tokens are auto-assigned to the creating admin.

### Personal tokens (user-managed)

Any authenticated user can create personal tokens from **Preferences → My Tokens**. Notifications received through a personal token are only visible to the token's owner (and admins). The number of personal tokens per user is capped by the `max_private_tokens` setting (default: 3).

Admins can disable private access tokens entirely via the **Allow private access tokens** [admin setting](#admin-settings). When disabled, users can no longer create new personal tokens, and existing personal tokens are rejected (`403 Forbidden`) for notification ingestion. Global tokens continue to work as normal.

### Testing a token

Both **Admin → Access Tokens** and **Preferences → My Tokens** have a "Test" button that opens a dialog with ready-to-use, syntax-highlighted, copy-paste examples (curl, PowerShell, Python, PHP, wget, and the shoutrrr generic URL scheme) for sending a test notification with that token.

### Filtering by scope

The notification log has a **Scope** filter:

| Scope | What you see |
|---|---|
| **All** | Global token notifications + your own personal token notifications (admins see everything) |
| **Global** | Only notifications from global tokens |
| **My tokens** | Only notifications from your own personal tokens |

### Token lifecycle

Each token can optionally be given an expiry date — expired tokens are rejected immediately. Tokens can be activated/deactivated without deleting them.

---

## Admin settings

**Admin → Settings** controls application-wide behavior. All settings are stored in the database and take effect immediately — no restart required.

| Setting | Default | Description |
|---|---|---|
| Retention period | `0` (forever) | Automatically delete notifications older than this many days. |
| Items per page | `20` | Number of notifications shown per page in the log. |
| Auto-refresh interval | `30` seconds | How often the notification log refreshes automatically. `0` disables auto-refresh. |
| Statistics window | `30` days | Number of days shown in the `/stats` activity chart. Cannot exceed Retention period or API metrics retention (when either is non-zero). |
| Allow private access tokens | enabled | Whether users may create their own private access tokens from Preferences → My Tokens. When disabled, existing private tokens are also rejected for ingestion. |
| Max private tokens per user | `3` | Cap on personal access tokens each user may create. `0` = unlimited. |
| Notification rate limit | `0` (unlimited) | Default per-token ingestion rate limit, in notifications per minute. Overridable per token — see [Rate limiting](#rate-limiting). |
| API metrics retention | `30` days | Automatically delete `/performance` latency records older than this many days. `0` keeps them forever. |
| Audit log retention | `365` days | Automatically delete audit log entries older than this many days. `0` keeps them forever. |
| Email alerts enabled | disabled | Master toggle for email alerts. Enables the SMTP settings below. |
| SMTP Settings | _(none)_ | Host, Port, Username, Password, and From Address. Used to dispatch email alerts. Once a password is saved, the API and UI never show its plaintext value again — the field displays a placeholder, which is left untouched unless you type a new password (or clear the field to remove it). |

Retention sweeps for notifications, API metrics, and audit logs run hourly. In multi-worker deployments, only one Gunicorn worker performs the sweep — workers coordinate via a PostgreSQL session-level advisory lock, so the same rows are never purged twice.

---

## Audit log

**Admin → Audit Log** records every admin action: creating, updating, or deleting users, access tokens, and plugin configuration, plus changes to the settings above.

Each entry captures the acting user, an action code (`user.create`, `user.update`, `user.delete`, `token.create`, `token.update`, `token.delete`, `settings.update`, `plugin.update`), the affected resource, a redacted snapshot of what changed, the source IP, and a timestamp. Fields that look like secrets (tokens, passwords, keys, HEC URLs, etc.) are masked as `***REDACTED***` before being stored, so raw access tokens and plugin credentials never appear in the audit log — including both the old and new values for `settings.update` entries.

The admin UI supports filtering by action and time range. The same data is available via `GET /api/v1/admin/audit-logs`. Entries older than the **Audit log retention** setting above are purged automatically.

---

## Plugins

Plugins react to every incoming notification — forward it to an external system, transform it, trigger an alert, and so on. The bundled **Splunk HEC** plugin forwards events to a Splunk HTTP Event Collector with configurable field mappings, and the **Slack** plugin forwards events to a Slack workspace via an Incoming Webhook URL.

Plugins are configured globally in **Admin → Plugins**. Click the plugin row to expand the configuration panel. Global configurations use the same named **profiles** as user configurations (see below): each profile has its own settings, routing rules, enable toggle, and **Send test** button, and admins may create any number of them. Admins can also toggle the ability for individual users to configure the plugin for themselves.

### User Plugin Configurations

If enabled by the admin, users can manage their own plugin configurations under **Preferences → Plugins**. A user can set up their own Slack webhook, for example, to receive notifications directly to their channel.

#### Configuration profiles

Both global (admin) and per-user plugin configurations support multiple **named configuration profiles**, shown as tabs in the plugin's panel. Every profile has its own settings, routing rules, and enable toggle, and every enabled profile is dispatched independently — so you can, say, send `critical` notifications to one Slack channel and everything else to another. Profiles can be renamed, duplicated ("copy settings and rules from the current profile"), deleted, and test-fired individually.

By default users may create up to **5 profiles per plugin** — adjustable via the *Max plugin profiles per user* setting in **Admin → Settings** (0 = unlimited). Admins are always exempt from the cap.

### Routing Rules

Both global admin configurations and individual user plugin configurations support **Routing Rules**. By default, all notifications are routed to an enabled plugin. You can define routing rules to only forward notifications that match specific criteria:
- **Severity**: only forward if severity is `critical` or `error`.
- **Sender**: only forward if sender matches a specific name.
- **Tags**: only forward if the notification contains specific tags.
- **Token ID**: only forward if the notification was ingested using a specific access token.
- **Message Content**: only forward if the message matches a regex pattern.

Routing rules are evaluated per plugin, meaning each integration can have its own distinct set of filters.

### Security (SSRF Protection)

All outbound plugin integrations that require HTTP connections (e.g., Slack webhooks, Splunk HEC) are strictly validated to prevent **Server-Side Request Forgery (SSRF)**. 
- The target hostname is resolved via `socket.getaddrinfo`.
- The resolved IP address is verified against a strict denylist, immediately rejecting connections to private (RFC 1918), loopback, link-local, multicast, or reserved IP ranges.
- This ensures users cannot abuse the plugin system to blindly scan or attack services on the internal network or the Docker host.

If you are self-hosting and need to route webhooks to an internal service (e.g. an internal Splunk instance on your LAN), you can whitelist specific hostnames or IP addresses by setting the `SSRF_ALLOWED_HOSTNAMES` environment variable to a comma-separated list.
Example: `SSRF_ALLOWED_HOSTNAMES=vm-splunk01.xiro.net,192.168.1.1`

To build a custom plugin, see **[PLUGINS.md](PLUGINS.md)**.

---

## API reference

Interactive documentation is served by the running application:

| Interface | URL |
|---|---|
| Swagger UI | `https://<your-domain>/api/docs` |
| ReDoc | `https://<your-domain>/api/redoc` |
| OpenAPI schema | `https://<your-domain>/api/openapi.json` |

During local development (backend running directly): `http://localhost:9000/api/docs`

**Pagination**: `GET /api/v1/notifications` and `GET /api/v1/admin/audit-logs` use cursor-based (keyset) pagination. Each response includes `next_cursor`; pass it as the `cursor` query parameter to fetch the next page. `next_cursor` is `null` on the last page.

---

## Development setup

### Prerequisites

- Python 3.14+ with [uv](https://docs.astral.sh/uv/)
- Node.js 22+ with pnpm 10+
- PostgreSQL 17 (local install or `docker compose up postgres`)

### Backend

```bash
cd backend

# Install dependencies with uv
uv sync

# Set required environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/shoutrrr_logger"
export SECRET_KEY="dev-secret-not-for-production"
export OIDC_DISCOVERY_URL="http://localhost:8080/realms/shoutrrr/.well-known/openid-configuration"
export OIDC_CLIENT_ID="shoutrrr-logger"
export OIDC_CLIENT_SECRET="dev-secret"
export APP_BASE_URL="http://localhost:4000"

# Run with auto-reload
uv run uvicorn main:app --reload --port 9000
```

Swagger UI is available at `http://localhost:9000/api/docs`.

### Database migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/). The
migration scripts live in `backend/migrations/versions/`.

```bash
cd backend

# After changing a model in models.py, generate a migration for it
uv run alembic revision --autogenerate -m "describe the change"

# Review the generated script in migrations/versions/, then apply it
uv run alembic upgrade head
```

Notes:

- On startup, `init_db()` still creates any missing tables/columns/indexes
  from `models.py` directly (as it always has) and stamps a fresh
  `alembic_version` table at the baseline revision if one doesn't exist yet —
  so existing databases (created before Alembic was introduced) need no
  manual `alembic stamp` step.
- **In the Docker image, pending migrations are applied automatically at
  container startup** (the entrypoint runs `alembic upgrade head` before the
  servers start), so deploying a new release needs no manual migration step.
  Set `AUTO_MIGRATE=false` to opt out and run migrations out-of-band — e.g.
  for multi-replica deployments where exactly one process should migrate.
- When running the backend outside Docker, run `alembic upgrade head` as part
  of your deploy after pulling a release that adds migrations.
- Always review autogenerated migrations before committing; Alembic doesn't
  reliably detect every change (e.g. some index option changes).
- Never edit a migration that has already been applied to a shared/production
  database — add a new migration instead.

### Frontend

```bash
cd frontend
pnpm install

# Point the dev server at the local backend
echo 'BACKEND_URL=http://localhost:9000' > .env.local

pnpm dev --port 4000
```

App is available at `http://localhost:4000`.

### Running tests

```bash
# Backend
cd backend
uv run pytest

# Frontend
cd frontend
pnpm test:run
```

---

## Building the Docker image

The Dockerfile uses a three-stage build:

1. **`frontend-builder`** — Node 22 Alpine: runs `pnpm build` from the workspace root and emits a standalone Next.js bundle.
2. **`python-deps`** — Debian slim with build tools: compiles Python dependency wheels (no build tools in the final image).
3. **`runtime`** — `python:3.14-slim`: installs pre-built wheels, copies the Next.js standalone output and the FastAPI source tree, generates version metadata from build args.

```bash
# Build
docker build \
  --build-arg GIT_HASH=$(git rev-parse --short HEAD) \
  --build-arg BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  -t shoutrrr-logger:0.2.0 \
  -t shoutrrr-logger:latest \
  .

# Run standalone (requires external Postgres)
docker run --rm \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/shoutrrr_logger" \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e OIDC_DISCOVERY_URL="https://keycloak.example.com/realms/shoutrrr/.well-known/openid-configuration" \
  -e OIDC_CLIENT_ID="shoutrrr-logger" \
  -e OIDC_CLIENT_SECRET="your-client-secret" \
  -e APP_BASE_URL="http://localhost:4000" \
  -p 4000:4000 -p 9000:9000 \
  shoutrrr-logger:latest
```

Or use `docker compose` which also starts a PostgreSQL 17 sidecar and the nginx reverse proxy:

```bash
docker compose up --build
```

The `postgres` container's port 5432 is not exposed to the host by default. Uncomment the `ports` block in `docker-compose.yml` if you need direct database access during development.

---

## Reverse proxy (nginx)

`docker-compose` runs nginx 1.31.1 as the **only** service exposed to the host (ports 80 and 443). It terminates TLS and reverse-proxies:

- `/api/*` → FastAPI backend at `app:9000` — REST API, Swagger/ReDoc, the OIDC callback, and the shoutrrr ingest endpoint
- everything else → Next.js frontend at `app:4000`

The `app` and `postgres` containers use `expose:` (not `ports:`), so they are reachable only from nginx over the internal compose network.

The nginx config is generated from the template at [`nginx-config/templates/default.conf.template`](nginx-config/templates/default.conf.template) using the official nginx image's `envsubst` mechanism, substituting `${NGINX_SERVER_NAME}` from the container environment. Edit that file to change routing or TLS settings; the rendered config is regenerated on each `docker compose up`.

### Requirements

1. **Set `NGINX_SERVER_NAME`** in `.env` to the public hostname (e.g. `shoutrrr-logger.example.com`) — no scheme, no port.

2. **Place TLS material on the Docker host:**
   ```
   /etc/ssl/certs/<NGINX_SERVER_NAME>.crt       # certificate (PEM, full chain)
   /etc/ssl/private/<NGINX_SERVER_NAME>.key      # private key (PEM)
   ```
   These two files are bind-mounted read-only into the nginx container (only this site's cert/key — not the whole `/etc/ssl` tree). The filenames must match `NGINX_SERVER_NAME` exactly.

3. **Set `APP_BASE_URL=https://<NGINX_SERVER_NAME>`** (no port — nginx terminates TLS on 443) and register the matching redirect URI with your OIDC provider: `https://<NGINX_SERVER_NAME>/api/auth/callback`.

Plain HTTP requests on port 80 are permanently redirected to HTTPS.

---

## Contributing & security

- **Contributing**: see [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, and the [Code of Conduct](CODE_OF_CONDUCT.md) that applies to all project spaces.
- **Security**: please report vulnerabilities privately per the [security policy](SECURITY.md) — not via public issues.
- **License**: [MIT](LICENSE).
