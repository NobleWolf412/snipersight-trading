# SniperSight — Thread Ledger (living status board)

The single place that answers "what have we found, and where does each thing stand?"
Decisions/ holds the deep per-topic write-ups; memory holds one-liners; the debrief
re-surfaces live flags. THIS file is the kanban: every thread, its status, and the ONE
next action — so nothing gets validated-then-dropped when we jump to the next problem.

**Update rule:** when a thread changes state, edit its row here in the SAME commit as the
work. Status: 🔴 OPEN · 🟡 IN-VALIDATION (measuring before fixing) · 🟠 NEEDS-TRACE
(mechanism unconfirmed) · 🟢 SHIPPED+VERIFIED · ⚫ REFUTED/CLOSED.
Tier = CLAUDE.md triage (1 BROKEN · 2 RISKY · 3 CORRECTNESS · 4 FRICTION · 5 NICE).

Last updated: 2026-06-06 (after session f193dd54, n=29; clean post-clamp corpus now n=138).

---

## 🔴 OPEN — found, validated or clear, NOT yet fixed (the "abc we left behind")

| ID | Thread | Tier | Evidence | NEXT ACTION |
|----|--------|------|----------|-------------|
| T1 | **MACD Veto "ANTI" was a FALSE ALARM (confound) — DO NOT remove** | 3 | Investigated 2026-06-05: r_out −0.15 ALL-data → **+0.02 post-clamp** (confound, not anti-predictive). And it's a binary VETO GATE (scorer.py:2790-2799 score 0/100; :3206 score<50 hard-blocks APEX/A), so among taken trades it's 100±0 by construction — r_out is range-restricted/uninterpretable, not "dead." Removing the gate would let MACD-opposed trades through with zero evidence it helps. **Keep it.** | **DIAGNOSTIC FIX SHIPPED:** factor_contribution now judges ANTI/KEEP on the CLEAN post-clamp window (CLAMP_DATE 2026-05-31), labels VETO_FACTORS as "GATE (r_out not interpretable)", and flags CONFOUND when full-history signal vanishes on clean data. MACD Veto now correctly reads GATE (not ANTI). Side-effect: de-confounding surfaced two clean-ANTI candidates the full-history view had MASKED — now tracked as **T10**. |
| T2 | **Inert/constant factors** — Weekly StochRSI always 50; Institutional Sequence / Multi-Candle / Nested OB pegged near-max (std≈0). ~20 weighted pts of no-discrimination padding inflating every score | 4 | factor_contribution.py (4–6 "dead" each run) | Trim/zero-weight after a tune-confluence-weights pass; re-baseline + symmetry-guard + §16. Hygiene, not edge. NOT started. |
| T3 | **SMC TF/mode routing — 5 open defects** (~~F1~~ ✅ SHIPPED; F2/F3 intraday wide-stop pathway [RISKY]; F4/F5 correctness; F6 friction) | 2 | decisions/2026-05-31__smc-tf-mode-routing-audit.md | **F1 FIXED** (track_pool_sweeps per-iteration reset — was NameError + stale-leak; symmetry-guard PASS / backend-integrity CLEAN / §16 green; test_track_pool_sweeps_reset.py). F2/F3 next (intraday wide-stop pathway). |
| T4 | **Cascade scalp monoculture** — bot trades ~93.5% scalp; global "compressed" regime saturation strips swing | 3 | orchestrator.py:2347-2358; memory project_cascade_scalp_monoculture | Instrument regime-band distribution before any gate tune. NOT started. |
| T5 | **Stops land inside SMC liquidity pools** (PWL/PDH/EQL) → systematically swept | 2 | memory project_stop_placement_pwl_proximity (deferred) | Audit risk_engine stop placement vs liquidity map. NOT started. |

## 🟡 IN-VALIDATION — measuring on clean data BEFORE writing any fix

