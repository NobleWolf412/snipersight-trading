# User-pinned stale-symbol drop — closing the auto-drop bypass

## Headline
The `_NO_DATA_DROP_THRESHOLD` auto-drop mechanism in `pair_selection.py` only
fires when symbols flow through `select_symbols()`. When the user pins
specific symbols via `config.symbols`, both `paper_trading_service` and
`live_trading_service` bypass `select_symbols()` entirely — so the Stage-0
stale-drop never sees those symbols. New helper `filter_stale_symbols()` is
called immediately after `scan_symbols` is built in both services, applying
the same drop regardless of which path populated the list.

## Context
- Calibrated on session 84fd5c96 (May 2026): 11-hour user-pinned scan,
  BONK/USDT + FLOKI/USDT failed `no_data` on 220/220 (100%) cycles each.
- `_NO_DATA_DROP_THRESHOLD = 10` should have caused both to be excluded ~30
  minutes into the session. They were not.
- Root cause located at:
  - [paper_trading_service.py:1350-1352](backend/bot/paper_trading_service.py#L1350) — `if self.config.symbols: scan_symbols = list(self.config.symbols)` — direct path, no `select_symbols()` call.
  - [live_trading_service.py:1045-1046](backend/bot/live_trading_service.py#L1045) — identical shape.
- The Stage-0 stale filter at [pair_selection.py:397-409](backend/analysis/pair_selection.py#L397)
  only executes inside `_select_symbols_impl`, which is never reached on the
  user-pinned path.

## Resolution
- New helper [pair_selection.py:filter_stale_symbols](backend/analysis/pair_selection.py#L340) — partitions a list into `(kept, dropped)` by `is_symbol_stale`, with a runtime mass-conservation assert and an INFO log emit when drops happen.
- Wired into both bot services immediately after `scan_symbols` is built and
  before the `exclude_symbols` filter, so the drop applies symmetrically to
  both the user-pinned and auto-selected paths.
- Helper uses loguru's `{}`-style format strings rather than stdlib `%s`.
  Note: several other emits in `pair_selection.py` still use `%s`-style and
  produce un-interpolated output under loguru; that is pre-existing and out
  of scope for this commit.
- New test file `backend/tests/unit/test_filter_stale_symbols.py` with 15
  cases covering: kept/dropped partition (positive and negative), off-by-one
  threshold guard, recovery via `record_no_data_success`, mass-conservation
  parametrized 4 ways, and loguru log-emit observability.

## Why it matters next time
- Auto-drop on the user-pinned path is the more common live case. The
  previous coverage by `test_stale_symbol_autodrop.py::test_stage0_*` only
  exercises the `select_symbols()` flow, so the bypass was undetectable.
- Mass-conservation invariant + tests catch any future refactor that
  silently drops symbols from one partition without recording them in the
  other.
- The `context=` tag on the helper's log emit makes drops trivially
  grep-able per scan source (`grep STALE_SYMBOL_SKIP paper_trading_service`
  vs `live_trading_service`).
- Loguru `{}` vs stdlib `%s` formatting is the kind of silent-bug class
  CLAUDE.md §11 warns about: log emits look fine in code review but emit
  literal `%s` to the console. Future emits in `pair_selection.py` should
  use `{}`.
