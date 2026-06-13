# 2026-06-13 — Fill-geometry distortion: realized-RR floor + honest journal RR

## Problem (root cause, confirmed in code — not inferred)

A snap_taker (market) entry fills at whatever the tape is doing when the order is
placed, which can be materially away from the plan's entry. The plan's stop/target
levels and recorded `risk_reward_ratio` are **not** recomputed against the actual
fill, so a position can open with inverted geometry while the journal records the
planned (optimistic) numbers.

Mechanism:

- Planned RR is computed off `entry_zone.midpoint`
  ([planner.py:260-266](../../shared/models/planner.py#L260)).
- `PositionState`/journal open at `entry_price = fill.price`
  ([position_manager.py:412-442](../../bot/executor/position_manager.py#L412)),
  but `stop_loss`, `targets`, `risk_reward_ratio`, `stop_distance_atr`,
  `tp1_realized_rr` are **copied from the plan unchanged**.
- The LIMIT-SNAP block
  ([paper_trading_service.py:2327-2358](../../bot/paper_trading_service.py#L2327))
  already recomputes **position size** to hold $-risk constant when it snaps the
  entry toward current price — but it does **nothing** for the **reward** side. If
  the snap pushes the entry toward a nearby TP1, reward-to-target collapses while
  risk-to-stop widens, inverting RR (observed: planned 2.09 → realized 0.29 on
  ADA/USDT_1781273754, session 2d4b8e97).

The journal then records the planned RR (2.09), masking the distortion — which also
poisons the TP1-reachability-clamp VERIFY-NEXT data
([[project_longbook_degradation_fix]], [[project_planner_reason_mask]]).

## Baseline (measure-before-build, §16 Rubric 5)

`entry_rr_distortion.py` over `trade_journal.jsonl` (n=101 trades with computable
geometry, all sessions):

| metric | value |
|---|---|
| realized RR median | 1.47 (recorded median 2.19 — systematic optimism) |
| realized RR < 1.0 | 33/101 (33%) |
| realized < 50% of recorded | 38/101 (38%) |
| avg PnL, realized RR < 1.0 | **−1.27** (n=33) |
| avg PnL, realized RR ≥ 1.0 | **+5.02** (n=68) |

Realized RR = reward-to-nearest-target / risk-to-stop, both measured from the actual
fill. The < 1.0 cohort is net-negative; the ≥ 1.0 cohort carries the book. The
breakpoint at **RR = 1.0** is the data-driven floor.

## Decision

**A (observability, no behavior change):** add a `realized_rr` key to the journal
(`CompletedTrade.to_dict()`), computed from the stored fill/stop/target. Makes every
future row honest about its as-filled geometry. Shared dataclass → covers paper +
live journals.

**B (execution behavior):** reject an entry whose realized RR at the actual fill
(snapped `limit_price`) falls below `config.rr_floor_at_entry` (default **1.0**),
reason code `rr_collapsed_at_entry`. The signal was approved on its planned edge;
once execution inverts the geometry that edge is gone. Symmetric across LONG/SHORT
(abs-based). Gate sits after the limit snap, before `place_order`, and measures realized
RR off `limit_price` (the actual fill in every mode) — see the reference-point note below.

The gate measures realized RR off `limit_price` — the **actual fill price** in every
mode (snap_taker snaps toward market; rest_maker/no-snap rests at `near_entry`). This is
deliberately NOT the planner's RR reference (`entry_zone.midpoint`): the point of the fix
is that the midpoint-based planned RR lies about the as-filled geometry. Consequence: a
rest_maker fill at `near_entry` (the OB edge nearest target / farthest from stop) reads
structurally lower than its midpoint-based planned RR, so the gate **can** fire on a
rest_maker entry — this is correct, not a false reject, because `near_entry` IS that
position's real geometry. The floor=1.0 baseline above was computed off actual journal
fills, i.e. the same basis the gate uses, so gate and baseline are self-consistent.

Single source of truth: module-level `_entry_realized_rr(entry, stop, targets)` used
by both the gate and the journal so the math cannot drift.

## Blast radius

- **B rejects ~33% of historically-taken trades** (the net-negative cohort). This is
  a material change to which trades execute. Accepted by operator (2026-06-13,
  "A + B now"). The floor is config-exposed (`rr_floor_at_entry`) so it is tunable
  without a code change; 0 disables.
- `realized_rr` is a new JSONL canonical key, additive on `CompletedTrade.to_dict()`.
  It does NOT appear in `db_contracts.json` and the contract diff stays CLEAN: the
  capture tool sniffs JSONL keys from the **first line** of `trade_journal.jsonl`
  ([capture_contracts.py:234](../capture_contracts.py#L234)), which is a legacy
  pre-`realized_rr` row. Re-baselining now would not capture the key either (the first
  row is unchanged), so the baseline is intentionally left as-is. The key is purely
  additive and downstream-safe (additive keys break no consumer). If the JSONL contract
  is ever switched to a union-of-keys or latest-row sniff, `realized_rr` should be
  accepted at that point. Not a contract regression.
- No change to scorer/orchestrator/regime/SMC. No new endpoint. No EventType added
  (reject uses existing `_log_signal`/`_log_activity` plumbing).

## Live-path mirror (REQUIRED before any live deploy — NOT done in this diff)

The bot production mode is STEALTH = paper today
([[feedback_bot_hard_restart_required]]), so the paper entry path IS the live-relevant
path. `live_trading_service.py` has its own entry/order-placement path that does **not**
yet carry the B gate. Mirroring B into the LiveExecutor path is real-money and gets its
own design-entry sign-off (§15). `realized_rr` (A) already covers the live journal via
the shared `to_dict`. Tracked as open follow-up.

## Verify-next

- Run a paper session post-fix; confirm `rr_collapsed_at_entry` appears in
  `signals.jsonl` rejects and `realized_rr` populates journal rows.
- Re-run `entry_rr_distortion.py --since <session>`: the realized-RR<1.0 share of
  *executed* trades should drop toward 0 (rejected pre-fill); survivors' realized_rr
  should track recorded RR far more closely.
