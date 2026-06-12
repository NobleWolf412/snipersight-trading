# Phase 4F — score calibration: 4E confirmed biting, gate recalibration DEFERRED

**Date:** 2026-06-12
**Phase:** 4F (data-collection + analysis; terminal phase of the SMC/scoring remediation)
**Diagnostic:** `backend/diagnostics/phase4f_score_calibration.py` (re-runnable)
**Tool:** `python -m backend.diagnostics.phase4f_score_calibration`

## What 4F was supposed to do

Collect post-fix signals, compute the per-setup score Δ vs the pre-fix baseline,
and propose a gate recalibration **if** the data supports one. The fixes under
test: 4C (OB wick demotion + source tagging), 4D (wall-clock freshness
recompute), 4E (institutional-sequence temporal ordering).

## Method (and why it's not naive)

- **Pre/post split by code signature, not date.** The bot ran STALE code after
  the 4C–4E commits landed (backend never hard-restarted until 2026-06-11). So
  filename/date can't classify a session. Instead: post-4E sessions emit the new
  institutional-sequence rationale strings (arrow form + "no subsequent / no
  preceding / temporal order" tier reasons); pre-fix emits "Sweep + Shift + OB".
- **Dedup per (session, symbol, direction).** Raw factor-bearing rows are
  inflated by re-scoring the same setup every scan (one ADA short logged 226×).
  Deduped to the last row per distinct setup.
- **Gate-clearers only.** `signals.jsonl` persists the `factors` breakdown ONLY
  for signals that clear the gate (confluence ≥ mode threshold). Sub-gate scored
  signals carry a confluence number but no breakdown. This is a known sampling
  limitation — see "Open follow-up" below.

## Result

| Institutional tier | Pre-fix (n=441) | Post-4E (n=9) |
|---|---|---|
| 100 | **94.8%** | **44.4%** |
| 70  | 1.8% | 0% |
| 50  | 0% | 0% |
| 40 (temporal violation) | **0%** | **22.2%** |
| 20 (sweep, no follow-through) | **0%** | **33.3%** |
| 0   | 3.4% | 0% |
| Confluence median | 75.3 | 71.5 |
| OB wick-capped (≤35) | 2.3% | 0% |

## Findings

1. **4E is confirmed working — unambiguously, even at n=9.** The 40 and 20 tiers
   *did not exist* under the old code (it was effectively binary: all-present →
   100). Post-4E, **55.6% of setups land in those new intermediate tiers** —
   setups the old scorer would have rubber-stamped at 100 are now correctly
   down-rated for wrong temporal order (40) or sweep-with-no-follow-through (20).
   The 94.8% → 44.4% collapse in the perfect-score rate is the
   rubber-stamp-to-discriminating shift the whole remediation set out to prove.

2. **Score distribution compressed toward the gate.** Confluence median dropped
   75.3 → 71.5 (~3.8 pts). De-rating the institutional component pulls borderline
   setups down toward the 70 line — the predicted effect. (Post max 76.6 vs pre
   95.9 is mostly the tiny sample missing rare high outliers, not a real ceiling
   change.)

3. **4C wick demotion: INCONCLUSIVE.** 0/9 post-4E setups wick-capped vs 10/441
   (2.3%) pre. Wick-only setups are rare; n=9 wouldn't be expected to contain one
   regardless. No claim either way.

## Decision: NO gate recalibration on this sample

The post-4E sample is **n=9 distinct setups, single regime (`down_normal`),
single session-cluster, asian hours.** That is not a baseline. CLAUDE.md §15 is a
hard boundary: *do not modify `min_confluence_score` / pre-scoring thresholds
without documented baseline data + reasoning.* Proposing a gate change off n=9
would be the exact "wet bandaid on a symptom" failure the constitution warns
against (§FUNDAMENTALS-FIRST).

**The directional hypothesis** — that 4E systematically shaves ~4 pts off scores,
so the 70 gate (tuned on inflated pre-fix scores) is now effectively stricter and
*may* eventually justify a downward recalibration — is **logged but unproven.**

### Threshold to revisit
Re-run `phase4f_score_calibration` once post-4E data reaches:
- **≥30 distinct setups**, across
- **≥2 distinct regimes** (not just `down_normal`), collected over
- **active-hours sessions** (London/NY), not asian-hours `down_normal` only.

Only then is a gate-recalibration proposal defensible.

## Open follow-up (queued, post-4F)

**Sub-gate breakdown persistence.** The `factors` breakdown is discarded for
~62% of scored signals (everything that scored 40–69 but didn't clear the gate).
That is the single reason this calibration is sample-starved: we can only see the
top slice. Persisting the breakdown for all scored signals (an observability
change, NOT a gate change — §LOOP) would let the next calibration measure the
institutional-tier distribution across the full score range and converge far
faster. No pre-fix sub-gate counterpart exists, so it doesn't help *this*
comparison — it's forward infrastructure.

## Status

Phase 4 (4-pre → 4F) of the SMC/scoring remediation is **complete**. 4C/4D/4E are
shipped and on origin/main; 4E is confirmed live and discriminating. 4F closes as
*analysis delivered, recalibration deliberately deferred for insufficient data* —
not as a tuning action.
