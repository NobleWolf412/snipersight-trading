# Quick Diagnostic Guide: Low Signal Count

## Your Situation
**Scanning:** 20 symbols  
**Getting:** 2 signals  
**Rate:** 10% (2/20)

**This could be:**
1. ✅ Working as intended (institutional-grade filtering)
2. ⚠️ A bug or misconfiguration
3. ⚠️ Overly restrictive thresholds

---

## Step 1: Check Your Logs (RIGHT NOW)

When you run the scanner, look for these lines in the output:

```
⚪ SYMBOL: No qualifying setup
❌ GATE FAIL (confluence) | Score=52.3 < 60.0
```

**What to look for:**
- How many say "GATE FAIL (confluence)" vs other reasons?
- What's the typical gap? (Score=52 vs Required=60 = 8 point gap)

---

## Step 2: Identify The Bottleneck

Run the scanner with logging enabled:

```bash
# If using CLI
python backend/cli.py scan --symbols BTC/USDT ETH/USDT SOL/USDT ADA/USDT BNB/USDT --mode strike --log-level INFO

# Check the output for rejection reasons
```

**Look for patterns:**

### Pattern 1: "low_confluence" dominates (70%+ of rejections)
```
⚪ BTC/USDT: ❌ GATE FAIL (confluence) | Score=52.3 < 60.0 | Top: HTF_Structure=-5 | MACD=8 | RSI=12
⚪ ETH/USDT: ❌ GATE FAIL (confluence) | Score=48.1 < 60.0 | Top: OB=15 | FVG=10 | BOS=8
```

**THIS MEANS:** Your confluence threshold is too high OR your scoring is broken.

**FIX OPTIONS:**
1. Lower `min_confluence_score` by 5-10 points
2. Check if any factors are consistently negative (dragging score down)

---

### Pattern 2: "missing_critical_tf" dominates (30%+ of rejections)
```
⚪ SYMBOL: ⚠️ Missing critical timeframes: 1W, 1D
⚪ SYMBOL: ⚠️ Missing critical timeframes: 1D
```

**THIS MEANS:** Your exchange doesn't have weekly/daily data OR data fetch is failing.

**FIX:**
1. Check which TFs are missing
2. Remove them from `critical_timeframes` in mode config
3. Or verify exchange has this data

---

### Pattern 3: "no_data" dominates (20%+ of rejections)
```
⚪ SYMBOL: Data ingestion failed
```

**THIS MEANS:** API connection issues.

**FIX:**
1. Check API rate limits
2. Verify API keys
3. Check network

---

### Pattern 4: "no_trade_plan" dominates (20%+ of rejections)
```
⚪ SYMBOL: Trade planner failed to generate plan
```

**THIS MEANS:** Planner can't find valid structure for stops/targets.

**FIX:**
1. Check if SMC patterns are being detected
2. Verify timeframe responsibility settings

---

## Step 3: Check Your Mode Config

### STRIKE Mode (default settings):
```python
min_confluence_score=60.0  # Moderate threshold
critical_timeframes=("15m",)  # Only 15m is critical
timeframes=("4h", "1h", "15m", "5m")
```

**If getting <10% signal rate:**
- Try lowering min_confluence_score to 55.0
- Check if 15m data is loading

### OVERWATCH Mode:
```python
min_confluence_score=75.0  # HIGH threshold
critical_timeframes=("1w", "1d")  # Weekly & Daily critical
```

**If getting <5% signal rate:**
- This is EXPECTED for macro mode (very selective)
- Try lowering to 70.0 if too restrictive

### SURGICAL Mode:
```python
min_confluence_score=70.0  # HIGH threshold
critical_timeframes=("15m",)
```

**If getting <5% signal rate:**
- Lower to 65.0
- Very selective by design

---

## Step 4: Run Diagnostic Script

I created a diagnostic script for you. Run it:

```bash
python backend/debug_scanner_bottleneck.py --mode strike --count 20
```

This will show you:
1. **Rejection Breakdown** - Which filter is rejecting most signals
2. **Confluence Factor Analysis** - Which factors are weakest
3. **Recommendations** - What to adjust

