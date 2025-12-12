# SniperSight SMC Refactoring Plan
## Complete Implementation Guide: Integrating Best Practices from smartmoneyconcepts

---

## Executive Summary

After deep analysis of both codebases, here's the verdict:

| Component | Your Implementation | Their Implementation | Winner | Action |
|-----------|---------------------|---------------------|--------|--------|
| **BOS/CHoCH** | Simple "break level" detection | 4-swing pattern validation | **THEIRS** | Adopt their logic |
| **Order Blocks** | Rejection-wick based | Last-candle-before-BOS | **DIFFERENT** | Hybrid approach |
| **FVG** | Solid, with freshness decay | Clean, with consecutive merge | **TIE** | Steal consecutive merge |
| **Liquidity/EQ H/L** | ATR-tolerant clustering | Percentage-based clustering | **YOURS** | Keep, add sweep tracking |
| **Liquidity Sweep** | Reversal-based detection | Forward scan with index | **THEIRS** | Add swept index tracking |
| **Mitigation** | Enhanced with tap depth/reaction | Simple index tracking | **YOURS** | Keep yours |
| **Swing Detection** | Loop-based, clean | Vectorized with deduplication | **THEIRS** | Adopt deduplication |
| **Grading** | ATR-based A/B/C | Volume imbalance % | **YOURS** | Add their volume metric |
| **OB Lifecycle** | Fresh → Mitigated → Stale | Fresh → Mitigated → Breaker → Invalid | **THEIRS** | Add breaker state |
| **Retracements** | Not implemented | Current + deepest tracking | **THEIRS** | Add new module |
| **Sessions** | Not in SMC module | Kill zones built-in | **THEIRS** | Add session filter |

---

## STEAL LIST — DETAILED IMPLEMENTATION PLAN

---

## 1. BOS/CHoCH 4-Swing Pattern Validation — PRIORITY: HIGH

### Current Problem
Your `bos_choch.py` (lines 136-244) does simple level breaks:
```python
# Your current logic - TOO SIMPLE
if current_close > last_swing_high:  # Marks as BOS
if current_close < last_swing_low:   # Marks as CHoCH
```

This doesn't validate the **swing sequence** — a proper BOS requires the full HH/HL or LL/LH pattern.

### Their Solution (smc.py lines 256-331)
```python
# Bullish BOS: Requires [-1, 1, -1, 1] pattern (Low, High, Low, High)
# AND levels must be: LL < HL < LH < HH (trending up)
np.all(highs_lows_order[-4:] == [-1, 1, -1, 1])
np.all(level_order[-4] < level_order[-2] < level_order[-3] < level_order[-1])

# Bullish CHoCH: Same pattern but coming FROM downtrend
# Levels: New HH breaks the prior downtrend structure  
np.all(level_order[-1] > level_order[-3] > level_order[-4] > level_order[-2])
```

### Implementation

**File**: `backend/strategy/smc/bos_choch.py`

