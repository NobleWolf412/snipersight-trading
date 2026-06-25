# Heart-change chunk 4 — score-gate demotion behind SS_DECISION_POLICY (2026-06-24)

§15 record: this changes go/no-go gate behavior, so it requires documented baseline + reasoning.
This is the behavioral cutover of the heart-change (chunks 1-3 were inert infrastructure).

## Baseline (the measured problem this addresses)

- The bot traded **0 trades in 47h** on a correctly-sized universe (9 symbols, after the
  perp-volume fix 7006369). Not a universe problem — the **70 confluence score-gate** rejects
  everything: ~48% of signals rejected at `confluence_score`, median rejected score ~9 points
  below the 70 gate, in a down-conflicted tape.
- The confluence score has **measured no edge** ([[project_edge_after_fees_verdict]]: clean n=142,
  +0.43/tr gross, 95% CI spans zero; 1/26 factors predict). The one profitable cohort ever found
  was the **BOS-continuation override** (2026-06-13__pd-factor-inverted-in-trends-finding.md).
- Consequence: "run a clean session → re-measure (#7)" is **impossible** — a strategy that never
  fires produces no data. The data-gate is empty (see project_v1_salvage_regime_router).

## The change

Add `SS_DECISION_POLICY` env-var flag (default `legacy`). In `thesis` mode:
1. **Direction** comes from `ThesisPolicy` (chunk 3): structure-led (BOS/CHoCH), regime-blind,
   CHoCH-reversal priority, FLAT on no-structure / conflict / BOS-vs-strong-opposite-regime.
2. **The 70 score-gate is DEMOTED at BOTH sites** (must move together or the bot's own gate
   secretly re-score-gates the thesis trades — the shared paper/live trap):
   - `orchestrator._process_symbol`: `FLAT` decision → reject (`reason_type=no_thesis`, loud +
     telemeterized); actionable decision → the `score < min_confluence_score` rejection is
     **skipped**. The score becomes logged context.
   - `paper_trading_service`: the sensitivity-floor `else: return` (skip-below-floor) becomes
     `elif is_thesis_mode(): size_modifier = 0.5` — a below-floor score takes at minimum size
     instead of being skipped. Score now informs **sizing**, not trade/no-trade.
3. The **4 pre-scoring gates stay** (structural anchor → regime alignment → BTC impulse →
   conflict density). They run upstream of scoring and are unchanged. min_confluence_score itself
   is **not modified** — it is bypassed-as-a-gate in thesis mode, not retuned.

Env-var (not config) on purpose: no SniperContext/ScanConfig field → **no contract drift**.
Enabling requires a hard backend restart (per [[feedback_bot_hard_restart_required]]).

## Why this is "trade DIFFERENTLY", not "trade garbage the gate rejected"

The bar changes from *"high confluence score"* (no edge) to *"confirmed market structure in the
trade direction"* (the only cohort with evidence). It is a **better selection criterion**, not a
lower one. FLAT lets the engine abstain (it could not before — "no edge" was a raised exception).

## Risks + mitigations (the honest part)

- **Trade-more-in-a-no-edge-system = lose faster.** Mitigated: paper-only behind a default-off
  flag; FLAT abstains liberally; the 4 pre-gates + the ML gate + the regime counter-trend gate all
  remain in force (NOT demoted — only the *score* gate is).
- **Known interaction to OBSERVE (not pre-solved):** the bot's regime counter-trend gate
  (paper_trading_service, strong_up/down blocks counter-trend) may block exactly the CHoCH-reversal
  LONGs that ThesisPolicy is designed to allow in a downtrend → could re-create a down-only bias.
  This is a forward-run finding to watch, flagged here deliberately; a follow-up chunk addresses it
  if the data shows it biting.
- **ML gate** still applies in thesis mode (out of scope for this change).

## Validation plan (no shortcuts)

The forward paper run behind the flag is **data generation**, not validation-by-vibes. It produces
the entry-regime-labeled trades that **re-open #7**. HARD RULE: **no real capital until a per-cell
Deflated-Sharpe gate clears** on that forward data (multiple-comparisons-aware, per the §11.6
guardrails). Enable order: hard-restart with `SS_DECISION_POLICY=thesis`, watch one paper session,
pull the trade/FLAT/rejection mix, then decide.

## Verification in this diff

- `symmetry-guard`, `backend-integrity`, `adversarial-review` — pasted in the commit thread.
- 23 decision-core tests (flag default-legacy, flag-flip, unknown-value-failsafe-legacy,
  case-insensitive; ThesisPolicy rules all bull+bear paired).
- Default-off proven: `is_thesis_mode()==False` with no env var → LegacyScorePolicy + score-gate
  authoritative = byte-identical legacy behavior.

## Rollback

Unset `SS_DECISION_POLICY` (or set `legacy`) + hard-restart. Zero code revert needed — the flag is
the kill switch.
