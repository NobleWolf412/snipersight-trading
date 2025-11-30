#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
# Standard dev ports: Backend 5000 (FastAPI), Frontend 5173 (Vite)
FRONTEND_PORT=${FRONTEND_PORT:-5173}
BACKEND_PORT=${BACKEND_PORT:-5000}

# Load local environment overrides if present (auto-export)
if [[ -f .env.local ]]; then
	echo "Loading .env.local"
	set -a
	source .env.local
	set +a
fi

echo "Starting backend on :$BACKEND_PORT"
# Pre-flight: free ports if occupied
if ss -ltnp | grep -q ":$BACKEND_PORT"; then
	echo "Port $BACKEND_PORT in use — attempting to free it"
	ss -ltnp | grep ":$BACKEND_PORT" || true
	pkill -f "uvicorn backend.api_server:app" || true
	pkill -f "python backend/api_server.py" || true
fi

if ss -ltnp | grep -q ":$FRONTEND_PORT"; then
	echo "Port $FRONTEND_PORT in use — attempting to free it"
	ss -ltnp | grep ":$FRONTEND_PORT" || true
	pkill -f "vite" || true
	pkill -f "npm run dev" || true
	pkill -f "node" || true
fi

nohup ./.venv/bin/python -m uvicorn backend.api_server:app --host 0.0.0.0 --port $BACKEND_PORT --reload > logs/backend.log 2>&1 &
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
nohup npm run dev > logs/frontend.log 2>&1 &
FRONT_PID=$!

echo "Backend PID: $BACK_PID"
echo "Frontend PID: $FRONT_PID"

echo "Use: tail -f logs/backend.log | sed -n '1,120p' and tail -f logs/frontend.log"
echo "Stop with: kill $BACK_PID $FRONT_PID"
echo "Quick health: curl -sS http://127.0.0.1:$BACKEND_PORT/api/health"
echo "Or run: pkill -f uvicorn; pkill -f vite"
