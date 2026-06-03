#!/bin/sh
set -e

# Start the Next.js frontend on port 4000 in the background
echo "[shoutrrr-logger] Starting Next.js frontend..."
PORT=4000 node /app/frontend/server.js &
FRONTEND_PID=$!

# Start the FastAPI backend with Gunicorn + Uvicorn workers on port 9000
echo "[shoutrrr-logger] Starting FastAPI backend with ${WORKERS:-4} workers..."
exec gunicorn main:app \
    --chdir /app/backend \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "${WORKERS:-4}" \
    --bind "0.0.0.0:9000" \
    --access-logfile - \
    --error-logfile - \
    --log-level "${LOG_LEVEL:-info}" \
    --timeout 120 \
    --graceful-timeout 30
