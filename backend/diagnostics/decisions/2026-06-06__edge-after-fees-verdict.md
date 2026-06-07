# 2026-06-06 — Edge-after-fees VERDICT (the smoking gun) + journal-pnl-is-GROSS correction

**Trigger:** operator asked "is there anything we can run to find the smoking gun." Built
`backend/diagnostics/edge_significance.py` (read-only): bootstrap CI on per-trade expectancy +
breakeven-fee, across the clean post-clamp window.

## Correction to the 2026-06-06 fills-fees scope doc
That doc stated the journal `pnl` is "modeled-net (fee_rate=0.001)". **Empirically false for the
journal ROW.** Verified: `pnl == quantity*(exit-entry)*dir` to the cent (gap 0.000% on 8/9 sampled
trades; the 9th is a 2x partial/TP-ladder artifact). The modeled fee charges the paper executor
**balance** (paper_executor.py:210-212 `_calculate_fee`), but is **NOT** subtracted into the
per-trade journal `pnl`. Slippage IS already in (executor slips fill prices). So the journal
expectancy is GROSS-of-fees, and modeled edge-after-fees IS computable from paper data now — we do
NOT need live fills for a MODELED fee rate (only for REAL per-fill reconciliation, which still
needs live per the scope doc).

## Verdict (clean post-clamp window, --since 2026-05-31, n=142)
| fee | exp/trade | 95% CI (20k bootstrap) | P(edge>0) |
|---|---|---|---|
| gross (0) | +0.43 | **[-0.66, +1.54]** | 78% |
| Phemex taker 0.06%/side | -0.14 | [-1.34, +1.04] | 41% |
| bot model 0.10%/side | -0.52 | [-1.83, +0.73] | 21% |

- **Even GROSS, the edge is not statistically distinguishable from zero** (CI spans 0, P=78%).
- **Breakeven per-side fee = 0.045%** vs Phemex taker 0.06% → **net-negative at taker fees.**
- Full history (n=292): gross -2.15, at-taker -3.42, CI [-6.48,-0.42], P(edge>0)=1% — decisively net-negative.
- Funding on held swings NOT modeled → real net is LOWER (these are optimistic ceilings).

## The one nuance — viability hinges on EXECUTION, not signal
Breakeven 0.045%/side sits BETWEEN maker (~0.01%) and taker (0.06%):
- Current execution = **taker** (LIMIT orders snap-to-market and fill immediately = cross spread =
  taker) → net-negative.
- **Maker** fills (resting limits, no chase) → breakeven clears → net-POSITIVE *if* the thin gross
  edge is real (it's not yet significant).

So: a "better signal" has nothing to bite on (gross edge insignificant). The ONLY lever touching
the breakeven is fee tier — i.e. maker execution — which directly conflicts with the LIMIT-SNAP
chase (T9, previously called benign; benign for risk, NOT for fees).

## Conclusion (closes T8)
The strategy has **no edge that survives taker fees**, and no statistically demonstrated edge even
gross. This is a strategy/execution-level verdict, not a bug. Implications:
1. Stop hunting for a predictive signal/factor — the gross edge isn't significant; there's nothing
   for a new input to improve toward profitability.
2. The only path to net-positive is **cheaper execution (maker fills)** — rest limits instead of
   snapping to market. That is a real, bounded engineering question (and it re-opens T9 as a
   fee-relevant thread, not a benign one).
3. Or accept the strategy is structurally edgeless at this timeframe/universe and rethink the premise.

VERIFY-NEXT: re-run as clean sessions accumulate (n grows → CI tightens). If gross stays
CI-spans-zero, conclusion hardens. A maker-execution experiment would test lever #2 directly.