```python
# NEW: Add after line 100 (after swing detection)

def _build_swing_sequence(swing_highs: pd.Series, swing_lows: pd.Series) -> tuple:
    """
    Build alternating swing sequence for pattern matching.
    
    Returns:
        tuple: (highs_lows_order: list, level_order: list, index_order: list)
               highs_lows_order: 1 for swing high, -1 for swing low
               level_order: price levels
               index_order: timestamps/indices
    """
    # Combine and sort by timestamp
    all_swings = []
    
    for ts, level in swing_highs.items():
        all_swings.append((ts, 1, level))  # 1 = high
    
    for ts, level in swing_lows.items():
        all_swings.append((ts, -1, level))  # -1 = low
    
    all_swings.sort(key=lambda x: x[0])
    
    # Deduplicate consecutive same-type swings (keep more extreme)
    cleaned = []
    for swing in all_swings:
        if not cleaned:
            cleaned.append(swing)
            continue
        
        ts, swing_type, level = swing
        last_ts, last_type, last_level = cleaned[-1]
        
        if swing_type == last_type:
            # Same type - keep the more extreme one
            if swing_type == 1:  # High - keep higher
                if level > last_level:
                    cleaned[-1] = swing
            else:  # Low - keep lower
                if level < last_level:
                    cleaned[-1] = swing
        else:
            cleaned.append(swing)
    
    highs_lows_order = [s[1] for s in cleaned]
    level_order = [s[2] for s in cleaned]
    index_order = [s[0] for s in cleaned]
    
    return highs_lows_order, level_order, index_order


def _detect_bos_choch_pattern(
    highs_lows_order: list,
    level_order: list,
    index_order: list,
    current_idx: int
) -> tuple:
    """
    Detect BOS/CHoCH using 4-swing pattern validation.
    
    Returns:
        tuple: (break_type: str or None, level: float, broken_index: int)
               break_type: 'BOS', 'CHoCH', or None
    """
    if len(highs_lows_order) < 4:
        return None, 0.0, -1
    
    # Get last 4 swings
    last_4_types = highs_lows_order[-4:]
    last_4_levels = level_order[-4:]
    
    # Bullish BOS: Low-High-Low-High with ascending structure
    # Pattern: [-1, 1, -1, 1] and LL < HL < LH < HH
    if last_4_types == [-1, 1, -1, 1]:
        ll, lh, hl, hh = last_4_levels
        if ll < hl < lh < hh:
            return 'BOS', lh, current_idx  # BOS breaks the prior high
    
    # Bearish BOS: High-Low-High-Low with descending structure
    # Pattern: [1, -1, 1, -1] and HH > LH > HL > LL
    if last_4_types == [1, -1, 1, -1]:
        hh, hl, lh, ll = last_4_levels
        if hh > lh > hl > ll:
            return 'BOS', hl, current_idx  # BOS breaks the prior low
    
    # Bullish CHoCH: Low-High-Low-High but REVERSING from downtrend
    # Pattern: [-1, 1, -1, 1] but prior structure was bearish
    if last_4_types == [-1, 1, -1, 1]:
        ll, lh, hl, hh = last_4_levels
        # CHoCH: new high breaks above the sequence (reversal)
        if hh > lh > ll > hl:
            return 'CHoCH', lh, current_idx
    
    # Bearish CHoCH: High-Low-High-Low but REVERSING from uptrend
    if last_4_types == [1, -1, 1, -1]:
        hh, hl, lh, ll = last_4_levels
        # CHoCH: new low breaks below the sequence (reversal)
        if ll < hl < hh < lh:
            return 'CHoCH', hl, current_idx
    
    return None, 0.0, -1
```

---

## 2. Swing Deduplication — PRIORITY: HIGH

### Current Problem
Your swing detection can produce consecutive same-type swings (two highs in a row without a low between them).

### Their Solution (smc.py lines 165-193)
```python
while True:
    # Find consecutive same-type swings
    consecutive_highs = (current == 1) & (next_swing == 1)
    
    # Keep the higher high, remove the lower one
    index_to_remove[:-1] |= consecutive_highs & (highs < next_highs)
    index_to_remove[1:] |= consecutive_highs & (highs >= next_highs)
    
    # Same for lows - keep the lower low
    consecutive_lows = (current == -1) & (next_swing == -1)
    index_to_remove[:-1] |= consecutive_lows & (lows > next_lows)
    index_to_remove[1:] |= consecutive_lows & (lows <= next_lows)
    
    if not index_to_remove.any():
        break
    
    swing_highs_lows[positions[index_to_remove]] = np.nan
```

### Implementation

**File**: `backend/strategy/smc/swing_structure.py` (or add to `bos_choch.py`)

