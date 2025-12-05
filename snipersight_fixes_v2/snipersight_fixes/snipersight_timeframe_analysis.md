# SniperSight Scanner: Timeframe Fundamentals & Entry Logic Analysis

## Executive Summary

Your scanner is **properly structured** with clear timeframe responsibility, but there are some **critical gaps** in how it implements the trading principles we discussed. Here's what I found:

---

## Scanner Modes Overview

SniperSight has 4 primary modes, each with different timeframe stacks:

### 1. **OVERWATCH (Macro Surveillance)**
**Purpose:** High-conviction swing trades  
**Timeframes:** `1W → 1D → 4H → 1H → 15M → 5M`

**Timeframe Responsibilities:**
- **Bias TFs:** 1W, 1D (macro trend identification)
- **Entry TFs:** 4H, 1H (swing position entries)
- **Structure TFs:** 1W, 1D, 4H (HTF structure for stops/targets)
- **Stop TFs:** 4H, 1H
- **Target TFs:** 1D, 4H

**Confluence Gate:** 75% minimum  
**Min R:R:** 2.0:1  
**Min Target Move:** 1.5% (macro moves only)

**Analysis:**
✅ **CORRECT:** Uses 1W/1D as bias, 4H/1H for entries  
✅ **CORRECT:** Doesn't use 5M/15M for entry (swing-only)  
⚠️ **ISSUE:** Timeframe conflict handling is unclear - what happens when 1W is bullish but 1D is bearish?

---

### 2. **STRIKE (Intraday Aggressive)**
**Purpose:** Fast scalp/intraday momentum trades  
**Timeframes:** `4H → 1H → 15M → 5M`

**Timeframe Responsibilities:**
- **Bias TF:** 4H, 1H (intraday directional bias)
- **Entry TFs:** 15M, 5M (aggressive scalp entries)
- **Structure TFs:** 4H, 1H, 15M (HTF structure for target clipping)
- **Stop TFs:** 15M, 5M (tight scalp stops)
- **Target TFs:** 1H, 15M (faster exits)

**Confluence Gate:** 60% minimum  
**Min R:R:** 1.5:1  
**Min Target Move:** 0.4%

**Analysis:**
✅ **CORRECT:** Uses 4H/1H as bias (not Weekly/Daily)  
✅ **CORRECT:** Entry on 15M/5M (scalp timeframes)  
⚠️ **ISSUE:** 4H is included, but **no mechanism** to ensure 4H isn't actively invalidating 1H bias  
❌ **CRITICAL FLAW:** Missing logic to check if 1H is at a **4H structural level** (demand/supply zone, FVG, key level)

**What's Missing:**
- When 4H is bearish and 1H flips bullish, the system needs to verify:
  1. Is 1H at a 4H level of interest? (demand zone, FVG, structure)
  2. Has 4H shown exhaustion? (divergence, sweep, range formation)
  3. If not, flag as LOW PROBABILITY or skip

---

### 3. **SURGICAL (Precision Scalping)**
**Purpose:** Tight, high-quality entries with minimal exposure  
**Timeframes:** `1H → 15M → 5M`

**Timeframe Responsibilities:**
- **Bias TF:** 1H (anchor for precision)
- **Entry TFs:** 15M, 5M (surgical precision)
- **Structure TFs:** 1H, 15M (tight structure, no 5M)
- **Stop TFs:** 15M, 5M (tightest stops)
- **Target TFs:** 1H, 15M (fast exits)

**Confluence Gate:** 70% minimum  
**Min R:R:** 1.5:1  
**Min Target Move:** 0.4%

**Analysis:**
✅ **CORRECT:** Simplified to 1H/15M/5M (no higher noise)  
✅ **CORRECT:** 1H is the bias anchor  
✅ **CORRECT:** Allows 15M AND 5M for entries (surgical precision needs both)  
⚠️ **ISSUE:** Same problem as STRIKE - no validation that 5M/15M entries are at 1H levels

---

### 4. **STEALTH (Balanced Swing)**
**Purpose:** Multi-TF swing trading with adaptability  
**Timeframes:** `1D → 4H → 1H → 15M → 5M`

**Timeframe Responsibilities:**
- **Bias TFs:** 4H, 1H (swing context)
- **Entry TFs:** 1H, 15M, 5M (flexible swing entries)
- **Structure TFs:** 1D, 4H, 1H (HTF structure for target clipping)
- **Stop TFs:** 15M, 5M (tighter swing stops)
- **Target TFs:** 1H, 15M (adaptable exits)

**Confluence Gate:** 65% minimum (70% with strict mode)  
**Min R:R:** 1.8:1  
**Min Target Move:** 0.5%

**Analysis:**
✅ **CORRECT:** Uses 1D/4H/1H for context, allows 1H/15M/5M for entries  
✅ **CORRECT:** Balances swing holding with flexible entry timing  
⚠️ **ISSUE:** Allows 5M entries for swing trades - this could create overtrading on noise

---

## CRITICAL FINDINGS: What's Missing

### 1. **No Higher Timeframe Structural Validation**

