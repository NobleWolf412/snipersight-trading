# 2026-06-16 — Regime→Strategy Router: design entry + V1/V2 verdict + edge reality

**Trigger:** Operator review of V1 (`snipersight-trading`) vs a ground-up rewrite V2 (`snipersightV2`,
delivered as a zip — not in this repo). Question evolved: "is the confluence scoring fundamentally
broken — salvage, reshape, or scrap for V2?" → "I want a bot that trades EVERY regime with a
different strategy per regime (trend → intraday with-trend + confirmation; sideways → range
strategy), under hard rules (no illiquid pairs, confirmation-based)."

**Method:** Multi-agent investigation (read-only). Outputs reconciled below. Line numbers are
as-of-investigation and may drift — confirm in code (Serena) before editing.

**Status:** DESIGN ONLY. No code changed. This entry is the authoritative capture so the work
survives context reset. Build order deferred to operator (see §9).

> ⚠️ **PARTIALLY SUPERSEDED — see §11 AUDIT (appended 2026-06-16).** A four-agent audit found a
> CONFIRMED measurement bug (regime is labeled at trade CLOSE, not entry) that poisons every
> per-regime cell, plus engine correctness bugs (P/D inversion, FVG under-grading). The §2 edge
> matrix is bug-contaminated and must be RE-MEASURED after the §11 bug-fix backlog clears. Verdicts
> in §0.2 / §0.4 / §0.5 are downgraded. Only the bug-independent claims (blended no-edge after fees;
> scorer demote-able at ~4 sites; no liquidity filter; regime-switching lag tax) still stand as
> written. Read §11 before acting on §0–§9.

---

## 0. TL;DR / VERDICTS

1. **Salvage V1, do not scrap to V2.** The confluence *scorer* is cleanly demote-able (gates trades
   at only 4 sites in ~3 files; the planner reads geometry, not the score). V2 is a Phase-0 scaffold
   (18/44 files stubs, no live path) whose *philosophy* we adopt but whose *code* we don't port.
2. **The confluence score is broken as an EDGE tool — proven by V1's own diagnostics**, not opinion:
   only 1 of 26 factors (VWAP) predicts outcomes; the blended strategy has no edge after taker fees.
   It is coherent engineering that scores noise. Demote it from a gate to logged-context.
3. **Direction/type are currently chosen by argmax-over-score** — structurally compelled to pick a
   side/type every scan. Replace with thesis (regime+structure, may return FLAT) + journal-earned
   regime→type lookup + a short stack of binary, edge-proven gates.
4. **The multi-regime router is the right architecture, but it is a framework to EARN edge per
   regime, not a set of strategies to switch on.** Validated edge exists in **1** regime×type cell;
   2 are proven losers; all UP and all true-SIDEWAYS regimes have ZERO clean data.
5. **"Sideways = scalp" is refuted by our own data** (down_compressed × scalp = −1.06/t net, n=73).
   Ranging markets need a mean-reversion-at-boundary strategy, earned in paper — not an assumed scalp.
6. **Regime switching has a structural "lag tax"** that kills naive implementations (peer-reviewed):
   a plain classifier's edge drops below buy-and-hold at a 5-day detection delay. Mandatory
   guardrails: persistence/hysteresis, no-trade/size-down at transitions, Deflated-Sharpe per cell,
   walk-forward on filtered (not smoothed) labels.
7. **Biggest edge-independent gap = the rule the operator named first: there is NO liquidity filter.**
   V1 excludes stablecoins + stale symbols + spot-when-leveraged, but has no min-volume / OI / spread
   cap. "Don't trade illiquid pairs" is currently unenforced.

---

## 1. V1 vs V2 — what they are

| | V1 (`snipersight-trading`) | V2 (`snipersightV2`) |
|---|---|---|
| Python files | 417 | 44 |
| Test files | 134 | 4 (26 tests, all pass) |
| Frontend | 315 JS/TS files | none |
| Posture | full-stack signal app | edge-first engine, Phase-0 scaffold |
| Scoring | 26-factor weighted confluence → 0–100 → gate | **none — "binary gates, never weighted scores" (`strategies/base.py`)** |
| Self-assessment | — | README: "First principles (from **v1's failure**)" |

