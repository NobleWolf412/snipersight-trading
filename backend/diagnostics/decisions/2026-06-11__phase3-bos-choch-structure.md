# 2026-06-11 — Phase 3: bos_choch.py structural fixes (3A/3B/3C)

SMC remediation Phase 3 (per `project_smc_scoring_remediation` tracker). Plan agent
output on record in-session; symmetry-guard + §16 audit verdicts pasted alongside the
commit. Only production file touched: `backend/strategy/smc/bos_choch.py`.

## 3A — CHoCH 4-swing conditions were garbled

`_detect_bos_choch_pattern` unpacked the chronological swing sequence
`[L1,H1,L2,H2]` with structure-assuming names (`ll, lh, hl, hh`) and got the CHoCH
relationships inverted:

- **Bullish CHoCH (old)**: required `hh > lh` — the NEWEST high above the OLDER high,
  which contradicts a prior-bearish structure — and broke the OLDER high (`lh`,
  timestamp index -3).
- **Bearish CHoCH (old)**: required `ll < hl < lh < hh` — that decodes to lower highs
  AND lower lows, i.e. a DOWNTREND, while claiming "reversal from prior bullish" —
  and broke the older low.

**Fix**: chronological unpack (`l1, h1, l2, h2` / `h1, l1, h2, l2`); CHoCH now
requires genuine opposite-direction prior structure (bullish: `h2 < h1 and l2 < l1`,
close > h2; bearish mirror) and breaks the MOST RECENT swing (index -1). Both BOS
branches were correct — provably pure-renamed (pinned by tests).

**Consequence**: 4swing modes (OVERWATCH, STEALTH) almost never emitted a valid
CHoCH; when one fired it carried a wrong level + timestamp into every consumer
(`reversal_detector` `_find_bullish/bearish_choch` — the T16 path; scorer's
`_score_structural_breaks` CHoCH base-60; `detect_obs_from_bos`, which consumes
CHoCHs too — it never filters `break_type`).

**KNOWN LIMITATION (flagged, not fixed)**: bullish CHoCH only detectable in the
H-ending shape `[-1,1,-1,1]`, bearish only in the L-ending shape. The alternate-shape
CHoCH (break before the final swing confirms) is not covered. Minimal fix-in-place
chosen; shape expansion is a measured follow-up.

## 3B — state machine: initial-trend look-ahead + ranging deadlock

- `_determine_initial_trend` compared `values[-1] > values[-2]` — the LAST two swings
  of the entire dataframe seeded the INITIAL trend (look-ahead; docstring said
  "first"). Fixed to `values[1] > values[0]`.
- An initial `"ranging"` trend deadlocked the scan: the loop only had
  uptrend/downtrend branches and trend was only mutated inside them → the whole scan
  silently emitted ZERO breaks. Fixed: a `ranging` branch resolves the trend on the
  first decisive break **without emitting it** (no prior trend exists to classify
  BOS-vs-CHoCH; defaulting one would be a silent directional bias — same class as
  `test_no_silent_long_default.py`). Resolution is logged at INFO.
- **DEFERRED (flagged in code)**: swing refs become usable at the swing's OWN index,
  but confirmation needs `swing_lookback` future candles — historical scans see
  breaks ~lookback candles earlier than live could. Fixing shifts every break
  timestamp in ALL modes and relocates every BOS-linked OB. Same deferral pattern as
  Phase 1B's `entry_engine .timestamp` note.

## 3C — BOS volume-reject used `continue` (state desync)

BOS volume rejection skipped the swing-ref update, so the state machine pretended the
break never happened and the same stale level re-fired on later candles (emitting
with a stale level once volume passed). Converted to the CHoCH-style `skip_signal`
pattern: signal gated, swing-ref advance unconditional. Exact mirror in both trend
branches.

**LATENT under current wiring** (Plan agent refinement): the BOS-volume-reject path
is only reachable for `macro_surveillance` and `stealth_balanced` — both 4swing
modes, where detection is pattern-driven, not swing-ref-driven. Expected live-mode
output delta: **nil**. Tests make the path observable via a monkeypatched
simple+BOS-gated profile.

## Behavior-shift map

| Mode | 3A | 3B | 3C |
|------|----|----|----|
| OVERWATCH (4swing) | YES — wrong CHoCHs stop, correct ones start | YES | latent/nil |
| STEALTH (4swing) | YES | YES | latent/nil |
| STRIKE (simple) | No | YES | No (gate unreachable) |
| SURGICAL (simple) | No | YES | No |

