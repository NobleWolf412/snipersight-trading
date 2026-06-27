# §15 DESIGN ENTRY — fresh-price entry geometry (plan→fill staleness root fix)

**STATUS: DESIGN — AWAITING OPERATOR APPROVAL. No code lands until this is signed off.**
Touches `entry_engine.py` + the orchestrator plan path, which are **SHARED WITH THE LIVE
TRADING PATH** → CLAUDE.md §15 requires a documented design entry + explicit approval before
any code change. This is that entry.

---

## 1. Problem (observed)

Heart-change thesis trades now reach the execution stage but die on plan→fill staleness:
- **Form A** `revalidation_entry_above/below_price` (BTC LONG: buy-the-dip zone `[62637–62814]`
  ended up ABOVE a price that fell to `60887` → blown-through zone).
- **Form B** `rr_collapsed_at_entry` (SOL SHORT: planned RR 2.70 → realized 0.60 after the limit
  snap chased the entry toward market, preserving $-risk but not reward).

## 2. Root cause (from the plan→fill investigation, 2026-06-24)

Entry geometry — OB selection, near/far entry, stop, TP1 — is computed against
`_get_current_price(multi_tf_data)` (`orchestrator.py:~3870`) = **the most recent candle CLOSE
from the scan-time OHLCV snapshot**, which on 15m/1h candles can be **minutes old**. The entry is
a **retrace/limit zone** (an order block away from market). In any moving window the zone is
stranded by fill time. The gates (`max_entry_drift_pct=0.15`, `rr_floor_at_entry=1.0`) are
**reporting truth, not misfiring** — they correctly reject blown-through / reward-collapsed
entries. So the fix is at the **price-freshness layer**, NOT the tolerances. (Loosening tolerances
to force fills = the wet bandaid §11.6 warns against — it admits dead-edge trades.)

## 3. Proposed change

Compute the entry geometry against a **FRESH ticker fetched at plan time**, not the stale
scan-time candle close. The orchestrator already fetches a fresh `fetch_ticker` at post-plan
revalidation (`orchestrator.py:~3442`) — this moves that freshness **earlier**, so OB selection
and zone placement reflect current price and fewer zones are stranded before they're even built.

Mechanism (high level):
1. At plan-generation start (orchestrator `_generate_trade_plan`, before `entry_engine`), fetch a
   fresh `last`/`close` tick (same call the revalidation already uses; reuse one fetch).
2. Pass that fresh price as the `current_price` reference into `entry_engine._calculate_entry_zone`
   (and stop/target derivation) **in place of** the stale candle close.