| ID | Thread | Tier | Status | NEXT ACTION |
|----|--------|------|--------|-------------|
| T6 | **Entry-location / exhaustion ("dead-cat") signal** — score rates structure, blind to "entering at the spent extreme." Merges old T7. | 3 | **WEAKENING — FADED below the noise floor as data grew (2026-06-06).** Was exh_bb/loc_bb ±0.22 at n=111 (above the ±0.19 floor); at n=138 (after f193dd54 added +27 trades) it's ±0.16, BELOW the ±0.17 floor. The "strengthens with data" trend (0.19→0.20→0.21→0.22) REVERSED to 0.22→0.16. The credibility rested on it strengthening — that reversed. exh_vol popped +0.21 but wrong-signed (decel→better) = noise. The 3 motivating shorts losing was anecdote, not proof. **No longer a validated lead.** | DO NOT wire (instrumentation correctly deferred — dodged shipping noise). Keep measuring: if it keeps fading → refuted pile; if it re-firms clearly above a shrinking floor over several more sessions → reconsider. Demoted "about-to-ship" → weakening/unproven. |
| T7 | **Dead-cat detector exists but is deaf on the continuation side** — detect_pullback_setup (extension+volume-exhaustion+SMC) only ENABLES counter-trend; computes "extension favors opposite dir" then discards it for the with-trend short (pullback_detector.py:204 early-return). MERGED INTO T6 (same signal). | 3 | Root-caused this session. Live AVAX/XRP/APT shorted swept oversold support; pullback_prob only 0.465. **(a) DONE** — exhaustion proxies validated (see T6). | Wiring = T6 step 3. The fix is to feed the existing detector's output as a penalty, not to build a new detector. |
| T8 | **Edge after fees** — post-clamp the bot is ~breakeven GROSS; no factor predicts outcome beyond noise | strategic | factor_contribution best |r|≈0.15 vs noise ±0.12; direction cohorts breakeven. f193dd54 was +0.90/tr but carried by 3 trailing/target winners (38% win × 2.39 payoff = variance, not edge). | Keep measuring as sessions accumulate; this is the gate on whether the strategy is viable at all. |
| T10 | **Kill Zone Timing + Close Momentum read clean-ANTI** (high factor score → loses, on clean data) — surfaced by the T1 de-confound, now the most-persistent lead | 3 | HELD across 2 sessions where T6 faded: Kill Zone −0.24→−0.18, Close Momentum −0.19→−0.18 (n=138, vs ±0.17 floor — barely above, but not fading). | Keep measuring. OPEN QUESTION: real anti-signal (factor mis-wired/inverted) vs down-regime artifact (kill-zone timing in a one-directional market). If it holds above a shrinking floor → investigate the Kill Zone / Close Momentum scorer logic (touches scorer → symmetry-guard + §16); do NOT act on n=138 borderline alone. |

## 🟠 NEEDS-TRACE — found, mechanism unconfirmed (do NOT call it a bug yet)

_(none open)_

## 🟢 SHIPPED + VERIFIED (this session arc)

| ID | Thread | Refs | Verified by |
|----|--------|------|-------------|
| S1 | TP1 reachability clamp (wide-stop × 1.5R → unreachable TP1) | 99303ff | Live: febadc4a tp1_clamped=3/11, avg targets_hit 0.12→0.64 |
| S2 | Journal calc-geometry (stop branch / clamp / levels) | e6715f8 | Live: febadc4a rows carry stop_loss_rationale etc (was 0/247) |
| S3 | 8 silent-LONG `.get(chosen_direction,"LONG")` defaults → loud/UNKNOWN | 8233b21 | test_no_silent_long_default.py; live UNKNOWN rejections visible |
| S4 | **Stale bot-process / port-8001 zombie + Windows-broken `npm run kill`** (fuser→kill-port) | 3c78ec4 + killed PID 19108 | Fresh --reload backend 7:12pm; S1/S2/S3 only became live AFTER this |
| S5 | Direction-cohort backtest tooling | 819ade0 | — |
| S6 | factor_contribution + session_debrief FACTOR EDGE + entry_quality_probe | d4e1113 / 524b66c / 01677c3 | — |

## ⚫ REFUTED / CLOSED — investigated, disproven, correctly abandoned

| ID | Thread | Why closed |
|----|--------|-----------|
| R1 | **Stage-1 direction rewrite** (with-trend-only / conviction model) | Step-0 backtest: "with-trend bleeds" was ENTIRELY the wide-stop era; post-clamp both directions breakeven-noise. No losing-direction cohort to gate. decisions/2026-06-02 |
| R2 | **"Structural swing stops too wide" = the loss** | 1000FLOKI(−22) vs APT(+7) A/B: APT's stop was WIDER and won. Differentiator was entry location, not stop width. |
| R3 | **pullback_probability filter (−0.21)** | Collapses to −0.05 post-clamp — wide-stop-era confound (3rd instance of this trap). |
| R4 | **Redundant/multicollinear factors (HTF/regime/BTC triple-count)** | 0 factor pairs correlate ≥0.70 in data; a-priori claim refuted by factor_contribution. |
| R5 | **Entry-fill divergence / LIMIT SNAP is a bug or the dead-cat mechanism** (was T9) | NOT a bug: LIMIT SNAP (paper_trading_service.py:2261-2307) is by-design fill-assurance and PRESERVES risk $ (size recalc 2280-2290). snap_gap measured vs PnL on clean data (n=111) → r=+0.06 (within ±0.19 noise), big-snap trades marginally POSITIVE. Snap magnitude carries no signal; it is NOT the dead-cat mechanism (that's the band-extreme/location = T6, separable). Closed 2026-06-05. |

---

### The loop we're in (and why it's fine)
find → run bot → measure/validate → run bot → find next. Correct iteration, but it strands
"found-but-unfixed" threads (T1, T2, T3). This ledger is the backstop: **open threads don't
disappear just because we chased a deeper cause.** When a 🟡 validates, it becomes a fix task;
when a 🔴 is the highest open tier, it gets picked up before lower work (CLAUDE.md triage).