## Gate findings (addressed or flagged)

- **symmetry-guard FIX-01-SUSPECT (addressed via in-code flag)**: the first-two-swings
  seed retains a bounded residual look-ahead — swing #2 can post-date the scan's first
  candle in sparse-swing dataframes. Flagged in-code at `_determine_initial_trend`
  (same treatment as the swing-confirmation limitation). Full fix = temporal guard
  (`swing index <= scan start`), which pushes more starts to "ranging" (now handled);
  deferred to keep 3B minimal.
- **symmetry-guard FIX-02-SUSPECT (pre-existing, out of diff)**: absolute-ATR fallback
  in `regime_detector.py:723-732`, reachable only when `current_price` is
  unobtainable (logs a warning). Check warning frequency in session logs; if it fires
  in normal sessions, escalate.
- **backend-integrity (pre-existing, out of diff)**: `orchestrator.py:3048` derives
  telemetry direction as `"bullish" if break_type == "BOS" else "bearish"` instead of
  reading `brk.direction` — wrong for bearish BOS and bullish CHoCH; the corrected
  CHoCH population will make this field visibly wrong more often. Follow-up ticket.

## Additional findings (flagged, NOT fixed)

1. **4swing re-fire**: the same break re-fires on every qualifying candle until the
   swing sequence advances (no emission dedup). Inflates 4swing break counts;
   `detect_obs_from_bos`'s `(timestamp, direction)` dedup doesn't absorb it
   (timestamps differ). Follow-up candidate.
2. **`detect_obs_from_bos` never filters `break_type`** — CHoCH breaks also mint
   "BOS-linked" Grade-A OBs. Possibly intentional; noted because 3A changes the
   CHoCH population for 4swing modes, therefore the Grade-A OB pool.
3. Stale fixtures (pre-existing, also logged in Phase 1B): `tests/fixtures/
   smc_patterns.py` constructs `StructuralBreak` with dead fields; only callers are
   disabled `.skip` tests.

## Stealth/Overwatch Grade-A starvation — design NOTE (propose, don't apply)

Phase-0 §0.4: swing modes get ~0–2 BOS-linked Grade-A OBs vs 13–27 for
strike/surgical on identical candles. Confirmed co-causes: (1) the 3A CHoCH garble —
fixed this phase, expect partial recovery; (2) the 4swing sequence requirement
itself; (3) volume gates suppressing break *emission* rather than break *signaling*
(`detect_obs_from_bos` can only mint from emitted breaks). Candidate future
remediations, in preference order:

(a) extend the 3C `skip_signal` pattern so volume-rejected breaks are still emitted
    with a `volume_confirmed=False` tag (or grade demotion) and remain OB-taggable —
    gate the signal weight, not the structure fact;
(b) lower stealth's BOS ratio (1.3x) toward overwatch parity (BOS-only gating);
(c) drop CHoCH from stealth's `apply_to`.

**None applied.** Decision gate: rerun `diag_ob_source_composition.py` after Phase 3
lands; if stealth/overwatch Grade-A counts remain < ~30% of strike/surgical, bring
option (a) to the operator with the new baseline.

## Tests

- `backend/tests/unit/test_bos_choch_structure.py` (30): BOS pinned through rename
  (both dirs), CHoCH fixed positive pairs with level+timestamp asserted, garble-dead
  regressions (both dirs), shape/length/close-inside negatives, mirror-symmetry
  property tests, initial-trend first-vs-last (both dirs), ranging-deadlock e2e
  (simple up + mirrored down + 4swing resolve + stays-ranging negative),
  3C stale-level no-refire (bull + bear mirror), current-wiring macro volume gate
  (suppress + emit).
- `backend/tests/unit/test_bos_ob_linkage.py` (4): bullish/bearish BOS→Grade-A-OB
  with temporal-prior assertion (BOS-ordering standing fix); stealth volume-confirmed
  linkage (Phase-0 §0.4 regression) + low-volume negative pair.

## Post-deploy measurement

Rerun `python -X utf8 -m backend.diagnostics.diag_ob_source_composition` and compare
vs the 2026-06-09 Phase-0 baseline (bos 31% / structural 51% / wick 18%; stealth/
overwatch Grade-A ~0–2). Expect: 4swing CHoCH emission rises from ~0; partial
Grade-A recovery for swing modes. That measurement decides whether starvation option
(a) goes to the operator.
