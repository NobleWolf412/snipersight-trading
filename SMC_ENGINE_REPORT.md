# SniperSight SMC Detection Engine Diagnostic
**Generated:** 2026-03-22
**Scope:** `backend/strategy/smc/` — all detection modules
**Files reviewed:** `order_blocks.py`, `fvg.py`, `liquidity_sweeps.py`, `bos_choch.py`, `sessions.py`

---

## 🔴 Critical Issues

### 1. Kill Zone UTC→EST Conversion Is Inverted — All Times Are Wrong by 10 Hours

**File:** `sessions.py` — `get_current_kill_zone()` and `get_current_session()` (lines 153–159)

```python
est_offset = timedelta(hours=-5)
timestamp = (
    timestamp.replace(tzinfo=None)
    + (timestamp.utcoffset() or timedelta(0))
    - est_offset   # <-- THIS IS THE BUG
)
```

For a UTC-aware datetime, `timestamp.utcoffset()` returns `timedelta(0)`. The formula becomes:

```
converted = utc_naive + timedelta(0) - timedelta(-5)
          = utc_naive + timedelta(+5)       # Adds 5 hours ← WRONG
```

**Intended:** UTC → EST = subtract 5 hours. **Actual:** adds 5 hours (produces UTC+5 time).

The result is every kill zone fires **10 hours off** from when it should. Concretely:

| Kill Zone | Should fire (UTC) | Actually fires (UTC) |
|-----------|-------------------|----------------------|
| London Open (EST 02:00–05:00) | 07:00–10:00 UTC | 21:00–00:00 UTC |
| NY Open (EST 07:00–10:00) | 12:00–15:00 UTC | 02:00–05:00 UTC |
| Asian Open (EST 19:00–22:00) | 00:00–03:00 UTC | 14:00–17:00 UTC |

This explains why your scorer shows Kill Zone = 0 even during market-active hours — the entire detection system is offset by half a trading day. This also means the +25 point kill zone bonus was never correctly rewarding genuine high-probability time windows.

**The fix:** change `- est_offset` to `+ est_offset`:
```python
timestamp = timestamp.replace(tzinfo=None) + (timestamp.utcoffset() or timedelta(0)) + est_offset
```

---

### 2. FVG `size_atr` Attribute Is Never Set — Size Bonus Is Dead Code

**File:** `fvg.py` (FVG creation, lines 154–165 and 200–211)
**Impact:** Scorer `_score_fvgs_incremental()` line 3003

Every FVG is created with only `size` (absolute price difference), never with `size_atr` (ATR-normalized size):

```python
fvg = FVG(
    timeframe=..., direction="bullish", top=..., bottom=...,
    size=gap_size,          # ← absolute size, set
    overlap_with_price=0.0,
    freshness_score=1.0,
    grade=grade,
    # size_atr is NEVER SET
)
```

The scorer's size bonus:
```python
if getattr(best_fvg, "size_atr", 0.0) > 1.0:
    score += 15.0  # ← NEVER fires
```

This +15 is permanently dead. The practical impact: a Grade B unfilled FVG scores `30 + 20 = 50` — exactly at the quality threshold for coverage penalty avoidance. With the size bonus firing on any significant gap (>1 ATR, which is common in impulsive moves), that becomes 65 — a solid quality factor. Without it, every FVG in the system is on the razor edge of passing the coverage check and will fail it whenever a single candle moves the grade down.

---

## 🟡 High Impact Issues

### 3. `check_price_overlap` Measures Position in Gap, Not Fill Percentage

**File:** `fvg.py` line 315 — `check_price_overlap()`

The function name and the way it's used are misaligned. It calculates how far **into** the gap the current price is (0.0 = at gap bottom, 1.0 = at gap top), not how much of the gap has been "filled" over time.

In `detect_fvgs()`, this gets stored as `overlap_with_price`:
```python
overlap = check_price_overlap(current_price, fvg)
fvgs[i] = replace(fvg, overlap_with_price=overlap, ...)
```

In `_score_fvgs_incremental()` (scorer, line 2999):
```python
elif best_fvg.overlap_with_price > 0.5:
    score -= 15.0  # "Filled >50%"
```

And in `evaluate_htf_structural_proximity()` (scorer, line 623):
```python
if fvg.overlap_with_price > 0.5:
    continue  # Skip this FVG
```

**The problem:** a bullish FVG where price is currently at the **midpoint of the gap** (meaning price is trading right in the middle of the demand zone — an ideal entry position) returns `overlap_with_price = 0.5`. The scorer then treats this as ">50% filled" and penalizes or skips it. You're actively penalizing price being precisely at the best entry within the FVG.