```python
def detect_swings_with_deduplication(
    df: pd.DataFrame, 
    swing_length: int = 10
) -> pd.DataFrame:
    """
    Detect swing highs/lows with proper alternation (no consecutive same-type).
    
    STOLEN from smartmoneyconcepts library - ensures clean swing structure.
    
    Args:
        df: OHLC DataFrame
        swing_length: Lookback/forward for swing detection
        
    Returns:
        DataFrame with columns: HighLow (1/-1), Level (price)
    """
    # Initial detection (vectorized for speed)
    swing_length_total = swing_length * 2
    
    # Swing high: current high is highest in window
    swing_highs_lows = np.where(
        df['high'] == df['high'].shift(-swing_length).rolling(swing_length_total).max(),
        1,
        np.where(
            df['low'] == df['low'].shift(-swing_length).rolling(swing_length_total).min(),
            -1,
            np.nan
        )
    )
    
    # DEDUPLICATION LOOP - Remove consecutive same-type swings
    while True:
        positions = np.where(~np.isnan(swing_highs_lows))[0]
        
        if len(positions) < 2:
            break
        
        current = swing_highs_lows[positions[:-1]]
        next_swing = swing_highs_lows[positions[1:]]
        
        highs = df['high'].iloc[positions[:-1]].values
        lows = df['low'].iloc[positions[:-1]].values
        
        next_highs = df['high'].iloc[positions[1:]].values
        next_lows = df['low'].iloc[positions[1:]].values
        
        index_to_remove = np.zeros(len(positions), dtype=bool)
        
        # Consecutive highs - keep the higher one
        consecutive_highs = (current == 1) & (next_swing == 1)
        index_to_remove[:-1] |= consecutive_highs & (highs < next_highs)
        index_to_remove[1:] |= consecutive_highs & (highs >= next_highs)
        
        # Consecutive lows - keep the lower one
        consecutive_lows = (current == -1) & (next_swing == -1)
        index_to_remove[:-1] |= consecutive_lows & (lows > next_lows)
        index_to_remove[1:] |= consecutive_lows & (lows <= next_lows)
        
        if not index_to_remove.any():
            break
        
        swing_highs_lows[positions[index_to_remove]] = np.nan
    
    # Build level array
    level = np.where(
        ~np.isnan(swing_highs_lows),
        np.where(swing_highs_lows == 1, df['high'], df['low']),
        np.nan
    )
    
    return pd.DataFrame({
        'HighLow': swing_highs_lows,
        'Level': level
    }, index=df.index)
```

---

## 3. Order Block — Last Candle Before BOS — PRIORITY: HIGH

### Current Approach
Your OB detection finds **rejection candles** (big wicks):
```python
# Your current logic (order_blocks.py lines 202-243)
if lower_wick / body >= min_wick_ratio:  # Wick >= 2x body
    displacement = _calculate_displacement_bullish(df, i, lookback_candles)
    # Create OB if displacement sufficient
```

### Their Approach (smc.py lines 450-484)
They find the **last candle before structure break**:
```python
# After confirming close > swing_high (BOS):
# Look back between swing and break, find lowest low candle
segment = _low[start:end]
min_val = segment.min()
candidate_index = start + np.nonzero(segment == min_val)[0][-1]  # Last occurrence

# That candle's range = OB zone
obBtm = _low[candidate_index]
obTop = _high[candidate_index]
```

### Implementation — HYBRID APPROACH

**File**: `backend/strategy/smc/order_blocks.py`

```python
# ADD new detection method alongside existing

def detect_order_blocks_structural(
    df: pd.DataFrame,
    swing_highs_lows: pd.DataFrame,  # From detect_swings_with_deduplication
    config: SMCConfig | dict | None = None
) -> List[OrderBlock]:
    """
    Detect order blocks using "last candle before BOS" method.
    
    STOLEN from smartmoneyconcepts - finds institutional footprint candle.
    
    This complements the rejection-wick detection. Use both and score
    higher when they agree.
    """
    if config is None:
        smc_cfg = SMCConfig.defaults()
    elif isinstance(config, dict):
        smc_cfg = SMCConfig.from_dict(config)
    else:
        smc_cfg = config
    
    ohlc_len = len(df)
    _high = df['high'].values
    _low = df['low'].values
    _close = df['close'].values
    _volume = df['volume'].values
    swing_hl = swing_highs_lows['HighLow'].values
    
    crossed = np.full(ohlc_len, False, dtype=bool)
    order_blocks = []
    
    swing_high_indices = np.flatnonzero(swing_hl == 1)
    swing_low_indices = np.flatnonzero(swing_hl == -1)
    
    from backend.indicators.volatility import compute_atr
    atr = compute_atr(df, period=14)
    
    # Process for bullish OBs (break above swing high)
    for close_idx in range(1, ohlc_len):
        pos = np.searchsorted(swing_high_indices, close_idx)
        if pos == 0:
            continue
        last_top_idx = swing_high_indices[pos - 1]
        
        if _close[close_idx] > _high[last_top_idx] and not crossed[last_top_idx]:
            crossed[last_top_idx] = True
            
            # Find the lowest candle between swing high and break
            if close_idx - last_top_idx > 1:
                start = last_top_idx + 1
                end = close_idx
                segment = _low[start:end]
                
                if len(segment) > 0:
                    min_val = segment.min()
                    candidates = np.nonzero(segment == min_val)[0]
                    ob_idx = start + candidates[-1]
                else:
                    ob_idx = close_idx - 1
            else:
                ob_idx = close_idx - 1
            
            # Calculate volume imbalance (STOLEN metric)
            vol_cur = _volume[close_idx]
            vol_prev1 = _volume[close_idx - 1] if close_idx >= 1 else 0
            vol_prev2 = _volume[close_idx - 2] if close_idx >= 2 else 0
            high_volume = vol_cur + vol_prev1
            low_volume = vol_prev2
            max_vol = max(high_volume, low_volume)
            volume_imbalance = (min(high_volume, low_volume) / max_vol * 100) if max_vol > 0 else 100
            
            # Grade based on ATR displacement
            displacement = _high[close_idx] - _low[ob_idx]
            atr_val = atr.iloc[close_idx] if close_idx < len(atr) and pd.notna(atr.iloc[close_idx]) else 1
            disp_atr = displacement / atr_val
            grade = smc_cfg.calculate_grade(disp_atr)
            
            # Boost grade if strong volume imbalance (< 30% = very imbalanced)
            if volume_imbalance < 30 and grade == 'B':
                grade = 'A'
            
            ob = OrderBlock(
                timeframe=_infer_timeframe(df),
                direction="bullish",
                high=_high[ob_idx],
                low=_low[ob_idx],
                timestamp=df.index[ob_idx].to_pydatetime(),
                displacement_strength=(disp_atr / 3.0) * 100,
                mitigation_level=0.0,
                freshness_score=100.0,
                grade=grade,
                displacement_atr=disp_atr,
                volume_imbalance=volume_imbalance,
                detection_method="structural"
            )
            order_blocks.append(ob)
    
    # Similar for bearish OBs...
    # (mirror the above for swing_low_indices, finding highest candle)
    
    return order_blocks
```

