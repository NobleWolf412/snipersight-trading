# SniperSight Confluence Rejection Diagnostic
**Generated:** 2026-03-22
**Scope:** `backend/strategy/confluence/scorer.py` — full code audit
**Problem:** Excessive signal rejections due to systematically low confluence scores

---

## The Core Problem in One Sentence

The scoring system has had thresholds raised 3–4 times without any compensating recalibration of factor scoring, while simultaneously accumulating structural penalties (kill zone, coverage, direction margin, cycle gates) that stack to produce a total score drag of **15–35 points before a single SMC factor is scored**.

---

## 🔴 Critical Issues (Causing Majority of Rejections)

### 1. Threshold Inflation Without Rebalancing

| Mode | Old Threshold | Current Threshold | Required Score Increase |
|------|--------------|-------------------|------------------------|
| OVERWATCH | 72% | 78% | +6 pts |
| STRIKE | 60% | 70% | +10 pts |
| STEALTH | 65% | 70% | +5 pts |
| SURGICAL | 75% | 72% | -3 pts (only one reduced) |

Thresholds were raised across the board — multiple times based on the comments in `scanner_modes.py` — but the underlying factor scoring functions were not recalibrated. Every single point you added to the threshold came directly out of your signal rate. A score that passed at 72% now fails at 78%, with zero change to what the market is showing.

---

### 2. Kill Zone Scoring: Systematic 0 for Sydney Hours

**Function:** `_score_kill_zone_incremental()` (line 3877)

The kill zone scoring awards:
- +25 pts if any kill zone is active
- +10 pts if NY Open or London Open specifically

Total possible: **35 points** (raw) contributing up to ~1.75 pts to weighted score at 0.05 weight.

But the check uses `datetime.now(timezone.utc)`. Sydney active hours (roughly 7am–5pm AEST) map to approximately **8pm–6am UTC**, which puts you in or near the **Asian session** only. Asian kill zone gets the +25 "active" points but NOT the +10 Prime Session bonus.

London Open and NY Open occur during Sydney late afternoon/evening, so any morning scan session in Sydney scores 0 for kill zone timing. This also means the **Coverage Penalty** (see below) gets triggered more often, since Kill Zone Timing counts as one of the 6 "quality" factors required to avoid the penalty.

**Additionally:** There's a self-import bug at line 2116:
```python
from backend.strategy.confluence.scorer import get_current_kill_zone, _score_kill_zone_incremental
```
This imports from itself. It happens to work because the top-level import at line ~33 already populated those names, but it's dead weight in a `try/except` — if there's ever a circular import scenario, the kill zone silently scores 0 and you'd never know.

---

### 3. Coverage Penalty: A Tax on Normal Market Conditions

**Location:** Final formula in `calculate_confluence_score()`

```python
coverage_penalty = (6 - quality_factors) * 3.0  # Max -15 pts
```

"Quality factors" = factors that score ≥50. The system requires **6 of them** to avoid penalty. Each missing one costs 3 points, capped at -15.

These are the factors that routinely score **0 in a typical non-ideal setup**:
- **Fair Value Gap** — 0 if no aligned FVG exists in the snapshot
- **Kill Zone Timing** — 0 outside London/NY during Sydney hours (your situation)
- **Price-Indicator Divergence** — 0 unless the primary TF dataframe has ≥50 bars AND divergence is actually detected
- **Multi-Candle Confirmation** — 0 if the pattern isn't present
- **Nested Order Block** — 0 unless an LTF OB exists with ≥50% overlap inside an HTF OB
- **LTF Structure Shift** — 0 if no CHoCH/BOS detected on LTF

In a perfectly valid SMC setup that simply doesn't have a stacked FVG or nested OB (which is most of them), you're routinely starting at **-6 to -9 points** before a single trade-relevant factor is evaluated.

---

### 4. Structural Minimum Gate: Hard Cap at 60 for Swing Modes

**Location:** Lines 2133–2160

For OVERWATCH and STEALTH modes, if `ob_score == 0 AND fvg_score == 0 AND sweep_score == 0`, a `ConfluenceFactor` with score=0 and weight=0.30 is injected. This doesn't just penalize — it **mathematically caps the raw score near 60** because a 0.30-weight zero-score factor pulls the weighted average down by ~30 raw points.

