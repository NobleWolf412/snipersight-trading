# 2026-06-13 — Persist per-factor breakdown for sub-gate (low_confluence) signals

**Type:** observability-only (logging layer). No scoring / gating / threshold / execution change.

## Problem
~74% of filtered signals are `low_confluence` (scored 40–69, below the 70 STEALTH
gate). They were logged to `signals.jsonl` WITHOUT their per-factor breakdown, so the
calibration diagnostics that filter on `factors` presence
(`phase4f_score_calibration`, `pd_direction_efficacy`, `session_debrief` factor-edge)
only ever saw gate-clearers. Live sample (session 06ca0188): 2991/4020 filtered rows
were `low_confluence`, all factorless. phase4f Confluence `min=70.0` — proof it saw
gate-clearers only. Recent calibration cuts hit n=9 / n~40.

## Root cause (verified)
`_log_signal` attaches factors from `plan.confluence_breakdown.factors`. Sub-gate
signals are rejected BEFORE a plan is built → no plan → no factors. But the scorer
DID compute the breakdown (that's how the sub-gate score is known). The orchestrator
already returns it on the rejection item as `all_factors`
(`orchestrator.py` low_confluence return, ~line 2238–2260). It survives verbatim into
`rejection_summary["details"][reason_type]` (appended at `orchestrator.py:686`, no
whitelist; `scan_with_heartbeat` runs in a thread executor → same process, no pickling
strip). The bot's rejection-funnel loop (`paper_trading_service.py` ~1716–1749) built a
`mock_plan` SimpleNamespace but never forwarded `all_factors` to `_log_signal`.
**Orchestrator needed NO change** — the breakdown already reaches the bot.

## Change
`backend/bot/paper_trading_service.py` only:
1. Rejection-funnel loop: thread `sub_gate_factors=item.get('all_factors')` and
   `gate_cleared=False` into the `_log_signal` call; loud-failure WARNING if a
   `low_confluence` reject arrives without `all_factors` (§THE LOOP — never silent).
2. `_log_signal`: set `entry["gate_cleared"]` (default True; funnel passes False), and
   when there's no plan-attached breakdown, normalize `sub_gate_factors` into the SAME
   `factors` shape gate-clearers emit (`name/score/weight/weighted/rationale`; maps the
   orchestrator's `weighted_contribution` → `weighted`). Real plans are never
   overwritten by stray `sub_gate_factors`.

## Additive contract keys (signals.jsonl)
- `gate_cleared` (bool) — True = full-breakdown gate-clearer, False = sub-gate row.
- `factors` — now ALSO present on sub-gate `low_confluence` rows (was gate-clearers only).

`signals.jsonl` is **not** tracked in `db_contracts.json` (only `trade_journal.jsonl`
is, under `backend/cache/`). `capture_contracts diff` is CLEAN (0 changes); no
re-baseline required. Documented here per §20. (`trade_journal.jsonl` untouched.)

## Blast radius — consumers of signals.jsonl (additive key, none break)
- `pd_direction_efficacy.py` / `phase4f_score_calibration.py` / `session_debrief.py` /
  `phase5_pd_anchor_disagreement.py` — filter on `factors` presence; now see the 40–69
  band too (the intended 3–5× sample gain). All verified to still parse.
- `ml/signal_dataset_builder.py` — `_signal_to_record` reads ONLY top-level keys
  (confluence, rr, stop_distance_atr, pullback_probability, timestamp, conviction_class,
  plan_type, trade_type, direction, kill_zone, regime). It never reads `factors`, so the
  set of `result=="filtered"` rows it includes is UNCHANGED (sub-gate rows already
  carried those top-level keys and were already in the dataset). **Inert for ML.**
- `api_server.py` — mid-session diag uses a different key (`factor_scores`); signal_log
  is passed through to the frontend Signal panel, which reads specific fields. Additive
  key is harmless.

## Verification
- New regression: `backend/tests/unit/test_subgate_factor_logging.py` — 7 tests, LONG &
  SHORT symmetry, gate-clearer-unchanged, stray-`sub_gate_factors`-ignored, and negative
  (pre-scoring gate row → no fabricated factors). PASS.
- End-to-end disk round-trip: sub-gate row (confluence 58, gate_cleared=False) persisted
  to signals.jsonl WITH key-identical factors; no plumbing leak; `pd_stance()` consumes
  the rationale. PASS.
- `capture_contracts diff` CLEAN (exit 0). `pipeline_smoke` DRIFT is pre-existing &
  environmental (offline run → "error" keys; identical with/without this change).
