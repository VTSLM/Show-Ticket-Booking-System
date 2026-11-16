#!/usr/bin/env bash
# Start the backend (FastAPI, :8000) and frontend (Next.js, :3000) for local development.
# Run from the repo root: ./scripts/dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

[ -f backend/.env ] || { echo "Missing backend/.env (copy backend/.env.example)"; exit 1; }
[ -f frontend/.env.local ] || { echo "Missing frontend/.env.local (copy frontend/.env.example)"; exit 1; }

if [ ! -d backend/.venv ]; then
  echo "[backend] Creating virtual environment"
  python3.12 -m venv backend/.venv
fi
echo "[backend] Installing dependencies"
backend/.venv/bin/pip install -q -r backend/requirements.txt

echo "[backend] Starting FastAPI on :8000"
(cd backend && .venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

echo "[frontend] Installing npm packages"
(cd frontend && npm ci --silent)
echo "[frontend] Starting Next.js on :3000"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null' EXIT INT TERM
echo
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000 (docs at /docs)"
wait
