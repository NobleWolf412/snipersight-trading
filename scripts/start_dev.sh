#!/usr/bin/env bash

set -euo pipefail

mkdir -p logs

# Defaults
FRONTEND_PORT_DEFAULT=5000
BACKEND_PORT_DEFAULT=8001

FORCE_PORTS=${FORCE_PORTS:-1}
FRONTEND_PORT=${FRONTEND_PORT:-$FRONTEND_PORT_DEFAULT}
BACKEND_PORT=${BACKEND_PORT:-$BACKEND_PORT_DEFAULT}
START_TUNNELS=${START_TUNNELS:-1}
HEALTH_CHECK=${HEALTH_CHECK:-1}
START_DEV_NO_RELOAD=${START_DEV_NO_RELOAD:-0}
UVICORN_EXTRA=${UVICORN_EXTRA:-}

BACK_PID=""
FRONT_PID=""
TUNNEL_BACK_PID=""
TUNNEL_FRONT_PID=""
FRONT_URL=""
BACK_URL=""

cleanup() {
  echo "Cleaning up background processes..."
  for pid in "$BACK_PID" "$FRONT_PID" "$TUNNEL_BACK_PID" "$TUNNEL_FRONT_PID"; do
    if [[ -n "${pid:-}" ]]; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT

print_links() {
  printf "\n--- Current Tunnel Links ---\n"
  local front back
  front=$(grep -o 'https://[^ |]*\.trycloudflare\.com' logs/tunnel_frontend.log 2>/dev/null | head -n1 || true)
  back=$(grep -o 'https://[^ |]*\.trycloudflare\.com' logs/tunnel_backend.log 2>/dev/null | head -n1 || true)

  if [[ -n "$front" ]]; then
    echo "Frontend: $front"
  else
    echo "Frontend: (not found)"
  fi

  if [[ -n "$back" ]]; then
    echo "Backend:  $back"
  else
    echo "Backend:  (not found)"
  fi

  printf "---------------------------\n\n"
}

resolve_cloudflared() {
  # 1) Explicit override
  if [[ -n "${CLOUDFLARED_BIN:-}" ]]; then
    echo "$CLOUDFLARED_BIN"
    return
  fi

  # 2) scripts/cloudflared
  if [[ -x "scripts/cloudflared" ]]; then
    echo "scripts/cloudflared"
    return
  fi

  # 3) system cloudflared
  if command -v cloudflared >/dev/null 2>&1; then
    command -v cloudflared
    return
  fi

  echo "ERROR: cloudflared not found. Put a binary at scripts/cloudflared or install cloudflared in PATH." >&2
  exit 1
}

kill_by_port() {
  local port="$1"

  if command -v fuser >/dev/null 2>&1; then
    if fuser -n tcp "$port" >/dev/null 2>&1; then
      echo "Port $port is in use. Killing process..."
      fuser -k -n tcp "$port" >/dev/null 2>&1 || true
      sleep 1
    fi
  elif command -v lsof >/dev/null 2>&1; then
    if lsof -i :"$port" >/dev/null 2>&1; then
      echo "Port $port is in use. Killing process..."
      lsof -ti :"$port" | xargs -r kill || true
      sleep 1
    fi
  else
    echo "Warning: no fuser or lsof, cannot auto-kill port $port"
  fi
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

  nohup npm run dev:frontend > logs/frontend.log 2>&1 &
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

start_tunnels_cloudflare() {
  local cf_bin
  cf_bin=$(resolve_cloudflared)

  echo "Using cloudflared binary: $cf_bin"
  chmod +x "$cf_bin" 2>/dev/null || true

  echo "Starting public tunnels with cloudflared..."
  nohup "$cf_bin" tunnel --url "http://localhost:$BACKEND_PORT" > logs/tunnel_backend.log 2>&1 &
  TUNNEL_BACK_PID=$!

  nohup "$cf_bin" tunnel --url "http://localhost:$FRONTEND_PORT" > logs/tunnel_frontend.log 2>&1 &
  TUNNEL_FRONT_PID=$!

  echo "Tunnel PIDs — backend: $TUNNEL_BACK_PID, frontend: $TUNNEL_FRONT_PID"
  echo "Waiting for Cloudflare URLs (this may take up to 30s)..."

  # Backend URL
  for i in {1..30}; do
    if grep -q "trycloudflare.com" logs/tunnel_backend.log 2>/dev/null; then
      BACK_URL=$(grep "trycloudflare.com" logs/tunnel_backend.log | grep -o 'https://[^ |]*\.trycloudflare\.com' | head -n1)
      if [[ -n "$BACK_URL" ]]; then
        echo "✅ Backend tunnel: $BACK_URL"
        break
      fi
    fi
    (( i % 5 == 0 )) && echo "   ...still waiting for backend tunnel..."
    sleep 1
  done

  # Frontend URL
  for i in {1..30}; do
    if grep -q "trycloudflare.com" logs/tunnel_frontend.log 2>/dev/null; then
      FRONT_URL=$(grep "trycloudflare.com" logs/tunnel_frontend.log | grep -o 'https://[^ |]*\.trycloudflare\.com' | head -n1)
      if [[ -n "$FRONT_URL" ]]; then
        echo "✅ Frontend tunnel: $FRONT_URL"
        break
      fi
    fi
    (( i % 5 == 0 )) && echo "   ...still waiting for frontend tunnel..."
    sleep 1
  done

  if [[ -z "$BACK_URL" || -z "$FRONT_URL" ]]; then
    echo "⚠️  Could not auto-detect URLs yet. Check logs manually:"
    echo "   grep -o 'https://.*\.trycloudflare\.com' logs/tunnel_*.log"
  else
    echo ""
    echo "🎉 Tunnels Active!"
    echo "   Frontend: $FRONT_URL"
    echo "   Backend:  $BACK_URL"
    echo ""
  fi
}

start_tunnels() {
  if [[ "$START_TUNNELS" != "1" ]]; then
    echo "Skipping tunnels (START_TUNNELS=0)"
    return
  fi
  start_tunnels_cloudflare
}

# -------------------- main --------------------

if [[ "${1:-}" == "print-links" ]]; then
  print_links
  exit 0
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
start_tunnels

echo
echo "================ DEV ENV READY ================"
echo "Backend:  http://127.0.0.1:$BACKEND_PORT"
echo "Frontend: http://127.0.0.1:$FRONTEND_PORT"
if [[ -n "$FRONT_URL" || -n "$BACK_URL" ]]; then
  echo
  echo "Cloudflare URLs:"
  echo "  Frontend: ${FRONT_URL:-(not detected)}"
  echo "  Backend:  ${BACK_URL:-(not detected)}"
fi
echo
echo "Logs:"
echo "  Backend:  tail -f logs/backend.log"
echo "  Frontend: tail -f logs/frontend.log"
echo "  Tunnels:  tail -f logs/tunnel_backend.log logs/tunnel_frontend.log"
echo "================================================"
echo
