#!/bin/bash
set -e
echo "=== TicketFlow Dev Startup ==="

# Check backend venv
if [ ! -d "backend/venv" ]; then
  echo "[backend] Creating virtual environment..."
  python3 -m venv backend/venv
fi

echo "[backend] Installing dependencies..."
backend/venv/bin/pip install -q -r backend/requirements.txt

echo "[backend] Starting FastAPI on :8000..."
cd backend && ../venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

echo "[frontend] Installing npm packages..."
cd frontend && npm install --silent

echo "[frontend] Starting Next.js on :3000..."
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=== TicketFlow is running ==="
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
