# SMC Pipeline Refactor - Implementation Game Plan

**Version**: 1.0  
**Date**: December 3, 2025  
**Status**: In Progress

---

## Executive Summary

### Problem Statement

The current SniperSight SMC pipeline **rejects patterns too early** at the detection level using ATR-based thresholds (`min_displacement_atr`, `fvg_min_gap_atr`, `structure_min_break_distance_atr`). This prevents the confluence scoring layer from evaluating patterns holistically.

**Example**: A valid order block with 0.8x ATR displacement gets rejected in `order_blocks.py` before confluence scoring can consider that it's:
- At the bottom Bollinger Band on HTF
- In a confirmed DCL zone
- With RSI curling up from oversold
- Aligned with Weekly StochRSI bullish crossover

### Solution Overview

Transform from **binary rejection** to **pattern grading**:
1. **Detect ALL patterns** regardless of ATR thresholds
2. **Assign quality grades** (A/B/C) based on ATR-relative strength
3. **Let confluence scoring weight** patterns by grade
4. **Add missing indicator integration** (BB MTF, OBV, VWAP, Weekly StochRSI gate)
5. **Pre-computed cycle data** as a guideline layer
6. **Mode-aware HTF definitions** that respect each mode's "higher timeframe"

---

## Current vs Proposed Architecture

### Current Pipeline (Rejection Model)
```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: Data Ingestion → Multi-TF OHLCV                       │
│ LAYER 2: Indicators → RSI, StochRSI, MACD, ATR, BB, etc.       │
│ LAYER 3: SMC Detection → ❌ REJECTS patterns below ATR threshold│
│ LAYER 4: Confluence Scoring → Only sees "strong" patterns       │
│ LAYER 5: Trade Planning → Based on filtered data                │
│ LAYER 6: Risk Validation → R:R, exposure limits                 │
└─────────────────────────────────────────────────────────────────┘
```

### Proposed Pipeline (Grading Model)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 0: PRE-COMPUTED INPUTS                                                │
│  ├─ CycleCalendar: DCL/WCL dates, translation history (JSON)               │
│  └─ Weekly StochRSI state: Bullish/Bearish/Neutral gate                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 1: DATA INGESTION                                                     │
│  └─ Multi-TF OHLCV (mode-specific TFs + always 1W for gate)                │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 2: INDICATOR COMPUTATION                                              │
│  ├─ Momentum: RSI, StochRSI (K/D + K_prev/D_prev), MFI, MACD               │
│  ├─ Mean Reversion: BB (upper/middle/lower per TF), BB position context    │
│  ├─ Volatility: ATR, ATR%, Realized Vol                                    │
│  └─ Volume: Volume spike, OBV trend, VWAP context                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 3: SMC PATTERN DETECTION (ALL patterns, graded A/B/C)                │
│  ├─ Order Blocks: Detect ALL, grade by displacement ATR                    │
│  ├─ FVGs: Detect ALL, grade by gap size ATR                                │
│  ├─ BOS/CHoCH: Detect ALL, grade by break distance ATR                     │
│  ├─ Liquidity Sweeps: Detect ALL, grade by reversal strength               │
│  └─ Swing Structure: HH/HL/LH/LL labels (no grading needed)                │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 4: CONFLUENCE SCORING (holistic evaluation)                          │
│  ├─ SMC Pattern Scores: Weighted by grade (A=100%, B=70%, C=40%)           │
│  ├─ Indicator Checkpoints (sequential, mode-dependent):                     │
│  │   1. BB MTF Context: HTF position + LTF position + BOS confirmation      │
│  │   2. RSI State: Oversold curling up? Overbought curling down?            │
│  │   3. MACD Position: Above/below zero on mode's HTF?                      │
│  │   4. Volume Confirmation: OBV rising? Volume spike?                      │
│  │   5. VWAP Context: Price above/below VWAP?                               │
│  ├─ Cycle Alignment: Phase + translation bonus (from pre-computed calendar)│
│  └─ Weekly StochRSI Gate: Universal direction filter                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 5: TRADE PLANNING                                                     │
│  ├─ Entry: From Grade A/B OBs in allowed entry TFs                         │
│  ├─ Stop: Structure-based (swing low/high), minimum ATR buffer             │
│  └─ Targets: FVG fill, next OB, R:R matrix                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 6: RISK VALIDATION                                                    │
│  └─ R:R ratio, exposure limits, correlation matrix                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Mode-Aware HTF Definitions

