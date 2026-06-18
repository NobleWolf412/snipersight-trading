# 2026-06-18 — Liquidity admission filter (regime-strategy-router rules layer, Chunk 1+2)

On-main design + implementation record for the first edge-independent piece of the
regime-strategy-router (the §9-A "rules layer"). The broader router design lives in PR #58
(`2026-06-16__regime-strategy-router-design.md`, branch `claude/app-quality-concerns-jzr0f7`);
THIS entry is the §15 documented design entry for the live-path change landed here.

## Why
The operator's #1 named rule for the regime router is "don't trade illiquid pairs." A read-only
investigation (2 agents) found the rule was NOT enforced: a hardcoded `MIN_VOLUME_USDT = 5_000_000`
floor inside `PhemexAdapter.get_top_symbols` **silently** dropped micro-caps with no log/reason
(CLAUDE.md §11 silent-skip violation), its docstring lied (said 500k, code was 5M), and the
user-pinned path (which STEALTH/production commonly uses) bypassed it entirely — so an illiquid
pinned pair would be scanned and traded, blowing through stops on exit.

Of the four candidate liquidity metrics, only **24h quote-volume** is wired today (open interest +
funding are unimplemented placeholders; spread needs a new ticker read; ATR-relative is impossible
at universe stage). So this chunk is **volume-only**; OI/spread/funding are deferred.

## Operator decisions (2026-06-18)
- **Filter pinned symbols too** (not operator-trusted-exempt): a pinned illiquid pair is still a
  capital risk, so the gate covers BOTH auto-selected and user-pinned symbols.
- Commit Chunk 1 + Chunk 2 as one coherent unit.

## Change
- `phemex.py` `get_top_symbols`: silent floor → LOUD + configurable. New optional
  `min_volume_usdt` param (default 5M = behavior-preserving); dropped pairs logged
  `LOW_LIQUIDITY_SKIP`; docstring fixed. Extracted pure `partition_by_volume_floor` staticmethod
  (unit-testable; missing/null ticker → 0 vol → dropped, fail-safe).
- `phemex.py` `get_symbol_volumes(symbols)`: batch ticker volume lookup for symbols that bypass
  `get_top_symbols` (pinned). **Total fetch failure returns `{}`** (distinct from per-symbol miss)
  so the caller SKIPS the filter loudly rather than wiping the universe / halting the bot on a
  transient infra glitch.
- `pair_selection.py` `filter_illiquid_symbols(symbols, volume_by_symbol, min_volume_usdt, *, context)`:
  companion to `filter_stale_symbols`; (kept, dropped) partition, body-level mass-conservation
  assertion, loud log. Applied AFTER `scan_symbols` is built so it covers pinned + auto.
- `scanner_modes.py`: `ScannerMode.min_24h_volume_usdt: float = 5_000_000.0` (config home; default
  matches the prior silent floor; raise per mode for stricter discipline).
- `paper_trading_service.py` + `live_trading_service.py`: call the gate symmetrically right after
  the existing `filter_stale_symbols` call, reading the per-mode floor. Fail-open on `{}` volume map.
- `tests/unit/test_liquidity_floor.py`: 7 tests (boundary-inclusive, configurable floor, fail-safe
  drop of unknown/null/missing, mass-conservation, every-mode-has-a-floor). All pass.

## Audit gate (§16 / §20) — verdict
- **backend-integrity: CLEAN.** `get_top_symbols` gained a trailing optional kwarg (all 4 live
  callers use keywords → no break); new symbols consumed only by the 2 bot services; new ScannerMode
  field is defaulted + keyword-constructed everywhere (no `replace`/`asdict`/`eq`/`hash` consumer).
  Contract diff: api/telemetry/pipeline CLEAN; the one `db_contracts` drift (`trade_journal.jsonl`
  45→25) is PRE-EXISTING and NOT introduced here (must be re-baselined under its own entry, not here).
- **§16 14-point: PASS** on all safety/correctness points — paper↔live symmetric (both resolve the
  same $5M STEALTH floor; identical fail-open/fail-safe semantics), fail-open cannot halt the bot,
  per-symbol fail-safe does not endanger the majors-fallback list, standing fixes (§10) untouched
  (direction-agnostic universe filter), mass-conservation asserted in body, negative tests paired.
  Two governance 🟡s were resolved before commit: (11) this design entry now exists on main; (9) the
  unrelated working-tree `CLAUDE.md` edit was kept OUT of this commit (staged selectively).

## Scope guards / what this is NOT
- Direction-agnostic (no scoring/regime/SMC edit → symmetry-guard not triggered).
- No `min_confluence_score` / pre-scoring threshold change. No real→mock swap. No log suppression.
- Capital-protective only: REMOVES illiquid symbols, never adds. Default behavior unchanged ($5M).

## VERIFY-NEXT
- Run a fresh paper session (HARD-RESTART backend first) and confirm `LOW_LIQUIDITY_SKIP` fires and
  the scanned universe excludes sub-$5M pairs; confirm pinned illiquid pairs are now dropped.
- Later chunks: per-mode floor tuning (e.g. stricter STEALTH); spread-cap (needs a ticker bid/ask
  read); OI/funding filters (need new adapter methods — currently unwired).
