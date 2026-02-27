#!/usr/bin/env bash
set -euo pipefail

# Safely kill dev processes bound to backend/frontend ports without nuking the shell
# Default ports: backend 5000, frontend 5173
BACKEND_PORT=${BACKEND_PORT:-5000}
FRONTEND_PORT=${FRONTEND_PORT:-5173}

echo "Scanning ports :$BACKEND_PORT and :$FRONTEND_PORT for listeners..."

kill_by_port() {
  local port="$1"
  # Use ss to get PIDs listening on the port
  # Example line: users:(("node",pid=19140,fd=28))
  local pids
  pids=$(ss -ltnp | awk -v p=":$port" '$0 ~ p {print $NF}' | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | sort -u)
  if [[ -z "$pids" ]]; then
    echo "No listeners found on :$port"
    return 0
  fi
  echo "Found PIDs on :$port -> $pids"
  for pid in $pids; do
    # Skip current shell PID and parent shell
    if [[ "$pid" -eq "$$" || "$pid" -eq "$PPID" ]]; then
      echo "Skipping shell pid $pid"
      continue
    fi
    # Inspect command to avoid killing unrelated system nodes
    cmd=$(ps -o cmd= -p "$pid" || true)
    echo "Killing pid $pid ($cmd)"
    kill "$pid" 2>/dev/null || true
    # If still alive, escalate after short wait
    sleep 0.2
    if ps -p "$pid" > /dev/null 2>&1; then
      echo "Force killing pid $pid"
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
}

kill_by_port "$BACKEND_PORT"
kill_by_port "$FRONTEND_PORT"

echo "Port cleanup complete. Current listeners:"
ss -ltnp | grep -E "(:$BACKEND_PORT|:$FRONTEND_PORT)" || true
