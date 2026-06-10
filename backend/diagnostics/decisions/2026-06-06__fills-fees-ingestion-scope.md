# 2026-06-06 — Scope: read-only fills/fees ingestion for edge-after-fees

**Trigger:** operator asked whether an MCP/plugin could improve "trade quality",
narrowed to the standing open question: *edge-after-fees (~breakeven gross → likely
net-negative)*. Scoped a "read-only fills/fees feed against the journal schema."
No code landed — this is the design entry CLAUDE.md §15 requires before any
live-path touch.

## Finding — the ingestion already exists (live path)

The fills/fees feed is **already built**; it is not a missing plugin.

- `backend/data/adapters/phemex.py:598 fetch_my_trades` — read-only REST pull of the
  authenticated user's executed trades; each ccxt trade dict carries the real `fee`,
  `cost`, `price`, `amount`, `side`. Full auth/429/5xx error + metrics instrumentation.
- `backend/bot/live_trading_service.py:582 _backfill_loop` / `:613 _run_backfill_once`
  — 5-min poll since `last_trade_sync.json`, dedupe by `fill_id`, appends each fill
  (incl. `fee`) to a **session-scoped fills log** (`_fills_log_path`). Surfaced via
  `/api/integrations/phemex/healthz` backfill metrics.
- `backend/bot/trade_journal.py:49 upsert` — dedupe-by-`trade_id` (exchange order id);
  used on round-trip close at `live_trading_service.py:1933`.

**Deliberate design boundary** (live_trading_service.py:587-592): raw fills are
intentionally **NOT** written into `trade_journal` — doing so would corrupt the
round-trip win-rate / P&L aggregates. The fills log is an audit/recovery trail only.

## The real gap (and why it isn't an MCP)

The journal's `pnl` is the bot's **modeled** close — paper executor assumes
`fee_rate=0.001` (`paper_executor.py:171,212`; `live_executor.py:517`). The exchange's
**actual** per-fill fee lives only in the fills log, never reconciled back into a
round-trip net-of-actual-fee P&L. So "is our gross-breakeven edge net-negative after
real fees?" is **not answerable from the journal today**.

Closing that gap is a **read-only reconciliation diagnostic**, not a connector:
join fills-log fees → round-trip trades (by `order_id`/`trade_id`) → recompute net
P&L → diff against the journal's modeled `pnl`. It runs entirely off data we already
persist. An external MCP would (a) duplicate `fetch_my_trades`, (b) re-implement the
dedupe/`since` state machine, and (c) re-cross the live-credential boundary for zero
new capability. Rejected.

## Hard blocker — paper mode has no real fills

Production bot mode is **STEALTH = paper** (CLAUDE.md §15). The entire fills/backfill
machinery lives in `live_trading_service`, gated on Phemex credentials. In paper the
fills log is never populated ⇒ **real net edge is unmeasurable until live capital is
deployed.** Until then, edge-after-fees can only be *modeled*, and that model already
exists: `risk_engine.py:2465 _MIN_TP_DISTANCE = entry_ref * fee_rate * 2 * 2.5`
(round-trip cost × 2.5 floor on TP1 distance).

## Decision

1. **No MCP / plugin.** The fetch + persistence already exist internally.
2. **No live-path edit** under this scope (§15 boundary intact).
3. If/when the operator wants to attack net edge *with real data*, the unit of work is
   a **read-only fills↔journal reconciliation diagnostic** under `backend/diagnostics/`
   (own Plan-agent pass, blast-radius map, §16 audit) — and it only yields signal once
   a live session has populated the fills log.
4. **For the current paper posture**, the only lever on edge-after-fees is tightening
   the *model* (the risk_engine round-trip floor / TP1 reachability clamp — already the
   live VERIFY-NEXT item), not ingesting data that paper mode cannot produce.

## Blast radius (for the future reconciliation diagnostic — not built here)

- Reads: fills log (`_fills_log_path` schema, line 644-657), `trade_journal.jsonl`
  (canonical keys → `db_contracts.json`). No writes to either.
- Touches no `engine/` `strategy/` `services/` `bot/` runtime path → no contract diff.
- Upstream callers / downstream consumers: none (new standalone diagnostic).