V2's `EDGE_AUDIT.md` reaches a **"Phase-0 no-edge verdict"** and flays its *own* gate (3 ways it
flatters paper vs live). V2 = correct architecture + intellectual honesty, but embryonic. **Adopt V2's
discipline (edge gate component #1; binary gates not scores; shared "SACRED" cost model; net-of-fee
everywhere), not V2's code.**

---

## 2. Edge reality — the per-regime coverage matrix

Source: V1's own `trade_journal.jsonl` via `edge_significance.py` / `edge_by_regime.py`, captured in
`decisions/2026-06-14__edge-research-scalp-pocket-vs-swing-drag.md` and `2026-06-06__edge-after-fees-verdict.md`.
(Journal not present in this cloud clone — `backend/cache/` is gitignored; re-derive on the operator's box.)

Net-of-fees at Phemex taker 0.06%/side, post-clamp window (n=349):

| regime | type | n | win% | NET/t | net total | Classification |
|---|---|---|---|---|---|---|
| down_normal | **scalp** | 58 | 53% | **+6.42** | +372.6 | **PROVEN-POSITIVE (only one)** |
| down_normal | intraday | 12 | 42% | +4.23 | +50.7 | NO-DATA (n too small) |
| down_compressed | intraday | 10 | 60% | +0.93 | +9.3 | NO-DATA (n too small) |
| down_compressed | **scalp** | 73 | 52% | **−1.06** | −77.7 | **PROVEN-NEGATIVE** |
| down_normal | **swing** | 46 | 46% | **−8.32** | −382.8 | **PROVEN-NEGATIVE** |
| all UP regimes | * | 0 | — | — | — | NO DATA (pre-clamp = confounded) |
| genuine SIDEWAYS | * | 0 | — | — | — | NO DATA (bot idles in chop) |

Blended verdict (n=142, 20k bootstrap): gross +0.43 [−0.66,+1.54] P=78%; at-taker −0.14 P=41%.
**Breakeven 0.045%/side < taker 0.06% → blended net-negative.** Full history n=292: P(edge>0)=1%.

Factor efficacy (`factor_contribution`, n=190 clean): **only VWAP Alignment (r=+0.21) predicts;
25 of 26 factors at/below noise.** Confluence score is undifferentiated w.r.t. outcomes.

**One-line:** validated edge in 1 cell; flying blind everywhere else; entire clean history is
down_* tape, so no cross-regime comparison is even possible yet.

---

## 3. Adversarial verdict (skeptic, different prior) — CHALLENGE, leaning REJECT for sizing

Read 7 decision logs. Key points (all sourced from the build's own files):

- **The +6.42 pocket is likely a multiple-comparisons artifact.** 6+ regime×type cells searched, one
  winner at ~1.5–2σ, no Bonferroni/FDR correction. `edge_by_regime.py`'s own header says post-clamp
  data spans only one regime → "regime-conditional edge" is **unfalsifiable on current data.**
- **Maker execution (the net-positive lever) likely adverse-selects.** Resting limits fill when price
  ticks *into* them (the reversal = loser); winners gap away. +6.42 was measured on snap-taker fills
  that took both sides. The build's own `2026-06-06__maker-execution-experiment-design.md` predicts
  maker won't rescue net.
- **Regime-flip top/bottom-picking:** bot busiest when downtrend most extended (near the bottom),
  where the detector lags hardest and "with-trend only" shorts the reversal. The swing-cut forensic
  found 41/44 swings were shorts in the bottom 20% of range.

**Required before the edge claim is load-bearing:** (1) multiple-comparisons-corrected significance +
forward/OOS; (2) maker fill-rate / adverse-selection experiment (GATE 1) FIRST; (3) instrument
trades-within-N-bars-of-a-flip + fix `regime=None` telemetry. **Do now (reversible, edge-independent):
cut swing (done), remove the cascade type-bonus that prefers the loser.**

---

## 4. Coupling / blast radius — the scorer is cleanly demote-able

`total_score`/`confidence_score`/`min_confluence_score` GATES or RANKS at only **4 live sites**:

1. Orchestrator gate — `orchestrator.py:2162-2165` (`score_rounded < threshold_rounded`).
2. Cascade type-argmax — `orchestrator.py:3469` (`_CASCADE_TYPE_BONUS`), `3640-3644` (effective),
   `3677` (max).
3. Direction decider — `confluence_service.py:40-77` `resolve_directional_tie` (+ non-tie
   `bullish > bearish` in `score()`); sets `chosen_direction` at `:497`.
4. **Bot's OWN second gate — `paper_trading_service.py:2277-2331`** (easy to miss; demoting only the
   orchestrator gate leaves the bot still score-gating).

Plus scorer's tier/`setup_state` labelers (`scorer.py:3211-3218, 3304-3312`) — labels, not trade gates.

**Everything else (~50 consumers) is display/telemetry/persist OR geometry.** The entire planner
(`entry_engine.py`, `risk_engine.py`) reads breakdown GEOMETRY (`htf_aligned`,
`nearest_htf_level_type`, `htf_proximity_atr`), NOT the score → survives untouched **as long as the
`ConfluenceBreakdown` object keeps being computed and `chosen_direction` keeps being set.**

Catches: (a) the second bot gate above; (b) `conviction_class`/`confidence_score` feed the ML
training set (`feature_extractor.py`, `position_manager.py:426`) → decoupling score from gating
silently shifts the training distribution; version/document it. (c) Pre-existing contract DRIFT
(baseline 103 routes vs 67 now; `trade_journal.jsonl` removed) unrelated to this work — rebaseline
via `/contract-check` before landing anything.

**Verdict: salvage, not rewrite — 2-3 files for the decision logic, keep the breakdown computing.**

---

## 5. Regime detector — statically SOUND (with a caveat)

- **Percentage-ATR standing fix holds:** `regime_detector.py:735` `atr_pct=(atr/price)*100`; thresholds
  2.5/5.0/7.0/9.5% calibrated off BTC daily baseline. ✅
- States: 5 trend × 4 vol; composite `{trend}_{vol}` (e.g. `down_normal`). The `_compressed`
  monoculture lexical-sort bug is **already fixed** (`regime_detector.py:43-45`, real-minutes TF select).
- `regime=None` since 2026-06-13 is a **telemetry gap, not a computation gap** — regime IS computed
  (`orchestrator.py:443`) and in `rejection_summary`, just never passed into `create_scan_completed_event()`.
  Fix: add `regime_label` param to that event.
- `down_normal` = bearish swing structure + ATR% ∈ [2.5, 5.0).

**Caveat:** this is a static code read, not empirical — the live label *distribution* is unmeasured
(`telemetry.db` empty) and **lag-at-flips is untested**. Sound enough to be the primary selector;
the lag risk (see §6) must be instrumented before it carries real capital.

---

## 6. Canonical regime→strategy research (the anti-overfitting anchor)

**The hardest empirical result:** a plain regime classifier's edge does NOT survive realistic
detection lag — at a 5-day delay HMM Sharpe (0.25) drops *below* buy-and-hold (0.30); a
persistence-penalized Statistical Jump Model holds 0.38 and cuts turnover 141%→44%
*(Shu/Mulvey et al. 2024, peer-reviewed)*. Trying many regime/strategy combos and keeping the best
**drives expected OOS returns negative**, not to zero *(Bailey/López de Prado, AMS 2014; Deflated
Sharpe; PBO)*.

**Mandatory guardrails (convergent across academic + institutional + practitioner):**
1. **Persistence + hysteresis** — never switch on a 1-bar flip; asymmetric enter/exit thresholds.
2. **No-trade / size-down at transitions** — boundaries are where the literature says most money dies.
3. **Per-cell edge gate with Deflated Sharpe** — corrected for #cells tried; proven cells trade,
   must-earn cells run shadow/paper.
4. **Walk-forward on FILTERED (live-lagged) labels, never smoothed** — smoothed = hidden look-ahead.
5. **Anchor to economically meaningful structure** (trend persistence, range mean-reversion), not
   data-mined pockets.

**Crypto-specific modifiers:**
- Momentum→reversal flips at **~1 month** (vs equities ~12mo) *(Dobrynskaya)* — regime polarity is
  **horizon-dependent**: daily = reversal regime; multi-week = momentum/trend regime. Equity-calibrated
  windows are too long.
- **Time-series momentum survives costs; cross-sectional ranking doesn't** *(Han/Kang/Ryu)* — trend
  on the asset's own series, not relative-rank baskets. (V2's `trend_momentum` is the right primitive.)
