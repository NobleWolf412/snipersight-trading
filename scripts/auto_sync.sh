#!/usr/bin/env bash
# Auto-sync script to pull latest changes from origin main periodically.
# Use cautiously; may create merge conflicts if you have local uncommitted changes.

set -euo pipefail

INTERVAL="15"  # seconds between syncs; adjust as needed
BRANCH="main"
REMOTE="origin"

echo "[auto_sync] Starting auto sync loop: $REMOTE/$BRANCH every $INTERVAL seconds"

while true; do
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[auto_sync] Fetching..."
    git fetch "$REMOTE" --quiet || echo "[auto_sync] Fetch failed"
    LOCAL_HASH=$(git rev-parse "$BRANCH")
    REMOTE_HASH=$(git rev-parse "$REMOTE/$BRANCH")
    if [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
      echo "[auto_sync] Updating local $BRANCH from $REMOTE/$BRANCH"
      git pull --rebase "$REMOTE" "$BRANCH" || echo "[auto_sync] Pull/rebase failed"
    else
      echo "[auto_sync] Already up to date"
    fi
  else
    echo "[auto_sync] Not a git repo"
  fi
  sleep "$INTERVAL"
done
