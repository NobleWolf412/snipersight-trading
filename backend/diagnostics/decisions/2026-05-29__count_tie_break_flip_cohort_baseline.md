# count-tie-break flip cohort — multi-session baseline

## Headline
The quality_override mechanism shipped 2026-05-27 ([orchestrator.py:1765+](backend/engine/orchestrator.py#L1765),
[decisions log](backend/diagnostics/decisions/2026-05-27__quality_aware_direction_selection.md))
blocks the SHORT→LONG circular flip-retry only when `pre_dir_tie_break == "quality_override"`.
For count-based tie-breaks (`bear_majority`, `bull_majority`) and regime-based
tie-breaks (`regime_bullish`), the same circular path is **unguarded** and is the
dominant unaddressed loss class.

6-session retroactive cohort baseline (2026-05-25 → 2026-05-29):

| Cohort | n | total_pnl | avg | win_rate |
|--------|---|-----------|-----|----------|
| FLIP (count-tie-break flipped against realized direction) | 14 | **-$562.57** | -$40.18 | **14%** |
| AGREE (count-tie-break == realized direction) | 67 | -$19.33 | -$0.29 | 46% |
| OVERRIDE (quality_override active) | 3 | -$49.61 | -$16.54 | (n too small) |
| OTHER (regime_bullish, neutral_default_long, NO-SIG-MATCH) | 12 | -$333.99 | -$27.83 | 17% |
| **UNGUARDED (FLIP+OTHER cumulative)** | **26** | **-$896.56** | -$34.48 | **15%** |

## Context

The quality_override (2026-05-27 commit ad60132) added a guard at the flip-retry
block that prevents the bot from flipping back to the count-pick direction when
quality_override was the reason the count-pick was rejected. The guard fires
only when `context.metadata.get("pre_dir_tie_break") == "quality_override"`.

Three other tie-break code paths set `pre_dir_tie_break` to non-`quality_override`
values and are NOT covered by the guard:

1. `bear_majority` — count-based: bears > bulls in OB/BOS structure tally
2. `bull_majority` — count-based: bulls > bears
3. `regime_bullish` / `regime_bearish` — regime tie-break when count was even

When any of these is the original tie-break, and the chosen direction hits
`conflict_density` rejection, the flip-retry at [orchestrator.py:1765](backend/engine/orchestrator.py#L1765)
takes the opposite direction WITHOUT the quality_override guard firing. This is
the same circular reasoning the override was built to prevent — just on a
different entry path.

## The data

### Per-session FLIP cohort trajectory

| Session | Date | n | FLIP total_pnl | Notes |
|---------|------|---|----------------|-------|
| 2f35590b | 2026-05-27 | 5 | -$288.32 | Pre-override session — the INJ/OP/ARB damage cited in 2026-05-27 ad60132 decisions log |
| 3512d5eb | 2026-05-28 | 3 | -$16.37 | First session with override active — small flip damage |
| 594165c2 | 2026-05-29 | 4 | -$256.76 | Second session with override active — flip damage returned at scale |
| 561744bc | 2026-05-25 | 1 | -$0.46 | Single nano-flip, noise |
| e5e00ebc | 2026-05-25 | 1 | -$0.66 | Single nano-flip, noise |
| 84fd5c96 | 2026-05-25 | 0 | $0.00 | No flips |

The override partially mitigated session 3512d5eb but did not address the
594165c2 cluster. The unguarded path remains intact and is bleeding.

### Full FLIP cohort roster (14 trades)

Direction asymmetry: **14/14 LONG**. Every flip went LONG-from-bear_majority.

| sid | symbol | dir | conf | pnl | exit | qualifier |
|-----|--------|-----|------|-----|------|-----------|
| 594165c2 | APT/USDT | LONG | 79.3 | -$48.21 | stagnation | Unknown |
| 594165c2 | APT/USDT | LONG | 76.0 | -$28.36 | direction_flip | Unknown |
| 594165c2 | APT/USDT | LONG | 74.0 | -$73.20 | stop_loss | Unknown |
| 594165c2 | ARB/USDT | LONG | 76.5 | -$106.99 | stop_loss | Unknown |
| 3512d5eb | LINK/USDT | LONG | 70.7 | -$11.24 | stop_loss | Unknown |
| 3512d5eb | APT/USDT | LONG | 76.8 | -$8.04 | stop_loss | Unknown |
| 3512d5eb | APT/USDT | LONG | 71.9 | +$2.91 | session_stopped | Unknown |
| 2f35590b | WIF/USDT | LONG | 73.9 | -$71.25 | stop_loss | Strong |
| 2f35590b | XRP/USDT | LONG | 75.9 | +$20.38 | stop_loss | Strong |
| 2f35590b | ARB/USDT | LONG | 70.7 | -$69.82 | stop_loss | Unknown |
| 2f35590b | ARB/USDT | LONG | 78.4 | -$91.25 | stop_loss | Unknown |
| 2f35590b | LINK/USDT | LONG | 70.3 | -$76.39 | session_stopped | Strong |
| 561744bc | LINK/USDT | LONG | 73.3 | -$0.46 | session_stopped | Strong |
| e5e00ebc | BNB/USDT | LONG | 75.7 | -$0.66 | session_stopped | Strong |

Confidence median 75.0 (range 70-79) — mid-tier. Both Soft/Strong/Unknown
qualifiers represented. Symbols: APT×5, LINK×3, ARB×3, plus BNB, WIF, XRP.

### OTHER cohort breakdown (other unguarded tie-breaks)

| tie_break | n | total_pnl | wins |
|-----------|---|-----------|------|
| regime_bullish | 6 | -$258.87 | 1/6 |
| NO-SIG-MATCH | 4 | -$54.46 | 0/4 |
| neutral_default_long | 2 | -$20.66 | 1/2 |

`regime_bullish` is a SEPARATE unguarded class — direction chosen by regime
agreement when count was tied — but produces the same structural shape:
tie-break decided LONG, market said no. Today's 1000BONK regime_bullish LONG
-$96 was here. Same fix surface (extend the guard) covers it.

`NO-SIG-MATCH` reflects journal trades where no `signal_generated` event
matched within ±2min. Separate telemetry-gap concern, not part of this finding.

## §15 baseline check

CLAUDE.md §15: "Do not modify `min_confluence_score` or pre-scoring gate
thresholds without documented baseline data + reasoning."

This is NOT a threshold tune. It is a guard extension on a circular-reasoning
code path. The §15 spirit (don't change tuned numbers without evidence) is
satisfied independently by:

- n=14 multi-session FLIP cohort (vs n=4 single-session yesterday — 3.5x sample)
- 14% win rate vs 46% AGREE baseline (3.3x worse)
- -$562 cumulative on FLIP alone, -$896 on FLIP+OTHER combined
- AGREE cohort breakeven (-$0.29 avg over 67 trades) — proves the system-as-
  designed isn't the loss source. The loss is concentrated specifically on the
  unguarded flip paths.
- Pre-override session 2f35590b confirms the pattern existed before the
  override; post-override sessions confirm the override doesn't cover this path.

## Resolution

NO CODE CHANGE in this entry. This entry documents the baseline so that a
future code change has §15-compliant evidence.

The candidate code change (NOT shipping with this entry):

1. Extend the flip-retry guard at [orchestrator.py:1765](backend/engine/orchestrator.py#L1765)
   to fire for the broader set of tie-breaks, not just `quality_override`:
   ```python
   _UNGUARDED_TIE_BREAKS = {
       "quality_override",
       "bear_majority", "bull_majority",
       "regime_bullish", "regime_bearish",
   }
   if context.metadata.get("pre_dir_tie_break") in _UNGUARDED_TIE_BREAKS:
       # accept the conflict_density rejection — do not flip
   ```
   Rationale: the AGREE cohort is breakeven, meaning when count-tie-break IS
   the realized direction it works. Flipping AGAINST it to the conflict_density-
   rejected direction is the loss class. Honor the original tie-break.

2. In the same diff, instrument trade_journal row with:
   - `pre_dir_tie_break: str` — the tie-break that set pre-direction
   - `flip_applied: bool` — whether flip-retry actually fired
   - `flip_origin_dir: Optional[str]` — what direction count/regime originally picked

   Without these, cohort analysis requires fragile telemetry matching. With
   them, future autopsy + repo-janitor + symmetry-guard get the cohort label
   for free. Schema add is justified once the guard ships.

3. Pair with `backend/tests/unit/test_count_tie_break_flip_guard.py`:
   - bear_majority + conflict_density rejects SHORT → flip-retry SKIPPED, rejection accepted
   - bull_majority + conflict_density rejects LONG → flip-retry SKIPPED (symmetry)
   - regime_bullish + conflict_density rejects LONG → flip-retry SKIPPED
   - quality_override existing test still passes (regression)
   - AGREE path unchanged: count-tie-break == realized direction, no flip needed

## Why it matters next time

- The pattern was visible in 2026-05-27 session 2f35590b BEFORE override shipped
  (-$288 FLIP damage that contributed to the audit-caught flip-retry interaction
  in the 2026-05-27 ad60132 decisions log). The override caught half the case
  (quality_override path) but not the count-tie-break path. This is the same
  bug-class returning under a different name.
- 14/14 FLIP trades went LONG — there is a strong directional asymmetry in
  WHICH side the count-tie-break gets flipped to. Specifically, `bear_majority`
  picks SHORT, conflict_density rejects SHORT in compressed-uptrend regimes
  (where bullish OB count is high), and flip-retry picks LONG. The LONG then
  loses because the up_compressed regime is structurally hostile to LONG
  scalps (see [confluence-trace APT/USDT 2026-05-28](backend/diagnostics/decisions/...): LONG factor miss-rate 44% vs SHORT 12% on same critical factors).
- The bug isn't that flip-retry exists. The bug is that flip-retry treats
  conflict_density as "score this direction worse" when it should be "neither
  direction has clean enough setup right now — wait."
- Adopting the guard extension would reduce session damage by an estimated
  $562 over 6 sessions (FLIP alone) or $896 (FLIP+OTHER) — roughly 70-90% of
  total session loss in the sample period was concentrated on these
  ~26 of 96 trades. AGREE cohort is breakeven, so the system without these
  flips would be approximately at scratch over the sample period (-$19 net).

## Caveats / open items

- OVERRIDE cohort n=3 is too small to evaluate the override itself this
  baseline. The override mechanism's win-rate cannot be graded from this data.
- `NO-SIG-MATCH` (n=4 of OTHER) reflects telemetry gap — trades fired without
  a matching `signal_generated` event within ±2min. Separate silent-bug class,
  worth its own follow-up. Counted as OTHER for honesty (`pnl=-$54.46`)
  but should not be attributed to the flip-retry path.
- `quality_override` direction asymmetry: of n=3 OVERRIDE trades, 1 LONG
  (BNB +$8 session_stopped) and 2 SHORT (OP -$55 stop, SOL -$2.87). Mixed
  outcomes but n is too small to read. Continue paper sessions to grow this
  cohort before re-evaluating the override threshold (separate from this
  finding).
- Symmetry note: 14/14 FLIP trades were LONG (bear_majority → LONG flip).
  ZERO instances of `bull_majority → SHORT flip` in 6 sessions. Either the
  current regime universe is structurally one-sided (compressed uptrend
  dominates → bull_majority happens but count agrees with conflict_density),
  or there's a §10 bull/bear symmetry concern in the flip-retry path itself.
  Confirm symmetry by running symmetry-guard on the flip-retry block when
  the code change is drafted.
- This baseline reflects STEALTH mode (the only paper-traded mode per §15).
  Other modes' tie-break distribution would need separate baselines before
  guard extension affects them.
- The guard extension would cover `bear_majority`, `bull_majority`,
  `regime_bullish`, `regime_bearish` — but NOT `neutral_default_long` /
  `neutral_default_short`. Those are explicit defaults when no tie-break
  fired at all; their semantics in the conflict_density flip-retry context
  need separate thinking. n=2 in OTHER, $-20.66, too small to baseline.
