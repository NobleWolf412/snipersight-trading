# 2026-05-31 — Replay router contract re-baseline (+ tradfi restore)

## What changed
Committing in-flight WIP that extracts the candle-by-candle Replay UX into a dedicated
router/engine, splits the Training hub into separate pages, and restores an accidentally
deleted route.

## API contract delta (intentional)
`python -m backend.diagnostics.capture_contracts diff` reported `api_contracts: DRIFT`:

- **added** `/api/replay/sessions` (POST)
- **added** `/api/replay/sessions/{session_id}` (GET, DELETE)
- **added** `/api/replay/sessions/{session_id}/step` (POST)
- **added** `/api/replay/sessions/{session_id}/jump-to-next-signal` (POST)

Downstream consumers updated in the same commit: `src/utils/api.ts`
(`createReplaySession/getReplaySession/stepReplay/jumpToNextSignal/deleteReplaySession`) and
`src/pages/training/Replay.tsx`. Router registered in `api_server.py`
(`include_router(replay_router)` + `configure_replay_router(exchange_adapter=…)`). Engine builds
its own dedicated replay-mode orchestrator per session — live orchestrator state untouched.

## tradfi restore (NOT a contract change — a regression fix)
`/api/market/tradfi` had been **accidentally deleted** from `api_server.py` while the operator
was editing the Intel page, but `src/utils/api.ts::getTradFi` + `src/pages/Intel.tsx` still
consume it (Intel MacroTicker DXY/10Y/GOLD/VIX strip). The contract diff caught it as a
`removed item`. Restored verbatim from the last committed version; the contract baseline therefore
shows it as unchanged (present before, present after).

## Action
Re-baselined `backend/diagnostics/contracts/api_contracts.json` via
`python -m backend.diagnostics.capture_contracts capture` so the frozen baseline reflects the new
replay routes. telemetry/pipeline/db contracts unchanged. `pipeline_smoke verify` CLEAN.

## Regression evidence
tsc clean · vite build OK · pipeline_smoke CLEAN · backend imports OK (5 replay routes register).
Pre-existing/unrelated failures NOT introduced here: 5 pytest (RR/HTF/RSI stale-assertion drift),
1 vitest (scanHistoryService random-ID flake). eslint non-functional repo-wide (missing v9 config).