- **Funding rate = confluence MODIFIER, not a gate** — directionally real as crowding/reversal signal
  but never a standalone trigger (stays extreme through trends; contaminated by carry demand).
- **Liquidation cascades are long-skewed and thin-liquidity-driven** → reinforces the liquidity floor;
  treat breakout-into-thin-book differently by direction.
- Weekend = thinner book, possibly stronger short-horizon alt momentum (single-source, verify).

(Confidence tags: lag tax / overfitting math / filtered-vs-smoothed = WELL-ESTABLISHED. Exact lag
magnitudes, transition-is-worst framing, funding-predicts-reversal, weekend momentum = WEAK/EMERGING.)

---

## 7. What V1 already has vs what's missing

**Already built (regime-aware):** `regime_policies.py` (per-regime sizing/confluence/RR adjustments);
`MODE_REGIME_THRESHOLDS` (per-profile ADX); Gate-2 regime alignment (hard-blocks counter-trend per
regime, CHoCH/cycle-low exceptions); conflict-density per mode; sweep-confirmation-level per mode.

**Confirmation toolbox (built, but only VWAP is edge-proven):** BOS, CHoCH, OB, FVG, liquidity sweep,
kill-zone, VWAP reclaim, retest, divergence, RSI-fade (70/30), MACD veto, institutional sequence,
volume acceleration, MTF/HTF composite, close momentum, multi-close, cycle/WCL/DCL.