---

## 4. OB Breaker Lifecycle — PRIORITY: MEDIUM

### Their Logic (smc.py lines 427-444, 491-507)
```python
# When OB gets broken through:
if _low[close_index] < bottom_arr[idx]:  # Price broke OB
    breaker[idx] = True

# If breaker gets broken again, invalidate it:
if breaker[idx]:
    if _high[close_index] > top_arr[idx]:
        ob[idx] = 0  # Reset - OB is dead
```

### Implementation

**File**: `backend/strategy/smc/order_blocks.py`

```python
def update_ob_lifecycle(
    df: pd.DataFrame,
    order_blocks: List[OrderBlock]
) -> List[OrderBlock]:
    """
    Update OB lifecycle states: Fresh → Mitigated → Breaker → Invalidated
    """
    updated = []
    
    for ob in order_blocks:
        future_candles = df[df.index > ob.timestamp]
        
        if len(future_candles) == 0:
            updated.append(ob)
            continue
        
        is_breaker = getattr(ob, 'breaker', False)
        is_invalidated = getattr(ob, 'invalidated', False)
        
        for ts, candle in future_candles.iterrows():
            if is_invalidated:
                break
                
            if ob.direction == "bullish":
                if not is_breaker and candle['close'] < ob.low:
                    is_breaker = True
                elif is_breaker and candle['close'] > ob.high:
                    is_invalidated = True
            else:
                if not is_breaker and candle['close'] > ob.high:
                    is_breaker = True
                elif is_breaker and candle['close'] < ob.low:
                    is_invalidated = True
        
        updated.append(replace(ob, breaker=is_breaker, invalidated=is_invalidated))
    
    return [ob for ob in updated if not getattr(ob, 'invalidated', False)]
```

---

## 5. FVG Consecutive Merging — PRIORITY: MEDIUM

### Their Logic (smc.py lines 106-111)
```python
if join_consecutive:
    for i in range(len(fvg) - 1):
        if fvg[i] == fvg[i + 1]:  # Same direction
            top[i + 1] = max(top[i], top[i + 1])
            bottom[i + 1] = min(bottom[i], bottom[i + 1])
            fvg[i] = np.nan  # Remove first
```

### Implementation

**File**: `backend/strategy/smc/fvg.py`