Each scanner mode has its own definition of "Higher Timeframe" (HTF). The Weekly StochRSI gate always uses actual Weekly data, but indicator checkpoints use mode-relative HTF.

| Mode | HTF Tier | HTF (Bias/Context) | MTF (Structure) | LTF (Entry) | Weekly Gate | Checkpoint Style |
|------|----------|-------------------|-----------------|-------------|-------------|------------------|
| **OVERWATCH** | Macro | 1W, 1D | 4H | 1H | ✅ Required | Soft (3/5 min) |
| **STEALTH** | Swing | 1D, 4H | 1H | 15m, 5m | ✅ Required | Soft (3/5 min) |
| **STRIKE** | Intraday | 4H, 1H | 15m | 5m | ⚠️ Advisory | Hard on structure |
| **SURGICAL** | Scalp | 1H | 15m | 5m | ⚠️ Advisory | Hard on structure |

### Mode Consolidation: RECON + GHOST → STEALTH

**Rationale**: RECON and GHOST had nearly identical HTF definitions. Merging into STEALTH with configurable strictness:

```python
"stealth": ScannerMode(
    name="stealth",
    description="Stealth mode: balanced swing trading with multi-TF confluence; adaptable and mission-ready.",
    timeframes=("1d", "4h", "1h", "15m", "5m"),
    min_confluence_score=65.0,  # Base threshold
    profile="balanced",
    critical_timeframes=("4h", "1h"),
    primary_planning_timeframe="1h",
    entry_timeframes=("1h", "15m", "5m"),
    structure_timeframes=("1d", "4h", "1h"),
    overrides={
        "min_rr_ratio": 1.8,
        "atr_floor": 0.0015,
        "stealth_strict": False,  # Set True for higher conviction (was GHOST)
    },
)
```

**UI Backward Compatibility**: Frontend `ScannerContext.tsx` SCANNER_MODES will map:
- `recon` → `stealth` (stealth_strict=False)
- `ghost` → `stealth` (stealth_strict=True)

---

## Pattern Grading System

### Grade Thresholds by SMC Preset

Each SMC preset defines different grade boundaries:

| Preset | Grade A (Excellent) | Grade B (Good) | Grade C (Marginal) | Use Case |
|--------|--------------------:|---------------:|-------------------:|----------|
| **defaults** | ≥1.0x ATR | ≥0.5x ATR | <0.5x ATR | Balanced detection |
| **luxalgo_strict** | ≥1.5x ATR | ≥1.0x ATR | <1.0x ATR | High-quality only |
| **sensitive** | ≥0.5x ATR | ≥0.3x ATR | <0.3x ATR | Backtesting/research |

### Confluence Score Multipliers by Grade

```python
GRADE_MULTIPLIERS = {
    'A': 1.0,   # Full score (100%)
    'B': 0.7,   # Good score (70%)
    'C': 0.4,   # Marginal score (40%)
}
```

### Implementation in SMC Detectors

**Before (Rejection)**:
```python
# order_blocks.py - CURRENT
if displacement_atr >= min_displacement_atr:
    order_blocks.append(ob)  # Only strong OBs
# Weaker OBs are lost forever
```

**After (Grading)**:
```python
# order_blocks.py - PROPOSED
grade = _calculate_grade(displacement_atr, preset_thresholds)
ob.grade = grade
order_blocks.append(ob)  # ALL OBs kept, graded
```

---

## Indicator Integration Plan

### Currently Unused Indicators