**Rules — confirmation gates BUILT, liquidity MISSING:**
- Built: 4 hard pre-scoring gates (structural anchor → regime alignment → BTC impulse → conflict
  density); critical-TF, cooldown, data-completeness; portfolio risk caps (max positions, asset/
  correlation exposure, daily/weekly loss halts); R:R-by-regime; adaptive stagnation holds.
- **Missing (the operator's #1 ask):** min-volume / OI / spread cap / market-cap floor. "All symbols
  pass if they fetch data." Also missing: spread-cap-at-entry, funding modifier, session-liquidity filter.

**Missing layer:** dynamic regime→strategy SELECTION. Modes (OVERWATCH/STRIKE/SURGICAL/STEALTH) are
static + operator-picked; regime is dynamic. They're conflated. Need a new `RegimeStrategyRouter`
ABOVE modes that maps detected-regime → StrategyBundle {confirmations · trade type · rule overrides}.

---

## 8. The design — RegimeStrategyRouter

```
detect regime ──(persistence + hysteresis; FLAT during transitions)──▶ RegimeStrategyRouter
  └─▶ StrategyBundle { which confirmations to require · trade type · rule overrides }
       └─▶ universal RULES layer (liquidity floor, spread cap, confirmation gates, risk caps)
            └─▶ existing planner geometry (entry/stop/RR) ──▶ size (vol-target) ──▶ maker fill ──▶ place
```

- **Host:** new selection layer on V1's machinery (do NOT port V2's skeleton; its 3-state regime is
  too coarse, its strategies 0% wired). Adopt V2's *pluggable strategy → intent* philosophy.
- **Each regime cell tagged** PROVEN-POSITIVE (trades live) / PROVEN-NEGATIVE (never) / MUST-EARN
  (shadow→paper→Deflated-Sharpe gate→live). Today: 1 proven, 2 negative, rest must-earn.
- **Direction** = thesis from regime+structure (returns LONG/SHORT/NONE), replacing
  `resolve_directional_tie` argmax. **Type** = journal-earned regime→type lookup, replacing
  `_CASCADE_TYPE_BONUS`. **Admission** = short binary gate stack, replacing `min_confluence_score`.
- **Confluence breakdown keeps computing** (telemetry/research), no longer gates.
- **Strategy primitives crypto-tuned:** trend = TS-momentum + with-trend pullback + confirmation,
  multi-week-ish window; range = mean-reversion at boundary (fade extreme WITH confirmation), NOT
  "scalp the chop"; funding = modifier not gate.

**Operator's two mappings, judged:** "trend → intraday with-trend + confirmation" = structurally sound
(trend persistence is real; our 1 proven cell is a trend cell) — UP mirror must be earned. "Sideways →
scalp" = refuted by our data + literature; sideways gets a mean-reversion strategy, earned in paper.

