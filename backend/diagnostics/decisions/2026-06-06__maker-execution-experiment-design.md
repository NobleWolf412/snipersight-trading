# 2026-06-06 — §15 Design Entry: Maker-Execution A/B Experiment (PAPER ONLY)

**Type:** design entry (CLAUDE.md §15 — required before any live-execution-path-adjacent change).
No code landed under this entry; it authorizes a phased, default-off, paper-only experiment.
**Trigger:** the edge-after-fees verdict (2026-06-06__edge-after-fees-verdict.md / ledger T8):
gross expectancy +0.43/tr (95% CI spans 0), breakeven per-side fee 0.045% — BETWEEN maker
(~0.01%) and taker (0.06%). Maker fills are the ONLY lever that flips net-negative→positive.
The bot currently takes TAKER fills via the LIMIT-SNAP. Full Plan-agent design pasted in the
session transcript; this records the decisions.

## Key finding (de-risks the work)
The resting-maker path ALREADY EXISTS end-to-end: pending-order machinery + monitor-loop fill +
per-type TTL (paper_trading_service.py:1010-1240, _PENDING_TTL_MINUTES :46-50). The paper executor
fills a limit ONLY when price reaches it (paper_executor.py:379-382) — today's "immediate" fill is
purely an artifact of the caller snapping the limit to ~market (:2261-2307) then calling
execute_limit_order(order_id, current_price) at :2320. So getting maker execution is a CALLER-side
change (skip snap + skip the immediate fill), NOT an executor rewrite.

## Phasing + gates (measure before trusting)
- **Phase 1 (small, default-off, paper-only):** add `execution_mode: "snap_taker"|"rest_maker"` to
  PaperTradingConfig (default snap_taker = ZERO behavior change), sourced from botConfig (NOT
  ScannerContext, per §15 CLAUDE.md:59). In rest_maker: skip the snap (limit = entry_zone.near_entry,
  the OB) and skip the immediate fill → fall into the existing pending branch; the monitor loop fills
  it only when price retraces to the OB. Tag execution_mode on telemetry + CompletedTrade. NO fee
  modeling yet (journal pnl is GROSS → measure net via edge_significance).
- **GATE 1:** run a rest_maker window; measure FILL RATE (pending_order_placed vs trade_opened vs
  pending_order_expired) + adverse selection (outcome of filled vs expired-unfilled, entry-location
  loc_bb). If fill rate collapses or filled trades are reversal/loser-biased → STOP; maker execution
  is structurally incompatible with trend-shorting → §15 verdict conclusion #3 (rethink premise).
- **Phase 2 (only if GATE 1 passes):** add maker/taker fee distinction to PaperExecutor
  (_calculate_fee +liquidity arg; monitor-loop fill→maker, snap immediate→taker, market exit→taker)
  + a maker scenario in edge_significance.FEE_SIDES (0.0001/side). Re-run edge_significance over the
  rest_maker cohort (maker rate) vs snap_taker cohort (taker rate).
- **GATE 2:** does rest_maker net-expectancy CI clear zero AND beat snap_taker? Even if yes, treat as
  a CEILING (paper overstates maker fills — no queue position / trade-through; funding unmodeled).

## HARD BOUNDARY (§15) — paper only
- **DO NOT touch live_executor.py.** No changes to the live path.
- **CRITICAL bleed risk:** paper_trading_service.py:485-492 constructs a **LiveExecutor** when
  `use_testnet=True`. The snap-skip / fill-skip live in shared `_process_signal`. MITIGATION
  (mandatory): forbid `execution_mode="rest_maker"` when `use_testnet=True` (force snap_taker or
  raise). Keep maker/taker fee args OFF the LiveExecutor constructor.
- snap_taker (default) must be proven byte-inert: when the toggle is absent/snap_taker, behavior is
  identical to today.

## Honest prior (skeptical)
Even gross edge isn't statistically distinguishable from zero, so a positive result is NOT
guaranteed even with maker fees. The strategy shorts downtrends; a passive sell-limit ABOVE a
falling market is the order that never fills on the winners and DOES fill on the reversals (losers)
— adverse selection likely eats the fee savings. Most probable outcome: fewer trades, similar-or-
worse net → confirms "rethink the premise." Worth running ONLY because Phase 1 is cheap/default-off
and GATE 1 kills it before fee work; a clean negative HARDENS the strategy verdict.

## Blast radius (Phase 1)
paper_trading_service.py (snap block, immediate-fill, PaperTradingConfig, telemetry payloads,
CompletedTrade), botConfig→config plumbing (api_server.py mirrors of sniper_mode :1164/1209/3079/
3148 — new optional field, contract diff expected clean w/ default). edge_significance.py (cohort
filter / maker scenario — Phase 2). NO engine/strategy/scorer changes. Each phase: symmetry-guard
N/A (execution, not scoring) but backend-integrity + §16 + contract-check gate it.

## Decision
Approved-pending-operator-go for **Phase 1 only** (default-off paper toggle + fill-rate measurement).
Phase 2 gated on GATE 1. Live path untouched; testnet+rest_maker forbidden. Ledger: new thread.
