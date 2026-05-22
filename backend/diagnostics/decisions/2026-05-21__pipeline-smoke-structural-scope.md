# 2026-05-21 — Tier 2.5: pipeline_smoke.py scoped STRUCTURAL ONLY (2.5a), behavioral end-to-end deferred (2.5b)

## Headline
`backend/diagnostics/pipeline_smoke.py` ships as a STRUCTURAL smoke test — verifies the orchestrator pipeline can be loaded and configured, with the frozen `pipeline_smoke_golden.json` capturing 8 invariants (imports, SniperContext fields, mode inventory, mode thresholds, RELATIVITY_MAP, pre-scoring gates signature, regime detector surface, telemetry EventType set). End-to-end behavioral smoke (orchestrator.scan against an OHLCV fixture) deferred as Tier 2.5b pending fixture-format decision.

## Context

CLAUDE.md §20 (added in Tier 1) references pipeline_smoke as a future enforcement hook for §16 Rubric 14 ("For pipeline changes, pipeline_smoke.py (when present) passes against golden_scan.json"). The "when present" carve-out was deliberate — the design wasn't locked.

Plan agent (invoked per §18 for feature work) recommended structural-only scope this round on three grounds:

1. **Frozen multi-TF OHLCV fixture format isn't decided.** Which symbol (BTC? a mid-cap with stable behavior?), which timeframes (the STEALTH default 1d/4h/1h/15m/5m?), frozen on what date? Each is a multi-hour design choice.

2. **Adapter-mock seam doesn't exist.** Importing `backend.api_server` instantiates a Phemex client at module-load (line 47-ish of api_server.py loads markets from Phemex). For deterministic smoke, that needs a `PHEMEX_DRY_RUN=1` env shim OR an adapter factory. Either is a backend change subject to §20 + §16 Rubric 13 in its own right.

3. **Regime detection isn't deterministic.** `regime_detector.get_confirmed_regime` pulls live BTC dominance unless seeded. End-to-end behavioral comparison would need either a fixture-fed regime or accepting non-determinism in the golden — both wrong.

Structural smoke catches the dominant historical silent-break vector:

- Renamed / removed SniperContext fields → caught by `check_sniper_context_fields`
- A fifth scanner mode silently shipping (regresses §10 fix #6) → caught by `check_mode_inventory`
- `min_confluence_score` drift from the §4 table without documented reason → caught by `check_mode_thresholds`
- `RELATIVITY_MAP` keys / values changing → caught by `check_relativity_map`
- `run_pre_scoring_gates` signature drift → caught by `check_pre_scoring_gates`
- Telemetry EventType removals that would silently break /autopsy → caught by `check_telemetry_events`

What structural smoke does NOT catch: indicator-math regressions, planner logic drift, risk-validator changes, confluence weight tuning effects. Those require Tier 2.5b.

## Resolution

Files created (per Plan agent's file creation order):
- `backend/diagnostics/pipeline_smoke.py` — driver with `capture` + `verify`/`diff` modes. Each check function returns a JSON-serializable dict; failure is captured into payload (`{"error": "..."}`) rather than propagated. Reuses `capture_contracts.py`'s `_diff_dicts` pattern verbatim per Plan agent's "don't refactor for two callers" decision.
- `backend/diagnostics/pipeline_smoke_golden.json` — frozen baseline minted by `python -m backend.diagnostics.pipeline_smoke capture`. Contains 8 checks across `{imports, sniper_context, mode_inventory, mode_thresholds, relativity_map, pre_scoring_gates, regime_detector, telemetry_events}`. 217 lines.

Verified live:
- `python -m backend.diagnostics.pipeline_smoke capture` → mints golden, all 8 checks captured
- `python -m backend.diagnostics.pipeline_smoke verify` → `RESULT: CLEAN (0 changes)`
- `python -m backend.diagnostics.capture_contracts diff` → still CLEAN (no backend code modified)

Captured snapshot reflects current state:
- 4 modes (overwatch, stealth, strike, surgical) — §10 fix #6 ✅
- Thresholds: overwatch 72.0, strike 68.0, surgical 70.0, stealth 70.0 — §4 table ✅
- Cascade trade types on stealth: `["swing", "intraday", "scalp"]`
- SniperContext: 12 fields (was 9 in initial Tier 1 baseline before code-comment additions — Tier 1 decisions entry's "9 fields" claim was stale-as-noted by audit; pipeline_contracts.json has the correct 12)
- 19 EventType values; 4 /autopsy-required events present
- run_pre_scoring_gates signature: 8 params (btc_impulse, config, cycle_context, direction, is_btc, regime, relevant_timeframes, smc_snapshot) — §6 contract ✅
- GateResult fields: gate_name, metadata, passed, reason
- RegimeDetector methods: analyze_timeframe_trend, detect_global_regime, detect_intermediate_regime, detect_symbol_regime, get_confirmed_regime

## Why it matters next time

`pipeline_smoke verify` now closes §16 Rubric 14's "(when present)" carve-out for the structural-drift class. Future backend changes that touch the §20 trigger surface will surface drift in this golden alongside `capture_contracts diff` — two independent checks of the same configuration surface, structured for different failure modes.

When Tier 2.5b lands (behavioral end-to-end smoke against OHLCV fixture), the golden_scan.json file will be additive — separate baseline file, separate driver invocation, both wired into Rubric 14. Plan agent's reasoning: keep them independent so a fixture-format change can be re-baselined without disturbing the structural snapshot.

§20 wording reconciliation deferred to operator: the section currently describes pipeline_smoke as end-to-end with fixture. A one-line addendum distinguishing 2.5a structural (now present) from 2.5b behavioral (future) would tighten the cross-reference. Not a blocker — `(when present)` carve-out already covers it.

Cross-ref: CLAUDE.md §6/§7/§10/§16/§20; commits 72f64fe (Tier 1 with capture_contracts), 9024ef2 (Tier 2 agents+skills), 373c51c (Tier 3 memory archive + snapshot fix), 712f494 (Tier 4a hooks); `2026-05-21__workflow-enhancement-tier1.md` for the §20 design rationale.
