# Swing-Based Stop Fallback - Complete ✅

**Status**: Planner enhanced with swing-level fallback for stop loss placement

## Executive Summary

Added swing-based stop loss calculation as a fallback mechanism when SMC structures are unavailable. This expands the tradeable signal universe while preserving the "no structure = no trade" philosophy by defining structure more broadly.

---

## Implementation Overview

### Stop Loss Hierarchy
**Before**: SMC structure → reject
**After**: SMC structure → swing levels → reject

```
Priority Order:
1. SMC Structure (Order Blocks, FVGs) - IDEAL
2. Swing Highs/Lows from primary timeframe - FALLBACK
3. Reject trade - NO VALID INVALIDATION POINT
```

### Design Philosophy
- **No arbitrary ATR-only stops**: Maintained strict requirement for price-based invalidation
- **Structure definition broadened**: Swing levels are structural (local extremes), not mathematical
- **Context-aware**: Uses primary planning timeframe for swing detection
- **Conservative by default**: 20-bar lookback with 2-bar confirmation on each side

---

## Technical Implementation

### New Function: `_find_swing_level()`
**Location**: `backend/strategy/planner/planner_service.py`

```python
def _find_swing_level(
    is_bullish: bool,
    reference_price: float,
    candles_df: pd.DataFrame,
    lookback: int = 20
) -> Optional[float]:
    """
    Find swing high or swing low from price action.
    
    Swing Detection Logic:
    - Swing Low: Bar where low < 2 bars before AND < 2 bars after
    - Swing High: Bar where high > 2 bars before AND > 2 bars after
    
    Returns:
        - For bullish: Highest swing low below reference (closest to entry)
        - For bearish: Lowest swing high above reference (closest to entry)
        - None if no clear swing found
    """
```

**Algorithm**:
1. Search last 20 bars of primary timeframe
2. Identify local extremes (2-bar confirmation window)
3. Filter by direction (below entry for bullish, above for bearish)
4. Return closest valid swing to entry price

### Updated Function: `_calculate_stop_loss()`
**Changes**:
- Added `multi_tf_data: Optional[MultiTimeframeData]` parameter
- Fallback logic after SMC structure check fails
- Logs swing fallback usage for telemetry
- Preserves plan composition tracking (structure vs non-structure)

**Bullish Trade Logic**:
```python
# 1. Try SMC structure (OBs, FVGs below entry)
if valid_stops:
    stop_level = max(valid_stops) - (0.3 * atr)
    rationale = "Stop below entry structure invalidation point"
    used_structure = True

# 2. Fallback: swing low from primary timeframe
else:
    swing_level = _find_swing_level(is_bullish=True, ...)
    if swing_level:
        stop_level = swing_level - (0.3 * atr)
        rationale = "Stop below swing low on {primary_tf} (no SMC structure)"
        used_structure = False
    
    # 3. Reject if no swing found
    else:
        raise ValueError("No structure or swing level for stop loss")
```

**Bearish Trade Logic**: Mirror logic with swing highs above entry

### Integration Updates

#### 1. Planner Service Signature
**File**: `backend/strategy/planner/planner_service.py`
```python
def generate_trade_plan(
    # ... existing params ...
    multi_tf_data: Optional[MultiTimeframeData] = None  # NEW
) -> TradePlan:
```

#### 2. Orchestrator Integration
**File**: `backend/engine/orchestrator.py`
```python
plan = generate_trade_plan(
    # ... existing params ...
    multi_tf_data=context.multi_tf_data  # Pass candles for swing calculation
)
```

---

## Behavior Changes

### Signal Generation Impact
**Expected Outcome**: Increased valid signal yield

**Scenario A - Before**: 
- Setup detected, SMC confluence good
- No clear OB/FVG near entry → **REJECTED**

**Scenario A - After**:
- Setup detected, SMC confluence good
- No clear OB/FVG near entry
- Swing low found at recent support → **ACCEPTED** (with swing-based stop)

**Quality Gate**: Swing-based stops still require:
- Minimum distance validation (min_stop_atr)
- Maximum distance validation (max_stop_atr)
- R:R threshold passes
- Must be beyond local structure (not arbitrary)

### Plan Composition Tracking
**`plan_composition['stop_from_structure']`**:
- `True`: SMC structure used (OB/FVG)
- `False`: Swing level used (fallback)

This flag enables downstream filtering if needed (e.g., "SMC-only mode" could filter out swing-based plans).

---

## Configuration

### Swing Detection Parameters
**Hardcoded** (can be made configurable later):
```python
lookback = 20       # Bars to search back
confirmation = 2    # Bars on each side for local extreme
buffer = 0.3 * ATR  # Safety buffer beyond swing level
```

### Mode Integration
Uses `config.primary_planning_timeframe` for swing detection:
- **Surgical (15m)**: 20-bar lookback = ~5 hours of price action
- **Recon (4H)**: 20-bar lookback = ~3 days of price action
- **Overwatch (4H)**: 20-bar lookback = ~3 days of price action

Timeframe matters: Higher TF swing levels are more significant but may be farther from entry.

---

## Testing Recommendations

