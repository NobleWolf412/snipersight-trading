# 2026-06-09 — Phase 2: DST-aware kill-zone / session timing

## Root cause (bigger than scoped)
`get_current_session` / `get_current_kill_zone` converted timestamps with a hardcoded
`timedelta(hours=-5)` (fixed EST). Two failure modes:
- **tz-aware UTC input** (the live scorer path, `scorer.py:2567` passes
  `datetime.now(timezone.utc)`): correct in winter, **1 hour off in summer** (EDT).
- **naive input** (`get_session_info` via `df.index`, naive-UTC): the `if tzinfo is not None`
  guard SKIPPED conversion entirely → raw UTC matched against Eastern windows (**~5h off**).
  This path has NO live callers (dormant).

## Fix
`sessions.py`: shared `_to_eastern()` helper converts via `zoneinfo.ZoneInfo("America/New_York")`
(DST-aware); naive timestamps treated as UTC (system convention). Replaced the hardcoded -5 in
both `get_current_session` and `get_current_kill_zone`. Tables `KILL_ZONE_TIMES_EST` /
`SESSION_TIMES_EST` keep their `(sh,sm,eh,em)` shape (external consumer `api_server.py` unpacks them).
`api_server.py` `/api/kill-zone-status`: was hardcoding its OWN `EST_OFFSET_HOURS=5` for countdown +
UTC-projection — my fix made the module DST-aware while the endpoint stayed UTC-5, so they DISAGREED
by 1h in summer (the comment "mirror the module's fixed UTC-5" became false). Fixed in-diff with the
same `_to_eastern` conversion + a per-call `est_offset_hours` (5 EST / 4 EDT). Rubric-9 in-scope
expansion: my Phase-2 change introduced the divergence, so I resolved it rather than ship a regression.
Tests: `test_kill_zone_dst.py` (10) — DST-aware, naive=UTC, summer bug gone, false-positive gone,
session path, March + November transition dates. `tzdata` resolves on Windows (verified).

## Live blast radius — 6 consumers of get_current_kill_zone (corrected from initial undercount)
| Consumer | Impact |
|----------|--------|
| `scorer.py:2567` | "Kill Zone Timing" confluence factor (weight ≤0.15). Fires at correct Eastern time now; summer timing shifts ~1h → score shift at boundary. CORRECTNESS fix, not a threshold change. |
| `paper_trading_service.py:2549` | Score-floor relaxation (floor −3 when a KZ is active). Its trigger window shifts ~1h in summer. Decision-affecting. |
| `paper_trading_service.py:2052`, `position_manager.py:405` | ML feature `kill_zone` at signal/position open. Corrected label drifts the live feature distribution vs PRE-Phase-2 training rows (mild; not a schema break). |
| `paper_trading_service.py:1753`, `live_trading_service.py:1354` | Diagnostic log strings (try/except guarded; safe). |
| `api_server.py:927` | HUD `/api/kill-zone-status` — now internally consistent (fixed above). |

`get_current_session` + `get_session_info`/`is_kill_zone_active`/`filter_candles_in_kill_zone`:
**zero live callers** — the ~5h naive-path bug there is dormant (still fixed for correctness).

## §15 check — NOT a boundary violation
This shifts WHEN an existing factor evaluates; it does not touch `min_confluence_score`, any
pre-scoring gate threshold, or the `kill_zone` weight (still `get_w("kill_zone", 0.05)`). Correctness,
not a tuned-threshold change.

## 4F interaction
Phase 2 < Phase 4F, so the gate-recal baseline is measured AFTER this fix → it observes corrected
DST-aware kill-zone timing (no contamination). Caveat: do not mix pre/post-Phase-2 paper rows when
measuring kill_zone-conditioned behavior (the ML feature label changed for summer rows).

## KNOWN LIMITATION (deliberate scope decision)
London kill zones (`LONDON_OPEN` 2-5 / `LONDON_CLOSE` 11-12) remain expressed in the **Eastern
frame**, NOT `Europe/London`. The task suggested evaluating London windows in `Europe/London`, but
that requires restructuring the shared `KILL_ZONE_TIMES_EST` table (per-zone tz), which would break
`api_server.py`'s `(sh,sm,eh,em)` unpack contract. Consequence: during the ~3 NY/London DST-mismatch
weeks/year, London windows can be 1h off. Low impact (London windows are low-weight + the dominant
live path is NY/Asian timing). Deferred; revisit if a London-tz-accurate window is ever needed
(would need a per-zone-tz table + api_server payload update together).

## Gate results
- symmetry-guard: SKIPPED with rationale — sessions.py isn't a symmetry-trigger file; timezone logic
  is direction-agnostic (no bull/bear surface). Confirmed by §16 Rubric 12.
- backend-integrity: contract diff CLEAN (exit 0), pipeline_smoke CLEAN; blast radius = 6 consumers
  (above); api_server table shape unchanged.
- §16 audit: see re-audit after this entry + the api_server fix landed (initial round HELD on
  Rubric 13 blast-radius undercount + missing this decision entry).
