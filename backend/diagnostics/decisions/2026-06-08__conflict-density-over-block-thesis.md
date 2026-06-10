# 2026-06-08 — Conflict-density "over-block" thesis: measured, narrowed, next step queued

## Context
Operator probed the `conflict_density` pre-scoring gate after a 100% STRIKE-mode wipeout
cycle (run 352871f6, 2026-06-08 23:44, 16/16 blocked). Two hypotheses raised:
- **(A) weak zones counted equally with strong ones** — gate does `conflict_count += 1` per
  opposing A/B OB + opposing BOS, flat (`scorer.py:415-432`), reject at >=3 (non-overwatch)/>=5.
- **(B) HTF "magnet/target" zones miscounted as continuation threats** — a scalp drawn UP into
  a 1h bearish OB sees that OB as overhead TARGET, but the gate counts it as opposition.

## What we built (measure-first, read-only)
`backend/diagnostics/conflict_density_anatomy.py` (commit 1cc77cb). Telemetry-only, no engine
imports, does NOT touch the gate. Buckets every conflict_density rejection by grade / type /
timeframe-tier / inferred primary direction. Args: `--since --until --symbol --htf-min-tf --top`.
Auto-resolves last session via inter-scan time-gap.

## Findings
- **(A) REFUTED.** Opposition is overwhelmingly strong A-grade: 82.4% A on the borderline
  2026-06-09 overnight session, **97.1% A** on the WLD/STRIKE wipeout. Almost no marginal zones
  inflate the count. Grade-weighting the conflict score would change ~nothing. **Dead idea.**
- **(B) HOLDS ONLY AT THE MARGIN.** Borderline session: mean 4.9 conflicts, **52% HTF (>=1h)**,
  almost all 1h — these 1-2-over-threshold rejections are where HTF structure is the swing vote.
  WLD wipeout: mean 36.5 conflicts, **58.6% in-scale (5m/15m)** strong structure — a genuine wall,
  correctly blocked. So the geometry fix targets the MARGINAL band (low count, HTF-weighted), NOT
  deep wipeouts (which are the gate working).
- Refined thesis: "the gate over-blocks" is too broad. Precise claim = *HTF structure tips
  marginal (3-5 conflict) rejections that may be targets, not threats.*

## Blocker / next step
Grade + timeframe took us as far as telemetry allows. **target-vs-threat needs price geometry**
(is the opposing OB above/below price, in-path or against-path) — and the reject event records
OB grade + TF but NOT `ob.top/ob.bottom` NOR scan-time `current_price`. Uncomputable today.

NEXT (queued for next session): additive telemetry enrichment — serialize `ob.top/ob.bottom`
+ `current_price` into the conflict_density `GateResult.metadata` (`scorer.py:454-463`). It is
metadata-only (does NOT change conflict_count / threshold / pass-fail), BUT scorer.py is
standing-fix-protected → requires **design entry → symmetry-guard → §16 audit → contract diff**
before landing. After it ships + one bot session, re-run `conflict_density_anatomy.py` focused
on the marginal band to finally classify magnets vs walls.

Downstream of THAT (operator's actual goal): path-aware gate + scalp-long-into-HTF-zone-then-
intraday-short-at-zone sequence. Note `reversal_detector` exists but is inert (T16) = dormant
machinery for the "flip short at the zone" leg. Two-leg sequence doubles fee drag on an already
marginal/negative net edge → only viable under maker execution (T14).

## Status
🟡 WATCH-FORWARD. No scorer/gate code touched. Diagnostic + skill-map fix committed (1cc77cb,
pushed origin/main). Overnight STEALTH scan launching to grow the marginal-band sample.
