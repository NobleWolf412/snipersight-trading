# SniperSight — Thread Ledger (living status board)

The single place that answers "what have we found, and where does each thing stand?"
Decisions/ holds the deep per-topic write-ups; memory holds one-liners; the debrief
re-surfaces live flags. THIS file is the kanban: every thread, its status, and the ONE
next action — so nothing gets validated-then-dropped when we jump to the next problem.

**Update rule:** when a thread changes state, edit its row here in the SAME commit as the
work. Status: 🔴 OPEN · 🟡 IN-VALIDATION (measuring before fixing) · 🟠 NEEDS-TRACE
(mechanism unconfirmed) · 🟢 SHIPPED+VERIFIED · ⚫ REFUTED/CLOSED.
Tier = CLAUDE.md triage (1 BROKEN · 2 RISKY · 3 CORRECTNESS · 4 FRICTION · 5 NICE).

Last updated: 2026-06-05.

---

## 🔴 OPEN — found, validated or clear, NOT yet fixed (the "abc we left behind")

| ID | Thread | Tier | Evidence | NEXT ACTION |
|----|--------|------|----------|-------------|
| T1 | **MACD Veto is an ANTI-signal** — pegged 100, r_out −0.15/−0.16 vs PnL (scores high on losers) | 3 | factor_contribution.py corpus (237–247 trades) | Investigate scorer MACD veto logic — is it inverted / rewarding the wrong condition? Touches scorer.py → symmetry-guard + §16. NOT started. |
| T2 | **Inert/constant factors** — Weekly StochRSI always 50; Institutional Sequence / Multi-Candle / Nested OB pegged near-max (std≈0). ~20 weighted pts of no-discrimination padding inflating every score | 4 | factor_contribution.py (4–6 "dead" each run) | Trim/zero-weight after a tune-confluence-weights pass; re-baseline + symmetry-guard + §16. Hygiene, not edge. NOT started. |
| T3 | **SMC TF/mode routing — 6 open defects** (F1 liquidity_sweeps.py `swept`-before-assign NameError [RISKY]; F2/F3 intraday wide-stop pathway [RISKY]; F4/F5 correctness; F6 friction) | 2 | decisions/2026-05-31__smc-tf-mode-routing-audit.md | Fix F1 first (loud NameError). NOT started. |
| T4 | **Cascade scalp monoculture** — bot trades ~93.5% scalp; global "compressed" regime saturation strips swing | 3 | orchestrator.py:2347-2358; memory project_cascade_scalp_monoculture | Instrument regime-band distribution before any gate tune. NOT started. |
| T5 | **Stops land inside SMC liquidity pools** (PWL/PDH/EQL) → systematically swept | 2 | memory project_stop_placement_pwl_proximity (deferred) | Audit risk_engine stop placement vs liquidity map. NOT started. |

## 🟡 IN-VALIDATION — measuring on clean data BEFORE writing any fix

| ID | Thread | Tier | Status | NEXT ACTION |
|----|--------|------|--------|-------------|
| T6 | **Entry-location / exhaustion ("dead-cat") signal** — score rates structure, blind to "entering at the spent extreme." Merges old T7. | 3 | **VALIDATED (borderline, STRENGTHENING):** post-clamp n=111, exh_bb −0.22 / loc_bb +0.22 / EXH_composite −0.21 / exh_rsi −0.20 — 5 features now clear the ±0.19 floor AND beat every factor. Trend across re-runs 0.19→0.20→0.21→0.22 (strengthens with data; confounds faded). Direct hit: the 3 motivating shorts (AVAX/XRP/APT, session 89db3a85) ALL lost −2.86/−4.95/−3.99. Still modest (~5% var), proxies, session_stopped exits. | (1) **NEXT: instrument** — log real detect_pullback_setup inputs (extension_pct, volume_exhausted, "favors-opposite" flag) per signal (orchestrator/scorer → signal record). (2) Accumulate clean sessions. (3) If holds → wire SYMMETRIC entry penalty (not veto), flag + re-baseline + symmetry-guard + §16. |
| T7 | **Dead-cat detector exists but is deaf on the continuation side** — detect_pullback_setup (extension+volume-exhaustion+SMC) only ENABLES counter-trend; computes "extension favors opposite dir" then discards it for the with-trend short (pullback_detector.py:204 early-return). MERGED INTO T6 (same signal). | 3 | Root-caused this session. Live AVAX/XRP/APT shorted swept oversold support; pullback_prob only 0.465. **(a) DONE** — exhaustion proxies validated (see T6). | Wiring = T6 step 3. The fix is to feed the existing detector's output as a penalty, not to build a new detector. |
| T8 | **Edge after fees** — post-clamp the bot is ~breakeven GROSS; no factor predicts outcome beyond noise | strategic | factor_contribution best |r|≈0.15 vs noise ±0.12; direction cohorts breakeven | Keep measuring as sessions accumulate; this is the gate on whether the strategy is viable at all. |

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
