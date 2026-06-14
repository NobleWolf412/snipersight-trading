# Cut the swing tier from the STEALTH cascade (evidence-based disable)

**Date:** 2026-06-14
**Decision:** Remove `swing` from STEALTH `cascade_trade_types` → `("intraday", "scalp")`.
**Type:** Strategy/cascade change (scanner_modes.py) — gated: symmetry-guard + backend-integrity + adversarial-review + §16.
**Reversible:** one-line revert restores `("swing","intraday","scalp")`.

## Evidence (all this session, decisions on record)
- **Swing is the strategy's drag.** Post-clamp cohort net-after-fees: down_normal swing **-8.32/trade, -382.8 total, n=46, win 46%, payoff 0.37** (avg win +$7 vs avg loss -$20, stops 2.44 ATR wide). It nearly perfectly cancels the profitable scalp pocket (+6.42/t) → blended breakeven. See `2026-06-14__edge-research-scalp-pocket-vs-swing-drag.md`.
- **It loses by location, 100% of the time.** Reconstruction of all 44 reconstructable swings: every one is a SHORT entered at the BOTTOM of the macro 1d range (avg position 0.11; 41/44 in the bottom 20%; **0/44 at the directionally-correct extreme even at a loose 35% threshold**). It shorts into support — the worst location for a short. Matches the P/D-inversion finding (`2026-06-13__pd-factor-inverted-in-trends-finding.md`).
- **The cascade actively prefers it.** `_CASCADE_TYPE_BONUS` pays swing +6 (intraday +3, scalp 0) — biased toward the losing tier.
- **The proposed replacement is NOT ready.** Operator idea = swing only at major HTF S/R + confirmations. Backtest `swing_htf_reversal_backtest.py` (location-only, no confirmations): blind fade at the extreme = **16% win, -0.30R, 156/185 stops** → location alone is insufficient; the confirmation layer (untested) is load-bearing. So we cut the proven loser NOW and build the replacement separately, only if the confirmation-gated backtest proves out.

## The change
`scanner_modes.py` STEALTH `cascade_trade_types`: drop `swing`. The cascade is the only swing-generation path in STEALTH, so this fully disables swing entries. `allowed_trade_types` left as-is (broader permission filter; cascade never produces swing now — backend-integrity to verify swing is unreachable via any other path). intraday + scalp (the two money-makers) remain.

## Scope / boundaries
- STEALTH only (the bot's production mode). OVERWATCH/STRIKE/SURGICAL untouched. Four-modes standing fix intact.
- No threshold/min_confluence change. No scoring-formula change. Pure cascade-tier removal.
- bull/bear symmetry unaffected (removing a tier is direction-agnostic).

## Adversarial-review CHALLENGE — acknowledged (gate output on record)
This is a **regime-and-bug-confounded amputation, NOT a proven verdict on swing-as-a-class.**
The −8.32/trade is built on n=46 in a single down-market, 100% shorts, entered at the wrong
location by the SAME P/D-anchoring + direction bugs that 5E is fixing. We accept the cut as
near-term capital protection (swing was the biggest measured drag, the replacement is not ready
— 16%-win backtest, and the +6 bonus made the loser the DEFAULT), with eyes open that the
inference is not yet earned. Operator chose hard-cut over neutralize-and-keep-alive because 5E
is data-starved (dead market → no trades → "keep alive to re-test" can't happen soon anyway);
the named trigger below preserves the path back.

## Named re-enable trigger (reversibility is conditional, not theater)
Swing returns to the STEALTH cascade ONLY when BOTH:
  (a) the 5E P/D-anchoring + direction-selection fixes have landed AND been verified live, AND
  (b) `swing_htf_reversal_backtest.py` WITH a confirmation layer beats the benchmark
      (current location-only screen: 16% win / −0.30R — must materially exceed this).
Until both hold, swing stays off. No re-enable on vibes.

## Follow-ups (NOT in this change)
1. **Replacement swing tier** — confirmation-gated reversal at major HTF S/R (the operator idea).
   Gated on the named trigger above. Design-first.
2. **intraday vs scalp bonus** — data: scalp (+6.42, n=131) more proven than intraday (+4.23, n=12);
   the +3 intraday-over-scalp preference is a separate, thin-data tuning question (adversarial
   flagged deferring it as a "half-fix" — accepted as a deliberate, low-stakes defer since both
   tiers are net-positive; not bundled into this diff to avoid scope creep on n=12).
3. **VERIFY-NEXT (CI-framed, not point-estimate):** post-deploy, confirm 0 swing trades execute,
   AND re-run `edge_significance` on the post-cut blend — report the 95% CI and P(edge>0), not
   just the point estimate. "Blend turned positive" on a point estimate ≠ demonstrated edge; the
   surviving down_normal-scalp pocket (n=58) must be tracked as the regime rotates (it is
   regime-conditional — scalp's edge is NOT guaranteed to persist in an up/sideways tape).
