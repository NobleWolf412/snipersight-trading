# Phase 5E DESIGN ENTRY — condition the P/D factor on trend/structure context

**Date:** 2026-06-13
**Status:** DESIGN QUEUED — NOT implemented. Ship gated on data (see finding doc).
**Basis:** `decisions/2026-06-13__pd-factor-inverted-in-trends-finding.md` — P/D endorsement
inverted in trends (favored cohort 38% WR / −212; opposed-with-BOS cohort 54% WR / +67).

## Problem
The Premium/Discount factor applies "premium=sell / discount=buy" UNCONDITIONALLY. That's a
ranging/reversal rule; in a confirmed trend continuation it's a category error that penalizes
with-trend trades. The P/D factor and the Market Structure (BOS/CHoCH) factor are independent
additive terms with no arbitration — so on a continuation breakout they fight, and the data
shows P/D loses (its endorsement correlates with losses).

## Proposed change (the WHAT — HOW to be designed via Plan agent before code)
Make the P/D direction-reward **conditional on trend/structure context**:
- When a confirmed **aligned BOS continuation** exists (Market Structure says BOS in the trade
  direction, HTF-aligned), **suppress or invert** the premium/discount direction penalty — a
  with-trend continuation should not be docked for being in the "wrong" zone.
- When structure is **ranging / reversing** (CHoCH against prior trend, or no continuation
  BOS), **keep P/D as-is** (fade extremes — that's where premium/discount is valid).
- Regime input already exists: `regime_detector` classifies trend-vs-range; the BOS/CHoCH
  signal is already computed as the Market Structure factor. Plumbing is available — the fix
  is wiring it into the P/D scoring branch.

## Constraints (constitution-level)
- **Standing-fix-protected** (`scorer.py`, direction-aware scoring): bull/bear symmetry MUST
  hold — the conditioning must be mirror-symmetric (suppress premium-short penalty in confirmed
  downtrend continuation ⇔ suppress discount-long penalty in confirmed uptrend continuation).
- §15: no min_confluence_score / gate-threshold change. This is a FACTOR-logic change, not a
  gate change. (Though note the HTF gate's −40 PremiumDiscount_VIOLATION has the same blind
  spot — decide in design whether 5E also conditions the gate violation or only the factor.)
- Measure-first: this design entry is on record BEFORE code (CLAUDE.md §18).
- symmetry-guard + backend-integrity + §16 audit on the eventual diff.

## Ship gate (do NOT implement until)
1. **n grows** past the ~40/bucket caveat — fed by the sub-gate breakdown-persistence track
   (logs factor breakdowns for sub-gate signals → 3-5× sample for this exact re-measurement).
2. **Ranging-regime sample** confirms the conditional — that P/D is CORRECT (favored cohort
   wins) in ranging markets, so we condition rather than delete. Without this we risk removing
   a factor that's only wrong in one regime.
3. Re-run `pd_direction_efficacy` to confirm the inversion persists at larger n before coding.

## Sub-steps (when unblocked)
- 5E-pre: re-run efficacy at grown n + segment by regime label (trend vs range).
- 5E-A: implement conditional P/D (factor-logic), behind the regime/BOS context; symmetry pairs.
- 5E-B (maybe): condition the HTF gate's PremiumDiscount_VIOLATION likewise.
- 5E-verify: post-deploy re-run efficacy — the P/D-favored bucket should stop being the worst.

## Open questions for operator (at implementation time)
- Q: suppress vs INVERT the penalty on continuation? (Neutralize to 50, or actively reward
  with-trend?) — measure both.
- Q: does 5E also touch the gate −40, or factor-only first? (smaller blast radius factor-first)
- Q: trend/range threshold source — regime label, or BOS-presence directly?
