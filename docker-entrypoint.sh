#!/bin/sh
set -e

# Match the timestamp format produced by gunicorn/uvicorn (logging_config.json)
# so every line in the combined container log shares one uniform shape.
log() {
    printf '%s [shoutrrr-logger] %s\n' "$(date -u '+[%Y-%m-%d %H:%M:%S +0000]')" "$1"
}

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