```python
def _merge_consecutive_fvgs(fvgs: List[FVG]) -> List[FVG]:
    """Merge consecutive same-direction FVGs into single zones."""
    if len(fvgs) < 2:
        return fvgs
    
    sorted_fvgs = sorted(fvgs, key=lambda f: f.timestamp)
    merged = []
    i = 0
    
    while i < len(sorted_fvgs):
        current = sorted_fvgs[i]
        j = i + 1
        
        while j < len(sorted_fvgs):
            next_fvg = sorted_fvgs[j]
            time_diff = (next_fvg.timestamp - current.timestamp).total_seconds()
            
            if next_fvg.direction == current.direction and time_diff < 7200:
                current = replace(
                    current,
                    top=max(current.top, next_fvg.top),
                    bottom=min(current.bottom, next_fvg.bottom),
                    size=max(current.top, next_fvg.top) - min(current.bottom, next_fvg.bottom),
                    timestamp=next_fvg.timestamp
                )
                j += 1
            else:
                break
        
        merged.append(current)
        i = j
    
    return merged
```

---

## 6. Liquidity Sweep Index Tracking — PRIORITY: MEDIUM

### Their Logic (smc.py lines 624-632)
```python
cond = ohlc_high[c_start:] >= range_high
if np.any(cond):
    swept = c_start + int(np.argmax(cond))  # Index of sweep candle
```

### Implementation

**File**: `backend/shared/models/smc.py` — Update LiquidityPool model:

```python
@dataclass(frozen=True)
class LiquidityPool:
    level: float
    pool_type: str
    touches: int
    timeframe: str
    grade: str = "B"
    first_touch: Optional[datetime] = None
    last_touch: Optional[datetime] = None
    tolerance_used: float = 0.002
    spread: float = 0.0
    swept: bool = False  # NEW
    swept_index: Optional[int] = None  # NEW
    swept_timestamp: Optional[datetime] = None  # NEW
```

**File**: `backend/strategy/smc/liquidity_sweeps.py`

```python
def track_pool_sweeps(df: pd.DataFrame, pools: List[LiquidityPool]) -> List[LiquidityPool]:
    """Track when liquidity pools get swept."""
    updated = []
    
    for pool in pools:
        if pool.swept or pool.last_touch is None:
            updated.append(pool)
            continue
            
        future_mask = df.index > pool.last_touch
        future_indices = np.where(future_mask)[0]
        
        swept, swept_idx, swept_ts = False, None, None
        
        for idx in future_indices:
            if pool.pool_type == "equal_highs" and df['high'].iloc[idx] > pool.level:
                swept, swept_idx, swept_ts = True, idx, df.index[idx].to_pydatetime()
                break
            elif pool.pool_type == "equal_lows" and df['low'].iloc[idx] < pool.level:
                swept, swept_idx, swept_ts = True, idx, df.index[idx].to_pydatetime()
                break
        
        updated.append(replace(pool, swept=swept, swept_index=swept_idx, swept_timestamp=swept_ts))
    
    return updated
```

---

## 7. Volume Imbalance Percentage — PRIORITY: MEDIUM

Already included in the OB structural detection above:

```python
volume_imbalance = min(high_volume, low_volume) / max(high_volume, low_volume) * 100
# Lower = more imbalanced = stronger
if volume_imbalance < 30 and grade == 'B':
    grade = 'A'
```

---

## 8. Retracement Percentage Tracking — PRIORITY: LOW

**File**: `backend/strategy/smc/retracements.py` (NEW)

```python
def calculate_retracements(df: pd.DataFrame, swing_highs_lows: pd.DataFrame) -> pd.DataFrame:
    """Track how deep price retraces within swing legs."""
    n = len(df)
    direction = np.zeros(n, dtype=np.int32)
    current_retracement = np.zeros(n, dtype=np.float64)
    deepest_retracement = np.zeros(n, dtype=np.float64)
    
    top, bottom = 0.0, 0.0
    swing_hl = swing_highs_lows['HighLow'].values
    swing_level = swing_highs_lows['Level'].values
    
    for i in range(n):
        if swing_hl[i] == 1:
            direction[i], top = 1, swing_level[i]
        elif swing_hl[i] == -1:
            direction[i], bottom = -1, swing_level[i]
        else:
            direction[i] = direction[i - 1] if i > 0 else 0
        
        if top > 0 and bottom > 0 and top != bottom:
            if direction[i] == 1:
                current_retracement[i] = 100 - (((df['low'].iloc[i] - bottom) / (top - bottom)) * 100)
            elif direction[i] == -1:
                current_retracement[i] = 100 - (((df['high'].iloc[i] - top) / (bottom - top)) * 100)
            
            if i > 0 and direction[i] == direction[i - 1]:
                deepest_retracement[i] = max(deepest_retracement[i - 1], current_retracement[i])
            else:
                deepest_retracement[i] = current_retracement[i]
    
    return pd.DataFrame({
        'Direction': direction,
        'CurrentRetracement%': current_retracement,
        'DeepestRetracement%': deepest_retracement
    }, index=df.index)
```

