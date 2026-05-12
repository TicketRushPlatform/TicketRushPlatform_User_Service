#!/bin/sh
set -eu

worker_pid=""
api_pid=""

shutdown() {
  if [ -n "$worker_pid" ]; then
    kill "$worker_pid" 2>/dev/null || true
  fi
  if [ -n "$api_pid" ]; then
    kill "$api_pid" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}

trap 'shutdown; exit 143' INT TERM

if [ -n "${REDIS_URL:-}" ]; then
  echo "Starting email worker in background with Redis queue."
  python -m app.workers.email_worker &
  worker_pid="$!"
else
  echo "REDIS_URL is not set; email dispatcher will use in-process background thread fallback."
fi

gunicorn -b "0.0.0.0:${SERVER_PORT:-8082}" wsgi:app &
api_pid="$!"

wait "$api_pid"
status="$?"
shutdown
exit "$status"
