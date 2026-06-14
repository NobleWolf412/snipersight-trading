# Edge research — the "no edge" verdict is an averaging artifact: a profitable scalp pocket dragged negative by the swing tier

**Date:** 2026-06-14
**Trigger:** Operator "full research, willing to adapt" after factor_contribution showed only 1 of 26 factors tracks outcomes.
**Tools:** `edge_significance.py`, `edge_by_regime.py`, `factor_contribution.py`, manual cohort net-after-fees from `trade_journal.jsonl` (n=349, post-clamp window).

## 1. Blended verdict (unchanged): no demonstrated edge after fees
`edge_significance` post-clamp n=199, win 51%, payoff 1.15:
- gross +1.11/trade (95% CI [-3.06,+5.62], P>0 = 68% — not even gross-positive with confidence)
- Phemex taker (0.06%/side): **-0.14/trade**, CI spans zero, P>0 = 46%
- breakeven per-side fee 0.0532% < taker 0.06% → **net-negative blended.**

## 2. But the blend hides a real split — cohort net-after-fees (taker 0.06%/side)
| regime | type | n | win% | gross/t | **NET/t** | net total |
|---|---|---|---|---|---|---|
| down_normal | **scalp** | 58 | 53% | +8.47 | **+6.42** | **+372.6** |
| down_normal | intraday | 12 | 42% | +6.47 | +4.23 | +50.7 |
| down_compressed | intraday | 10 | 60% | +1.30 | +0.93 | +9.3 |
| down_compressed | scalp | 73 | 52% | -0.27 | -1.06 | -77.7 |
| down_normal | **swing** | 46 | 46% | -7.39 | **-8.32** | **-382.8** |

**The strategy has a genuinely fee-positive core: down_normal SCALP, +6.42/trade NET, n=58 — it survives taker fees comfortably.** It is dragged to blended-breakeven by the **swing tier (-8.32/trade net, -382.8 total)**, which nearly perfectly cancels the scalp pocket. This validates the operator's own earlier thesis (scalps = money-makers; swings rare-but-here-LOSING).

Note: the cascade's `_CASCADE_TYPE_BONUS` (swing +6, scalp 0) actively biases selection toward the LOSING tier — backwards vs the data.

## 3. Edge is REGIME-CONDITIONAL (down_normal), not universal
Same trade type, opposite result by regime: down_normal scalp +6.42 net vs down_compressed scalp -1.06 net. The edge pocket is specifically **down_normal scalp.** down_compressed and (per the user's live chart) sideways/low-vol regimes do NOT carry it.

## 4. Why the bot trades nothing right now (operator chart confirms)
Operator observed BTC ~18h sideways, low volume. Matches the data exactly: 0 trades, max confluence 64.7 (<68 gate), 100% reject. **The edge pocket (down_normal scalp) requires a trending-down tape; the current sideways chop doesn't produce those setups, so the bot correctly idles.** (Telemetry note: scan_completed regime field has logged `None` since 2026-06-13 — a labeling/telemetry gap to flag separately; API status still reported down_normal.)

## 5. Factor efficacy (factor_contribution, n=190 clean): 1 of 26 predicts
Only VWAP Alignment (r_clean +0.21) tracks winners above the noise floor. 25 of 26 factors are at/below noise — no demonstrated outcome-tracking (small-n caveat: unproven ≠ useless). The confluence score is mostly undifferentiated w.r.t. outcomes.

## VERDICT: viable in a pocket, not as currently blended
The strategy is NOT dead. It has a profitable, fee-surviving engine (down_normal scalp) buried under (a) a money-losing swing tier the cascade actively prefers, and (b) a 26-factor score where only 1 factor predicts.

## ADAPT ROADMAP (evidence-ranked, all gated/design-first per §15/§16)
1. **Cut or fix-and-reprove the swing tier.** -382.8 net is the single biggest drag; removing it flips the blend net-positive. (Swing also uses the mis-anchored 1d dealing range — Jan-high issue — and has no demonstrated edge.) Design-first: disable swing in the STEALTH cascade vs fix its anchoring then re-prove.
2. **Invert the cascade preference.** `_CASCADE_TYPE_BONUS` favors swing (+6); data says scalp earns. Flip/remove.
3. **Concentrate on down_normal scalp** — the proven pocket. Consider gating the bot to its edge regime.
4. **Rebuild the factor stack around VWAP** + re-test the other 25 as the clean sample grows.
5. **Maker execution** widens the margin further (scalp already survives taker).

## Caveats
n=58 scalp pocket is decent not huge; modeled (not real-fill) fees; funding on swings unmodeled (swing net is an optimistic ceiling — i.e. swing is likely EVEN WORSE). Keep accumulating down_normal scalp trades to harden +6.42.
