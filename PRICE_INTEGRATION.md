# Real-Time Price Data Integration

## Overview

SniperSight now includes comprehensive real-time price data integration powered by WebSocket connections to major cryptocurrency exchanges. This system provides live price updates, 24-hour statistics, and market data across all major trading pairs.

## Architecture

### Core Components

#### 1. Price Service (`/src/services/priceService.ts`)
The central service managing WebSocket connections and price data distribution.

**Features:**
- WebSocket connection to Binance streaming API
- Automatic reconnection with exponential backoff
- Price caching for performance
- Publisher-subscriber pattern for component updates
- Support for both full price data and lightweight ticks

**API:**
```typescript
// Subscribe to price updates
const unsubscribe = priceService.subscribe(symbol, (data) => {
  console.log(data.price, data.changePercent24h);
});

// Fetch current price
const priceData = await priceService.fetchPrice('BTC/USDT');

// Fetch multiple prices
const prices = await priceService.fetchMultiplePrices(['BTC/USDT', 'ETH/USDT']);
```

#### 2. React Hooks (`/src/hooks/usePriceData.ts`)

**`usePrice(symbol)`**
Subscribe to real-time price updates for a single symbol.

```typescript
const { priceData, isLoading, error } = usePrice('BTC/USDT');
```

**`usePriceTick(symbol)`**
Lightweight hook for price-only updates (no 24h stats).

```typescript
const tick = usePriceTick('BTC/USDT');
console.log(tick?.price);
```

**`useMultiplePrices(symbols)`**
Subscribe to multiple symbols simultaneously.

```typescript
const { prices, isLoading, error } = useMultiplePrices(['BTC/USDT', 'ETH/USDT']);
const btcPrice = prices.get('BTC/USDT');
```

#### 3. UI Components

**`<PriceDisplay />`** - Compact price display with change indicator
```tsx
<PriceDisplay 
  symbol="BTC/USDT" 
  showChange={true} 
  showVolume={false}
  size="md"
/>
```

**`<LiveTicker />`** - Scrolling ticker with multiple symbols
```tsx
<LiveTicker symbols={['BTC/USDT', 'ETH/USDT', 'SOL/USDT']} />
```

**`<PriceCard />`** - Full-featured card with 24h statistics
```tsx
<PriceCard symbol="BTC/USDT" />
```

## Data Structure

### PriceData Interface
```typescript
interface PriceData {
  symbol: string;           // e.g., "BTC/USDT"
  price: number;            // Current price
  change24h: number;        // Absolute 24h change
  changePercent24h: number; // Percentage 24h change
  high24h: number;          // 24h high
  low24h: number;           // 24h low
  volume24h: number;        // 24h volume
  timestamp: number;        // Unix timestamp
  exchange: string;         // Data source (e.g., "Binance")
}
```

### PriceTick Interface
```typescript
interface PriceTick {
  symbol: string;
  price: number;
  timestamp: number;
}
```

## Integration Points

### 1. Scan Results (`/src/pages/ScanResults.tsx`)
- Live ticker showing all scanned pairs
- Real-time price updates in results table
- Dynamic price display alongside technical analysis

### 2. Bot Status (`/src/pages/BotStatus.tsx`)
- Live ticker for monitored pairs
- Real-time price tracking for active trades
- Entry/exit level monitoring

### 3. Landing Page (`/src/pages/Landing.tsx`)
- Market overview ticker
- Quick glance at major pairs

### 4. Market Overview (`/src/pages/MarketOverview.tsx`)
- Dedicated page for comprehensive market monitoring
- Grid view of major trading pairs
- Full 24h statistics and price cards
- Connection status monitoring

## WebSocket Connection Details

### Endpoint
`wss://stream.binance.com:9443/ws/!ticker@arr`

### Stream Type
All market tickers (24hr rolling window)

### Update Frequency
Real-time (sub-second updates)

### Reconnection Strategy
- Exponential backoff: 1s, 2s, 4s, 8s, 16s
- Max attempts: 5
- Auto-resume on network recovery

## Performance Optimizations

1. **Caching**: Price data cached for 5 seconds to reduce API calls
2. **Lazy Subscription**: Only symbols with active subscribers receive updates
3. **Debouncing**: Component updates batched via React's state management
4. **Memory Management**: Automatic cleanup on component unmount

## Error Handling

