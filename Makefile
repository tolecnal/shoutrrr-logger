GIT_HASH  := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
BUILD_TIME := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

export GIT_HASH
export BUILD_TIME

.PHONY: build up down logs

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
