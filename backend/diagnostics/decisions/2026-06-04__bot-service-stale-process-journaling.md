# 2026-06-04 — Bot-service process is long-lived & stale; session_id ≠ restart

**Type:** operational/diagnosability finding (no code change — code is correct).
**Trigger:** overnight session 6e03d98e journaled `stop_loss_rationale`/`tp1_clamped`/
`stop_loss_level`/`target_levels`/`tp1_realized_rr` as ABSENT (not empty), so the §16
stop-branch + reachability diagnostics built 2026-06-02 (commit e6715f8) showed nothing.

## What we thought vs what's true
Autopsy thread read "stop_loss_rationale not yet journaled (bot needs restart)". Initially
suspected a code bug because the bot was emitting `direction=UNKNOWN` rejections (proof the
2026-06-03 silent-LONG fix `8233b21` was live) — which seemed to prove the bot ran latest code.
**That inference was wrong.** Scans run in fresh worker subprocesses (re-import current
modules → UNKNOWN is live), but **execution + position management + journaling run in the
long-lived parent bot-service process**, which is stale.

## Proof (incontrovertible)
- The full write chain is correct in HEAD: `StopLoss.rationale` is a REQUIRED field
  (planner.py:83-84 raises if empty) → `position_manager` captures at open
  (position_manager.py:442-443) + snapshots levels (173-176) → `CompletedTrade` populates
  (paper_trading_service.py:2837-2840) + emits in `to_dict` (281-284) → `trade_journal.append`
  writes the dict verbatim, NO key filtering (trade_journal.py:42-47).
- Yet **0 of 247 journal rows across EVERY session (2026-05-21 → 06-04) carry the keys** —
  including session `0202c781`, which started 2026-06-02T20:41, just **27 min after** the
  journaling commit `e6715f8` (20:14). The journaling code has therefore **literally never
  executed** → the writing process predates 2026-06-02 20:14 and has never recycled.
- `dev_servers.log` shows a `--reload` instance (WatchFiles, reloads on edits); `backend.err.log`
  shows a plain `Started server process` with NO reloader. The trading bot ran on the
  non-reloading (or simply never-restarted) parent. `npm run backend` = uvicorn `--reload` exists,
  but the persistent bot process is not it / was not recycled.

## Mechanism
`/api/paper-trading/start|stop` toggles a SESSION inside the running process and mints a new
`session_id` — it does NOT restart the OS process. So stop/start in the UI → new session_id,
same stale Python. **`session_id` rotation is not evidence of a code reload.**

## Consequence (the important part)
Every bot-path change shipped this week ran ONLY in scan workers, never in the bot parent:
- e6715f8 journal calc-geometry (stop branch / clamp) — never recorded
- 8233b21 silent-LONG guards where the BOT consumes direction (the scan-side UNKNOWN is the
  worker; the executor-side guard is stale)
- tp1_clamped capture (position_manager.py:443) — so `tp1_clamped=0/8` is a STALE-PROCESS
  ARTIFACT, not proof the reachability clamp didn't fire
We have effectively been validating half-updated code for ~2 weeks of sessions.

## Fix (operational, no code)
HARD-restart the backend parent (kill the python/uvicorn process, relaunch) before each
validation run — `npm run kill` then `npm run dev:all`, or restart `C:\start-sniper.bat`.
Confirm via a fresh `Started server process` in the log + the NEXT closed trade carrying
`stop_loss_rationale`. Do NOT trust UI stop/start to reload code.

## ROOT CAUSE CONFIRMED (process inspection) — it's a port-hold zombie + a broken kill script
Initial framing ("long-lived process, never recycled") was right but incomplete. Live inspection:
- **PID 19108** = `python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8001`
  (note: **NO `--reload`**), **started 2026-06-02 18:15** — ~2h BEFORE the journaling commit
  (20:14) — still holding port 8001 at time of autopsy (2026-06-04). It never auto-reloads
  (no --reload) and was never killed.
- **Why `npm run dev:all` never replaced it:** the `kill` script was
  `fuser -k 5000/tcp || true && fuser -k 8001/tcp || true`. `fuser` is a **Linux** command that
  does not exist on Windows → it errors, `|| true` swallows it → **the port is never freed**.
  So each `npm run dev:all` started a new backend that collided on port 8001, lost the bind, and
  silently died while the June-2 zombie kept serving. The operator was restarting into a brick wall.
- Same failure class as the known "stale vite holds 5000 → taskkill" note, unfixed for the backend.

**Fix applied 2026-06-04:**
- Killed PID 19108 (`taskkill /F /PID 19108`), port 8001 freed.
- Patched `package.json` `kill` script: `fuser -k ...` → `npx --yes kill-port 5000 8001`
  (cross-platform, actually frees the ports on Windows). `npm run kill` now works.
- Correct restart sequence going forward: `npm run kill` THEN `npm run dev:all` (kill-port frees
  8001 so the fresh `--reload` backend can bind and load current code).

## VERIFY-NEXT
After a hard restart + one paper session, `session_debrief` stop-branch column must show
structural/max-stop-cap/atr-fallback (not `unrecorded`) and `tp1_clamped` must reflect real
clamp activity. That unblocks the wide-stop swing-short diagnosis (session 6e03d98e thread 1:
SHIB/1000FLOKI swing shorts, 1.56 ATR stops, -21/-22 each).
