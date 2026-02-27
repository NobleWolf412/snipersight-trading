# How to Get Confluence Breakdown

Since the Python environment needs setup, here are **3 easy ways** to see the confluence breakdown:

## Option 1: Run Through Your Existing Setup (Easiest)

If you normally run the backend through your IDE or existing setup:

1. **Start your backend** (however you normally do it - venv, IDE, etc.)
2. **Run an OVERWATCH scan** through the frontend or API
3. **Check the console/logs** for lines starting with:
   ```
   📊 CONFLUENCE BREAKDOWN | SYMBOL LONG/SHORT
   ├─ Final Score: XX.XX (Raw: XX.XX)
   ├─ Components:
   │  ├─ Weighted Base: XX.XX
   │  ├─ Synergy Bonus: +XX.XX
   │  ├─ Conflict Penalty: -XX.XX
   │  └─ Macro Score: XX.XX
   └─ Top Factors:
      1. Factor Name: XX.X × 0.XX = XX.XXpts
      ...
   ```

## Option 2: Check Recent Logs

If you've run scans recently, the breakdown might already be logged:

```bash
# Search backend logs
find . -name "*.log" -exec grep -l "CONFLUENCE BREAKDOWN" {} \;

# Or check stdout/stderr logs
grep "📊 CONFLUENCE BREAKDOWN" <your-log-file>
```

## Option 3: Add Temporary File Logging

Add this to the top of `backend/strategy/confluence/scorer.py` to write breakdowns to a file:

```python
# Add after imports (around line 40)
import os
BREAKDOWN_LOG = open("/tmp/confluence_breakdown.log", "a")

# Then in the logging section (line 2547), add:
BREAKDOWN_LOG.write(f"\\n{trace_data}\\n")
BREAKDOWN_LOG.flush()
```

Then run a scan and check:
```bash
cat /tmp/confluence_breakdown.log
```

---

## What the Breakdown Shows

The enhanced logging reveals:

1. **Final Score** - After variance amplification curve
2. **Raw Score** - Before curve (base + synergy - penalty)
3. **Components**:
   - **Weighted Base**: Sum of all factor scores × weights
   - **Synergy Bonus**: Positive boost from factor alignment
   - **Conflict Penalty**: Negative penalty from conflicts
   - **Macro Score**: BTC/market regime overlay
4. **Top 5 Factors**: Which factors contributed most to the score

---

## What to Look For (Score Inflation Investigation)

### ✅ **Healthy Breakdown** (Score 78-82):
```
Final Score: 79.50 (Raw: 75.20)
├─ Weighted Base: 68.00
├─ Synergy Bonus: +5.00
├─ Conflict Penalty: -2.00
└─ Macro Score: +4.20
```

### 🚨 **Inflated Breakdown** (All pairs passing):
```
Final Score: 85.00 (Raw: 78.50)  ← Raw score already high
├─ Weighted Base: 70.00          ← Base scores generous
├─ Synergy Bonus: +12.00         ← SYNERGY TOO HIGH
├─ Conflict Penalty: -0.50       ← PENALTY TOO SMALL
└─ Macro Score: +6.00            ← Macro adding extra
```

### Key Inflation Indicators:
- **Raw score > 75** for most pairs (should be 60-75)
- **Synergy bonus > 10pts** (should be 3-8pts)
- **Conflict penalty < 2pts** (should be 5-15pts when conflicts exist)
- **Weighted base > 65** (should be 55-65)
- **Variance curve boosting 75+ by 5-8pts** (intended, but compounds if raw is already high)

---

## Next Steps After Seeing Results

Once you have the breakdown, share it and I can:
1. Identify which factors are scoring too generously
2. Check if synergy bonuses are stacking excessively
3. Verify conflict penalties are being applied
4. Adjust gradient curves or caps as needed
