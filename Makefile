GIT_HASH  := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
BUILD_TIME := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

export GIT_HASH
export BUILD_TIME

RUFF := backend/.venv/bin/ruff
PYTEST := .venv/bin/pytest

.PHONY: build up down logs lint lint-backend lint-frontend test test-backend test-frontend

## Build the image with correct git metadata baked in
build:
	docker compose build

## Build + start in detached mode
up:
	docker compose up -d --build

## Stop containers
down:
	docker compose down

## Tail logs
logs:
	docker compose logs -f

## Ruff lint + format check, mirroring the CI "Backend (ruff)" job.
## Paths are relative to the repo root: `cd backend && ruff check backend/`
## would fail with E902, since there is no backend/backend.
lint-backend:
	$(RUFF) check backend/
	$(RUFF) format --check backend/ --exclude backend/build/

## ESLint + tsc + i18n parity, mirroring the CI "Frontend (ESLint + tsc)" job
lint-frontend:
	cd frontend && pnpm lint
	cd frontend && pnpm exec tsc --noEmit
	cd frontend && pnpm i18n:check

## All lint gates
lint: lint-backend lint-frontend

## pytest, mirroring the CI "Backend tests (pytest)" job (runs from backend/)
test-backend:
	cd backend && $(PYTEST) tests/ -v --tb=short

## vitest, mirroring the CI "Frontend tests (vitest)" job
test-frontend:
	cd frontend && pnpm test:run

## All test suites
test: test-backend test-frontend