---

## 9. Build order — options (operator decides)

**Edge-independent, safe now (no approval, reversible):**
- **A. Liquidity + rules layer** — min-volume/OI floor, spread-vs-ATR cap, funding-as-modifier. The
  #1 gap; pure capital protection. Smallest, highest-certainty.
- **B. Remove `_CASCADE_TYPE_BONUS`** (prefers the proven loser); fix `regime=None` telemetry.
- **C. Router scaffold (shadow/default-off)** — selection layer + StrategyBundle + persistence/
  hysteresis + no-trade-at-transitions. A framework, not an edge claim.

**Must be earned before sizing capital:**
- **D. Per-cell validation harness** — shadow→paper + Deflated-Sharpe edge gate; start with the
  UP-trend mirror of the proven down_normal-scalp cell, crypto-tuned windows.
- Maker GATE 1 (fill-rate / adverse-selection) BEFORE assuming maker rescues net.

**Pre-flight for any code:** Plan agent + blast-radius + symmetry-guard (touches scoring/direction) +
contract rebaseline. Live STEALTH decision changes need explicit operator approval + a decisions entry.

---

## 10. Open questions / VERIFY-NEXT
1. Re-derive the +6.42 pocket with a multiple-comparisons correction (Deflated Sharpe) — is it edge
   or noise? Run forward/OOS before sizing.
2. Maker fill-rate experiment: do winners actually fill, or only losers? (Build's own doc predicts
   adverse selection eats the fee savings.)
3. Measure the live regime-label distribution + trades-within-N-bars-of-a-flip once telemetry is fixed.
4. Restore/locate `trade_journal.jsonl` on the operator's box to re-run `edge_by_regime` as clean
   non-down trades accumulate.

**Source decision logs:** `2026-06-06__edge-after-fees-verdict.md`,
`2026-06-14__edge-research-scalp-pocket-vs-swing-drag.md`,
`2026-06-06__maker-execution-experiment-design.md`,
`2026-06-14__cut-swing-tier-from-stealth-cascade.md`,
`2026-05-31__cascade-scalp-monoculture-regime-compressed-saturation.md`,
`2026-06-13__pd-factor-inverted-in-trends-finding.md`.

---

## 11. AUDIT (2026-06-16) — four-agent review: the lens was dirty

Operator challenge: "incomplete logs/testing are not law; coding bugs may have caused false
readings; nail the fundamentals bug-free, THEN test." Four read-only agents audited this doc:
(1) trader-lens strategy, (2) measurement-integrity bug hunt, (3) engine-fundamentals correctness,
(4) document claim-by-claim validity. The challenge was correct. Findings below SUPERSEDE the
overclaimed parts of §0–§9.

### 11.1 SMOKING GUN — regime is labeled at trade CLOSE, not entry (CONFIRMED)
The journal `regime` field — the bucketing key for the entire §2 matrix — is written from fields
that are OVERWRITTEN every scan with the live regime:
- entry regime captured correctly at `position_manager.py:423-424`, then
- clobbered each cycle by `paper_trading_service.py:2770-2771` (`_update_position_regimes`), then
- persisted at close as the trade's `regime` (`:3163`) and `regime_trend_at_entry` (`:3173` — the
  "at_entry" name is a lie; it reads the clobbered field).

So every cohort is bucketed by the regime present when the position CLOSED, not at entry/held-through.
The `down_normal` vs `down_compressed` split (the exact `normal`↔`compressed` band separating the
+6.42 winner from the −1.06 loser) is precisely what this bug scrambles; the two scalp cells leak
into each other. **This invalidates the regime axis of §2.**

### 11.2 Per-number trust verdicts (measurement-integrity audit)
| Number | Verdict | Defect |
|---|---|---|
| +6.42 down_normal scalp | **LIKELY-ARTIFACT** | regime mis-bucketing (§11.1) + uncorrected multiple-comparisons + n=58 |
| −1.06 down_compressed scalp | **SUSPECT** | other side of the same scrambled band; cells leak |
| −8.32 down_normal swing | **SUSPECT magnitude / safe direction** | 48h holds → worst mis-bucketing; funding-omission keeps "swing loses" robust |
| "1 of 26 factors predict" | **SUSPECT** | `factor_contribution` can't separate a DEAD factor from a wired-BACKWARDS one (P/D proven inverted) |
| "no edge after fees, BLENDED" | **TRUSTWORTHY** | independent of the regime label; P(edge>0)=1% full history; stands regardless of all other bugs |

