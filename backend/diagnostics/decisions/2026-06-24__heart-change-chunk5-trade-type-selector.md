# Heart-change chunk 5 — trade-type core (regime->type selector) (2026-06-24)

§15-adjacent record: changes how trade TYPE is selected (a decision-core change). Flag-gated to
thesis mode (SS_DECISION_POLICY=thesis); legacy unchanged. Two sub-chunks:

## 5a — strong-trend discipline (shipped bdc9341)
ThesisPolicy rule 3 now vetoes ANY counter-trend entry (BOS OR CHoCH) against a STRONG trend, not
just BOS. "Never trade against the trend" is strongest in a strong trend; a bare CHoCH there is
usually a trap. NORMAL/sideways trends: no veto, structure wins. (Operator design call 2026-06-24:
strong-trend = with-trend-only is correct trend-respect, NOT the down-only defect — the bot longs
in uptrends/ranges/normal-trend reversals, just not fighting a strong downtrend.)

## 5b — regime->type selector (this entry)

### The defect (from the trade-type path map)
After the score-gate demotion, thesis trades reached the planner and died at a TRADE-TYPE mismatch
(ADA SHORT: structure produced 1.0-ATR LTF geometry -> classified 'scalp' -> rejected by the
intraday cascade scale's `allowed_trade_types=('intraday',)`). Root: type was reverse-engineered
from post-hoc geometry then validated against a one-type-per-scale whitelist (dead zones), and the
cascade winner was `argmax(confluence_score + _CASCADE_TYPE_BONUS)` where the bonus PREFERS swing
(the proven -8.32/t loser) and penalizes scalp (the only proven-positive cell).

### The fix (thesis mode only)
1. **Close the dead zone** — `_build_cascade_config` sets `allowed_trade_types=("intraday","scalp")`
   so a scale accepts its honest geometry-derived type (intraday scale producing a scalp keeps it).
   SWING excluded (operator-deferred) so swing-geometry is still dropped.
2. **Neutralize the swing bonus** — `_CASCADE_TYPE_BONUS` contribution = 0 in thesis mode.
3. **Pick the winner by REGIME->TYPE preference** (`regime_type_rank` in decision.py), not score+bonus:
   range/sideways -> scalp; trend (normal or strong) -> intraday; swing rank 0 everywhere. Tiebreak
   by confluence score. Direction-AGNOSTIC (type only).

### Why a seeded table, not edge-earned (the honest caveat)
The design doc wants an EDGE-EARNED regime->type table. We have NO trustworthy edge data — every
regime×type cell is bug-contaminated / MUST-EARN (the +6.42 scalp cell included; regime was labeled
at close not entry). So `_REGIME_TYPE_PREF` is a **seeded HYPOTHESIS from operator trader-priors**,
NOT proven edge. Our limited data even mildly contradicts "range->scalp" (down_compressed×scalp lost
-1.06). This is the legitimate way to GENERATE the data: trade the hypothesis in paper, measure
forward. HARD RULE: no real capital until a per-cell Deflated-Sharpe gate clears (§11.6 guardrails).

### Known limitations / forward-watch
- Swing deferred — earns back only via the (unbuilt) sweep->CHoCH sequence at confirmed cycle extremes.
- Type selector reads the regime label -> re-introduces regime-label dependence that direction
  escaped (next roadmap item: VERIFY regime-label trust before over-relying).
- TP1-unreachable rejections are NOT addressed here (that's the exit/risk pass, roadmap item 4).
- ML gate still in path (roadmap item 3).

### Verification
- symmetry-guard + backend-integrity + adversarial-review — pasted in the commit thread.
- 30 decision-core tests (regime_type_rank: range->scalp, trend->intraday, swing=0 everywhere,
  unknown failsafe, direction-agnostic). Legacy mode byte-identical (all changes `if is_thesis_mode()`).

### Rollback
Unset SS_DECISION_POLICY (legacy) + hard-restart. Flag is the kill switch; no code revert needed.