| Indicator | Current State | Proposed Integration |
|-----------|--------------|---------------------|
| **Bollinger Bands** | Stored but not scored | MTF context scoring |
| **OBV** | Stored but not scored | Trend confirmation (+15/-10) |
| **VWAP** | Computed, not scored | Price context (+10 bullish/-10 bearish) |
| **Realized Volatility** | Stored but not scored | Remove (duplicate of ATR%) |

### New Scoring Functions

#### 1. `_score_bollinger_mtf()`
Multi-timeframe Bollinger Band context:

```python
def _score_bollinger_mtf(
    htf_indicators: IndicatorSnapshot,
    ltf_indicators: IndicatorSnapshot,
    current_price: float,
    has_bos: bool,
    direction: str
) -> Tuple[float, str]:
    """
    Score Bollinger Band context across timeframes.
    
    Logic for LONG:
    - HTF at bottom band + LTF at bottom band + BOS = STRONG (+30)
    - HTF at bottom band + LTF at top band = WEAK (+5, likely pullback)
    - HTF at bottom band + LTF at bottom band + no BOS = MODERATE (+15)
    - HTF middle band = NEUTRAL (+0)
    - HTF at top band = CONTRA (-10)
    
    Returns: (score, rationale)
    """
```

#### 2. `_score_obv_trend()`
```python
def _score_obv_trend(
    indicators: IndicatorSnapshot,
    direction: str
) -> float:
    """
    Score OBV trend alignment.
    
    - Rising OBV + bullish direction = +15
    - Rising OBV + bearish direction = -5 (divergence)
    - Falling OBV + bearish direction = +15
    - Falling OBV + bullish direction = -5 (divergence)
    """
```

#### 3. `_score_vwap_context()`
```python
def _score_vwap_context(
    indicators: IndicatorSnapshot,
    current_price: float,
    direction: str
) -> float:
    """
    Score price position relative to VWAP.
    
    - Price above VWAP + bullish = +10 (momentum confirmation)
    - Price below VWAP + bullish = +5 (buying discount)
    - Price below VWAP + bearish = +10 (weakness confirmation)
    - Price above VWAP + bearish = +5 (shorting premium)
    """
```

---

## Weekly StochRSI Gate

### Purpose
Universal directional filter that ALL modes respect. When Weekly StochRSI shows a clear signal, it overrides LTF noise.

### Signal Detection
```python
def _check_weekly_stoch_gate(
    weekly_indicators: IndicatorSnapshot
) -> Tuple[str, float]:
    """
    Check Weekly StochRSI for directional gate.
    
    Signals:
    - K crossing UP through 20 (from below) = BULLISH gate open
    - K crossing DOWN through 80 (from above) = BEARISH gate open
    - K between 20-80, no recent cross = NEUTRAL (no gate)
    
    Returns: (direction: "bullish"/"bearish"/"neutral", confidence: 0-100)
    """
    k = weekly_indicators.stoch_rsi_k
    k_prev = weekly_indicators.stoch_rsi_k_prev
    
    if k_prev is None:
        return ("neutral", 0.0)
    
    # Bullish crossover: K was below 20, now above
    if k_prev < 20 and k >= 20:
        return ("bullish", 80.0)
    
    # Bearish crossover: K was above 80, now below
    if k_prev > 80 and k <= 80:
        return ("bearish", 80.0)
    
    # In oversold zone, waiting for cross
    if k < 20:
        return ("bullish_pending", 40.0)
    
    # In overbought zone, waiting for cross
    if k > 80:
        return ("bearish_pending", 40.0)
    
    return ("neutral", 0.0)
```

### Required Model Changes
Add to `IndicatorSnapshot`:
```python
stoch_rsi_k_prev: Optional[float] = None
stoch_rsi_d_prev: Optional[float] = None
```

---

## Cycle Calendar Specification