**The Problem:**  
Your scanner checks if timeframes *align* (all bullish or all bearish), but it **doesn't validate** that lower timeframe entries are occurring at **higher timeframe structural levels**.

**Example Scenario (STRIKE mode):**
- 4H: Strong bearish trend (downtrending, momentum strong)
- 1H: Flips bullish (BOS to the upside)
- 15M: Bullish setup detected
- **Scanner behavior:** Generates LONG signal because 1H/15M align
- **What it SHOULD do:** Check if 1H bullish flip is at a 4H demand zone, FVG, or key level. If not, **reject or downgrade**.

**Where This Should Happen:**  
In `confluence/scorer.py`, the HTF proximity scoring exists but is **not mandatory**. It's a bonus, not a filter.

```python
# Current code (scorer.py, line ~900-1000)
# HTF proximity adds bonus points, but doesn't gate the trade
if distance_to_htf_level < atr:
    score += 15.0  # Bonus for being near HTF level
```

**What You Need:**  
A **gating mechanism** that checks:
1. Is the entry timeframe (15M, 5M) at a structure timeframe (4H, 1H) level?
2. If not, apply a **heavy penalty** or reject the trade outright.

---

### 2. **No Momentum Filter for Higher Timeframe Conflict**

**The Problem:**  
When higher TF is trending strongly, lower TF counter-moves should be heavily penalized or skipped. Your scanner treats all timeframe alignments equally.

**Example Scenario (SURGICAL mode):**
- 1H: Strong bullish trend, ATR expanding, volume increasing (MOMENTUM mode)
- 15M: Small bearish pullback
- **Scanner behavior:** Might flag bearish setup if 15M shows BOS down
- **What it SHOULD do:** Check if 1H is in strong momentum. If yes, skip 15M counter-trend trades.

**Where This Should Happen:**  
In the regime detection (`analysis/regime_detector.py`) and confluence scoring. Currently, regime detection classifies market state but **doesn't penalize counter-trend trades during strong momentum**.

---

### 3. **Timeframe Conflict Resolution is Unclear**

**The Problem:**  
You asked: *"What happens when Weekly is bull, Daily is bear, 4H is bear, 1H is bull?"*

**Current Behavior:**  
The scanner checks `critical_timeframes` (e.g., for OVERWATCH: 1W, 1D). If these are missing data, the symbol is rejected. But if they have data and conflict, **the scanner doesn't have clear rules** for how to resolve this.

**What You Need:**  
A **hierarchical conflict resolution system**:

1. **For SCALPS (STRIKE, SURGICAL):**
   - Primary bias: 1H
   - Filter: 4H must not be in strong momentum against 1H
   - If 4H is ranging or pulling back, allow 1H counter-moves
   - If 4H is accelerating, block 1H counter-moves

2. **For SWINGS (OVERWATCH, STEALTH):**
   - Primary bias: 1D or 4H
   - Filter: Weekly trend matters, but only as context
   - Allow 1D/4H counter-trends if Weekly is ranging or showing exhaustion

**Implementation Location:**  
Add this to `confluence/scorer.py` as a **directional alignment check** before calculating score. Pseudocode:

```python
def check_timeframe_alignment(indicators, direction, mode_config):
    """
    Gate trades based on higher TF momentum and alignment.
    Returns: (allowed: bool, penalty: float, reason: str)
    """
    bias_tf = mode_config.primary_planning_timeframe  # e.g., "1h"
    higher_tfs = get_higher_timeframes(bias_tf, mode_config.timeframes)
    
    for htf in higher_tfs:
        htf_trend = get_trend_direction(indicators[htf])
        htf_momentum = get_momentum_strength(indicators[htf])
        
        if htf_momentum == "strong" and htf_trend != direction:
            # Strong momentum against trade direction
            return False, -50.0, f"{htf} in strong {htf_trend} momentum, blocking {direction} trade"
        
        elif htf_trend != direction and not at_htf_structural_level(indicators[htf]):
            # Counter-trend without structural reason
            return False, -30.0, f"{htf} {htf_trend} without structural support for {direction}"
    
    return True, 0.0, "Timeframe alignment passed"
```

---

### 4. **Entry Selection Logic Needs Refinement**

**How Entries Are Currently Chosen:**

Looking at `planner/planner_service.py` (lines 400-600), the planner:
1. Identifies the **primary planning timeframe** (e.g., 1H for STRIKE, 4H for OVERWATCH)
2. Finds the most recent SMC pattern (OB, FVG, sweep) on that timeframe
3. Sets near entry at the pattern boundary, far entry deeper into the zone
4. Places stop based on structure (swing high/low from allowed stop_timeframes)

**What's Right:**
✅ Uses mode-specific `primary_planning_timeframe`  
✅ Respects `entry_timeframes` and `stop_timeframes` restrictions  
✅ Generates near/far entry zones for flexibility

**What's Wrong:**
❌ Doesn't verify the entry is at a **higher timeframe level**  
❌ Doesn't check if the setup is a **pullback into structure** vs random mid-trend entry  
❌ No penalty for entries that aren't at premium/discount zones relative to HTF range

