> Historical methodology and integration notes. The dated market assessment and
> UI examples below do not describe current runtime behavior or authorize cycle activation.
> See [the current architecture index](ARCHITECTURE_INDEX.md) for active paths and limits.

# Cycle Translation Intelligence System

## Overview

This system implements **Camel Finance's Cycle Translation methodology** for detecting trend strength across multiple timeframes. Translation analysis is fractal - the same logic applies from daily cycles up to the 4-year Bitcoin halving cycle.

## Core Concept: Translation

**Translation** measures WHERE a cycle's price peak occurs relative to the cycle's midpoint:

| Translation | Peak Position | Market Meaning | Trade Bias |
|-------------|---------------|----------------|------------|
| **RTR** (Right Translated) | After midpoint (>55%) | Bullish dominance | LONG favored |
| **MTR** (Mid Translated) | Near midpoint (45-55%) | Neutral/transitional | No clear bias |
| **LTR** (Left Translated) | Before midpoint (<45%) | Bearish dominance | SHORT favored |

### Why This Matters

- **RTR**: Price rallies for most of the cycle → short correction → higher low expected
- **LTR**: Brief rally ("blow-off top") → prolonged decline → lower low expected
- **Failed Cycle**: Price breaks below cycle low → trend CONFIRMED bearish

## Timeframes

### Daily Cycle Low (DCL)
- **Duration**: 18-28 days
- **Use**: Short-term timing and entries
- **Key signal**: LTR on daily = short-term weakness, avoid new longs

### Weekly Cycle Low (WCL)  
- **Duration**: 35-50 days
- **Use**: Intermediate trend assessment
- **Key signal**: WCL failure = first reliable confirmation bull run has ended

### 4-Year Cycle (4YC)
- **Duration**: ~1,460 days (4 years)
- **Anchor**: Bitcoin halving events
- **Key signal**: Historical peaks occur 12-18 months post-halving

## Implementation

### Backend Files

```
backend/strategy/smc/
├── symbol_cycle_detector.py    # Per-symbol DCL/WCL detection
├── four_year_cycle.py          # BTC 4-year macro cycle
└── cycle_detector.py           # Existing cycle low detection
```

### Frontend Components

```
src/components/market/
├── CycleBadge.tsx              # Single cycle indicator badge
├── SignalCycleBadges.tsx       # Badges for scanner signals
├── SymbolCyclePanel.tsx        # Full cycle panel for a symbol
├── BTCCycleIntel.tsx           # BTC cycle intelligence (all timeframes)
├── FourYearCycleGauge.tsx      # 4-year cycle visualization
└── index.ts                    # Exports
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/market/symbol-cycles?symbol=ETH/USDT` | DCL + WCL for any symbol |
| `GET /api/market/btc-cycle-context` | Complete BTC context (DCL + WCL + 4YC) |
| `GET /api/market/four-year-cycle` | 4-year macro cycle only |

## Detection Algorithm

### Step 1: Find Cycle Low
```python
# Find most recent significant swing low
swing_lows = find_swing_lows(df, lookback=3)  # N bars each side
cycle_low = most_recent_valid_swing_low(swing_lows)
```

### Step 2: Find Cycle High (Peak)
```python
# Highest point since cycle low
post_low_df = df[cycle_low_idx:]
cycle_high = post_low_df['high'].max()
peak_bar = argmax(post_low_df['high']) - cycle_low_idx
```

### Step 3: Calculate Translation
```python
# Where did peak occur relative to progress?
translation_pct = (peak_bar / bars_since_low) * 100

if translation_pct >= 55:
    translation = "RTR"  # Bullish
elif translation_pct <= 45:
    translation = "LTR"  # Bearish
else:
    translation = "MTR"  # Neutral
```

### Step 4: Check for Failure
```python
# Price below cycle low = FAILED
is_failed = current_price < cycle_low_price
```

## UI Integration

### Scanner Results

Each signal displays its symbol's cycle context:

```
┌─────────────────────────────────────────────────────────┐
│  ETH/USDT LONG  Score: 78                              │
├─────────────────────────────────────────────────────────┤
│  [DCL D22/28 RTR 🟢] [WCL D38/50 RTR 🟢] [4YC MARKUP 🟢]│
│                                                         │
│  ✓ All cycles support LONG                             │
└─────────────────────────────────────────────────────────┘
```

### Market Intel Page

Full BTC Cycle Intelligence panel showing all three timeframes:

```
┌─────────────────────────────────────────────────────────┐
│  ₿ BTC CYCLE INTELLIGENCE                              │
├─────────────────────────────────────────────────────────┤
│  DAILY CYCLE      │  WEEKLY CYCLE     │  4-YEAR MACRO  │
│  Day 22/25        │  Day 38/45        │  Day 1,136     │
│  Peak: Day 18     │  Peak: Day 29     │  Phase: MARKUP │
│  RTR 🟢           │  RTR 🟢           │  RTR 🟢        │
│  Bias: LONG       │  Bias: LONG       │  Bias: BULLISH │
└─────────────────────────────────────────────────────────┘
```

### Chart Modal

Symbol-specific cycle panel when viewing a symbol's chart.

## Alert Conditions

| Condition | Alert Type | Message |
|-----------|------------|---------|
| Entering DCL window | INFO | "{SYMBOL} entering Daily Cycle Low window" |
| DCL failed | WARNING | "{SYMBOL} DCL FAILED - broke ${price}" |
| DCL left-translated | WARNING | "{SYMBOL} DCL left-translated - short-term weakness" |
| WCL failed | CRITICAL | "🚨 {SYMBOL} Weekly Cycle FAILED - trend reversal confirmed" |
| WCL left-translated | WARNING | "⚠️ {SYMBOL} WCL left-translated - intermediate weakness" |
| 4YC danger zone | WARNING | "BTC entering late-cycle danger zone" |

## Usage Examples

### Fetch Symbol Cycles (Frontend)
```typescript
import { api } from '@/utils/api';

const response = await api.getSymbolCycles('ETH/USDT', 'bybit');
if (response.data?.status === 'success') {
  const { dcl, wcl, overall_bias, warnings } = response.data.data;
  console.log(`DCL: ${dcl.translation} | WCL: ${wcl.translation}`);
}
```

### Fetch BTC Context (Frontend)
```typescript
const btcContext = await api.getBTCCycleContext();
const { dcl, wcl, four_year_cycle, overall } = btcContext.data.data;
console.log(`BTC Alignment: ${overall.alignment}`);
```

### Display in Component
```tsx
import { SignalCycleBadges } from '@/components/market';

<SignalCycleBadges
  symbolCycles={cycleData}
  btcMacroBias={btcContext.four_year_cycle.macro_bias}
  signalDirection={signal.direction}
/>
```

## Key Decision Points

1. **Per-symbol cycles**: Each symbol has its own DCL/WCL timing - don't assume BTC's cycles apply to all
2. **4YC is BTC-only**: The 4-year halving cycle only applies to BTC but affects all crypto markets
3. **Visual not scoring**: Cycle context is displayed as visual aid - trader makes final decision
4. **Failed cycles are serious**: A failed WCL is the first reliable confirmation a bull run has ended

## Current Cycle Status (Dec 2025)

Based on the 4-year cycle anchored to Nov 21, 2022 FTX bottom:

| Metric | Value |
|--------|-------|
| Days since 4YC low | ~1,136 |
| Cycle position | ~78% |
| Phase | DISTRIBUTION |
| Macro bias | BEARISH |
| Days since halving | ~620 (Apr 2024) |
| Expected next low | Mid-late 2026 |

**Implication**: Late cycle - caution on new longs, prepare for markdown phase.

## Files Modified

- `backend/api_server.py` - Added `/api/market/symbol-cycles` and `/api/market/btc-cycle-context` endpoints
- `src/utils/api.ts` - Added TypeScript types and API methods

## Files Created

- `backend/strategy/smc/symbol_cycle_detector.py` - Core detection module
- `src/components/market/CycleBadge.tsx` - Badge component
- `src/components/market/SignalCycleBadges.tsx` - Signal badges
- `src/components/market/SymbolCyclePanel.tsx` - Full panel
- `src/components/market/BTCCycleIntel.tsx` - BTC intelligence panel
- `src/components/market/index.ts` - Component exports

## Next Steps

1. **Integrate into Scanner Results** - Add `<SignalCycleBadges>` to signal cards
2. **Add to Market Intel Page** - Add `<BTCCycleIntel>` component
3. **Chart Modal** - Add `<SymbolCyclePanel>` when viewing symbol details
4. **Notifications** - Wire up alert conditions to notification system
5. **Scanner Setup** - Show BTC cycle context in scanner configuration header

## References

- Camel Finance methodology
- Bitcoin halving cycle analysis
- Smart Money Concepts (SMC) cycle theory