The fill check that `check_fvg_fill()` (line 342) performs — checking if price has traversed entirely through the gap — is different logic. These two concepts need to be separate fields. The scorer is using position-in-gap as a proxy for historical fill, and they aren't the same thing.

---

### 4. `_infer_timeframe()` Called Inside OB Creation Loop — O(n²) Performance

**File:** `order_blocks.py` lines 276 and 358

```python
ob = OrderBlock(
    timeframe=_infer_timeframe(df),   # ← O(n) call
    ...
)
```

`_infer_timeframe()` recalculates the entire index delta series every time:
```python
time_deltas = df.index.to_series().diff().dropna()
avg_delta = time_deltas.mean()
```

This is called inside the main scan loop (`for i in range(20, len(df) - lookback_candles)`), once per detected OB. With a 500-bar DataFrame and 20 OBs, that's 20 × O(500) = 10,000 operations just for timeframe inference. Scale that across multi-timeframe, multi-symbol scanning (OVERWATCH scans hundreds of symbols) and you have meaningful scan latency from this alone.

The timeframe is constant for a given DataFrame — it should be inferred once at the top of `detect_order_blocks()` and reused.

---

### 5. OVERWATCH/STEALTH Volume Requirement Silently Drops Legitimate BOS

**File:** `bos_choch.py` — `MODE_VOLUME_REQUIREMENTS` and the filter inside `detect_structural_breaks()`

```python
"macro_surveillance": {
    "require_volume": True,
    "min_volume_ratio": 1.5,  # 1.5x average required for BOS
    "apply_to": ["BOS"],
},
"stealth_balanced": {
    "require_volume": True,
    "min_volume_ratio": 1.3,
    "apply_to": ["BOS", "CHoCH"],  # Both need volume
},
```

Volume on crypto exchanges is notoriously noisy and exchange-specific. Real institutional BOS moves frequently happen with average or below-average on-chain/exchange volume while total market volume is high (split across exchanges). If OVERWATCH silently drops a BOS because it happened on a 1.4x volume candle (just below 1.5x threshold), the swing structure state machine loses track of current structure. Downstream: the scorer's Market Structure factor gets 0, FVGs tagged to that BOS don't get graded, and OBs derived from that break don't exist.

There's no logging when a BOS is rejected for volume — it just silently `continue`s. This is a debugging black hole.

---

### 6. OB Range Is Median-Based — Tighter Zones Miss More Price Checks

**File:** `order_blocks.py` lines 273–280 (bullish) and 352–358 (bearish)

```python
# Bullish OB: low to median (not low to high)
median_price = (candle["high"] + candle["low"]) / 2
ob = OrderBlock(high=median_price, low=candle["low"], ...)

# Bearish OB: median to high (not low to high)
ob = OrderBlock(high=candle["high"], low=median_price, ...)
```

The LuxAlgo-style tighter zone is intentional — it focuses on where institutional orders actually were (not the full wick range). But it has a cascade effect:

- `check_mitigation()` determines mitigation % based on how far price re-entered `ob.low` to `ob.high`. A narrower zone means partial mitigation fires sooner.
- `evaluate_htf_structural_proximity()` checks `if ob.low <= entry_price <= ob.high` to give distance_atr = 0. With the narrower zone, price needs to be more precisely centered in the OB to get credit for "at the level."
- `_score_order_blocks_incremental()` penalizes `mitigation_level > 0.5` with -10 points. Narrower zones reach that threshold faster.

This is a trade-off, not necessarily a bug, but it's worth being explicit: the tighter zone increases precision but also increases the rate at which OBs are considered "mitigated" and filtered out, contributing to fewer valid OBs in the scanner output.

---

## 🟡 Medium Impact Issues

### 7. OB Freshness Scale Is 0–100, FVG Freshness Scale Is 0.0–1.0

**File:** `order_blocks.py` line 688 vs `fvg.py` line 227

```python
# OBs — 0 to 100 scale
return freshness * 100.0   # order_blocks.py:688

# FVGs — 0.0 to 1.0 scale
freshness = max(0.0, 1.0 - (candles_since * decay_factor))  # fvg.py:227
```

The scorer doesn't directly compare these fields against each other, but `filter_obs_by_mode()` in `order_blocks.py` compares OB freshness against thresholds like `40.0` (for OVERWATCH). If someone wrote a similar filter for FVGs using the same threshold, an FVG with freshness=0.4 (meaning 40% remaining) would be compared to 40.0 and wrongly filtered out.

