# shoutrrr-logger

A self-hosted notification logging service for [shoutrrr](https://containrrr.dev/shoutrrr/). It exposes an HTTP endpoint that accepts notifications from shoutrrr, stores them in PostgreSQL 17, and provides a web UI for searching, browsing, filtering, and managing them.

**Stack:** FastAPI (Python 3.14) · Next.js 16 · PostgreSQL 17 · OpenID Connect · Docker  
**Version:** 0.3.0

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
- [Watchtower integration](#watchtower-integration)
- [User roles](#user-roles)
- [Access tokens](#access-tokens)
- [Plugins](#plugins)
- [API reference](#api-reference)
- [Development setup](#development-setup)
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
| `WORKERS` | no | `4` | Number of Gunicorn/Uvicorn worker processes. |
| `DB_POOL_SIZE` | no | `5` | SQLAlchemy connection pool size, *per worker*. Total connections ≈ `WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW)` — keep this under PostgreSQL's `max_connections` (default 100). |
| `DB_MAX_OVERFLOW` | no | `5` | Extra burst connections allowed beyond `DB_POOL_SIZE`, per worker. |
| `BACKEND_URL` | no | `http://localhost:9000` | Internal URL the Next.js server uses to reach FastAPI. Only change this if you run the two as separate services. |

---

## OpenID Connect setup

shoutrrr-logger uses the **Authorization Code flow**. Any provider that publishes a standard OIDC discovery document (`/.well-known/openid-configuration`) works.

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
POST /api/shoutrrr
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
curl -X POST https://shoutrrr-logger.example.com/api/shoutrrr \
  -H "Authorization: Bearer <your-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Backup completed", "title": "Backup job"}'
```

**shoutrrr generic URL scheme:**

shoutrrr's `generic` service forwards to arbitrary HTTP endpoints. Pass the Bearer token via the `@Authorization` header parameter:

```
generic+https://shoutrrr-logger.example.com/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN
```

The `+` is URL-encoded space — shoutrrr decodes this before sending the header, so the server receives `Authorization: Bearer YOUR_TOKEN` correctly.

---

## Watchtower integration

[Watchtower](https://containrrr.dev/watchtower/) uses shoutrrr internally for all its notifications. Point it at shoutrrr-logger using the `generic` scheme and a Bearer token.

### URL format

```
generic+https://shoutrrr-logger.example.com/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN
```

> Behind the bundled nginx reverse proxy, port 9000 is **not** reachable from outside the Docker host — always send through the public HTTPS URL (port 443). For Watchtower running in the same compose stack, see [Same host / compose stack](#same-host--compose-stack) below.

### docker run

```bash
docker run -d \
  --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e WATCHTOWER_NOTIFICATION_URL="generic+https://shoutrrr-logger.example.com/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN" \
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
      WATCHTOWER_NOTIFICATION_URL: "generic+https://shoutrrr-logger.example.com/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN"
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
      WATCHTOWER_NOTIFICATION_URL: "generic+http://app:9000/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN&disabletls=Yes"
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
        WATCHTOWER_NOTIFICATION_URL: "generic+https://shoutrrr-logger.example.com/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN"
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

## User roles

| Role | Access |
|---|---|
| `viewer` | `/log` — browse, search, and inspect notifications; **Preferences → My Tokens** to create personal tokens |
| `admin` | `/log` + `/admin` — manage users, access tokens, plugins, and settings; `/stats` and `/performance` dashboards |

**Roles are controlled entirely by your SSO provider.** On every login the backend re-reads the role claim from the merged token/UserInfo claims and syncs it to the local user record. There is no role management inside shoutrrr-logger — the Admin → Users page is read-only with respect to roles.

To grant or revoke a role: assign or remove the `viewer` / `admin` role (or the custom names configured via `OIDC_ROLE_VIEWER` / `OIDC_ROLE_ADMIN`) in your SSO provider. The change takes effect on the user's next login.

A user who has neither role is refused at login with a diagnostic message.

---

## Access tokens

Access tokens are opaque bearer tokens used to authenticate ingest requests to `POST /api/shoutrrr`. They are stored as HMAC-SHA256 hashes — the plaintext is shown only once at creation time.

### Global tokens (admin-managed)

Created in **Admin → Access Tokens**. Global tokens are visible to all users — any notification received through a global token appears in every user's log view. Global tokens are auto-assigned to the creating admin.

### Personal tokens (user-managed)

Any authenticated user can create personal tokens from **Preferences → My Tokens**. Notifications received through a personal token are only visible to the token's owner (and admins). The number of personal tokens per user is capped by the `max_private_tokens` setting (default: 3).

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

## Plugins

Plugins react to every incoming notification — forward it to an external system, transform it, trigger an alert, and so on. The bundled **Splunk HEC** plugin forwards events to a Splunk HTTP Event Collector with configurable field mappings.

Plugins are configured in **Admin → Plugins**. Click the plugin row to expand the configuration panel. Each plugin has an enabled/disabled toggle and a **Send test event** button to verify connectivity without waiting for a real notification.

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
   These directories are bind-mounted read-only into the nginx container. The filenames must match `NGINX_SERVER_NAME` exactly.

3. **Set `APP_BASE_URL=https://<NGINX_SERVER_NAME>`** (no port — nginx terminates TLS on 443) and register the matching redirect URI with your OIDC provider: `https://<NGINX_SERVER_NAME>/api/auth/callback`.

Plain HTTP requests on port 80 are permanently redirected to HTTPS.