**Clean (trustworthy):** fee/PnL plumbing (journal pnl is gross, fee modeled once, slippage in
prices, no double-count); dedup (only `result=="executed"` matched; journal deduped); no look-ahead.
**Correction to §3:** V1 has NO `net=max(net,-0.999)` liquidation clamp — that was V2's backtester
(`EDGE_AUDIT.md` C2). V1's "clamp" is only the 2026-05-31 ship-date era boundary (a survivorship/era
split, real confound but not a per-trade distortion).

### 11.3 Engine correctness bugs (independent of the data — fundamentals not yet bug-free)
- **P/D inverted in trends (CONFIRMED, known):** `scorer.py:2870-2905` — mean-reversion logic applied
  in trends penalizes valid continuation; no arbitration with the BOS/structure factor.
- **FVG under-grading (CONFIRMED, new):** `scorer.py:1023-1043` — grade computed with entry-TF ATR
  before the FVG's own-TF ATR lookup; HTF FVGs graded too low → the FVG factor LOOKS like noise.
- **Regime ATR% TF-calibration (LIKELY):** `regime_detector.py:751-758` — daily-calibrated bands may
  apply to a weekly TF if that's the highest present → regime mislabel.
- **Cycle-bypass LONG-only (CONFIRMED, intentional):** longs get two counter-trend pathways
  (WCL/DCL + CHoCH), shorts one (CHoCH). Documented asymmetry, not silent, but a real directional bias.
- Lower-confidence flags (RSI gradient symmetry, MACD profile-sync, conflict-density staleness):
  largely self-resolved as "appears OK / needs a look." This bug list itself needs code confirmation
  before any fix lands.

### 11.4 Claims DOWNGRADED (document-validity audit)
- §0.2 / §2 "scorer is noise; only 1/26 predicts" → **WEAKEN→RETRACT.** Cannot distinguish "noise"
  from "buggy" while P/D is inverted and FVG is under-graded, on n≈190 single-regime data. The
  demote-scoring ACTION may still be right; the JUSTIFICATION is premature.
- §0.4 / §8 "validated edge in 1 cell; cells tagged PROVEN/NEGATIVE" → **WEAKEN.** §3 of this same
  doc calls that cell "likely a multiple-comparisons artifact." Re-tag every cell **MUST-EARN** until
  re-measured. No cell is PROVEN.
- §0.5 "sideways=scalp REFUTED by our data" → **RETRACT.** `down_compressed` is a trend×vol composite
  on a ~98%-bug-driven label — NOT sideways; the doc itself says zero true-sideways data exists.
  Category error. "Sideways → mean-reversion" stays a *literature-led hypothesis*, not a data verdict.
- §3 / §9B "swing is the proven loser; cascade prefers the loser" → **WEAKEN.** Right ACTION (don't
  let score pick type; edge-independent), bug-confounded REASON (−8.32 produced under live P/D bug).
- §5 "regime bug already fixed" → **WEAKEN.** Fix-in-code ≠ clean-data: the journal §2 partitions
  was logged under the buggy labeler; history must be re-labeled or discarded.
- Internal-consistency note: "n=349" is total journal rows; actual tests ran on n=142/199/190/123,
  per-cell n=10–73. Report the n entering each statistic.

### 11.5 Strategy-fundamentals revisions (trader-lens audit — separate from bugs)
Even bug-free, the strategy REPRESENTATION is wrong:
1. **SMC edge is a SEQUENCE, not a scored bag.** sweep → CHoCH/BOS shift → return to OB/FVG origin at
   discount → retest+displacement. A confluence score (even demoted to binary gates in arbitrary
   order) destroys the temporal/causal ordering that IS the edge. Build a **per-setup state machine**,
   not a confluence counter. There is no first-class "setup" object today.