### JSON Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "symbol": {"type": "string"},
    "dcl_history": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "date": {"type": "string", "format": "date"},
          "price": {"type": "number"},
          "confirmed": {"type": "boolean"},
          "days_since_last": {"type": "integer"}
        },
        "required": ["date", "confirmed"]
      }
    },
    "wcl_history": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "date": {"type": "string", "format": "date"},
          "price": {"type": "number"},
          "confirmed": {"type": "boolean"},
          "days_since_last": {"type": "integer"}
        },
        "required": ["date", "confirmed"]
      }
    },
    "current_translation": {
      "type": "string",
      "enum": ["LTR", "MTR", "RTR", "UNKNOWN"]
    },
    "current_phase": {
      "type": "string", 
      "enum": ["ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN", "UNKNOWN"]
    },
    "last_updated": {"type": "string", "format": "date-time"}
  },
  "required": ["symbol", "last_updated"]
}
```

### Example Calendar File
`/data/cycle_calendars/BTC_USDT.json`:
```json
{
  "symbol": "BTC/USDT",
  "dcl_history": [
    {"date": "2025-11-05", "price": 67234.50, "confirmed": true, "days_since_last": 22},
    {"date": "2025-11-28", "price": 91234.50, "confirmed": true, "days_since_last": 23}
  ],
  "wcl_history": [
    {"date": "2025-10-15", "price": 58234.50, "confirmed": true, "days_since_last": 42}
  ],
  "current_translation": "RTR",
  "current_phase": "MARKUP",
  "last_updated": "2025-12-03T00:00:00Z"
}
```

### Error Handling & Fallback

```python
def load_cycle_calendar(symbol: str) -> Optional[CycleCalendar]:
    """
    Load pre-computed cycle calendar for a symbol.
    
    Fallback behavior:
    1. Try to load from /data/cycle_calendars/{symbol_safe}.json
    2. If file missing → return None (use real-time detection)
    3. If file stale (>7 days) → log warning, use real-time detection
    4. If JSON invalid → log error, return None
    
    Returns: CycleCalendar or None
    """
    symbol_safe = symbol.replace("/", "_")
    path = Path(f"data/cycle_calendars/{symbol_safe}.json")
    
    if not path.exists():
        logger.debug(f"No cycle calendar for {symbol}, using real-time detection")
        return None
    
    try:
        data = json.loads(path.read_text())
        last_updated = datetime.fromisoformat(data["last_updated"].replace("Z", "+00:00"))
        
        if datetime.now(timezone.utc) - last_updated > timedelta(days=7):
            logger.warning(f"Cycle calendar for {symbol} is stale ({last_updated})")
            return None
        
        return CycleCalendar.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Invalid cycle calendar for {symbol}: {e}")
        return None
