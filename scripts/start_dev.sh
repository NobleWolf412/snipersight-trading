#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
FRONTEND_PORT=${FRONTEND_PORT:-5000}
BACKEND_PORT=${BACKEND_PORT:-8000}

echo "Starting backend on :$BACKEND_PORT"
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

nohup env PORT=$FRONTEND_PORT HOST_BIND=0.0.0.0 npm run dev > logs/frontend.log 2>&1 &
FRONT_PID=$!

echo "Backend PID: $BACK_PID"
echo "Frontend PID: $FRONT_PID"

echo "Use tail -f logs/backend.log or logs/frontend.log to view output."
echo "Stop with: kill $BACK_PID $FRONT_PID"
echo "Or run: pkill -f uvicorn; pkill -f vite"