### Unit Tests
```python
# Test swing detection
def test_find_swing_level_bullish():
    df = create_mock_ohlcv_with_swing_low()
    swing = _find_swing_level(is_bullish=True, reference_price=50000, candles_df=df)
    assert swing is not None
    assert swing < 50000

def test_find_swing_level_no_swing():
    df = create_trending_candles()  # No clear swings
    swing = _find_swing_level(is_bullish=True, reference_price=50000, candles_df=df)
    assert swing is None

# Test fallback hierarchy
def test_stop_loss_smc_priority():
    # If SMC structure exists, should use it over swing
    plan = generate_trade_plan(...)
    assert "structure invalidation" in plan.stop_loss.rationale

def test_stop_loss_swing_fallback():
    # If no SMC structure, should use swing
    plan = generate_trade_plan_no_smc(...)
    assert "swing" in plan.stop_loss.rationale.lower()
```

### Integration Tests
- Generate plan with SMC → verify SMC stop used
- Generate plan without SMC but with swings → verify swing stop used
- Generate plan with neither → verify rejection
- Verify swing-based plans pass R:R thresholds

---

## Telemetry Integration

### Log Events
**When Swing Fallback Activates**:
```
INFO: No SMC structure for stop - attempting swing-based fallback on 4H
INFO: Using swing-based stop: 48523.5
```

**When Swing Fallback Fails**:
```
WARNING: No swing level found - rejecting trade
```

### Metrics to Track
- **Swing fallback usage rate**: % of plans using swing vs SMC stops
- **Swing-based plan performance**: Do swing stops perform differently?
- **Rejection reduction**: % decrease in "no structure" rejections

---

## Plan Type Classification

### Impact on `plan_type`
Swing-based stops use `plan_type = "ATR_FALLBACK"` or `"HYBRID"` classification:
- If entry also lacks SMC structure → `"ATR_FALLBACK"`
- If entry has SMC but stop doesn't → `"HYBRID"`

This flows into R:R matrix validation:
- **ATR_FALLBACK**: min_rr=1.0, ideal_rr=1.8
- **HYBRID**: min_rr=1.2, ideal_rr=2.0

### Conviction Classification
Swing-based plans can achieve **Class B** conviction (capped, never A):
- Requires: R:R ≥ 1.0 + confluence ≥ 60%
- Cannot reach Class A (no SMC structure)

---

## Edge Cases Handled

### 1. Insufficient Candle Data
```python
if candles_df is None or len(candles_df) < 5:
    return None
```
Graceful fallback: treat as no swing found → continue to rejection

### 2. Trending Markets (No Swings)
Strong directional moves may not create local extremes.
**Behavior**: No swing found → reject trade
**Rationale**: If price isn't pausing, no structural invalidation point exists

### 3. Swing Too Far from Entry
Swing levels pass through sanity gates:
- `max_stop_atr`: If swing is 8 ATR away, still rejected
- R:R threshold: If swing creates R:R < min_rr, rejected

### 4. Multiple Swings Found
**Selection logic**:
- Bullish: Use highest swing low (closest to entry)
- Bearish: Use lowest swing high (closest to entry)

---

## Performance Considerations

### Computational Cost
**Swing detection**: O(lookback) iteration over 20 bars
- Negligible compared to SMC detection overhead
- Happens only when SMC structure unavailable (minority of cases)

### Memory Usage
No additional storage—operates on existing `multi_tf_data.timeframes[primary_tf]` dataframe.

---

## Future Enhancements

### 1. Configurable Confirmation Window
```python
# Currently hardcoded
confirmation_bars = 2

# Could be mode-specific
surgical_mode: confirmation_bars = 1  # Tighter swings
overwatch_mode: confirmation_bars = 3  # More significant swings
```

### 2. HTF Structure Fallback (Third Layer)
If primary TF has no swings, check higher TF for structure:
```
SMC on primary → Swing on primary → SMC on HTF → Swing on HTF → Reject
```

### 3. Swing Strength Scoring
Weight swing levels by:
- Volume at swing point (higher volume = stronger level)
- Number of touches (tested swing = stronger support/resistance)
- Age of swing (recent swings may be more relevant)

### 4. Adaptive Lookback
```python
# Base lookback on volatility regime
if high_volatility:
    lookback = 15  # Shorter memory in choppy markets
else:
    lookback = 30  # Longer memory in stable trends
```

---

## Migration Notes

### Backward Compatibility
**100% backward compatible**:
- `multi_tf_data` parameter is optional (defaults to `None`)
- If not provided, behavior is identical to before (SMC → reject)
- Existing callsites continue working unchanged

### Orchestrator Auto-Wiring
Orchestrator automatically passes `context.multi_tf_data` to planner:
- No manual wiring needed in other pipeline stages
- Context already contains multi-timeframe candles

---

## Documentation References

**Related Files**:
- Implementation: `backend/strategy/planner/planner_service.py`
- Data model: `backend/shared/models/data.py` (MultiTimeframeData)
- Integration: `backend/engine/orchestrator.py`
- Config: `backend/shared/config/defaults.py` (ScanConfig.primary_planning_timeframe)

**Related Concepts**:
- SMC detection: `backend/strategy/smc/`
- Plan type classification: `backend/shared/config/rr_matrix.py`
- Context pipeline: `backend/engine/context.py`

---

## Summary

🎯 **Impact**: Expands tradeable signal universe by 15-30% (estimated) while maintaining structural discipline.

✅ **Preserves Philosophy**: "No structure = no trade" still holds—swing levels ARE structure (price-based invalidation).

📊 **Quality Control**: Swing-based plans pass through same R:R thresholds, sanity gates, and conviction classification.

🔧 **Implementation**: Clean, testable, backward-compatible enhancement with clear fallback hierarchy.

**Next Steps**: Monitor swing fallback usage rate and performance in production to validate expansion of valid signals doesn't dilute quality.
