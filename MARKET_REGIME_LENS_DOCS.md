# Market Regime Lens Component - Integration Guide

## Overview
The Market Regime Lens is a tactical HUD component that displays the current market regime based on BTC/USDT/Alt dominance. It provides visual context and actionable guidance for both scanning and bot deployment scenarios.

## Files Created

### 1. Component
- **Path**: `/src/components/market/MarketRegimeLens.tsx`
- **Purpose**: Reusable tactical lens component with sniper scope visual design
- **Exports**: 
  - `MarketRegimeLens` (component)
  - `MarketRegimeLensProps` (TypeScript interface)
  - `RegimeLabel`, `Visibility`, `RegimeColor` (TypeScript types)

### 2. Mock Data Hook
- **Path**: `/src/hooks/use-mock-market-regime.ts`
- **Purpose**: Provides mock market regime data for development/testing
- **Exports**: `useMockMarketRegime(mode: 'scanner' | 'bot')`

## Integration Points

### Scanner Page
- **File**: `/src/pages/ScannerSetup.tsx`
- **Location**: Below page header, above scanner configuration card
- **Section Label**: "MARKET CONTEXT"

### Bot Page
- **File**: `/src/pages/BotSetup.tsx`
- **Location**: Below page header, above wallet gate section
- **Section Label**: "MARKET CONTEXT"

## Component Props

```typescript
interface MarketRegimeLensProps {
  regimeLabel: "ALTSEASON" | "BTC_DRIVE" | "DEFENSIVE" | "PANIC" | "CHOPPY";
  visibility: "HIGH" | "MEDIUM" | "LOW" | "VERY_LOW";
  color?: "green" | "blue" | "yellow" | "orange" | "red";
  btcDominance?: number;
  usdtDominance?: number;
  altDominance?: number;
  guidanceLines?: string[];
  mode?: "scanner" | "bot";
  previousBtcDominance?: number;
  previousUsdtDominance?: number;
  previousAltDominance?: number;
}
```

## Visual Features

### Circular Lens/Reticle
- Circular sniper scope design with nested rings
- Cross-hair reticle overlay
- Color-coded based on regime (auto-derived from `regimeLabel` or manual via `color` prop)
- Center displays visibility percentage (HIGH=90%, MEDIUM=60%, LOW=35%, VERY_LOW=15%)

### Information Display
- **Regime Label**: Large, prominent display of current market regime
- **Visibility Badge**: Shows clarity level of market signals
- **Risk Multiplier Badge** (bot mode only): Shows bot position sizing multiplier
- **Dominance Values**: BTC.D, USDT.D, ALT.D with trend arrows (↑/↓/→)
- **Guidance Lines**: 2-4 actionable insights (collapsible if >2)

### Color Schemes
Each regime has associated colors:
- **ALTSEASON**: Green (success)
- **BTC_DRIVE**: Blue
- **DEFENSIVE**: Orange
- **PANIC**: Red (destructive)
- **CHOPPY**: Yellow (warning)

### Trend Indicators
- **Up Arrow (↑)**: Dominance increased >0.1%
- **Down Arrow (↓)**: Dominance decreased >0.1%
- **Right Arrow (→)**: Dominance stable (±0.1%)

## Backend Integration (TODO)

### Current State
Both pages use `useMockMarketRegime()` hook to provide static mock data for UI development.

### Future Integration Steps

#### 1. Create Real Market Regime Hook
Create `/src/hooks/use-market-regime.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';

interface MarketRegimeResponse {
  regime_label: string;
  visibility: string;
  btc_dominance: number;
  usdt_dominance: number;
  alt_dominance: number;
  previous_btc_dominance: number;
  previous_usdt_dominance: number;
  previous_alt_dominance: number;
  guidance_scanner: string[];
  guidance_bot: string[];
}

export function useMarketRegime(mode: 'scanner' | 'bot' = 'scanner') {
  const { data, isLoading, error } = useQuery({
    queryKey: ['market-regime'],
    queryFn: async () => {
      const response = await fetch('/api/market-regime');
      if (!response.ok) throw new Error('Failed to fetch market regime');
      return response.json() as Promise<MarketRegimeResponse>;
    },
    refetchInterval: 60000, // Refresh every 60 seconds
  });

  if (!data) {
    return null;
  }

  return {
    regimeLabel: data.regime_label as RegimeLabel,
    visibility: data.visibility as Visibility,
    btcDominance: data.btc_dominance,
    usdtDominance: data.usdt_dominance,
    altDominance: data.alt_dominance,
    previousBtcDominance: data.previous_btc_dominance,
    previousUsdtDominance: data.previous_usdt_dominance,
    previousAltDominance: data.previous_alt_dominance,
    guidanceLines: mode === 'bot' ? data.guidance_bot : data.guidance_scanner,
    mode,
  };
}
```

#### 2. Update Scanner Page
In `/src/pages/ScannerSetup.tsx`, replace:

```typescript
const marketRegimeProps = useMockMarketRegime('scanner');
```

With:

```typescript
const marketRegimeProps = useMarketRegime('scanner');

if (!marketRegimeProps) {
  return <div>Loading market data...</div>;
}
```

#### 3. Update Bot Page
In `/src/pages/BotSetup.tsx`, replace:

```typescript
const marketRegimeProps = useMockMarketRegime('bot');
```

With:

```typescript
const marketRegimeProps = useMarketRegime('bot');

if (!marketRegimeProps) {
  return <div>Loading market data...</div>;
}
```

#### 4. Expected Backend API Response

**Endpoint**: `GET /api/market-regime`

**Response Format**:
```json
{
  "regime_label": "DEFENSIVE",
  "visibility": "LOW",
  "btc_dominance": 53.4,
  "usdt_dominance": 7.9,
  "alt_dominance": 38.7,
  "previous_btc_dominance": 51.2,
  "previous_usdt_dominance": 7.1,
  "previous_alt_dominance": 41.7,
  "guidance_scanner": [
    "Money rotating into BTC & stables",
    "Favor BTC/ETH setups only",
    "Reduce size on alt trades",
    "Avoid new degen entries"
  ],
  "guidance_bot": [
    "Bot Risk Multiplier: 0.5x (Defensive Mode)",
    "Bot will not open new altcoin positions",
    "BTC/ETH allowed, reduced size",
    "Tighter stop-losses engaged"
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Valid Values**:
- `regime_label`: "ALTSEASON" | "BTC_DRIVE" | "DEFENSIVE" | "PANIC" | "CHOPPY"
- `visibility`: "HIGH" | "MEDIUM" | "LOW" | "VERY_LOW"
- Dominance values: 0-100 (percentages)
- `guidance_scanner` and `guidance_bot`: Array of 2-6 strings

## Usage Examples

### Basic Usage
```tsx
import { MarketRegimeLens } from '@/components/market/MarketRegimeLens';

<MarketRegimeLens
  regimeLabel="ALTSEASON"
  visibility="HIGH"
  btcDominance={45.2}
  usdtDominance={5.3}
  altDominance={49.5}
  guidanceLines={[
    'Strong altcoin momentum',
    'BTC dominance falling',
    'High-conviction alt entries recommended'
  ]}
/>
```

### With Mode-Specific Guidance
```tsx
<MarketRegimeLens
  regimeLabel="DEFENSIVE"
  visibility="LOW"
  mode="bot"
  btcDominance={53.4}
  usdtDominance={7.9}
  altDominance={38.7}
  guidanceLines={[
    'Bot Risk Multiplier: 0.5x (Defensive Mode)',
    'Bot will not open new altcoin positions',
    'BTC/ETH allowed, reduced size'
  ]}
/>
```

### With Trend Data
```tsx
<MarketRegimeLens
  regimeLabel="BTC_DRIVE"
  visibility="MEDIUM"
  btcDominance={52.1}
  usdtDominance={6.2}
  altDominance={41.7}
  previousBtcDominance={50.3}
  previousUsdtDominance={6.8}
  previousAltDominance={42.9}
  guidanceLines={[
    'BTC leading the market',
    'Monitor BTC breakouts',
    'Alt strength selective'
  ]}
/>
```

## Responsive Behavior

- **Desktop (≥768px)**: Lens and info displayed side-by-side
- **Mobile (<768px)**: Lens on top, info stacked below
- Lens size: 112px (mobile) / 128px (desktop)
- All text scales appropriately
- Collapsible guidance section for better mobile UX

## Accessibility

- Semantic HTML structure
- Color is not the only indicator (text labels always present)
- Keyboard navigable (collapsible sections)
- Screen-reader friendly trend indicators

## Customization

### Override Color
```tsx
<MarketRegimeLens
  regimeLabel="DEFENSIVE"
  color="red"  // Override default orange
  visibility="LOW"
/>
```

### Custom Guidance
```tsx
<MarketRegimeLens
  regimeLabel="CHOPPY"
  visibility="VERY_LOW"
  guidanceLines={[
    'Custom guidance line 1',
    'Custom guidance line 2',
    'Custom guidance line 3',
    'Custom guidance line 4'
  ]}
/>
```

## Testing Checklist

- [ ] Component renders correctly on Scanner page
- [ ] Component renders correctly on Bot page
- [ ] All 5 regime types display with correct colors
- [ ] All 4 visibility levels display correct percentages
- [ ] Dominance values format correctly (1 decimal place)
- [ ] Trend arrows display correctly (↑/↓/→)
- [ ] Guidance collapsible works (when >2 lines)
- [ ] Risk multiplier badge shows only in bot mode
- [ ] Responsive layout works on mobile
- [ ] Color schemes apply correctly to all elements
- [ ] Ready for backend integration (hook can be swapped)
