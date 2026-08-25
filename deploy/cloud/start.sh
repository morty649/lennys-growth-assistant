#!/bin/sh
set -eu

export API_PORT="${PORT:-8000}"
export API_INTERNAL_URL="http://127.0.0.1:${API_PORT}"

cd /app/services/agent
node dist/index.js &
agent_pid=$!

cleanup() {
  kill "$agent_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd /app
exec /app/.venv/bin/python -m app