---

## 9. Session/Kill Zone Awareness — PRIORITY: LOW

**File**: `backend/strategy/smc/sessions.py` (NEW)

```python
KILL_ZONES = {
    "Asian": {"start": "00:00", "end": "04:00"},
    "London Open": {"start": "06:00", "end": "09:00"},
    "New York": {"start": "11:00", "end": "14:00"},
    "London Close": {"start": "14:00", "end": "16:00"},
}

def is_in_kill_zone(timestamp: datetime) -> tuple:
    """Check if timestamp falls within any kill zone."""
    t = timestamp.time()
    for zone_name, times in KILL_ZONES.items():
        start = datetime.strptime(times["start"], "%H:%M").time()
        end = datetime.strptime(times["end"], "%H:%M").time()
        if start <= t <= end:
            return True, zone_name
    return False, None

def filter_signals_by_session(signals: list, kill_zones_only: bool = True) -> list:
    """Filter signals to only those in kill zones."""
    if not kill_zones_only:
        return signals
    return [s for s in signals if is_in_kill_zone(s.timestamp)[0]]
```

---

## 10. Previous HTF High/Low Tracking — PRIORITY: LOW

**File**: `backend/analysis/htf_levels.py` (if not exists)

```python
def get_previous_htf_levels(df: pd.DataFrame, timeframe: str = "1D") -> pd.DataFrame:
    """Get previous period's high/low and track breaks."""
    resampled = df.resample(timeframe).agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    
    n = len(df)
    previous_high = np.zeros(n)
    previous_low = np.zeros(n)
    broken_high = np.zeros(n, dtype=np.int32)
    broken_low = np.zeros(n, dtype=np.int32)
    
    currently_broken_high, currently_broken_low = False, False
    last_period = None
    
    for i in range(n):
        prev_periods = resampled[resampled.index < df.index[i]]
        if len(prev_periods) < 2:
            continue
        
        prev_idx = prev_periods.index[-2]
        if last_period != prev_idx:
            currently_broken_high = currently_broken_low = False
            last_period = prev_idx
        
        previous_high[i] = resampled.loc[prev_idx, 'high']
        previous_low[i] = resampled.loc[prev_idx, 'low']
        
        if df['high'].iloc[i] > previous_high[i]:
            currently_broken_high = True
        if df['low'].iloc[i] < previous_low[i]:
            currently_broken_low = True
        
        broken_high[i] = 1 if currently_broken_high else 0
        broken_low[i] = 1 if currently_broken_low else 0
    
    return pd.DataFrame({
        'PreviousHigh': previous_high, 'PreviousLow': previous_low,
        'BrokenHigh': broken_high, 'BrokenLow': broken_low
    }, index=df.index)
```

---

## Implementation Order

### Phase 1 — HIGH PRIORITY (Do First)
1. **Swing Deduplication** — Foundation for everything
2. **BOS/CHoCH 4-Swing Pattern** — Core structure
3. **OB Structural Detection** — Complement rejection method

### Phase 2 — MEDIUM PRIORITY
4. **OB Breaker Lifecycle**
5. **FVG Consecutive Merge**
6. **Liquidity Sweep Tracking**
7. **Volume Imbalance** (already in OB structural)

### Phase 3 — LOW PRIORITY
8. **Retracement Tracking**
9. **Session/Kill Zones**
10. **Previous HTF Levels**

---

## Model Updates Required

**File**: `backend/shared/models/smc.py`

```python
@dataclass(frozen=True)
class OrderBlock:
    # ... existing fields ...
    volume_imbalance: float = 100.0  # NEW: Lower = stronger
    detection_method: str = "rejection"  # NEW: "rejection", "structural", "confirmed_both"
    breaker: bool = False  # NEW: OB broken, now acts as opposite S/R
    invalidated: bool = False  # NEW: Breaker failed
```

---

## Summary

**Steal**: Their detection precision (4-swing BOS/CHoCH, structural OB, swing deduplication, FVG merge, sweep tracking)

**Keep**: Your contextual intelligence (MTF, ATR grading, regime awareness, enhanced mitigation, scoring system)

After refactor, SniperSight will have the best of both worlds.
