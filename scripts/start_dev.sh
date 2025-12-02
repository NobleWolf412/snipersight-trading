#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
# Preferred (user env): Frontend 5000 (Vite), Backend 8001 (FastAPI)
FRONTEND_PORT_DEFAULT=5000
BACKEND_PORT_DEFAULT=8001
FORCE_PORTS=${FORCE_PORTS:-1}
FRONTEND_PORT=${FRONTEND_PORT:-$FRONTEND_PORT_DEFAULT}
BACKEND_PORT=${BACKEND_PORT:-$BACKEND_PORT_DEFAULT}
START_TUNNELS=${START_TUNNELS:-1}
LT_BIN=${LT_BIN:-npx localtunnel}

# Load local environment overrides if present (auto-export)
if [[ -f .env.local ]]; then
	echo "Loading .env.local"
	set -a
	source .env.local
	set +a
fi

# Force ports to known-good defaults unless explicitly disabled
if [[ "$FORCE_PORTS" == "1" ]]; then
	FRONTEND_PORT="$FRONTEND_PORT_DEFAULT"
	BACKEND_PORT="$BACKEND_PORT_DEFAULT"
fi

echo "Starting backend on :$BACKEND_PORT"
# Pre-flight: free ports if occupied
echo "Checking ports..."

# Kill process on Backend Port
if fuser -n tcp $BACKEND_PORT >/dev/null 2>&1; then
    echo "Port $BACKEND_PORT is in use. Killing process..."
    fuser -k -n tcp $BACKEND_PORT >/dev/null 2>&1 || true
    sleep 1
fi

# Kill process on Frontend Port
if fuser -n tcp $FRONTEND_PORT >/dev/null 2>&1; then
    echo "Port $FRONTEND_PORT is in use. Killing process..."
    fuser -k -n tcp $FRONTEND_PORT >/dev/null 2>&1 || true
    sleep 1
fi

# Backend hot-reload controls
# - By default we run with --reload for live iteration
# - Set START_DEV_NO_RELOAD=1 to disable reload (stability for long curls/tests)
# - Use UVICORN_EXTRA to pass additional flags (e.g., "--reload-include backend --reload-exclude logs")
START_DEV_NO_RELOAD=${START_DEV_NO_RELOAD:-0}
UVICORN_EXTRA=${UVICORN_EXTRA:-}

if [[ "$START_DEV_NO_RELOAD" == "1" ]]; then
	echo "Starting backend WITHOUT reload on :$BACKEND_PORT"
	nohup ./.venv/bin/python -m uvicorn backend.api_server:app --host 0.0.0.0 --port $BACKEND_PORT $UVICORN_EXTRA > logs/backend.log 2>&1 &
else
	echo "Starting backend WITH reload on :$BACKEND_PORT"
	nohup ./.venv/bin/python -m uvicorn backend.api_server:app --host 0.0.0.0 --port $BACKEND_PORT --reload $UVICORN_EXTRA > logs/backend.log 2>&1 &
fi
BACK_PID=$!

echo "Starting frontend on :$FRONTEND_PORT"
# If you're using a public dev tunnel (e.g., devtunnels.ms),
# set PUBLIC_HOST to the tunnel hostname (no protocol, no path), e.g.
#   PUBLIC_HOST=dhl9x06x-5000.usw3.devtunnels.ms
# This ensures Vite HMR websocket connects over wss to the public host
# instead of 0.0.0.0.
if [[ -n "${PUBLIC_HOST:-}" ]]; then
	echo "Detected PUBLIC_HOST=$PUBLIC_HOST — configuring HMR for wss over 443"
	export HMR_HOST="$PUBLIC_HOST"
	export HMR_PROTOCOL="wss"
	# Default to 443 for public tunnels; override via HMR_CLIENT_PORT if needed
	export HMR_CLIENT_PORT="${HMR_CLIENT_PORT:-443}"
fi

# Explicitly set Vite dev server host/port via exported env
export PORT=$FRONTEND_PORT
export FRONTEND_PORT=$FRONTEND_PORT
export HOST_BIND=0.0.0.0
export BACKEND_URL="http://localhost:$BACKEND_PORT"
nohup npm run dev:frontend > logs/frontend.log 2>&1 &
FRONT_PID=$!
echo "Backend PID: $BACK_PID"
echo "Frontend PID: $FRONT_PID"

echo "Use: tail -f logs/backend.log | sed -n '1,120p' and tail -f logs/frontend.log"
echo "Stop with: kill $BACK_PID $FRONT_PID"
echo "Quick health: curl -sS http://127.0.0.1:$BACKEND_PORT/api/health"
echo "Or run: pkill -f uvicorn; pkill -f vite"

# Optional: wait for backend to be ready before returning
HEALTH_CHECK=${HEALTH_CHECK:-1}
if [[ "$HEALTH_CHECK" == "1" ]]; then
	echo "Waiting for backend health on :$BACKEND_PORT ..."
	for _ in {1..30}; do
		if curl -sS "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null; then
			echo "Backend is healthy."
			break
		fi
		sleep 1
	done
fi

# Optional: start public tunnels for backend/frontend via localtunnel
if [[ "$START_TUNNELS" == "1" ]]; then
	echo "Starting public tunnels with localtunnel..."
	# Backend tunnel
	nohup $LT_BIN --port $BACKEND_PORT > logs/tunnel_backend.log 2>&1 &
	TUNNEL_BACK_PID=$!
	# Frontend tunnel
	nohup $LT_BIN --port $FRONTEND_PORT > logs/tunnel_frontend.log 2>&1 &
	TUNNEL_FRONT_PID=$!
	echo "Tunnel PIDs — backend: $TUNNEL_BACK_PID, frontend: $TUNNEL_FRONT_PID"
	# Attempt to surface the URLs once files have content
	for _ in {1..10}; do
		if grep -q "your url is:" logs/tunnel_backend.log 2>/dev/null; then
			BACK_URL=$(grep -m1 "your url is:" logs/tunnel_backend.log | awk '{print $4}')
			echo "Backend tunnel: $BACK_URL"
			break
		fi
		sleep 1
	done
	for _ in {1..10}; do
		if grep -q "your url is:" logs/tunnel_frontend.log 2>/dev/null; then
			FRONT_URL=$(grep -m1 "your url is:" logs/tunnel_frontend.log | awk '{print $4}')
			echo "Frontend tunnel: $FRONT_URL"
			break
		fi
		sleep 1
	done
	echo "Tip: tail -f logs/tunnel_backend.log | logs/tunnel_frontend.log to monitor tunnel status."
fi
