# 2026-05-25 — Intel page real-data wiring (Phase 1)

## Headline
Wired Intel page Regime Tape (4 bars) + Bias-Map tiles (Confluence Floor, BTC Veto) to existing backend endpoints; fixed silent `useMarketRegime` dominance bug.

## Context
- Operator directive: "the entire page needs to work with real data".
- `useMarketRegime` had been reading `data.dimensions?.dominance_btc` since hook creation, but `/api/market/regime` emits dominance under `data.dominance.btc_d` / `stable_d` / `alt_d`. Real dominance data was silently discarded → BTC.D / USDT.D dials always rendered the in-component fallback 54.32 / 4.12. Exactly the §11 hidden-bug pattern; §10 standing-fix #4 (real dominance data) was latent-broken.
- Hook didn't expose the five per-dimension scores (`trend_score`, `volatility_score`, `liquidity_score`, `risk_score`, `derivatives_score`) the backend already returns. RegimeTape rendered hardcoded literals 72/48/68/31 with an apologetic "synthetic" caption.
- Bias-map tiles `Confluence Floor`, `Active Setups`, `BTC Veto` were hardcoded copy; `/api/scanner/modes` and `/api/market/btc-cycle-context` already exist and carry the needed data.

## Resolution
- `src/hooks/useMarketRegime.ts` — bug fix at lines 96-99 (correct dominance path), extended return shape with 5 optional `*Score` fields + `compositeScore`. Code comment lines 86-92 documents the §10 #4 fix going operational.
- `src/pages/Intel.tsx` — added two fetch effects (`getScannerModes` for STEALTH min_confluence_score, `getBTCCycleContext` for macro veto). RegimeTape: 4 bars wired to hook scores, 4th bar renamed Correlation → Derivatives (backend has no correlation metric; inventing one would violate §15). Bias-map tiles: Confluence Floor renders `≥ {stealth.min_confluence_score.toFixed(1)}` (read-only; §15 boundary); BTC Veto renders CLEAR/WATCH/ACTIVE on `overall.macro_bias`.
- `tests/visual/setup.ts` — registered 2 new fixture routes (`/api/market/btc-cycle-context`, `/api/scanner/modes`) ordered to match before catch-all.
- `tests/visual/fixtures/{scanner-modes,btc-cycle-context}.json` — new fixtures mirroring backend response shapes.

## What's still synthetic (Phase 2, needs new backend)
Per the plan agent's deferred track:
- DXY / 10Y / GOLD / VIX in MacroTicker (needs TradFi feed endpoint)
- Liquidation Heatmap (needs Coinglass/Hyblock integration)
- Catalyst Wire (needs RSS/news ingestion)
- AI Analyst (needs Haiku endpoint + cost ceiling design)

All four still labelled `◌ SYNTHETIC` in the UI per §11 disclosure honesty.

## Why it matters next time
1. **Silent-undefined fallbacks hide real-data bugs**. The dominance read path was wrong from day one and never threw — the UI just fell through to its in-component placeholder constants. This is the §11 pattern in its purest form. Pre-commit grep for `data.dimensions?.dominance_` should be added to the symmetry-guard checklist; the typo class will recur whenever backend renames a top-level dict key.
2. **Backend regime endpoint already had everything needed** (5 per-dimension scores + 3 dominance values) — the frontend just wasn't reading it. When wiring a "synthetic" panel, always check the existing response shape first; many panels are synthetic only because the consumer code is stale.
3. **Audit advisory queued for follow-up**: explicit "intel-loading" state in `tests/visual/states.ts` that doesn't register the two new fixture routes, so the `(awaiting feed)` placeholder rendering has its own snapshot baseline. Current loading-state coverage is incidental (catch-all returns `{}` which still exercises the right branch by accident). Non-blocking; queue for the next snapshot-framework pass.

Linked files:
- `src/hooks/useMarketRegime.ts`
- `src/pages/Intel.tsx`
- `tests/visual/setup.ts`
- `tests/visual/fixtures/scanner-modes.json`
- `tests/visual/fixtures/btc-cycle-context.json`