2. **"With-trend only, flat in chop" (§4) is WRONG as a hard rule** — it bans the two highest-EV SMC
   setups (sweep-reversal, HTF-extreme reclaim). `liquidity_sweeps.py` is literally a reversal engine.
   Replace with: with-trend continuation in the pullback zone, OR confirmed-reversal at an HTF
   liquidity extreme, FLAT in the middle. The "41/44 shorts in the bottom 20%" is the bill for the
   missing **position-in-range / exhaustion** sub-state (not primarily detector lag).
3. **Confirmation must be per-SETUP, not per-mode.** Same volume/engulfing bar = continuation in a
   trend, breakout-risk at a range boundary. Regime-blind confirmation green-lights a fade on the bar
   the range is breaking.
4. **Trade management is the biggest silent gap.** Stops = setup-geometry (beyond the sweep wick / OB
   invalidation), NOT ATR multiples. Targets = opposing liquidity pool (`detect_equal_highs_lows`),
   NOT fixed R. Add partials. Restructure around the fee floor (maker + liquidity-pool targets so the
   average winner clears taker).
5. **Reconcile "flat at transitions" (§6) with reversals:** flat for *continuation*, ARMED for
   *confirmed sweep-reversal* — reversals happen AT transitions; don't cede turning points twice.
6. Prefer BOS-linked OBs (`detect_obs_from_bos`) as triggers; treat generic wick-OBs as context.

### 11.6 BUG-FIX-FIRST BACKLOG (hard gate — nothing about edge is testable until these clear)
Ordered. Each fix lands with a diagnostic that proves it (CLAUDE.md §13). Touches scoring/regime/
execution → symmetry-guard + audit + blast-radius before any commit; touches paper path → operator
review.
1. **[BROKEN] Entry-regime snapshot.** Stop clobbering the entry regime; write immutable entry fields
   at `open_position`, journal reads those (`paper_trading_service.py:2770-2771`, `:3163`, `:3173`).
   THE fix that decides whether the regime router has any trustworthy data.
2. **[CORRECTNESS] P/D trend/range conditioning + BOS arbitration** (`scorer.py:2870-2905`).
3. **[CORRECTNESS] FVG grade after TF-aware ATR** (`scorer.py:1023-1043`).
4. **[FRICTION] Restore regime telemetry** — `regime_label` into `create_scan_completed_event`
   (`orchestrator.py` ~716) — needed to VERIFY fix #1 live.
5. **[CORRECTNESS] Re-rank factors after sign-fixes** (signed/conditional efficacy mode in
   `factor_contribution.py`), then re-judge "which factors predict."
6. **[VERIFY] Confirm regime ATR% bands match the TF actually used** (`regime_detector.py:751-758`).
7. **THEN, not before:** re-label/re-bucket the journal, re-run `edge_by_regime` + `edge_significance`
   with per-cell bootstrap CIs + a multiple-comparisons (Deflated-Sharpe/FDR) correction. Only now are
   any regime-conditional edge claims believable.

### 11.7 Revised "what we KNOW vs ASSUMED"
**KNOW (bug-independent, survives the audit):** the strategy has **no edge after fees, blended**
(P(edge>0)=1% full history — TRUSTWORTHY). The confluence scorer is structurally **demote-able** at
~4 code sites; the planner reads geometry not score. There is **no liquidity filter** (real capital
gap). The regime-switching **lag tax / Deflated-Sharpe discipline** holds (external peer-reviewed).
The entire record is **one bearish tape** → no cross-regime claim is possible. SMC edge is a
**sequence**, and the current representation (and "with-trend only" rule) is wrong even bug-free.

**ASSUMED (now retracted/suspended pending §11.6):** that any specific regime cell is proven
(+6.42 LIKELY-ARTIFACT; −1.06/−8.32 SUSPECT — bucketed by the wrong clock). That the factors are
"noise" (≥2 are provably mis-scored). That "sideways=scalp" is refuted by data (no sideways data
exists; down_compressed isn't sideways).

**One line:** we have ONE bug-contaminated bearish-tape sample — enough to justify reversible,
edge-independent moves (liquidity floor; demote score from gate to context; kill the score-driven
type bonus; scaffold the router off; fix the bugs in §11.6) — but NOT enough to assert any regime
cell as proven or refuted until the entry-regime + P/D + FVG bugs are fixed and every cohort is
re-measured net-of-fees with per-cell CIs and a multiple-comparisons correction. **Fundamentals
bug-free FIRST, then test — the operator was right.**
