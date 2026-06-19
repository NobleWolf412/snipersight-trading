# 2026-06-18 — Decision-core heart-change SPEC (thesis-then-gate) + deep-dive seam map

Authoritative, code-grounded spec for replacing the bot's decision core (argmax-score-as-gate) with
a thesis-then-gate model that can return FLAT. Produced by a 3-agent deep-dive (seam map, shadow
harness, adversarial review). **This is the plan; the live wiring is GATED — see §Sequencing.**

## Branch hazard — RESOLVED this session
The PR #58 branch (`claude/app-quality-concerns-jzr0f7`) had diverged from `main` and was MISSING the
liquidity filter (`107e2fc`, the operator's #1 capital rule). Reconciled via `git merge main`
(merge commit `a039252`) — branch now carries BOTH the liquidity filter AND the bug fixes
(#1/#2/#4). 17/17 tests pass. Do not build heart-work on an unreconciled base again.

## The heart, mapped (current code, file:line)
Three coupled decisions, all driven by the 26-factor confluence score:
- **DIRECTION** — decided INSIDE `confluence_service.score()` (`backend/services/confluence_service.py:218-497`):
  margin-gated argmax (`DIRECTION_MARGIN=5.0`) + a chain of tiebreakers (range-reversion, elite,
  compressed-vol, regime-trend override via `resolve_directional_tie` :40-77). Writes
  `context.metadata["chosen_direction"]` at :497. **Cannot return FLAT** — "no direction" is expressed
  by RAISING `ConflictingDirectionsException` (:71 exact-tie, :647 counter-HTF block), caught by the
  orchestrator's ~300-line handler at `orchestrator.py:1941-1979+` and converted to a rejection.
- **GO/NO-GO** — `orchestrator.py:2167-2169` (`total_score < min_confluence_score`), + direction guard
  :2317. **SECOND gate** in `paper_trading_service.py:2312-2338` (gates on `confidence_score` AND sets
  size full/half/skip).
- **TRADE-TYPE** — cascade argmax of `score + _CASCADE_TYPE_BONUS` (`orchestrator.py:3473` bonus table,
  `:3647` effective, `:3681` argmax). Direction is inherited, not re-derived.

**Key seam finding:** only **site 1 (the in-`score()` argmax)** must be demoted. Sites 2/3/4 already
READ `chosen_direction`/`total_score`, so a policy that writes those flows through unchanged. The clean
insertion point is `_process_symbol` ~:1936 (post-scoring, pre-gate); all context a thesis needs
(`symbol_regime`, `global_regime`, `smc_snapshot.structural_breaks` BOS/CHoCH, both `ConfluenceBreakdown`
objects, `alt_confluence` scores) is in scope there.

## The change (when gated open)
1. **`Decision` value layer** — `Direction{LONG,SHORT,FLAT}` + `Decision{direction, reason, source}`.
   FLAT becomes a FIRST-CLASS decision (the router's required NO_TRADE state), not an exception.
2. **`DecisionPolicy` seam** at `_process_symbol` ~:1936 — `decide(context) -> Decision`.
   - `LegacyScorePolicy` (default): reproduces current behavior (reads `chosen_direction`;
     exception/unresolved → `Decision(FLAT, reason)`). Behavior-preserving.
   - `ThesisPolicy` (later): direction from regime+structure, returns FLAT on disagreement.
3. **Demote** the in-`score()` argmax so `score()` returns BOTH breakdowns and the policy chooses.
4. Config flag on `PaperTradingConfig` (precedent: `execution_mode`), default legacy.

## Shadow harness (validate before cutover — zero live change)
- **Hook point:** `PaperTradingService._log_signal` (`paper_trading_service.py:1921`) — fires for BOTH
  executed AND filtered rows; merges arbitrary `**extra` at :2009 (no signature change).
- **Log fields:** `shadow_direction (LONG|SHORT|FLAT)`, `shadow_reason`, `agree`, plus existing
  `direction`, `regime` (entry-snapshot, bug #1 fixed), `bull_score`/`bear_score` (`alt_confluence`).
- **Outcome join:** signals.jsonl row ↔ `CompletedTrade` journal row by symbol+entry-time → realized
  P&L. Headline metric: "thesis said FLAT, argmax traded it → P&L the thesis would have avoided."
  (Shadow-would-trade-but-argmax-filtered is NOT directly measurable — needs forward-return proxy.)
- **Config:** `PaperTradingConfig.shadow_decision_enabled: bool = False`. Diagnostic
  `shadow_decision_efficacy.py` in the same diff.

## Adversarial verdict — DO NOT wire now (premature)
1. **Reads the lag-prone regime label.** A thesis "direction from regime" top/bottom-picks at trend
   FLIPS — and shadow-mode on one bearish month cannot exercise the UP-flip (0 UP-regime data). High
   shadow agreement on bearish tape would read as "validated" while the divergence regime has no data.
2. **Comparison data is bug-contaminated.** It would be calibrated on the pre-#7 sample the §11 audit
   tagged LIKELY-ARTIFACT/SUSPECT, with #1/#2 committed but NOT on main and no clean session yet.
3. **It's a less-bad bag, not a sequence.** §11.5: the real edge is a SEQUENCE
   (sweep→CHoCH→OB-return→retest); a thesis-from-regime still preserves the instant-snapshot
   representation. The seam risks entrenching the wrong representation.
4. The seam is a refactor of the most symmetry-sensitive, standing-fix-protected code
   (`resolve_directional_tie` is a documented symmetry fix) — bigger than "swap an argmax."

## Sequencing (the gate on the wiring)
1. ✅ Reconcile branch with main (done, `a039252`).
2. ⬜ Deploy fundamentals: merge PR #58 → main (operator §15 decision).
3. ⬜ Run a clean post-fix paper session (hard-restart) → accumulate entry-regime-correct trades.
4. ⬜ #7 re-measure (`edge_by_regime` + Deflated-Sharpe, per-cell CIs).
5. ⬜ THEN build the `Decision`/FLAT seam + `ThesisPolicy` in SHADOW (this spec), compare, cut over
   only when shadow-admitted net CI clears zero OOS AND beats the score gate (both orchestrator gate
   AND the paper_trading second gate move together — don't leave the bot secretly score-gating).

**One line:** the heart change is fully designed and shovel-ready; it is deliberately NOT wired now
because the thesis it would encode reads an unverified label and would be validated on contaminated,
not-yet-re-measured data. Wire it after steps 2-4.
