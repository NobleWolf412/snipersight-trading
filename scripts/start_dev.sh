#!/usr/bin/env bash

set -euo pipefail

mkdir -p logs

# Defaults
FRONTEND_PORT_DEFAULT=5000
BACKEND_PORT_DEFAULT=8001

FORCE_PORTS=${FORCE_PORTS:-1}
FRONTEND_PORT=${FRONTEND_PORT:-$FRONTEND_PORT_DEFAULT}
BACKEND_PORT=${BACKEND_PORT:-$BACKEND_PORT_DEFAULT}
HEALTH_CHECK=${HEALTH_CHECK:-1}
START_DEV_NO_RELOAD=${START_DEV_NO_RELOAD:-0}
UVICORN_EXTRA=${UVICORN_EXTRA:-}

BACK_PID=""
FRONT_PID=""

kill_by_port() {
  local port="$1"
  local max_attempts=5
  local attempt=1

  while [ $attempt -le $max_attempts ]; do
    if command -v fuser >/dev/null 2>&1; then
      if fuser -n tcp "$port" >/dev/null 2>&1; then
        echo "Port $port is in use (fuser). Killing process..."
        fuser -k -n tcp "$port" >/dev/null 2>&1 || true
      else
        return 0
      fi
    elif command -v lsof >/dev/null 2>&1; then
      if lsof -i :"$port" >/dev/null 2>&1; then
        echo "Port $port is in use (lsof). Killing process..."
        lsof -ti :"$port" | xargs -r kill || true
      else
        return 0
      fi
    else
      echo "Warning: no fuser or lsof, cannot auto-kill port $port"
      return 1
    fi
    sleep 1
    attempt=$((attempt + 1))
  done
  echo "Warning: Could not clear port $port after $max_attempts attempts."
}

start_backend() {
  echo "Starting backend on :$BACKEND_PORT"

  if [[ "$START_DEV_NO_RELOAD" == "1" ]]; then
    echo "Starting backend WITHOUT reload"
    nohup ./.venv/bin/python -m uvicorn backend.api_server:app \
      --host 0.0.0.0 --port "$BACKEND_PORT" \
      $UVICORN_EXTRA > logs/backend.log 2>&1 &
  else
    echo "Starting backend WITH reload"
    nohup ./.venv/bin/python -m uvicorn backend.api_server:app \
      --host 0.0.0.0 --port "$BACKEND_PORT" \
      --reload $UVICORN_EXTRA > logs/backend.log 2>&1 &
  fi

  BACK_PID=$!
  echo "Backend PID: $BACK_PID"
}

start_frontend() {
  echo "Starting frontend on :$FRONTEND_PORT"

  if [[ -n "${PUBLIC_HOST:-}" ]]; then
    echo "Detected PUBLIC_HOST=$PUBLIC_HOST — configuring HMR for wss over 443"
    export HMR_HOST="$PUBLIC_HOST"
    export HMR_PROTOCOL="wss"
    export HMR_CLIENT_PORT="${HMR_CLIENT_PORT:-443}"
  fi

  export PORT="$FRONTEND_PORT"
  export FRONTEND_PORT="$FRONTEND_PORT"
  export HOST_BIND=0.0.0.0
  export BACKEND_URL="http://localhost:$BACKEND_PORT"

  # Pass --port and --strictPort to ensure we get the desired port or fail
  nohup npm run dev:frontend -- --port "$FRONTEND_PORT" --strictPort > logs/frontend.log 2>&1 &
  FRONT_PID=$!
  echo "Frontend PID: $FRONT_PID"
}

wait_for_health() {
  if [[ "$HEALTH_CHECK" != "1" ]]; then
    return
  fi

  echo "Waiting for backend health on :$BACKEND_PORT ..."
  for _ in {1..30}; do
    if curl -sS "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
      echo "Backend is healthy."
      return
    fi
    sleep 1
  done
  echo "Warning: backend health check did not pass in time."
}

# -------------------- main --------------------

# Manual restart mode: kill backend/frontend, free ports, restart servers
if [[ "${1:-}" == "restart" ]]; then
  echo "Restarting backend and frontend..."
  
  if [[ "$FORCE_PORTS" == "1" ]]; then
      FRONTEND_PORT="$FRONTEND_PORT_DEFAULT"
      BACKEND_PORT="$BACKEND_PORT_DEFAULT"
  fi

  # Kill existing processes on these ports specifically
  kill_by_port "$BACKEND_PORT"
  kill_by_port "$FRONTEND_PORT"
  
  sleep 1
  
  # Use exec to replace the current process
  exec bash "$0"
fi

if [[ -f .env.local ]]; then
  echo "Loading .env.local"
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

if [[ "$FORCE_PORTS" == "1" ]]; then
  FRONTEND_PORT="$FRONTEND_PORT_DEFAULT"
  BACKEND_PORT="$BACKEND_PORT_DEFAULT"
fi

echo "Checking ports and cleaning up..."
pkill -f "cloudflared tunnel" 2>/dev/null || true

kill_by_port "$BACKEND_PORT"
kill_by_port "$FRONTEND_PORT"

start_backend
start_frontend
wait_for_health

echo
echo "================ DEV ENV READY ================"
echo "Backend:  http://127.0.0.1:$BACKEND_PORT"
echo "Frontend: http://127.0.0.1:$FRONTEND_PORT"
echo
echo "Logs:"
echo "  Backend:  tail -f logs/backend.log"
echo "  Frontend: tail -f logs/frontend.log"
echo "================================================"
echo