3. The OBs themselves are unchanged (they're structural, from the candle data) — only the
   **selection reference + proximity/distance calcs** become current. A bullish OB that is now
   ABOVE the fresh price stops qualifying as a buy-the-dip long (correct), so we don't place a
   zone price has already fallen through.

This SHRINKS the stale window (does not eliminate it — cascade/planner/fill still take time, so
the revalidation gate stays as the residual-drift backstop). Goal: fewer stranded zones, more
valid fills, WITHOUT touching the gates or admitting dead-edge trades.

## 4. Gating (keeps live byte-identical until validated)

**Flag-gated, default OFF**, same discipline as the heart-change. Proposed flag:
`SS_FRESH_ENTRY_PRICE` (env var, no config/contract field). When unset/off, the entry geometry
uses the stale candle close exactly as today → **live path byte-identical**. Enable in paper,
validate forward, only then consider promoting to default/live. This bounds the §15 risk: the
shared code is touched, but the live BEHAVIOR is unchanged until the flag is deliberately set.

## 5. Blast radius (§20)

**Upstream** (who triggers entry-geometry computation):
- `orchestrator._generate_trade_plan` (paper + scanner) — the fresh-fetch insertion point.
- `_cascade_plan_generation` → `_generate_trade_plan` per scale.
- Live path: `live_trading_service` builds entries via the **same `entry_engine`** → **SHARED.**

**Downstream** (who consumes the entry zone):
- Planner stop/target/RR derivation; the limit snap; the post-plan revalidation; the executor fill.
- Journal `entry_zone`/`realized_rr` keys (unchanged shape — only the values shift when flag on).

**Shared-with-live confirmation:** `entry_engine.py` feeds both paper and live. The fresh-price
reference therefore changes LIVE entry geometry too **when the flag is on**. With the flag off,
both paths are byte-identical to today. No live session is currently active (STEALTH = paper), but
the code is shared, so the change must be correct for both and is gated accordingly.

**Contracts:** env-var flag → no SniperContext/ScanConfig field, no API/telemetry/DB schema change
→ contract diff clean. (Same pattern as `SS_DECISION_POLICY`.)

## 6. Risks + mitigations

- **R1: changes live entry geometry (§15 core risk).** Mitigation: flag default-off → live
  byte-identical until deliberately enabled; promotion to live is a SEPARATE future approval.
- **R2: fresh tick adds an exchange call per plan (latency/rate-limit).** Mitigation: reuse the
  fetch the revalidation already does (net-zero extra calls — move it earlier, don't duplicate);
  fall back to the stale candle close on fetch failure (loud log, never silent).
- **R3: a fresh tick is noisier than a candle close (a wick could mis-place a zone).** Mitigation:
  use `last`/`mark` consistently; the OB structure (not the tick) still anchors the zone — the tick
  only selects/references. Forward-observe whether fills degrade.
- **R4: fewer entries qualify (a now-above OB stops being a valid long).** This is the INTENDED
  effect (don't chase blown-through zones) — measured as a feature, not a regression.

## 7. What this does NOT change
- The drift tolerances (`max_entry_drift_pct`, `max_entry_drift_atr`) — left as-is.
- The RR floor (`rr_floor_at_entry=1.0`) — left as-is (empirically calibrated).
- The OB detection / SMC structure — unchanged.
- The limit-snap reward-blindness (Form B) — addressed SEPARATELY (the paper-only snap-RR-bound,
  option 1 from the 2026-06-24 discussion; still available, not in this entry).

## 8. Alternatives considered
- **(A) Loosen tolerances** — REJECTED (bandaid; admits dead-edge trades; gates report truth).
- **(B) Recompute the zone at revalidation instead of rejecting** — REJECTED (a recomputed entry
  is a different trade than was scored; muddies attribution; still stale by fill).
- **(C) Market entries instead of retrace limits** — DEFERRED (bigger execution-semantics change,
  abandons the SMC retrace edge, larger §15 surface). Fresh-price is the minimal root fix.

## 9. Validation plan
Enable `SS_FRESH_ENTRY_PRICE=1` in a paper session (alongside `SS_DECISION_POLICY=thesis`).
Measure: does the rate of `revalidation_entry_above/below_price` (form A) drop? Do valid fills
appear? Forward-track fill quality (realized vs planned RR). No promotion to live default until a
clean paper sample + (eventually) the per-cell Deflated-Sharpe gate.

## 10. Open questions for operator review
1. Approve the **flag-gated, default-off** approach (live byte-identical until enabled)? 
2. OK to **reuse/move the existing revalidation fetch** earlier (net-zero extra exchange calls)?
3. Should the fresh-price fix be **coupled to `SS_DECISION_POLICY=thesis`** (one flag) or its own
   independent `SS_FRESH_ENTRY_PRICE` flag (decouples the two experiments)?
4. Confirm the **limit-snap RR-bound (Form B, paper-only)** is handled separately, not here.

---

## 11. IMPLEMENTATION RECORD (operator-approved 2026-06-26)

Built behind `SS_FRESH_ENTRY_PRICE` (default off, independent of `SS_DECISION_POLICY`). Injection at
the orchestrator plan-gen dispatch (`_process_symbol`); `_fetch_fresh_price` helper. Deviations &
hardening from the original design, all operator-approved:

- **+1 fetch ACCEPTED (not net-zero, R2 revised):** the revalidation keeps its own inline fetch; the
  plan-time fetch is an additional ccxt `fetch_ticker`, only on the plan-gen path, flag-on only.
  Operator accepted the +1 over touching the shared revalidation.
- **OUTLIER GUARD added (adversarial-review hardening):** `current_price` is an OB-SELECTION filter
  downstream (entry_engine `max_pullback_atr`), so a big/painted fresh tick could swap the scored OB
  or flip to a market chase. The fresh price is now used ONLY when within `fresh_entry_max_dev_atr`
  (default 1.0) × primary-TF ATR of the candle close; otherwise it falls back to the close (loud
  WARNING) and the existing revalidation handles any stranded zone. This resolves the scored-vs-
  planned-OB divergence and the painted-tick steering for the dangerous (>1·ATR) cases.

### Gate results
- symmetry-guard PASS (guard direction-agnostic via abs(); flag-off byte-identical; ATR is the
  ABSOLUTE IndicatorSet.atr, not the percentage-ATR standing-fix trap).
- backend-integrity CLEAN (flag-off live byte-identical; flag-ON changes live entry geometry too —
  documented; no contract change).
- adversarial-review CHALLENGE → resolved to "ship-behind-flag-for-paper, ZERO must-fix." Challenges
  2 & 3 closed for the dangerous cases.

### PRE-LIVE-PROMOTION conditions (NOT required for paper; required before SS_FRESH_ENTRY_PRICE
### becomes a live default — a separate approval):
1. **Cross-TF ATR:** the guard reads PRIMARY-TF ATR while the OB filter uses ENTRY-TF ATR. Moot for
   STEALTH (primary 1h ≈ entry), but in STRIKE/SURGICAL (5m/15m entries) the guard is looser than
   "1·ATR" implies. Either switch the guard to entry-TF ATR or a percentage bound before live.
2. **Integration coverage:** the pure predicate `_fresh_within_guard` is unit-tested; add an
   integration assertion that a >1·ATR fresh tick lands `plan_price == current_price` at the
   injection site before live.
3. **Residual:** a sub-1·ATR painted tick can still nudge OB selection at a boundary OB — small but
   invisible; consider logging scored-OB-vs-planned-OB identity to make a re-anchor that swaps the
   OB observable.

**On approval:** implement behind the flag, with symmetry-guard + backend-integrity +
adversarial-review + a regression test, default-off proven byte-identical, before any commit. ✅ DONE.