Additionally: in `evaluate_htf_structural_proximity()`, the proximity gate checks:
```python
if ob.freshness_score < 0.5:
    continue  # Skip stale OBs
```
For OBs, freshness is 0–100, so `< 0.5` means "essentially expired" (less than 0.5/100). That's intentional. But if this same code accidentally processed an FVG, `< 0.5` would filter out any FVG more than halfway through its life. The scale inconsistency is a latent bug waiting to trip on any code that handles both types.

---

### 8. BOS Detection Updates `last_swing_high` with Raw Candle High, Not True Swing High

**File:** `bos_choch.py` lines 374–376

```python
# After detecting a bullish BOS:
last_swing_high = current_high  # Breaking candle's raw high
```

After a BOS, the structural reference level is reset to the breaking candle's full high, not the next properly formed swing high. The breaking candle's high is often an elevated momentum candle with a significant wick. Setting this as the new reference means the next BOS requires closing above that inflated level.

Result: after strong impulsive BOS moves, the scanner can get "stuck" and fail to detect subsequent valid structure breaks because the reference bar was set from an anomalously high candle. The proper approach is to wait for the next confirmed swing high.

---

### 9. OB Mitigation Check Scans All Future Candles — O(n²) Worst Case

**File:** `order_blocks.py` — `check_mitigation()` lines 490–539

```python
future_candles = df[df.index > ob.timestamp]
# Then scans all of them
lowest_revisit = future_candles["low"].min()
```

This is called in the update loop at lines 372–387 for every detected OB. For a 1,000-bar DataFrame with 30 OBs, that's 30 × O(1,000) minimum operations. The `check_mitigation_enhanced()` version (line 542) is worse — it iterates candle-by-candle in a Python loop rather than using vectorized pandas operations.

For OVERWATCH mode scanning daily/weekly bars where OBs can span months of history, this becomes the dominant performance bottleneck. The `check_mitigation_enhanced()` function could be replaced with a vectorized pandas approach in a fraction of the time.

---

## 📊 Cascade Summary: How Engine Bugs Reach the Scorer

The detection issues don't just affect individual factors — they cascade through the pipeline:

```
Kill Zone UTC bug (10h offset)
  → KZ always fires at wrong session
    → KZ factor scores 0 (or wrong session gets credit)
      → Coverage penalty triggered (one less quality factor)

FVG size_atr missing
  → FVG scores Grade B + Virgin = 50 (at quality floor)
    → Any additional penalty or overlap pushes FVG below 50
      → Coverage penalty triggered again

BOS volume filter drops legitimate structure
  → Market Structure factor gets 0
    → Structural minimum gate fires (swing modes)
      → Raw score hard-capped at ~60
        → OVERWATCH threshold 78 = automatic rejection

OB median zones + aggressive mitigation
  → More OBs filtered before reaching scorer
    → ob_score = 0 for valid direction
      → Structural minimum gate fires
        → Same cascade as above
```

---

## ✅ Fixes in Priority Order

**Fix 1: Kill Zone UTC conversion (sessions.py)**
Change `- est_offset` to `+ est_offset` on line 158. One character change that corrects 10 hours of timing error across all kill zone scoring.

**Fix 2: Set `size_atr` on FVG construction (fvg.py)**
After computing `gap_atr` (already calculated for the size filter), pass it to the FVG constructor: `size_atr=gap_atr`. This immediately enables the +15 scorer bonus for significant gaps.

**Fix 3: Separate FVG fill tracking from price position (fvg.py)**
Add a separate field `fill_pct` that tracks what percentage of the gap has been historically filled by wicks, distinct from `overlap_with_price` (current price position). Update the scorer to use `fill_pct > 0.5` for the fill penalty and keep `overlap_with_price` as the position indicator.

**Fix 4: Cache `_infer_timeframe` result (order_blocks.py)**
Calculate `inferred_tf = _infer_timeframe(df)` once at the top of `detect_order_blocks()` and pass it directly to each `OrderBlock()` constructor. Same for `detect_fvgs()` and `detect_liquidity_sweeps()`.

**Fix 5: Add logging when BOS is rejected for volume (bos_choch.py)**
Before `continue` in the volume filter: `logger.debug("BOS rejected for insufficient volume: ratio=%.2f < %.2f required (%s mode)", volume_ratio, vol_req["min_volume_ratio"], mode_profile)`. This alone will make the debugging visible in the scan logs.

**Fix 6: Standardize freshness scale to 0–100 (fvg.py)**
Change FVG freshness calculation to return `min(100.0, max(0.0, (1.0 - candles_since * decay_factor) * 100.0))` to match the OB scale. All downstream threshold checks can then use the same numbers.

---

*SMC engine diagnostic complete. The kill zone UTC bug (Fix 1) and FVG size_atr missing (Fix 2) are the two changes with the highest immediate signal-rate impact.*