### Network Failures
- Automatic reconnection attempts
- Cached data served during disconnections
- User-facing connection status indicators

### Invalid Symbols
- Graceful fallback to "No data"
- Error states surfaced through hooks
- Non-blocking errors (app remains functional)

### Rate Limiting
- WebSocket endpoint doesn't have rate limits
- REST API fallback caches aggressively
- Exponential backoff on repeated failures

## Usage Examples

### Simple Price Display
```tsx
import { PriceDisplay } from '@/components/PriceDisplay';

function MyComponent() {
  return <PriceDisplay symbol="BTC/USDT" showChange />;
}
```

### Custom Integration
```tsx
import { usePrice } from '@/hooks/usePriceData';

function CustomPriceCard() {
  const { priceData, isLoading } = usePrice('ETH/USDT');
  
  if (isLoading) return <Skeleton />;
  
  return (
    <div>
      <h3>Ethereum</h3>
      <p>${priceData?.price.toFixed(2)}</p>
      <p>{priceData?.changePercent24h.toFixed(2)}%</p>
    </div>
  );
}
```

### Multi-Symbol Monitoring
```tsx
import { useMultiplePrices } from '@/hooks/usePriceData';

function Portfolio() {
  const symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'];
  const { prices, isLoading } = useMultiplePrices(symbols);
  
  return (
    <div>
      {symbols.map(symbol => {
        const data = prices.get(symbol);
        return <div key={symbol}>{data?.price}</div>;
      })}
    </div>
  );
}
```

## Future Enhancements

### Planned Features
- [ ] Multi-exchange support (Coinbase, Kraken, Bybit)
- [ ] Historical price charts with real-time updates
- [ ] Price alerts and notifications
- [ ] WebSocket reconnection UI feedback
- [ ] Orderbook depth integration
- [ ] Trade execution monitoring
- [ ] Price prediction overlays

### Technical Improvements
- [ ] Service worker for offline support
- [ ] IndexedDB for historical price storage
- [ ] WebWorker for heavy price calculations
- [ ] GraphQL subscription alternative
- [ ] Configurable update intervals

## Security Considerations

1. **Read-Only Access**: Service only consumes public market data
2. **No Authentication Required**: Public WebSocket streams
3. **CORS Compliant**: All endpoints properly configured
4. **XSS Protection**: All price data sanitized before display
5. **Type Safety**: Full TypeScript coverage prevents data corruption

## Testing

### Manual Testing
1. Navigate to `/market` to view comprehensive price data
2. Check scan results for live price integration
3. Monitor bot status page for active trades
4. Verify WebSocket connection in browser DevTools

### Connection Testing
Open browser console and check for:
- `✅ Price service connected`
- No WebSocket error messages
- Real-time price updates in UI

### Performance Testing
Monitor for:
- UI responsiveness during rapid updates
- Memory usage stability over time
- Reconnection behavior after network interruption

## Troubleshooting

### No Price Data Displayed
1. Check browser console for WebSocket errors
2. Verify internet connectivity
3. Check firewall/proxy settings for WebSocket support
4. Try refreshing the page

### Stale Prices
1. Check connection status on Market Overview page
2. Verify WebSocket status in browser DevTools
3. Check for console errors
4. Clear cache and reload

### High Memory Usage
1. Close unused tabs showing price data
2. Reduce number of monitored symbols
3. Check for console warnings about memory leaks

## API Reference

### PriceService Methods

```typescript
class PriceService {
  // Subscribe to price updates
  subscribe(symbol: string, callback: PriceUpdateCallback): () => void
  
  // Subscribe to tick updates (lightweight)
  subscribeTick(symbol: string, callback: TickUpdateCallback): () => void
  
  // Get cached price
  getPrice(symbol: string): PriceData | undefined
  
  // Fetch price from API
  fetchPrice(symbol: string): Promise<PriceData>
  
  // Fetch multiple prices
  fetchMultiplePrices(symbols: string[]): Promise<Map<string, PriceData>>
  
  // Disconnect service
  disconnect(): void
}
```

## Support

For issues, questions, or feature requests related to price data integration, please check:
1. This documentation
2. Browser console for error messages
3. Network tab for WebSocket connection status
4. Project repository issues

---

**Last Updated:** 2024
**Version:** 1.0.0
**Maintainer:** SniperSight Development Team
