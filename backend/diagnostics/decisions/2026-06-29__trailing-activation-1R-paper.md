# Trailing-stop activation 1.5R → 1.0R (PAPER only) — 2026-06-29

Paper-only exit-parameter tune. NOT a §15 pre-scoring/min_confluence change; documented per §19.

## Baseline (measured, session 6117c631 + corpus)
The trailing stop arms at a profit **R-multiple** (`position_manager._check_trailing_activation`:
`profit_r >= trailing_stop_activation`). Default was **1.5R**. But measured excursions:
- Losers peak **~0.68R** favorable; even the best near-miss (ADA) only reached **1.20R** before reversing.
- So the 1.5R trigger sits **above where the trades travel** → trailing **almost never armed** → trades
  round-trip to full stops. (Also surfaced a UI mislabel — slider said "%", engine uses R — fixed in 37b8668.)

## Change
- `PaperTradingConfig.trailing_activation` 1.5 → **1.0** (paper_trading_service.py:272)
- `PaperTradingConfigRequest.trailing_activation` Field default 1.5 → **1.0** (api_server.py:1173; ge=1.0 kept)
- Frontend `DEFAULT_SETUP.trailing_activation` 1.5 → **1.0**; slider min 0.5 → **1.0** (align to API ge=1.0)
- Trail distance unchanged (0.5R). `position_manager` param default left at 1.5 (irrelevant — callers pass config).
- **LIVE untouched:** `LiveTradingConfigRequest.trailing_activation` stays 1.5 (§15; paper-only experiment).

## Why 1.0R (and its limit)
1.0R arms on the trades that reach ~1R (the near-misses like ADA@1.2R) → trails to ~0.5R, rescuing those.
HONEST LIMIT: the API floor is **ge=1.0**, but most losers peak **~0.68R** — so even at 1.0R the trailing
**still won't arm on the sub-1R round-trippers** (the majority). To reach those would require lowering the
floor below 1.0R (risking strangled winners) — a SEPARATE deliberate experiment, not done here.

## Validation (the point of this change)
Trailing activation is now JOURNALED (commit ffab8d7: `trailing_activated` / `initial_stop_loss` /
`trailing_final_stop`). Run a fresh paper session at 1.0R, then /autopsy shows definitively: did it arm,
where it trailed, did it help. Tune from THAT data, not from the prior crude (retracted) simulation.

## Caveat
Exit tuning on a NO-EDGE entry ([[project_edge_after_fees_verdict]] + factor analysis: 0/26 factors
predict outcome). 1.0R makes losses smaller/cleaner; it does NOT create edge. Rollback: set 1.5 everywhere.
