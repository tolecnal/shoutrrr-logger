# CLAUDE.md

All agent and contributor instructions for this repository live in
**[AGENTS.md](./AGENTS.md)** — read that file.

It is the single source of truth: project overview, terminal commands and
virtual-environment layout, workspace structure, code-generation guardrails
(SQLAlchemy, Alembic, API, OIDC, frontend, i18n), testing gates, security
boundaries, and the commit workflow.

This file is deliberately a pointer and nothing more. Do not copy guidance
into it — two parallel instruction files drift apart, which is exactly the
problem this indirection removes.

## Quick reference

```bash
make lint    # ruff check + format check, ESLint, tsc, i18n parity
make test    # backend pytest + frontend vitest
```

Note that there are two virtual environments and only `backend/.venv` exists
locally; the root `.venv` is created by the CI ruff job alone. See the
"Virtual environments" section of AGENTS.md before running backend tooling by
hand.