- OVERWATCH threshold: 78
- Cap from structural minimum gate: ~60
- **Gap: 18 points, unbridgeable**

This means any scan where the SMC engine hasn't detected OBs, FVGs, or sweeps in the trade direction automatically fails OVERWATCH/STEALTH with zero path to recovery. The original comment says "prevents pure HTF alignment setups" — but the detection of OBs/FVGs is sensitive to data freshness and the lookback window. Borderline detections can flip this gate on or off.

---

### 5. Direction Margin: 5-Point Gap Required Before Scoring Even Begins

**Location:** `confluence_service.py`

A setup must have a **5-point edge** between LONG raw score and SHORT raw score to even select a direction. Both scores are independently affected by cycle penalties that are **asymmetric**:

From `_calculate_synergy_bonus()`:
```python
WCL_FAIL_LONG_PENALTY:  overwatch = -12, stealth = -8, strike = -5
WCL_FAIL_SHORT_BOOST:   +5 (all modes)
# Net swing: LONG -12 vs SHORT +5 = 17-point directional gap just from WCL failure
```

Similarly:
```python
MARKDOWN_LTR_LONG_PENALTY:  overwatch = -10, stealth = -6
# SHORT penalty in markup: -10 (symmetric, which is newer)
```

In a WCL-failed market, the LONG vs SHORT gap starts at -17 before any SMC factor differences. The 5-point direction margin check then evaluates on these already-adjusted raw scores. LONGs in a WCL-failed market are being hard-pushed toward rejection before structure/momentum analysis has any say.

---

## 🟡 Significant Contributing Factors

### 6. Variance Amplification Punishes Near-Threshold Scores

After the raw score is computed, the amplification curve applies:

```
Score ≥ T+3:         +2 pts bonus
Score ≥ T:           +(score-T) * 0.4 boost
Score ≥ T-5 (miss):  0 (unchanged, fails)
Score ≥ 50 (weak):   dampened slightly
Score < 50:          quadratic decay
```

A setup scoring 73 against OVERWATCH threshold of 78 gets **exactly zero help from the amplification curve**. It's in the T-5 dead zone — not low enough to be dampened further, not high enough to be boosted. It just fails flat. The curve is designed to push strong setups higher and kill weak ones — there's no grace zone around the threshold.

---

### 7. Conflict Penalty Stacks and Overwatch Multiplies It

From `_calculate_conflict_penalty()`:
- BTC gate opposition: +20 penalty (or +10 if weak but not zero)
- Weak momentum vs strong structure: +10 penalty
- HTF neutral (ranging market): +8 penalty

These stack up to 35 pts (before the mode multiplier). For OVERWATCH: `1.2x multiplier` → a 35pt conflict penalty becomes 42pts effectively deducted.

**Synergy cap for OVERWATCH: 10 pts.** So even in a perfect setup, synergy can offset at most 10 points of the 42-point conflict stack. The math doesn't close.

---

### 8. FVG `size_atr` Attribute May Not Exist

`_score_fvgs_incremental()` (line 3003):
```python
if getattr(best_fvg, "size_atr", 0.0) > 1.0:
    score += 15.0  # Large Gap bonus
```

If the `FVG` object doesn't have a `size_atr` attribute (older data or schema mismatch), the +15 size bonus never fires. A valid bullish FVG would score 30 (Grade B) + 20 (Virgin) = 50 max — still below the quality threshold of 60 needed to count as a "quality factor" and avoid the coverage penalty.

---

### 9. Regime Detection Catches Too Many Markets as "Choppy"

`_detect_regime()` (lines 4512+) classifies market regime as choppy when:
- ATR% < 0.8% (relaxed from 0.4%)
- RSI between 35–65 (relaxed from 40–60)
- ≤2 BOS breaks, no CHoCH

This threshold relaxation means a significant portion of crypto markets in consolidation phases get labeled "choppy." The regime score for choppy conditions is reduced, which contributes to lower final scores.

---

## 📊 Approximate Score Impact Summary

