# Fix 1: Paper-fidelity fee + slippage baseline

Date: 2026-06-11  
Phase: Pipeline improvements → Fix 1  
Files: `backend/bot/executor/paper_executor.py`, `backend/bot/paper_trading_service.py`,
        `backend/bot/executor/position_manager.py`, `backend/api_server.py`

---

## Decision: Adopt Phemex real fee schedule and tiered slippage in paper trading

### Fee rates

| Session type | Old value | New value | Source |
|---|---|---|---|
| Taker (snap_taker / default) | 0.001 (0.1%) | 0.0006 (0.06%) | Phemex published perpetual fee schedule |
| Maker (rest_maker) | 0.001 (0.1%) | 0.0001 (0.01%) | Phemex published perpetual fee schedule |

The old 0.1% fee was an arbitrary placeholder that overstated trading costs by 1.67x for taker
sessions and 10x for maker sessions. Since edge-after-fees is the active gating question
(see `project_edge_after_fees_verdict.md`), accurate fee modeling is load-bearing.

### Slippage tiers

| Symbol class | Old bps | New bps | Rationale |
|---|---|---|---|
| BTC/USDT, ETH/USDT (major) | 15 bps (uniform) | 10 bps | Deep order books; bid-ask spread typically 1-2 bps; 10 bps is conservative for market orders during sessions |
| All other alts | 15 bps (uniform) | 35 bps | Shallower books, wider spreads; 35 bps conservative estimate for paper (live testing will refine) |

The old uniform 15 bps was too tight for alts (where spreads + impact easily run 30-50 bps
at 0.1-0.5 BTC notional) and slightly too generous for BTC/ETH. The tiered model is more
accurate for multi-symbol paper sessions.

### TP hold artificial delay

`SIMULATION_MIN_TARGET_HOLD_SECONDS` set to **0** (was 90 seconds).

Limit TP orders on live exchanges fill immediately when price touches the level — the 90s
delay was originally inserted to prevent "too-perfect" paper results but it actually
understates wins relative to live, introducing a directional bias. Removing it aligns paper
exit timing with live behavior.

### Blast-radius callers updated

| File | Change |
|---|---|
| `paper_executor.py` | Default `fee_rate=0.0006`, `slippage_bps=35.0`, `major_slippage_bps=10.0`; tiered `_calculate_slippage()` |
| `paper_trading_service.py` | `PaperTradingConfig` gains `taker_fee_rate`, `maker_fee_rate`, `major_slippage_bps`, `alt_slippage_bps`; `PaperExecutor` constructed with the right rate based on `rest_maker_active` |
| `position_manager.py` | `SIMULATION_MIN_TARGET_HOLD_SECONDS = 0` |
| `api_server.py:393` | Module-level `PaperExecutor(fee_rate=0.001)` → `0.0006` (paper UI endpoint, not live path) |

`live_executor.py` **not touched** — §15 hard boundary. Verified by test
`test_live_executor_fee_rate_not_changed` in `test_paper_fidelity.py`.

### Regression tests

`backend/tests/unit/test_paper_fidelity.py` — 16 tests covering all four change areas +
§15 blast-radius guard. All pass.
