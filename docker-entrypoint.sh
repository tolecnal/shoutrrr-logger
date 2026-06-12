#!/bin/sh
set -e

# Match the timestamp format produced by gunicorn/uvicorn (logging_config.json)
# so every line in the combined container log shares one uniform shape.
log() {
    printf '%s [shoutrrr-logger] %s\n' "$(date -u '+[%Y-%m-%d %H:%M:%S +0000]')" "$1"
}

# Apply any pending database migrations before starting the servers, so a
# release that changes the schema can never serve requests against an
# un-migrated database. Disable with AUTO_MIGRATE=false to run migrations
# out-of-band (e.g. multi-replica deployments).
#
# Retries cover the standalone-docker case where postgres may still be
# starting; under docker-compose the depends_on healthcheck already
# guarantees the database is ready.
if [ "${AUTO_MIGRATE:-true}" = "true" ]; then
    log "Applying database migrations (alembic upgrade head)..."
    attempt=1
    until (cd /app/backend && alembic upgrade head); do
        if [ "$attempt" -ge 5 ]; then
            log "ERROR: database migration failed after ${attempt} attempts; aborting startup."
            exit 1
        fi
        attempt=$((attempt + 1))
        log "Database not ready for migrations (attempt ${attempt}/5) - retrying in 3s..."
        sleep 3
    done
    log "Database migrations applied."
else
    log "AUTO_MIGRATE=false - skipping database migrations (apply them out-of-band)."
fi

# Start the Next.js frontend on port 4000 in the background
log "Starting Next.js frontend..."
PORT=4000 node /app/frontend/server.js &
FRONTEND_PID=$!

# Start the FastAPI backend with Gunicorn + Uvicorn workers on port 9000
log "Starting FastAPI backend with ${WORKERS:-4} workers..."
exec gunicorn main:app \
    --chdir /app/backend \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "${WORKERS:-4}" \
    --bind "0.0.0.0:9000" \
    --access-logfile - \
    --error-logfile - \
    --log-config-json /app/backend/logging_config.json \
    --log-level "${LOG_LEVEL:-info}" \
    --timeout 120 \
    --graceful-timeout 30