---

## Step 5: Common Issues & Fixes

### Issue 1: Score consistently 5-15 points below threshold

**Diagnosis:** One or two factors are consistently negative or missing.

**Check:**
```
Top factors: HTF_Structure=-15 | MACD=8 | RSI=12
```

If HTF_Structure is consistently negative, that's the bottleneck.

**Fix:**
- Check if HTF data is loading (4H/1D/1W)
- Verify swing structure detection is working
- Lower HTF alignment penalties in scorer.py

---

### Issue 2: "Missing critical timeframes: 1W, 1D"

**Diagnosis:** Weekly/Daily data not loading from exchange.

**Fix:**
Edit `backend/shared/config/scanner_modes.py`:

```python
# BEFORE (OVERWATCH mode)
critical_timeframes=("1w", "1d"),

# AFTER - Remove weekly if exchange doesn't support it
critical_timeframes=("1d",),
```

---

### Issue 3: Getting signals on ONLY BTC/ETH, nothing else

**Diagnosis:** Regime gate is blocking altcoins.

**Fix:**
Check `regime_detector.py` - it might be requiring high BTC correlation.

Temporarily disable regime gate:
```python
# In orchestrator.py, line ~275
if self.current_regime.score < self.regime_policy.min_regime_score:
    logger.warning("⚠️ Regime score %.1f below minimum", self.current_regime.score)
    # COMMENT OUT RETURN - let it continue anyway
    # return None, {...}
```

---

### Issue 4: Planner can't generate trade plans

**Diagnosis:** No valid structure for stop loss placement.

**Check:**
- Are order blocks being detected? (Look for "OB=0" in logs)
- Are FVGs being detected?
- Are there structural breaks?

**Fix:**
Lower SMC detection thresholds:
```python
# In backend/shared/config/smc_config.py
class SMCConfig:
    min_ob_displacement_atr: float = 1.0  # Lower from 1.5
    min_fvg_size_atr: float = 0.3  # Lower from 0.5
```

---

## Step 6: Expected Signal Rates by Mode

### OVERWATCH (Macro Surveillance)
**Expected:** 5-15% signal rate  
**Why:** Very selective, hunting only high-conviction macro swings

### STRIKE (Intraday Aggressive)
**Expected:** 15-30% signal rate  
**Why:** More aggressive, catches intraday momentum

### SURGICAL (Precision Scalping)
**Expected:** 10-20% signal rate  
**Why:** High quality only, tight entries

### STEALTH (Balanced Swing)
**Expected:** 15-25% signal rate  
**Why:** Balanced approach

**Your 10% rate in STRIKE is on the LOW end but not broken.**

---

## Quick Fixes to Try (in order)

### 1. Lower Confluence Threshold (EASIEST)
```python
# In backend/shared/config/scanner_modes.py
"strike": ScannerMode(
    # ...
    min_confluence_score=55.0,  # Lower from 60.0
)
```

### 2. Remove Critical Timeframes (if missing data)
```python
"strike": ScannerMode(
    # ...
    critical_timeframes=(),  # Empty = none required
)
```

### 3. Check HTF Data is Loading
```python
# Add this logging in orchestrator.py _detect_smc_patterns()
logger.info("📊 Available timeframes: %s", list(multi_tf_data.timeframes.keys()))
logger.info("📊 4H candles: %d | 1D candles: %d", 
           len(multi_tf_data.timeframes.get('4h', [])),
           len(multi_tf_data.timeframes.get('1d', [])))
```

### 4. Temporarily Disable Regime Gate
```python
# In orchestrator.py, line ~275
# Comment out the regime score check
```

---

## What's Your Next Step?

1. **Run a scan and check the logs** - look for "GATE FAIL" patterns
2. **Run the diagnostic script** - `python backend/debug_scanner_bottleneck.py`
3. **Share the output with me** - I'll tell you exactly what's wrong

**Most likely culprits:**
- Confluence threshold too high (60→55 will help)
- HTF data not loading properly
- One factor consistently dragging score down

Let me know what you find!