```

---

## Sequential Checkpoint Logic

### Mode-Dependent Checkpoint Style

**Swing Modes (OVERWATCH, STEALTH)**: Soft scoring
- Sum all checkpoint passes
- Require minimum 3/5 checkpoints to pass
- Each checkpoint contributes 0-20 points

**Scalp Modes (STRIKE, SURGICAL)**: Hard gate on structure
- BOS confirmation REQUIRED for BB context to score
- Other checkpoints are soft (additive scoring)
- Structure confirmation is the "gate keeper"

### Checkpoint Implementation

```python
def evaluate_indicator_checkpoints(
    indicators: IndicatorSnapshot,
    htf_indicators: IndicatorSnapshot,
    smc_snapshot: SMCSnapshot,
    direction: str,
    mode_profile: str
) -> Tuple[float, List[str], Dict[str, bool]]:
    """
    Evaluate indicator checkpoints for a trade direction.
    
    Args:
        indicators: LTF indicators
        htf_indicators: Mode-relative HTF indicators
        smc_snapshot: SMC patterns for structure confirmation
        direction: "bullish" or "bearish"
        mode_profile: Scanner mode profile for checkpoint style
        
    Returns:
        Tuple of (total_score, rationale_parts, checkpoint_results)
    """
    checkpoints = {}
    rationale = []
    score = 0.0
    
    # 1. BB MTF Context
    has_bos = any(sb.break_type == "BOS" and sb.htf_aligned 
                  for sb in smc_snapshot.structural_breaks[-5:])
    bb_score, bb_reason = _score_bollinger_mtf(
        htf_indicators, indicators, indicators.close, has_bos, direction
    )
    checkpoints["bb_mtf"] = bb_score > 10
    if bb_score > 0:
        rationale.append(bb_reason)
    score += bb_score
    
    # 2. RSI State
    rsi_aligned = (direction == "bullish" and indicators.rsi < 40) or \
                  (direction == "bearish" and indicators.rsi > 60)
    checkpoints["rsi_aligned"] = rsi_aligned
    if rsi_aligned:
        score += 15.0
        rationale.append(f"RSI {indicators.rsi:.0f} aligned with {direction}")
    
    # 3. MACD Position (on mode HTF)
    macd_above_zero = htf_indicators.macd_line is not None and htf_indicators.macd_line > 0
    macd_aligned = (direction == "bullish" and macd_above_zero) or \
                   (direction == "bearish" and not macd_above_zero)
    checkpoints["macd_htf"] = macd_aligned
    if macd_aligned:
        score += 15.0
        rationale.append(f"HTF MACD {'above' if macd_above_zero else 'below'} zero")
    
    # 4. Volume Confirmation
    obv_score = _score_obv_trend(indicators, direction)
    checkpoints["volume"] = obv_score > 0 or indicators.volume_spike
    if checkpoints["volume"]:
        score += obv_score if obv_score > 0 else 10.0
        rationale.append("Volume confirmation")
    
    # 5. VWAP Context
    vwap_score = _score_vwap_context(indicators, indicators.close, direction)
    checkpoints["vwap"] = vwap_score > 0
    if vwap_score > 0:
        score += vwap_score
        rationale.append("VWAP aligned")
    
    # === MODE-DEPENDENT GATING ===
    if mode_profile in ["intraday_aggressive", "precision"]:
        # Scalp modes: Hard gate on structure
        if not has_bos:
            score *= 0.5  # Penalize without BOS
            rationale.append("⚠️ No BOS confirmation (score halved)")
    else:
        # Swing modes: Soft scoring, check minimum checkpoints
        passes = sum(1 for v in checkpoints.values() if v)
        if passes < 3:
            score *= 0.7
            rationale.append(f"⚠️ Only {passes}/5 checkpoints ({', '.join(k for k,v in checkpoints.items() if v)})")
    
    return (score, rationale, checkpoints)
