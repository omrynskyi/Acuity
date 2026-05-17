#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  trap - EXIT INT TERM
  echo ""
  echo "Stopping..."
  kill 0 2>/dev/null
}
trap cleanup EXIT INT TERM

# Clear stale processes on dev ports
lsof -ti:8080 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

echo "Starting backend on :8080..."
cd "$ROOT"
source "$ROOT/.venv/bin/activate"
uvicorn backend.main:app --reload --port 8080 &

echo "Starting frontend on :5173..."
cd "$ROOT/frontend"
npm run dev &

wait
