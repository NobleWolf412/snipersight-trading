#!/usr/bin/env bash
# Safe sync: only pulls if no local uncommitted changes.
set -euo pipefail
BRANCH="main"
REMOTE="origin"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[safe_sync] Not a git repository" >&2
  exit 1
fi

STATUS=$(git status --porcelain)
if [ -n "$STATUS" ]; then
  echo "[safe_sync] Local changes detected. Commit/stash before syncing." >&2
  exit 2
fi

echo "[safe_sync] Fetching $REMOTE/$BRANCH" && git fetch "$REMOTE" --quiet || echo "[safe_sync] Fetch failed"
LOCAL_HASH=$(git rev-parse "$BRANCH")
REMOTE_HASH=$(git rev-parse "$REMOTE/$BRANCH")
if [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
  echo "[safe_sync] Updating local $BRANCH" && git pull --rebase "$REMOTE" "$BRANCH"
else
  echo "[safe_sync] Already up to date"
fi
