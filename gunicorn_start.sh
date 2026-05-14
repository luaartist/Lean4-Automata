#!/usr/bin/env bash
# gunicorn_start.sh — launch both ASGI apps under Gunicorn + UvicornWorker
# Usage:
#   ./gunicorn_start.sh          # starts both in background
#   APP=query ./gunicorn_start.sh   # query API only
#   APP=ingestion ./gunicorn_start.sh   # ingestion API only
set -euo pipefail

LOG_LEVEL="${LOG_LEVEL:-info}"

start_query() {
  echo "[gunicorn] Starting Query API on :8000"
  gunicorn app.query_api:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --log-level "${LOG_LEVEL}" \
    --access-logfile - \
    --error-logfile - \
    "$@"
}

start_ingestion() {
  echo "[gunicorn] Starting Ingestion API on :8001"
  gunicorn app.ingestion_api:app \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8001 \
    --log-level "${LOG_LEVEL}" \
    --access-logfile - \
    --error-logfile - \
    "$@"
}

case "${APP:-both}" in
  query)     start_query ;;
  ingestion) start_ingestion ;;
  both)
    start_query &
    QUERY_PID=$!
    start_ingestion &
    INGESTION_PID=$!
    echo "[gunicorn] Query PID=${QUERY_PID}  Ingestion PID=${INGESTION_PID}"
    wait
    ;;
  *)
    echo "Unknown APP='${APP}'. Use: query | ingestion | both" >&2
    exit 1
    ;;
esac
