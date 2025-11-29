#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
FRONTEND_PORT=${FRONTEND_PORT:-5000}
BACKEND_PORT=${BACKEND_PORT:-8000}

echo "Starting backend on :$BACKEND_PORT"
nohup ./.venv/bin/python -m uvicorn backend.api_server:app --host 0.0.0.0 --port $BACKEND_PORT --reload > logs/backend.log 2>&1 &
BACK_PID=$!

echo "Starting frontend on :$FRONTEND_PORT"
nohup env PORT=$FRONTEND_PORT npm run dev > logs/frontend.log 2>&1 &
FRONT_PID=$!

echo "Backend PID: $BACK_PID"
echo "Frontend PID: $FRONT_PID"

echo "Use tail -f logs/backend.log or logs/frontend.log to view output."
echo "Stop with: kill $BACK_PID $FRONT_PID"
echo "Or run: pkill -f uvicorn; pkill -f vite"
