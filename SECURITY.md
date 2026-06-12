# Security Policy

shoutrrr-logger is a self-hosted notification logging service. Security reports
are taken seriously and handled promptly — thank you for helping keep the
project and its users safe.

## Supported Versions

Only the latest release receives security fixes. There are no long-term support
branches; upgrading is the supported remediation path.

| Version        | Supported |
| -------------- | --------- |
| Latest release | ✅        |
| Older releases | ❌        |

## Reporting a Vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately through either channel:

1. **GitHub**: [Report a vulnerability](https://github.com/tolecnal/shoutrrr-logger/security/advisories/new)
   (GitHub private vulnerability reporting — preferred)
2. **Email**: tolecnal@tolecnal.net — include `[SECURITY] shoutrrr-logger` in
   the subject line

Include what you can of the following:

- A description of the vulnerability and its impact
- Steps to reproduce (a proof of concept helps a lot)
- The affected version(s) and relevant configuration (e.g. behind the bundled
  nginx or directly exposed)
- Any suggested fix, if you have one

### What to expect

This is a single-maintainer open-source project, so response times are
best-effort:

- **Acknowledgement** within 7 days
- **Assessment and fix timeline** communicated once the report is triaged
- **Credit** in the changelog and release notes, unless you prefer to remain
  anonymous

Please allow a fix to be released before disclosing publicly. Confirmed
vulnerabilities are documented in the [CHANGELOG](CHANGELOG.md) under a
`### Security` heading, as in past releases.

## Scope

**In scope:**

- The FastAPI backend (authentication, authorization, ingestion, plugins, API)
- The Next.js frontend
- The bundled deployment artifacts: `Dockerfile`, `docker-compose.yml`, the
  nginx config template, and CI workflows
- Dependency vulnerabilities that are actually exploitable through this
  application

**Out of scope:**

- Vulnerabilities in your OIDC provider (e.g. Keycloak), PostgreSQL, Docker, or
  the host OS
- Issues that require ignoring the documented deployment model (see below) —
  e.g. attacks that assume the backend port or PostgreSQL is exposed directly
  to the internet
- Denial of service through volume alone (ingestion is rate-limited per token;
  capacity planning is the operator's responsibility)
- Reports from automated scanners without a demonstrated impact

## Deployment Security Model

shoutrrr-logger's security posture assumes the documented deployment shape.
When reporting (and when deploying), note these expectations:

- **nginx is the only exposed service.** The backend (port 9000), frontend
  (port 4000), and PostgreSQL must not be published directly. The Prometheus
  `/metrics` endpoint is unauthenticated by default *because* nginx never
  routes it; set `METRICS_TOKEN` if you expose the backend port anyway.
- **HTTPS is required in production.** Session cookies are marked `Secure`
  based on `APP_BASE_URL`; the bundled nginx redirects HTTP→HTTPS and sends
  HSTS.
- **Secrets come from the environment.** `SECRET_KEY` must be ≥32 characters
  (enforced at startup in production); generate it with `openssl rand -hex 32`.
  Never commit `.env`.
- **Authentication is delegated to your OIDC provider** (Authorization Code
  flow with PKCE). Access control is role-based via token claims — keep the
  `viewer`/`admin` role mappings (`OIDC_ROLE_*`) accurate in your provider.
- **Ingestion tokens are bearer credentials.** They are stored hashed and shown
  once at creation; treat them like passwords and rotate them if leaked.
- **Outbound plugin requests are SSRF-filtered** (private/loopback/reserved IPs
  are blocked, with DNS-rebinding protection). `SSRF_ALLOWED_HOSTNAMES` and
  `SSRF_VALIDATION_DISABLED` weaken this deliberately — use the former
  sparingly and the latter never in production.

## Security-Relevant Configuration Reference

| Setting | Default | Notes |
| --- | --- | --- |
| `SECRET_KEY` | _(none)_ | Signs session JWTs; ≥32 chars enforced in production |
| `OIDC_CLIENT_SECRET` | _(none)_ | Required in production |
| `OIDC_VERIFY_AUDIENCE` / `OIDC_AUDIENCE` | off | Opt-in `aud` validation of OIDC access tokens |
| `METRICS_TOKEN` | _(empty)_ | Opt-in bearer auth for `GET /metrics` |
| `SSRF_ALLOWED_HOSTNAMES` | _(empty)_ | Allowlist for internal plugin destinations |
| `SSRF_VALIDATION_DISABLED` | `false` | Test suites only — never set in production |

See the [README](README.md) for full configuration documentation.
