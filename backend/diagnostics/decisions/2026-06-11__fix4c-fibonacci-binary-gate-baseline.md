# Fix 4c: Fibonacci Binary Gate — Calibration Baseline

**Date:** 2026-06-11
**Change:** `_score_fibonacci_incremental` in `scorer.py` rewritten from graduated
percentage-based proximity scoring to a binary ATR gate (within 0.5 ATR → 100.0, else 0.0).

---

## Why percentage-of-price was wrong

The old graduated scoring used fixed percentage bands (0.3%, 0.6%, 1.2%) as proximity thresholds.
Percentage-of-price proximity is not comparable across assets or volatility regimes:

| Asset | ATR | Daily vol % | Old 0.3% band | 0.5 ATR equivalent |
|-------|-----|------------|---------------|-------------------|
| BTC $100k, ATR $1000 | 1% | ~$300 | ~$500 |
| ETH $3000, ATR $80 | 2.7% | ~$9 | ~$40 |
| SOL $150, ATR $8 | 5.3% | ~$0.45 | ~$4 |

For BTC, 0.3% ≈ 0.3 ATR — meaning the highest band was already ATR-relative by accident.
For ETH, 0.3% ≈ 0.11 ATR — the band was extremely tight relative to ETH's daily range.
For SOL and alts, 0.3% ≈ 0.056 ATR — nearly always failing even when price was plainly near a level.

This meant Fibonacci proximity was effectively disabled for most altcoins (ATR% >> 0.3%)
and inconsistently applied across assets. The graduated scoring also added golden pocket
bonuses (+25pts) and TF weights (×1.2 for 1D) that created non-obvious score compositions
impossible to calibrate against a single threshold.

---

## Why 0.5 ATR was chosen

**Design rationale:**

0.5 ATR is the standard SMC "reaction zone" width. An order block or FVG is typically
defined as valid if price is within one OB body (≈0.3–0.8 ATR for most assets). Fibonacci
levels, being point-based rather than zone-based, deserve a narrower window — but one that
scales with volatility.

0.5 ATR:
- **More permissive than 0.3 ATR**: Prevents over-tightening that kills signal frequency entirely
- **Tighter than 1.0 ATR**: Prevents treating the entire "near vicinity" as confluent
- **Normalizes across assets**: BTC, ETH, and alts all use the same volatility-scaled proximity
- **Conservative on missing data**: When ATR is unavailable → score=0.0 (no inflated floor)

**Comparison to old system:**

The old highest-quality band (0.3% → 60 base pts + possible 25pt golden pocket + 1.2x TF = up
to 102pts, clipped to 100) was reached rarely for alts. The binary gate at 0.5 ATR will hit
more frequently for alts than the old 0.3% band but less frequently than the old 1.2% band.
For BTC, 0.5 ATR ≈ 0.5% — between the old 0.3% and 0.6% bands. Net effect: the gate is
**more inclusive for high-volatility assets, stricter for low-volatility assets**, which is
the correct direction (high vol = wider levels needed; low vol = tight levels valid).

---

## What cannot be measured yet

Historical hit-rate (what % of scored signals previously triggered the 0.3/0.6/1.2% bands)
is not available without a replay of archived sessions. The `confluence_breakdown.log`
(rotating, `logs/confluence_breakdown.log`) will accumulate Fibonacci factor observations
in the first post-deploy session. After one overnight run, the following can be measured:

```python
import json, pathlib
lines = pathlib.Path("logs/confluence_breakdown.log").read_text().splitlines()
fib_hits = [json.loads(l) for l in lines if '"Fibonacci Proximity"' in l]
hit_rate = sum(1 for h in fib_hits if h.get("score", 0) == 100.0) / max(len(fib_hits), 1)
miss_rate = sum(1 for h in fib_hits if h.get("score", 0) == 0.0) / max(len(fib_hits), 1)
print(f"Fib gate: {len(fib_hits)} scored | hit={hit_rate:.1%} miss={miss_rate:.1%}")
```

**Expected range:** 15–40% hit rate (the level must be within half an ATR — genuinely confluent).
If hit rate > 70%: gate is too wide → reduce to 0.3 ATR.
If hit rate < 5%: gate is too tight → widen to 0.75 ATR or check ATR data availability.

---

## Conservative properties / safety analysis

| Property | Value |
|----------|-------|
| Missing ATR (None, 0) | Returns 0.0 — conservative, no inflation |
| Missing swing_structure | Returns 0.0 — conservative |
| Binary outcome | No partial scores → no intermediate calibration needed |
| Function signature | `atr=None` default → backward-compatible, won't break callers without ATR |
| Weight in scoring | factor weight `get_w("fibonacci", 0.05)` unchanged — Fibonacci is 5% of total |
| Max score contribution | 100 × 0.05 weight = 5 points toward confluence score |

The 0.5 ATR coefficient is provisional. Post-session hit-rate analysis (see snippet above)
should be run after the first overnight session and documented here.
