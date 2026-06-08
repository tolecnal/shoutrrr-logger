# shoutrrr-logger

Self-hosted notification logging service for [shoutrrr](https://containrrr.dev/shoutrrr/). Exposes an HTTP ingest endpoint, persists notifications in PostgreSQL 17, and provides a searchable web UI with time-range filtering.

Authentication is handled via OpenID Connect — compatible with Keycloak, Auth0, Authentik, Okta, Microsoft Entra ID, and any other standards-compliant OIDC provider.

---

## Quick start

### docker compose (recommended)

The repository ships a compose file that starts the app, PostgreSQL 17, and an nginx reverse proxy (TLS termination). Copy and edit the example configuration, then start the stack:

```bash
curl -sL https://raw.githubusercontent.com/tolecnal/shoutrrr-logger/main/docker-compose.yml -o docker-compose.yml
curl -sL https://raw.githubusercontent.com/tolecnal/shoutrrr-logger/main/.env.example -o .env
# Edit .env — see Required environment variables below
docker compose up -d
```

Then open `https://<NGINX_SERVER_NAME>` in a browser and sign in via your OIDC provider.

### docker run (standalone)

Requires an external PostgreSQL 17 instance. Exposes the Next.js frontend on **4000** and the FastAPI backend on **9000**.

```bash
docker run -d \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/shoutrrr_logger" \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e OIDC_DISCOVERY_URL="https://your-provider/.well-known/openid-configuration" \
  -e OIDC_CLIENT_ID="shoutrrr-logger" \
  -e OIDC_CLIENT_SECRET="your-client-secret" \
  -e APP_BASE_URL="http://localhost:4000" \
  -p 4000:4000 -p 9000:9000 \
  tolecnal/shoutrrr-logger:latest
```

---

## Required environment variables

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Database password (compose only — also used to build `DATABASE_URL`) |
| `DATABASE_URL` | Full async DSN: `postgresql+asyncpg://user:pass@host:5432/shoutrrr_logger` |
| `SECRET_KEY` | Session signing key — generate with `openssl rand -hex 32` |
| `OIDC_DISCOVERY_URL` | Provider's `/.well-known/openid-configuration` URL |
| `OIDC_CLIENT_ID` | Client ID registered with your OIDC provider (default: `shoutrrr-logger`) |
| `OIDC_CLIENT_SECRET` | Client secret from your OIDC provider |
| `APP_BASE_URL` | Public URL the browser uses to reach the app (e.g. `https://shoutrrr-logger.example.com`) |
| `NGINX_SERVER_NAME` | Public hostname nginx serves (compose only — must match your TLS certificate CN) |

See the full [environment variable reference](https://github.com/tolecnal/shoutrrr-logger#environment-variables) for all options.

---

## Sending notifications

Create an access token in **Admin → Access Tokens**, then POST to the ingest endpoint:

```bash
curl -X POST https://your-instance/api/shoutrrr \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Deploy succeeded", "title": "CI/CD"}'
```

**shoutrrr generic URL** (e.g. for Watchtower):

```
generic+https://your-instance/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN
```

---

## Ports

| Port | Service |
|---|---|
| `4000` | Next.js frontend |
| `9000` | FastAPI backend (REST API + Swagger UI at `/api/docs`) |

In the bundled compose setup these are not exposed to the host — nginx proxies all traffic on ports 80/443.

---

## Image tags

| Tag | Description |
|---|---|
| `latest` | Most recent build from the `main` branch |
| `1.2.3` | Specific release version |
| `1.2` | Latest patch release for a major.minor |
| `sha-abc1234` | Pinned to a specific commit SHA |

---

## Full documentation

For complete setup instructions — including OIDC provider configuration, Keycloak step-by-step guide, Watchtower integration, plugin development, and the full environment variable reference — see the [project README](https://github.com/tolecnal/shoutrrr-logger#readme).