| Issue | Points Lost (Typical Setup) |
|-------|---------------------------|
| Kill Zone timing (Sydney morning hours) | −0 to −3 (via coverage penalty) |
| Coverage penalty (4–5 quality factors) | −3 to −9 |
| Cycle penalties (WCL or DCL failure) | −5 to −12 |
| Conflict penalty (HTF neutral/BTC weak) | −8 to −20 |
| Structural minimum gate (swing modes) | Cap raw score at ~60 |
| Direction margin failure (cycle skew) | Hard rejection, no score produced |
| **Total score drag before SMC scoring** | **−16 to −44 pts** |

With a threshold of 78 for OVERWATCH, a raw SMC/indicator score of 80 can end up at **36–64 after penalties** — well below the gate.

---

## ✅ Actionable Fixes (Ordered by Impact)

### Fix 1: Lower OVERWATCH Threshold Back to 73–75
The 78% threshold combined with the structural overhead is the single biggest lever. Going from 78 to 74 is equivalent to recovering 2–3 quality factors worth of points. This is the lowest-risk change with the highest signal-rate impact.

### Fix 2: Reduce Coverage Penalty or Lower the Required Quality Count
Change `(6 - quality_factors) * 3.0` to `(5 - quality_factors) * 3.0` — requiring 5 instead of 6 quality factors. This alone recovers 3 points for setups that are currently borderline. Alternatively, reduce the per-factor deduction from 3.0 to 2.0.

### Fix 3: Fix the Kill Zone Self-Import (Line 2116)
Replace:
```python
from backend.strategy.confluence.scorer import get_current_kill_zone, _score_kill_zone_incremental
```
With:
```python
# These are already imported at module top — use them directly
```
Then call `get_current_kill_zone(now)` and `_score_kill_zone_incremental(now, curr_kz)` directly. The try/except will still catch runtime failures.

### Fix 4: Make Kill Zone Neutral (Not Zero) Outside Active Sessions
Change `_score_kill_zone_incremental()` to return 40 (neutral/acceptable) instead of 0 when outside all kill zones. This prevents kill zone from triggering the coverage penalty every morning scan. The signal should indicate "no timing edge" — not "active red flag."

### Fix 5: Cap Synergy Better for Conservative Modes
OVERWATCH has synergy capped at 10 but conflict penalties can exceed 40. Either:
- Raise OVERWATCH synergy cap to 15–18, OR
- Reduce the conflict penalty cap from 35 to 20 for OVERWATCH specifically

### Fix 6: Add a Score Floor to Coverage Penalty
Cap the coverage penalty damage at -6 (max 2 missing quality factors) instead of -15 (5 missing). Most real SMC setups will have some factors that are structurally absent (nested OB, divergence) by design — the penalty was meant to catch lazy signals, not punish valid setups that lack rare confluence elements.

### Fix 7: Widen the Direction Margin Check Window
Reduce `DIRECTION_MARGIN` from 5 to 3 for STRIKE and SURGICAL modes. For OVERWATCH, the 5-point margin makes sense given the lower-frequency nature, but for intraday/scalp modes where the cycle gates already penalize direction heavily, a 3-point margin would reduce false direction failures.

---

## Quick Reference: What a Typical Rejection Looks Like

```
Symbol: ALTUSDT  |  Mode: OVERWATCH  |  Direction: LONG

Factor Scores:
  Market Structure:    72  ✓ (quality)
  HTF Alignment:       68  ✓ (quality)
  Momentum:            55  ✓ (quality)
  Order Block:         45  ✗ (below 50 threshold for quality)
  Liquidity Sweep:     38  ✗
  Fair Value Gap:       0  ✗ (no FVG in direction)
  Kill Zone Timing:     0  ✗ (9am Sydney = 10pm UTC = outside London/NY)
  Divergence:           0  ✗ (no divergence detected)

Quality factors ≥50: 3 (Market Structure, HTF Alignment, Momentum)
Coverage penalty: (6-3) × 3 = -9 pts

Raw weighted score: ~71
Coverage penalty:   -9
Cycle penalty:      -8 (DCL failed)
Final score:         54  →  REJECTED  (threshold: 78)

What it would need to pass: 24 more points, with 0 structural path to get there.
```

This is a structurally valid setup (aligned structure, momentum, HTF) being rejected because three minor factors scored 0, a cycle event occurred, and the threshold is set for best-in-class confluence.

---

*Report generated by SniperSight overnight diagnostic session. Recommendations are calibration adjustments — not logic rewrites.*
