# 2026-05-29 — Trading degradation root-cause: target geometry collapse (Tier 1.1 near_entry)

> **SUPERSEDED IN PART (2026-05-30):** the primary attribution below (Tier 1.1 near_entry as
> the root) is DEMOTED to a minor aggravator. Verified dominant driver is a **structure-finding
> success collapse (77%→43%) → regime-blind fixed-ATR fallback stop** widening stops ~3× →
> bigger losses AND unreachable TP1. See `2026-05-30__stop-distance-structure-collapse.md`.

**Type:** calibration / root-cause analysis (no code change yet — diagnosis on record before fix)
**Trigger:** operator reported "poor trading results lately." Forensic autopsy of `trade_journal.jsonl` (149 trades, sessions 2026-05-21 → 2026-05-29).
**Triage class:** #1 BROKEN — paper expectancy went from **+7.21/trade to −10.08/trade**.

## Inflection: 2026-05-24

Per-session win-rate / PnL has a clean break on 2026-05-24:

| Window | n | Win% | Avg win | Avg loss | Payoff (W/L) | Expectancy/trade |
|---|---|---|---|---|---|---|
| GOOD (≤05-23) | 44 | 70% | +11.37 | −2.72 | 4.19 | +7.21 |
| DEGRADED (≥05-24) | 105 | 37% | +19.44 | −27.52 | 0.71 | −10.08 |

Worst sessions: `2f35590b` (05-27, −538.75), `594165c2` (05-29, −410.88).
The break aligns exactly with the 2026-05-24 commit bundle: `1e0cbf8` (Tier 1.1 near_entry), `77eb256` (Tier 1.2 Gate-3 LONG bypass + STEALTH strong_down sizing), `8695c89` (Tier 2 enrichment).

## Root cause (confirmed): target geometry — TPs pushed out of reach

`1e0cbf8` moved the target generator anchor from `avg_entry` to `near_entry` in
`_calculate_targets` (backend/strategy/planner/risk_engine.py:2128-2461). It correctly
fixed a target-**strip** bug (targets landing between avg and near → executor stripped
them), but the side effect widened `risk_distance = |near_entry - stop|`, pushing every
TP further from the fill. Confirmed consequences in live journal data:

- avg `targets_hit` collapsed **0.34 → 0.13**
- stagnation exits **4 → 28** (4×)
- **61% of degraded trades (64/105) moved into profit, then still lost** (25 stagnation, 26 stop_loss, 4 direction_flip, 9 session_stopped)
- degraded no-target-hit trades had a *higher* median favorable excursion (0.60%) than good (0.40%) — price moved MORE in our favor yet TP was further away
- Example PEPE LONG: MFE +0.28%, stop 1.66% away, TP1 (1.8R) unreachable → round-tripped to stop

**Confluence/scoring is healthy** — signals scored 70–78 in `up_compressed`, gates passed
as designed, trade-type cascade iterated cleanly (Scalp/Day/Swing setups all observed).
The defect is downstream of confluence, in planner target geometry.

## Amplifiers

1. **Sizing not risk-normalized.** Stop-loss dollar losses: GOOD median −1.48 / stdev 4.07 /
   worst −5.72; DEGRADED median −22.77 / **stdev 47.23** / worst −124.32. Notional 48→7138
   (150× spread). Wide variable stops (ATR 0.77→1.14) turn each unreachable-TP loss
   catastrophic. (`77eb256` also bumped STEALTH `strong_down` sizing 1.1→1.2.)
2. **Gate-3 LONG bypass** (`77eb256`, scorer.py:336-371) — real but **secondary**. Initially
   suspected as prime cause; demoted by evidence: counter-BTC LONGs lost −462 (35% win) but
   *with-BTC* LONGs lost MORE (−784, 23% win), and LONGs into *rising* alt momentum were the
   worst cohort (24% win, −864). Which longs get admitted is not the main story — the entire
   LONG book exits badly regardless of admission path. Bypass nets ~−462 of the bleed.

## Calibration note (process)

Initial verdict named the Gate-3 LONG bypass as prime suspect at ~85% confidence on the
strength of the LONG/SHORT PnL asymmetry (LONG −1246 vs SHORT +188). Deeper cohort analysis
(direction × BTC velocity × alt velocity) overturned it: longs lose worst when entered WITH
upward momentum, which is a construction signature, not a gating/admission one. Lesson: the
direction-asymmetry headline invited a gating explanation; the favorable-then-lost rate
(61%) and targets_hit collapse were the decisive metrics. Pull the MFE/realized-R metrics
before anchoring on an admission-side hypothesis.

## Data-integrity flag (separate, lower priority)

`macro_state_at_entry='6'` (bare integer where a label belongs) on 17 degraded trades —
serialization bug, likely an enum index leaking instead of its name. Corrupts macro cohort
analysis; does not itself cause losses. Fix separately.

## Next action

Re-examine the Tier 1.1 `near_entry` target anchor against realized TP-hit rate. Do NOT
revert — the strip bug was real. Reconcile the generator so TP1 sits at honest fill-relative
distance WITHOUT drifting beyond the move the setup typically produces. risk_engine.py change
→ §17 Plan agent + symmetry-guard (LONG/SHORT geometry must stay mirrored) + §16 audit.
Plan drafted same day (see session). Diagnostic to add in the fix diff: per-plan realized-R
vs planned-R + TP1-reachability assertion, so a future reachability regression surfaces loud.

## CORRECTION (2026-05-29, post-commit f159766) — regime-key "fix" was a NO-OP

A first attempt (commit f159766) hypothesised a SECOND cause: that `_calculate_targets`
received the composite scan label `up_compressed`/`down_compressed` and that the
`_effective_regime == "compressed"` check let it fall through to 1.0× (no ladder
compression). **This was wrong.** The sole caller (`planner_service.py:403`) passes
`regime_label = get_atr_regime(...)`, and `get_atr_regime` (`regime_engine.py:19`) returns
the VOLATILITY regime ALREADY MAPPED to PlannerConfig keys (`compressed→calm`,
`volatile/chaotic→explosive`). So `regime_label` here is always one of
{calm,normal,elevated,explosive} — never a composite label. The original `== "compressed"`
was harmless dead code; the value was already `"calm"`, so compression fired correctly.
The substring change shipped in f159766 is therefore a **functional no-op** (none of the
mapped keys contain "compressed").

What survives from f159766: the **TP1-reachability diagnostic** (valid, kept) and the
substring line retained as an honest defensive guard (comment corrected in a follow-up).
The regime-key mechanism is **struck** as a cause. The single confirmed root cause remains
the Tier 1.1 `near_entry` anchor widening risk_distance. The real fix is still the
reachability clamp (Plan Option B), now with the corrected admission floor `min_rr=1.0` /
`target_min_rr_after_clip=1.2` (the Plan agent had assumed 1.5).

Calibration lesson (→ separate §19 entry `2026-05-29__regime-label-premise-miss.md`):
verify the DATA PATH (what value a parameter actually carries at the call site) before
asserting a mechanism. symmetry-guard + backend-integrity both PASSED the change because
they audited symmetry and blast-radius — not the truth of the premise. A premise about
"which label flows here" is a trace-the-caller check, and it must precede the fix, not
follow it.
