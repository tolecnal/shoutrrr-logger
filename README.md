# shoutrrr-logger

A self-hosted notification logging service for [shoutrrr](https://containrrr.dev/shoutrrr/). It exposes an HTTP endpoint that accepts notifications from shoutrrr, stores them in PostgreSQL 17, and provides a web UI for searching, browsing, and managing them.

**Stack:** FastAPI (Python 3.14) + Next.js 16, PostgreSQL 17, OpenID Connect (OIDC) authentication, Docker.

---

## Table of contents

- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [OpenID Connect setup](#openid-connect-setup)
  - [Keycloak](#keycloak-recommended)
  - [Other providers](#other-oidc-providers)
  - [First-admin bootstrap](#first-admin-bootstrap)
- [Sending notifications](#sending-notifications)
- [Watchtower integration](#watchtower-integration)
- [User roles](#user-roles)
- [Access tokens](#access-tokens)
- [API reference](#api-reference)
- [Development setup](#development-setup)
- [Building the Docker image](#building-the-docker-image)

---

## Architecture

```
browser
  │
  ▼
Next.js  :4000   ──/api/*──▶  FastAPI  :9000
                                  │
                                  ▼
                           PostgreSQL 17
```

The container runs both processes. The Next.js rewrite rule transparently proxies every `/api/*` request to the FastAPI backend, so the browser only ever talks to port 4000.

FastAPI runs under Gunicorn with multiple Uvicorn workers (default: 4, controlled by `WORKERS`).

---

## Quick start

### Prerequisites

- Docker 24+ with Compose v2
- An OIDC provider (Keycloak, Auth0, Authentik, Dex, …) — see [OpenID Connect setup](#openid-connect-setup)

### 1. Clone and configure

```bash
git clone https://github.com/yourorg/shoutrrr-logger.git
cd shoutrrr-logger
cp .env.example .env
```

Edit `.env` — at minimum set these four values:

```dotenv
POSTGRES_PASSWORD=a-strong-password-here
SECRET_KEY=                # output of: openssl rand -hex 32
OIDC_CLIENT_SECRET=        # from your OIDC provider
OIDC_DISCOVERY_URL=        # see OpenID Connect setup below
```

### 2. Start

```bash
docker compose up -d
```

On first boot the database schema is created automatically.

### 3. Open

Navigate to **http://localhost:4000**. You will be redirected to your OIDC provider to sign in.

---

## Environment variables

All variables are read from `.env` (or from the process environment). The `.env.example` file documents every option.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://shoutrrr:…@postgres:5432/shoutrrr_logger` | Full async SQLAlchemy DSN. Set automatically in docker-compose from the `POSTGRES_*` vars. |
| `POSTGRES_DB` | yes | `shoutrrr_logger` | Database name (docker-compose only) |
| `POSTGRES_USER` | yes | `shoutrrr` | Database user (docker-compose only) |
| `POSTGRES_PASSWORD` | **yes** | _(none)_ | Database password (docker-compose only) |
| `SECRET_KEY` | **yes** | `change-me-in-production` | Secret used to sign session JWTs. Generate with `openssl rand -hex 32`. |
| `OIDC_DISCOVERY_URL` | **yes** | Keycloak master realm | The `/.well-known/openid-configuration` URL of your provider. |
| `OIDC_CLIENT_ID` | yes | `shoutrrr-logger` | OIDC client / app ID. |
| `OIDC_CLIENT_SECRET` | **yes** | _(empty)_ | OIDC client secret. |
| `APP_BASE_URL` | yes | `http://localhost:4000` | Public URL the browser uses to reach the app. Used to build the redirect URI. Must match what you register in your OIDC provider. |
| `WORKERS` | no | `4` | Number of Gunicorn/Uvicorn worker processes. |
| `OIDC_ROLES_CLAIM` | no | `realm_access.roles` | Dot-separated path into the UserInfo JSON that contains the list of role strings. Use `roles` for flat claims (Auth0, Authentik, etc.). |
| `OIDC_ROLE_VIEWER` | no | `viewer` | The role string that maps to the viewer role. |
| `OIDC_ROLE_ADMIN` | no | `admin` | The role string that maps to the admin role. |

---

## OpenID Connect setup

shoutrrr-logger uses the **Authorization Code flow** with PKCE. Any provider that exposes a standard OIDC discovery document (`/.well-known/openid-configuration`) works.

The backend reads the discovery document once on startup and caches it for the lifetime of the process. It uses the following endpoints from the document:

- `authorization_endpoint` — to redirect the browser for login
- `token_endpoint` — to exchange the authorization code for tokens
- `userinfo_endpoint` — to retrieve `sub`, `email`, `preferred_username`, and `name`

The following claims are consumed from the UserInfo response:

| Claim | Used for |
|---|---|
| `sub` | Unique, stable user identifier (never changes) |
| `email` | Display email, synced on every login |
| `preferred_username` | Display username, synced on every login |
| `name` | Full name, synced on every login |
| _(path from `OIDC_ROLES_CLAIM`)_ | Role assignment — **required**. Must resolve to a JSON array of strings containing `viewer` or `admin` (or the values of `OIDC_ROLE_VIEWER` / `OIDC_ROLE_ADMIN`). Synced on every login. |

> Users are **auto-provisioned** on first login: a local user record is created automatically from the SSO claims. No pre-registration is needed. A user who has no recognised role is rejected at login.

The `scope` requested from the provider is `openid email profile`. The roles claim must be included in the UserInfo response — see your provider's mapper/claim configuration.

### Keycloak (recommended)

1. **Create a realm** (e.g. `shoutrrr`) or use an existing one.

2. **Create a client:**
   - Client ID: `shoutrrr-logger`
   - Client authentication: **On** (confidential client)
   - Authentication flow: **Standard flow** (Authorization Code)
   - Valid redirect URIs: `http://localhost:4000/api/auth/callback`
     (replace `localhost:4000` with your public domain in production)
   - Web origins: `http://localhost:4000`

3. **Copy the client secret:**
   Go to *Clients → shoutrrr-logger → Credentials → Client secret*.

4. **Create the roles** — you can use either **realm roles** or **client roles**:

   **Option A — Client roles (simpler, recommended):**
   Go to *Clients → shoutrrr-logger → Roles → Create role* and add `viewer` and `admin`.
   Then assign them: *Users → [select user] → Role mappings → Assign role*.
   The application automatically checks `resource_access.shoutrrr-logger.roles` as a
   fallback, so **no extra mapper or env var change is needed**.

   **Option B — Realm roles:**
   Go to *Realm roles → Create role* and add `viewer` and `admin`.
   Then assign them: *Users → [select user] → Role mappings → Assign role*.
   You will also need to add a protocol mapper (see step 5) so the roles appear in the
   UserInfo response.

5. **(Option B only) Expose realm roles in the UserInfo response:**
   By default Keycloak does not include `realm_access.roles` in the UserInfo endpoint.

   Go to *Clients → shoutrrr-logger → Client scopes → shoutrrr-logger-dedicated → Add mapper → By configuration → User Realm Role*:
   - Name: `realm roles`
   - Token Claim Name: `realm_access.roles`
   - Claim JSON Type: `String`
   - Add to userinfo: **On**
   - Add to access token: **On**

   Save the mapper. Keycloak will now include `"realm_access": {"roles": ["viewer"]}` (or `"admin"`) in the UserInfo response.

   > **Skip this step entirely if you used Option A (client roles).** The token already
   > contains `resource_access.shoutrrr-logger.roles` and the application reads it
   > automatically without any configuration change.

7. **Set the discovery URL** in `.env`:
   ```dotenv
   OIDC_DISCOVERY_URL=https://keycloak.example.com/realms/shoutrrr/.well-known/openid-configuration
   OIDC_CLIENT_ID=shoutrrr-logger
   OIDC_CLIENT_SECRET=<paste secret here>
   # Default claim path works for Keycloak — no need to change these:
   # OIDC_ROLES_CLAIM=realm_access.roles
   # OIDC_ROLE_VIEWER=viewer
   # OIDC_ROLE_ADMIN=admin
   ```

8. **Ensure the `email` scope is enabled** for the client (it is by default). The `profile` scope provides `preferred_username` and `name`.

### Other OIDC providers

The setup is identical for any provider. The only thing you need is the discovery URL and a way to include roles in the UserInfo response. Common examples:

| Provider | Discovery URL pattern | Role claim notes |
|---|---|---|
| Auth0 | `https://<tenant>.auth0.com/.well-known/openid-configuration` | Add a custom action/rule that sets `context.idToken["roles"]`; set `OIDC_ROLES_CLAIM=roles` |
| Authentik | `https://authentik.example.com/application/o/<slug>/.well-known/openid-configuration` | Use a Scope Mapping with `return {"roles": request.user.ak_groups()}` or a Group property; set `OIDC_ROLES_CLAIM=roles` |
| Dex | `https://dex.example.com/.well-known/openid-configuration` | Map groups to roles via a custom connector claim; set `OIDC_ROLES_CLAIM` accordingly |
| Okta | `https://<tenant>.okta.com/oauth2/default/.well-known/openid-configuration` | Add a Groups claim to the authorization server; set `OIDC_ROLES_CLAIM=groups` |
| Google | `https://accounts.google.com/.well-known/openid-configuration` | Google does not expose roles natively — use Authentik or Dex as a proxy in front of Google |
| Microsoft Entra | `https://login.microsoftonline.com/<tenant>/v2.0/.well-known/openid-configuration` | Use App Roles; set `OIDC_ROLES_CLAIM=roles` |

**Redirect URI to register with your provider:**

```
<APP_BASE_URL>/api/auth/callback
```

For example: `https://shoutrrr-logger.example.com/api/auth/callback`

This value must match exactly — no trailing slashes.

### First-admin bootstrap

Because roles come entirely from the SSO provider, getting your first admin is straightforward:

1. Create the `admin` role in your SSO provider (see the Keycloak steps above for reference).
2. Assign that role to your own user account in the SSO provider.
3. Log in to shoutrrr-logger. Your account will be auto-provisioned with the admin role on first login.

There is no bootstrap configuration needed in shoutrrr-logger itself.

**If something goes wrong** and you need to verify what claims your provider is returning, decode the access token at [jwt.io](https://jwt.io) or call the UserInfo endpoint directly:

```bash
curl -H "Authorization: Bearer <your-access-token>" \
     <OIDC_USERINFO_ENDPOINT>
# Confirm the claim path matches OIDC_ROLES_CLAIM and the values match
# OIDC_ROLE_VIEWER / OIDC_ROLE_ADMIN.
```

**Emergency SQL fallback** — if the UserInfo claim mapping cannot be fixed immediately and you need admin access now:

```sql
UPDATE users SET role = 'admin' WHERE sub = 'your-sub-here';
```

Note: this change will be overwritten on the user's next login once the SSO role is correct.

---

## Sending notifications

The notification ingest endpoint is:

```
POST /api/shoutrrr
Authorization: Bearer <access-token>
Content-Type: application/json
```

**Payload:**

```json
{
  "message": "Deployment succeeded",
  "title": "CI/CD"
}
```

Any additional JSON fields are accepted and stored verbatim in `raw_payload`.

**Creating an access token:**

Log in as an admin, go to **Admin → Access Tokens**, and create a token. Copy the raw token value — it is shown **only once**. Use it as the `Bearer` token in the `Authorization` header.

**Example with curl:**

```bash
curl -X POST https://shoutrrr-logger.example.com/api/shoutrrr \
  -H "Authorization: Bearer <your-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Backup completed successfully", "title": "Backup"}'
```

**Configuring shoutrrr to send to this endpoint:**

shoutrrr supports a generic HTTP sender. Add a URL of the form:

```
generic+https://shoutrrr-logger.example.com/api/shoutrrr?title=MyService&disabletls=No
```

And set the token via the shoutrrr `Authorization` header option, or use the `generic` scheme's `headers` parameter:

```
generic+https://shoutrrr-logger.example.com/api/shoutrrr?headers=Authorization:Bearer%20<token>
```

---

## Watchtower integration

[Watchtower](https://containrrr.dev/watchtower/) uses shoutrrr internally for all its notifications. Point it at shoutrrr-logger using the `generic` shoutrrr service scheme and a bearer token created in **Admin → Access Tokens**.

### How the URL is constructed

The shoutrrr `generic` service supports injecting arbitrary HTTP headers via `@HeaderName=value` query parameters. Use this to pass the `Authorization: Bearer` header directly in the URL:

```
generic+https://shoutrrr-logger.example.com/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN
```

For plain HTTP (e.g. internal network, no TLS):

```
generic+http://shoutrrr-logger.example.com:9000/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN&disabletls=Yes
```

Replace `YOUR_TOKEN` with the raw token value shown once when creating a token in **Admin → Access Tokens**.

> The `+` in `Bearer+YOUR_TOKEN` is URL-encoded space — shoutrrr decodes this before sending the header, so the server receives `Authorization: Bearer YOUR_TOKEN` correctly.

Watchtower sends the notification body as **plain text**. shoutrrr-logger accepts both plain text and JSON bodies automatically.

### docker run

```bash
docker run -d \
  --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e WATCHTOWER_NOTIFICATION_URL="generic+https://shoutrrr-logger.example.com/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN" \
  -e WATCHTOWER_NOTIFICATION_REPORT="true" \
  nickfedor/watchtower
```

### docker-compose

Add Watchtower as a service alongside your other containers:

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
      # Optional: check for updates every 24 h (in seconds)
      WATCHTOWER_POLL_INTERVAL: "86400"
```

### Running on the same host as shoutrrr-logger

If Watchtower runs in the same Docker Compose stack as shoutrrr-logger, use the internal service name (`app`) and the internal backend port (`9000`) — no TLS needed on an internal Docker network:

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

### Notification report format

With `WATCHTOWER_NOTIFICATION_REPORT=true` Watchtower sends a structured report after each update session. The message stored in shoutrrr-logger will look like:

```
3 Scanned, 2 Updated, 0 Failed
- myapp (myimage:latest): abc123 updated to def456
- otherapp (otherapp:stable): up to date
```

Without the report flag Watchtower sends individual log lines as separate notifications. Both formats are stored verbatim in the `message` field and fully searchable in the log viewer.

---

## User roles

| Role | Access |
|---|---|
| `viewer` | `/log` — browse, search, and inspect notifications |
| `admin` | `/log` + `/admin` — manage users and access tokens |

**Roles are controlled entirely by your SSO provider.** On every login the backend reads the configured claim from the UserInfo response, determines the user's role, and syncs it to the local user record. There is no role management inside shoutrrr-logger itself — the Admin → Users page shows users and lets you deactivate accounts, but the role column is read-only and always reflects the SSO state.

To grant or revoke a role, assign or remove the `viewer` / `admin` role (or whatever names you configure via `OIDC_ROLE_VIEWER` / `OIDC_ROLE_ADMIN`) in your SSO provider. The change takes effect on the user's next login.

A user who has neither role is refused at login with a clear error message.

---

## Access tokens

Access tokens are opaque bearer tokens used to authenticate calls to `POST /api/shoutrrr`. They are stored as bcrypt hashes — the plaintext is shown only at creation time.

Each token can optionally be linked to a user for auditing and can have an expiration date. Expired or deactivated tokens are rejected immediately.

---

## API reference

Swagger UI is available at:

```
http://localhost:9000/api/docs
```

ReDoc is available at:

```
http://localhost:9000/api/redoc
```

The OpenAPI schema is served at `/api/openapi.json`.

---

## Development setup

### Prerequisites

- Python 3.14+
- Node.js 22+
- pnpm 9+
- PostgreSQL 17 running locally (or via Docker)

### Backend

```bash
cd backend
pip install -e ".[dev]"

# Set required env vars (or create a .env file in backend/)
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/shoutrrr_logger"
export SECRET_KEY="dev-secret-not-for-production"
export OIDC_DISCOVERY_URL="http://localhost:8080/realms/master/.well-known/openid-configuration"
export OIDC_CLIENT_ID="shoutrrr-logger"
export OIDC_CLIENT_SECRET="dev-secret"
export APP_BASE_URL="http://localhost:4000"

uvicorn main:app --reload --port 9000
```

Swagger UI: http://localhost:9000/api/docs

### Frontend

```bash
cd frontend
pnpm install

# Point the dev server at the local backend
echo 'BACKEND_URL=http://localhost:9000' > .env.local

pnpm dev -- --port 4000
```

App: http://localhost:4000

---

## Building the Docker image

The Dockerfile uses a three-stage build:

1. **`frontend-builder`** — Node 22 slim, builds the Next.js standalone bundle.
2. **`python-deps`** — Compiles Python dependency wheels (requires gcc/libpq-dev).
3. **`runtime`** — `python:3.14-slim` (Debian trixie), installs pre-built wheels and copies both the Next.js standalone output and the FastAPI source. No build tools in the final image.

```bash
# Build
docker build -t shoutrrr-logger:latest .

# Run (requires a Postgres 17 instance accessible at DATABASE_URL)
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

Or use docker-compose which also starts a Postgres 17 sidecar:

```bash
docker compose up --build
```

Port 5432 is not exposed externally by default. Uncomment the `ports` block in `docker-compose.yml` if you need direct database access.