**Fix Needed:**  
Before finalizing entry, add a check:

```python
def validate_entry_against_htf(entry_price, htf_structure, htf_timeframe):
    """
    Verify entry is at a meaningful HTF level.
    Returns: (valid: bool, adjustment: float, reason: str)
    """
    # Check distance to nearest HTF OB/FVG/Key Level
    nearest_level = find_nearest_htf_level(entry_price, htf_structure)
    distance_atr = abs(entry_price - nearest_level) / atr
    
    if distance_atr > 2.0:
        # Entry is too far from any HTF structure
        return False, 0.0, f"Entry {distance_atr:.1f} ATR from nearest {htf_timeframe} level"
    
    # Check if entry is in premium/discount zone
    zone = get_premium_discount_zone(entry_price, htf_structure)
    if zone == "equilibrium":
        # Mid-range entry, lower quality
        return True, -10.0, f"Entry in {htf_timeframe} equilibrium (lower quality)"
    
    return True, 0.0, f"Entry at {htf_timeframe} {zone} zone"
```

---

## MACD Mode-Aware System (Already Good)

Your MACD system is **well-designed** and properly handles mode-specific behavior:

### OVERWATCH (Macro Mode):
- MACD is **PRIMARY** (treat_as_primary=True)
- Uses 4H MACD for directional bias
- Heavy weight (1.5x), strict histogram analysis
- No LTF veto allowed

### STRIKE (Aggressive Mode):
- MACD is **FILTER** (treat_as_primary=False)
- Uses 1H MACD for context
- Medium weight (0.7x)
- LTF MACD can veto trades

### SURGICAL (Precision Mode):
- MACD is **FILTER + VETO**
- Uses 1H MACD for context
- Light weight (0.6x), longer settings (24/52/9) to reduce noise
- LTF MACD veto active

**Verdict:** This part is solid. MACD is appropriately weighted per mode.

---

## Recommendations

### 1. **Add HTF Structural Validation (HIGH PRIORITY)**

**Where:** `confluence/scorer.py` or `planner/planner_service.py`  
**What:** Before finalizing entry, check if entry price is within 1-2 ATR of a higher TF structural level (OB, FVG, key level, premium/discount zone).  
**Impact:** Prevents random mid-trend entries, forces entries at meaningful levels.

### 2. **Implement Momentum Gating (MEDIUM PRIORITY)**

**Where:** `confluence/scorer.py` in the HTF alignment section  
**What:** If higher TF is in strong momentum (ATR expanding, volume high, trend strong), block counter-trend trades on lower TF unless at a major structural level.  
**Impact:** Prevents fighting strong trends with weak pullback trades.

### 3. **Clarify Timeframe Conflict Resolution (MEDIUM PRIORITY)**

**Where:** Add a new function in `confluence/scorer.py`  
**What:** Define explicit rules for how to handle conflicting timeframes. Use the framework I outlined above (strong momentum = block, ranging = allow).  
**Impact:** Makes scanner behavior predictable and reduces false signals.

### 4. **Limit 5M Entries for Swing Modes (LOW PRIORITY)**

**Where:** `scanner_modes.py` - STEALTH and OVERWATCH modes  
**What:** Remove 5M from `entry_timeframes` for swing modes (OVERWATCH, STEALTH). Use 15M as the lowest entry TF for swings.  
**Impact:** Reduces noise and overtrading on swing setups.

### 5. **Add Entry Quality Scoring (LOW PRIORITY)**

**Where:** `confluence/scorer.py`  
**What:** Add a bonus for entries at premium/discount zones (not equilibrium) and penalties for entries far from HTF structure.  
**Impact:** Improves setup quality by favoring better entry locations.

---

## Comparison to Trading Principles

### ✅ What You're Doing Right:

1. **Mode-specific timeframe stacks** - each mode uses appropriate TFs for its strategy
2. **Timeframe responsibility enforcement** - entry/structure/stop TFs are clearly defined
3. **MACD mode-aware weighting** - properly adjusts MACD role per mode
4. **Confluence gating** - enforces minimum score thresholds per mode
5. **R:R validation** - ensures minimum R:R per mode before signaling

### ❌ What Needs Fixing:

1. **No HTF structural validation** - entries can occur anywhere, not just at HTF levels
2. **No momentum filter** - counter-trend trades allowed even during strong HTF momentum
3. **Unclear timeframe conflict resolution** - no explicit rules for 1W bull + 1D bear scenarios
4. **5M entries in swing modes** - creates noise for longer-term holds

---

## Final Verdict

Your scanner's **architecture is solid**, but it's missing **execution-level filters** that would align it with the trading principles we discussed. The timeframe stacks are correct, but the system treats all setups within those stacks equally, regardless of **where in the HTF structure** they occur.

**Priority fixes:**
1. Add HTF structural proximity validation
2. Implement momentum-based gating for counter-trend trades
3. Clarify conflict resolution rules

Make these changes and your scanner will be **institutional-grade** in how it respects timeframe hierarchy.

Let me know if you want me to draft the actual code implementations for any of these fixes.