```

---

## Implementation Phases

### Phase 1: Foundation (Models & Config)
**Files**: `backend/shared/models/smc.py`, `backend/shared/config/smc_config.py`, `backend/shared/models/indicators.py`

- [ ] Add `grade: Literal['A', 'B', 'C']` to OrderBlock, FVG, StructuralBreak
- [ ] Add `luxalgo_strict()` and `sensitive()` presets to SMCConfig
- [ ] Add grade threshold fields to SMCConfig
- [ ] Add `stoch_rsi_k_prev`, `stoch_rsi_d_prev` to IndicatorSnapshot
- [ ] Create `CycleCalendar` dataclass

### Phase 2: SMC Detection Refactor
**Files**: `backend/strategy/smc/order_blocks.py`, `backend/strategy/smc/fvg.py`, `backend/strategy/smc/bos_choch.py`, `backend/strategy/smc/liquidity_sweeps.py`

- [ ] Change order_blocks.py from rejection to grading
- [ ] Change fvg.py from rejection to grading
- [ ] Merge bos_choch.py duplicate fix + add grading
- [ ] Change liquidity_sweeps.py from rejection to grading
- [ ] Add `_calculate_grade()` helper function

### Phase 3: Confluence Scoring Enhancement
**Files**: `backend/strategy/confluence/scorer.py`

- [ ] Add `_score_bollinger_mtf()`
- [ ] Add `_score_obv_trend()`
- [ ] Add `_score_vwap_context()`
- [ ] Add `_check_weekly_stoch_gate()`
- [ ] Add `evaluate_indicator_checkpoints()`
- [ ] Update pattern scoring to use grade multipliers

### Phase 4: Mode Consolidation
**Files**: `backend/shared/config/scanner_modes.py`, `src/context/ScannerContext.tsx`

- [ ] Merge RECON + GHOST → STEALTH in scanner_modes.py
- [ ] Add backward compatibility mapping for API
- [ ] Update frontend SCANNER_MODES constant
- [ ] Update UI mode selector labels

### Phase 5: Orchestrator Integration
**Files**: `backend/engine/orchestrator.py`

- [ ] Load cycle calendar on init
- [ ] Pass grade thresholds to SMC detectors
- [ ] Fetch Weekly data for all modes
- [ ] Pass mode-relative HTF to confluence scoring

### Phase 6: Testing & Validation
- [ ] Unit tests for grading logic
- [ ] Integration tests with mock calendar
- [ ] Backtest comparison: rejection vs grading model
- [ ] UI smoke tests for mode changes

---

## Staged Changes Disposition

Files currently in `extracted-fixes/snipersight-fixes/`:

| File | Action | Reason |
|------|--------|--------|
| `defaults.py` | ✅ ALREADY IN MAIN | `smc_preset` field present |
| `smc_config.py` (presets) | 🔄 MERGE | Add `luxalgo_strict()`, `sensitive()` |
| `bos_choch.py` | 🔄 MERGE | Duplicate fix + cycle bypass |
| `mitigation_tracker.py` | ✅ ALREADY IN MAIN | Freshness tracking present |
| `swing_structure.py` | ✅ ALREADY IN MAIN | HH/HL/LH/LL labeling present |
| `smc.py` | 🔄 REVIEW | CycleContext, ReversalContext additions |
| `orchestrator.py` | ⚠️ PARTIAL | Many enhancements, but needs grading refactor |

---

## Success Criteria

1. **Pattern Detection**: All patterns detected regardless of ATR, assigned A/B/C grades
2. **Confluence Scoring**: Holistic evaluation with grade-weighted SMC + indicator checkpoints
3. **Mode Awareness**: Each mode uses its own HTF definition for indicator context
4. **Weekly Gate**: StochRSI crossover detection working across all modes
5. **Cycle Integration**: Pre-computed calendars loaded with fallback to real-time
6. **UI Compatibility**: Frontend works with new mode structure (STEALTH replaces RECON/GHOST)
7. **Backward Compatibility**: Old API calls still work with deprecation warnings

---

## Appendix: Pseudo-Code Reference

### `_calculate_grade()` Helper
```python
def _calculate_grade(
    atr_ratio: float,
    preset: str = "defaults"
) -> Literal['A', 'B', 'C']:
    """
    Calculate pattern grade based on ATR ratio and preset thresholds.
    """
    thresholds = {
        "defaults": {"A": 1.0, "B": 0.5},
        "luxalgo_strict": {"A": 1.5, "B": 1.0},
        "sensitive": {"A": 0.5, "B": 0.3},
    }
    t = thresholds.get(preset, thresholds["defaults"])
    
    if atr_ratio >= t["A"]:
        return 'A'
    elif atr_ratio >= t["B"]:
        return 'B'
    else:
        return 'C'
```

### Mode HTF Lookup
```python
MODE_HTF_MAP = {
    "overwatch": {"htf": ("1w", "1d"), "mtf": ("4h",), "ltf": ("1h",)},
    "stealth": {"htf": ("1d", "4h"), "mtf": ("1h",), "ltf": ("15m", "5m")},
    "strike": {"htf": ("4h", "1h"), "mtf": ("15m",), "ltf": ("5m",)},
    "surgical": {"htf": ("1h",), "mtf": ("15m",), "ltf": ("5m",)},
}

def get_mode_htf(mode_name: str) -> Tuple[str, ...]:
    """Get the HTF timeframes for a mode."""
    return MODE_HTF_MAP.get(mode_name, MODE_HTF_MAP["stealth"])["htf"]
```
