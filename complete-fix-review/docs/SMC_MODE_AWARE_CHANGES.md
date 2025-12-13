# SMC Mode-Aware Detection Changes

## Problem Summary

SURGICAL mode was only finding BTC as a valid pair because:

1. **Structure confirmation was too strict** - All OBs required a BOS within 10 candles
2. **TF-specific thresholds weren't being applied** - `ob_min_wick_ratio` overrides were ignored
3. **LTF OB detection was disabled by default** - 15m and 5m had `detect_ob=False`
4. **Cascade effect** - No OBs → No structure score → Low confluence → Rejection

Additionally, **swing trades were appearing in SURGICAL mode** because:

5. **Trade type was derived from characteristics, not mode** - Large target moves (≥3.5%) would return 'swing' regardless of mode
6. **Rejection was too aggressive** - Instead of clamping to allowed type, it just rejected the plan

## Changes Made

### 1. Mode-Aware OB Filtering (`smc_service.py`)

**Before:** All OBs required structure confirmation regardless of timeframe or mode.

**After:** Structure confirmation requirement is now contextual:

| Timeframe | Structure Confirmation Required? |
|-----------|----------------------------------|
| HTF (4H+) | ✅ Yes - Institutional zones need BOS validation |
| MTF (1H)  | Mode-dependent (OVERWATCH/STEALTH=Yes, SURGICAL/STRIKE=No) |
| LTF (15m, 5m) | ❌ No - Entry refinement zones |

### 2. TF-Specific Threshold Application (`smc_service.py`)

**Before:** TF config overrides (`ob_min_wick_ratio`, etc.) were loaded but never passed to detection functions.

**After:** New `_create_tf_smc_config()` method merges base SMCConfig with TF-specific overrides:

```python
# 15m SURGICAL now uses:
min_wick_ratio = 2.0  # (vs 2.5 base)
min_displacement_atr = 1.2  # (vs 1.5 base)

# 5m SURGICAL now uses:
min_wick_ratio = 1.8
min_displacement_atr = 1.0
```

### 3. Updated Base TF Configs (`smc_config.py`)

**15m Base Config:**
- `detect_ob`: `False` → `True`
- Added: `ob_min_wick_ratio: 2.0`, `ob_min_displacement_atr: 1.2`

**5m Base Config:**
- `detect_ob`: `False` → `True`
- Added: `ob_min_wick_ratio: 1.8`, `ob_min_displacement_atr: 1.0`

### 4. Mode Overrides (`smc_config.py`)

**SURGICAL Mode (precision scalping):**
```python
'1h': {'detect_ob': True, 'detect_bos': True, 'detect_sweep': True},
'15m': {
    'detect_ob': True, 
    'detect_bos': True, 
    'ob_min_wick_ratio': 2.0,
    'ob_min_displacement_atr': 1.2,
},
'5m': {
    'detect_fvg': True, 
    'detect_bos': True,
    'detect_ob': True,
    'ob_min_wick_ratio': 1.8,
    'ob_min_displacement_atr': 1.0,
},
```

**OVERWATCH Mode (swing trading) - Explicitly disables LTF:**
```python
'15m': {'detect_ob': False, 'detect_bos': False, 'detect_fvg': True},
'5m': {'detect_ob': False, 'detect_fvg': False, 'detect_bos': False},
```

### 5. Trade Type Clamping (`planner_service.py`)

**Before:** If derived trade type wasn't in `allowed_trade_types`, the plan was rejected entirely.

**After:** Trade type gets **clamped** to an allowed type instead of rejected:

```python
# Example: SURGICAL mode
# Derived: 'swing' (large target move ≥3.5%)
# Allowed: ('intraday', 'scalp')
# Result: Clamped to 'intraday' with log message

# Priority order for downgrade: intraday > scalp > swing
```

This means:
- SURGICAL will never produce 'swing' trades - they get clamped to 'intraday'
- OVERWATCH will never produce 'scalp' trades - they get clamped to 'swing'
- The derived type is still logged for telemetry (helps tune thresholds)

## Expected Impact

### Before
- SURGICAL scans: 1/10 pairs passed (BTC only)
- Low scores due to missing OBs and structure
- Market Structure: 51%
- LTF OBs not detected at all
- Swing trades appearing in SURGICAL output

### After
- SURGICAL scans: More pairs should pass
- LTF OBs detected with relaxed thresholds for entry refinement
- HTF OBs still validated with structure confirmation
- Mode-appropriate pattern detection
- Trade types clamped to mode's allowed list (no more swings in SURGICAL)

## Pattern Detection Matrix by Mode

| Pattern | OVERWATCH | STRIKE | SURGICAL | STEALTH |
|---------|-----------|--------|----------|---------|
| **1W/1D OB** | ✅ Strict | ✅ Strict | N/A | ✅ Strict |
| **4H OB** | ✅ Strict | ✅ Normal | N/A | ✅ Normal |
| **1H OB** | ✅ Normal | ✅ Normal | ✅ Normal | ✅ Normal |
| **15m OB** | ❌ Skip | ✅ Relaxed | ✅ Relaxed | ✅ Relaxed |
| **5m OB** | ❌ Skip | ✅ Entry | ✅ Entry | ❌ Skip |
| **15m BOS** | ❌ Skip | ✅ Yes | ✅ Yes | ✅ Yes |
| **5m BOS** | ❌ Skip | ❌ Skip | ✅ Yes | ❌ Skip |

## Trade Type by Mode

| Mode | Allowed Types | If Derived=Swing |
|------|--------------|------------------|
| **SURGICAL** | intraday, scalp | Clamped to intraday |
| **STRIKE** | swing, intraday, scalp | Allowed |
| **STEALTH** | swing, intraday | Allowed or clamped to swing |
| **OVERWATCH** | swing only | Must be swing |

## How LTF OBs Work Now

LTF OBs (15m, 5m) are detected with relaxed thresholds because:
1. They're for **entry refinement** within HTF zones, not standalone trades
2. They don't require structure confirmation
3. The confluence scorer still weights HTF OBs higher (TF weight: 4H=1.0, 15m=0.6, 5m=0.3)
4. Scoring validates LTF OBs are inside HTF zones for bonus points

This gives you:
- **HTF OBs** = Where to look for trades (institutional zones)
- **LTF OBs** = Where to enter (precise entry zones within HTF)
