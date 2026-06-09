# 2026-06-07 — Session 1993dcd5 capstone + T16 reversal-gap investigation

**One line:** A −54.73 rest_maker session traced cleanly to an *entry-direction* failure (not stops, not management); the root-cause workflow found the direction-decision architecture has no reversal vote, but the read-only counterfactual showed the obvious fix is fragile/overfit and — decisively — **nothing at entry separated this session's winners from its losers, even in hindsight.** The entry-signal tuning road keeps dead-ending at T8 (no edge). The live levers remain execution cost (T14 maker) and correlation/position concentration.

## The session (1993dcd5, 2026-06-07 21:13→23:43 UTC)
- 9 trades, all SHORT, all `down_normal`, `execution_mode=rest_maker`. PnL **−54.73**, win 22%. 8 stop_loss + 1 session_stopped.
- **6 of 8 stops fired in a 58-second up-spike (22:14:28–22:15:26 UTC)** — a correlated alt-short book (DOT, ARB, LINK, 1000BONK, SHIB…) behaving as ONE bet; one candle erased it.

## Three things now nailed down (per-trade MFE/MAE + entry-proxy join, read-only)
1. **Entry-direction failure, not stops/management.** Losers averaged **MFE 0.16% vs MAE 2.33%**; 6 of 7 losers **never went green** (MFE = 0.00). Trades were wrong from the first tick. Confirms T16; consistent with R2 (loss = location, not stop width).
2. **The book was one correlated bet.** The 7 trades still open at 22:14 all died together in the spike. The 2 winners (PEPE, APT) simply exited earlier / were timed differently — not better setups.
3. **The entry signal carries no edge even in hindsight.** The 2 winners were **indistinguishable at entry** from the 7 losers — same regime, direction, and band/RSI range (PEPE bb 0.13/rsi 44; APT bb −0.18/rsi 38, *more* extreme than several losers). Outcome was timing vs the correlated spike, pure luck. No entry filter (band, RSI, or structural) could have kept the winners and dropped the losers. Strongest in-sample statement of T8 yet.

## T16 root cause (7-agent workflow wf_73fcbcdc, source-confirmed)
- **Decisive link: `backend/services/confluence_service.py:255-265`.** Direction is a magnitude race between two continuation-flavored scores; the clean `score_diff <= -5.0` branch falls through and **skips the only structure-aware tiebreak** (`_count_recent_structure`, reachable only in the ±5 `else` band). Nothing in the race can vote "the leader is reversing."
- **`reversal_detector.py` is wired-but-not-consulted-for-direction:** it only ADDS points to its own side (`confluence_service.py:710-722`, post-decision metadata), never vetoes the opposite, and was doubly inert via the `cycle_aligned` hard-gate (`:237`).
- Contributing: Multi-Candle "3 closes beyond level" = flat 100 with no staleness guard (`scorer.py:5912-5923`); HTF sourced from a stale 1d label; volume brake needs slope>0.1 on a trailing 5-bar OLS (`scorer.py:4515-4522`) → mechanically can't lead a surge.
- **Adversarial verdict: NEEDS-MORE-DATA, leaning DROP-as-scoped** — the veto keys on the T6/T7 exhaustion family that *faded below noise* (n=138); in a persistent down regime a bullish-CHoCH veto would preferentially skip the continuation-shorts that were working; T8 says no edge to protect; §16 would pass it clean but can't see it's strategically mis-sequenced.

## Counterfactual result (`backend/diagnostics/reversal_veto_counterfactual.py`, pre-registered gate)
- Aggregate gate (n=160 post-clamp) **PASSED** for band-extreme + RSI-fade: short-into-oversold underperforms; (keep−veto) bootstrap CI excludes zero.
- **Robustness DOWNGRADES it:** the sharp RSI≤30 effect (−3.37/tr) is **71% from one session (6e03d98e)** = fragile/overfit. The band form is broader (8/11 sessions net-neg for the veto set) but shallow (−1.23/tr) and blunt (vetoes 45% of shorts). LONG side untestable (band-veto n=4 / rsi-veto n=2 — down regime starved it → symmetric gate would ship on faith).
- **On THIS session the veto is blunt even where it should shine:** vetoes 7/9, halves the loss (−54.7 → −17.5), but skips **both** winners and keeps 2 losers.

## Decision
- **DO NOT** write scorer/smc code for a reversal veto or counter-extreme entry brake. It is real-but-fragile, in-sample, gross-of-fee, and indistinguishable-at-entry from the winners.
- **T16 → 🟡 WATCH-FORWARD.** Only honest next test is OUT-OF-SAMPLE: after the next overnight run, re-run `reversal_veto_counterfactual.py --since <next-session-start>` on fresh trades; does "short-into-lower-band underperforms" reproduce or evaporate? Watch-metric = band-extreme short veto exp vs keep exp on the new cohort. Persist across 2–3 fresh sessions AND clear net-of-fee before any §16 plan.
- **Strategic redirect:** the entry-signal road dead-ends at T8. The two live levers are **(a) execution cost — T14 maker experiment** (only maker fills flip net-negative→positive) and **(b) correlation/position concentration** — treat N correlated same-direction alt-shorts as one risk unit (would have directly capped this −54). The position-cap logic today counts slots, not correlation (`backend/bot/executor/position_manager.py`).

## Artifacts
- New diagnostic: `backend/diagnostics/reversal_veto_counterfactual.py` (read-only; `--since` for forward validation).
- Ledger: T16 (root-cause + adversarial + counterfactual), T14 (maker GATE 1, n=18 ≈ breakeven), T8 (no edge), T6/T7 (exhaustion family, faded-linear-but-tail-separates), R2 (location not width).
- Workflow transcript: wf_73fcbcdc.
