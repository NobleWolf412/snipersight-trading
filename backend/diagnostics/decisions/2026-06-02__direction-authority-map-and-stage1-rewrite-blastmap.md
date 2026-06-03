# 2026-06-02 — Direction-authority map + Stage-1 rewrite blast-radius

**Type:** architecture finding + design-prep (read-only pipeline audit; no code change).
**Method:** 6-agent parallel pipeline audit (stage1 / pre-scoring gates / scoring / planner-risk /
regime-cascade / contracts-telemetry) → synthesis. Run wf_7c695935-fe4.
**Trigger:** operator considering a Stage-1 direction-selection rewrite (count+tiebreak+default-long
→ weighted-conviction + ABSTAIN + regime-asymmetric).

## CORRECTION TO THE SESSION RECORD (important)

Earlier this session the direction mechanism was described as: "`_derive_pre_direction`
(orchestrator) counts a symbol's bullish vs bearish OBs+BOS, picks the majority, ties→regime,
neutral tie→default LONG; only ONE direction is then scored." **That is the less-important half
and is misleading about the authority.**

**The production direction authority is `confluence_service.score()` (confluence_service.py:186-497).**
It scores BOTH directions independently (`_score_direction` ×2 at :198-206), runs a winner-selection
ladder (:216-494), and **OVERWRITES `chosen_direction` at :497.** `_derive_pre_direction`
(orch ~4396-4459, the count+tiebreak+`neutral_default_long`) only **seeds the pre-scoring gates** —
its verdict is discarded before any post-scoring consumer reads it.

**Consequence:** a rewrite confined to `_derive_pre_direction` is a **silent no-op.** Any direction
rewrite MUST touch `confluence_service.py:186-497` in the same diff. (The single-threaded code read
that produced the earlier description missed the confluence_service winner-selection layer; the
multi-agent sweep caught it. Lesson: verify the AUTHORITATIVE writer, not the first writer.)

## Where the long-bias actually lives (revised)
1. Winner-selection ladder `confluence_service.py:216-494` — "never abstain, always pick a side"
   heuristics (range_reversion, elite_score, score_winner_below_gate, regime-trend fallback).
2. Regime double/triple-count in scoring factors — Regime Alignment (w0.08) + HTF Composite
   (w0.15, dominant) + BTC Impulse (w0.05) all re-apply the regime prior.
3. `neutral_default_long` (orch:4458-4459) — real but minor (only seeds gates).

## Blast radius (if Stage-1 emits ABSTAIN/None or a conviction score)
- **Silent-LONG landmines (worst):** 8 sites `.get("chosen_direction","LONG")`
  (orch 1901,2149,2240,2300,2588,2828,2944,3558) coerce ABSTAIN→phantom LONG. No crash, wrong trade.
- **Hard crash:** mass-conservation assert orch:1731-1735 AssertionErrors the scan loop on any new
  `pre_dir_tie_break` value — must be fixed FIRST.
- **Loud breaks:** scorer.py:129 `direction.lower()` and planner_service.py:254-255 throw on None
  (planner also silently builds SHORT on a non-"long" string sentinel).
- **Clean None-landing already exists:** orch:2308-2323 (`direction_unresolved`), entry-zone depth
  gate planner_service.py:290-292, cascade `if plan:` orch:3614, reason-mask fix 881e4ef.

## What to RETIRE, not just add (≥4 counter-trend authorities today)
- scorer **Gate 2 Regime Alignment** (scorer.py:189-296) — tautology under with-trend-only.
- confluence **counter-HTF penalty block** (confluence_service.py:535-701, −5/−10/−15/−20 + hard
  block) — ALREADY an asymmetric counter-trend bar requiring sweep/CHoCH/OB; the proposed rewrite
  duplicates it. Strongest consolidation candidate.
- bot **`regime_counter_trend` full-block** (paper_trading_service.py:2124-2137) — redundant.
  **KEEP the half-size scalp branch (:2152-2173, size_modifier*=0.5)** — tuned, exists nowhere else.
- count→tiebreak→`quality_override`→conflict-flip chain (orch:1677-1830, _apply_quality_override
  4514-4567) — a conviction score subsumes it.
- the winner-selection ladder's never-abstain heuristics (confluence_service.py:216-494).
- `directional_cap` — NOT redundant (orthogonal batch-correlation guard), keep.
**Conflict if you add-without-retiring:** an overwatch sweep+CHoCH counter-trend LONG admitted by a
new Stage-1 gets silently killed by Gate 2's strict else-branch (scorer.py:284-296) — split authority.

## Two paths
- **Path A — with-trend-only gate (SIMPLE):** one pre-Stage-1 gate abstaining counter-regime
  direction; rides existing `ConflictingDirectionsException`→`direction_unresolved` path; NO scoring
  weight change (no §15 trip). SMALL blast radius. Does NOT touch confluence_service.py:186-497.
- **Path B — full conviction+abstain (FULL):** rewrite confluence_service.py:186-497, de-weight the
  regime double-counts (§15 baseline + symmetry-guard mandatory), retire the redundant authorities,
  add `conviction_score` to telemetry/journal (re-baseline), build a "confirmed reversal" composite,
  add per-symbol trend hysteresis, resolve 4H-vs-daily scope. LARGE: 6 stages, 4 contract breaks,
  invalidates min_confluence_score tuning.

## RECOMMENDED SEQUENCE (audit's honest verdict: gate + backtest first, do NOT rewrite first)
- **Step 0 (read-only backtest):** from the `2026-05-29__count_tie_break_flip_cohort_baseline`
  cohort, measure counter-trend + neutral-tie trades' realized PnL + the future abstain population
  (4H-trend sideways/None rate). Decides whether abstaining removes edge. Bot has NO demonstrated
  edge — can't set abstain thresholds without this (§15, §16-R5).
- **Step 1 (do regardless):** replace the 8 `.get("chosen_direction","LONG")` defaults with explicit
  None/ABSTAIN + loud rejection; guard planner_service.py:254. Standalone #2-RISKY correctness fix (§11).
- **Step 2:** ship Path A (with-trend-only) behind a config flag; extend the mass-conservation assert;
  route abstain through the existing rejection path; add `direction_abstain` reason bucket + ONE
  observability consumer (pre_dir_tie_break is a write-only blind spot today). Path A IS the experiment.
- **Step 3:** decide Path B from Step-0 + Step-2 data, only if counter-trend expectancy is provably
  negative AND volume survives. Rewrite confluence_service.py:186-497 + retire redundancies IN THE
  SAME DIFF; de-weight as a §15-baselined scoring change with symmetry-guard.
Triage: do NOT start Path B while Step 1 is open (#2 RISKY before #3 CORRECTNESS).

**Likely outcome:** the data probably supports "with-trend-only + backtest," not a conviction-model
rewrite — given no demonstrated edge and direction being the highest-risk path.
