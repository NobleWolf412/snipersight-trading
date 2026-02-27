# Frontend-Backend Integration Guide

## Quick Start

### 1. Start Backend API

```bash
# Install dependencies
pip install -r requirements.txt

# Run API server
python -m backend.api
```

API will be available at: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

### 2. Start Frontend

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend will be available at: `http://localhost:5173`

---

## API Endpoints

### Scanner Endpoints

**POST `/api/scan`** - Run market scan
```typescript
Request: ScanConfigRequest {
  exchange: string
  topPairs: number
  customPairs: string[]
  categories: { majors, altcoins, memeMode }
  timeframes: string[]
  leverage: number
}
Response: ScanResult[]
```

**GET `/api/scan/results`** - Get cached scan results
```typescript
Response: ScanResult[]
```

### Bot Control Endpoints

**POST `/api/bot/configure`** - Configure bot parameters
```typescript
Request: BotConfigRequest {
  exchange: string
  pair: string
  modes: { swing, scalp }
  maxTrades: number
  duration: number
  leverage: number
}
Response: { success, message, config }
```

**POST `/api/bot/start`** - Start trading bot
```typescript
Query: ?wallet_address=string
Response: { success, message, balance }
```

**POST `/api/bot/stop`** - Stop trading bot
```typescript
Query: ?wallet_address=string
Response: { success, message }
```

**GET `/api/bot/status`** - Get bot status
```typescript
Query: ?wallet_address=string
Response: BotStatus {
  isActive: boolean
  currentTrades: number
  totalTrades: number
  profit: number
  winRate: number
  uptime: number
  lastActivity: string
}
```

**GET `/api/bot/activity`** - Get activity log
```typescript
Query: ?wallet_address=string&limit=number
Response: BotActivity[] {
  id, timestamp, action, pair, status, details
}
```

### Trading Endpoints

**POST `/api/trade/execute`** - Execute trade
```typescript
Request: TradeRequest {
  pair: string
  side: "BUY" | "SELL"
  orderType: "MARKET" | "LIMIT"
  quantity: number
  price?: number
  stopLoss?: number
  takeProfit?: number
}
Query: ?wallet_address=string
Response: { success, order_id, fill }
```

**POST `/api/position/calculate`** - Calculate position size
```typescript
Request: PositionSizeRequest {
  accountBalance: number
  pair: string
  currentPrice: number
  stopLossPrice: number
  riskPercentage: number
  leverage: number
}
Response: {
  quantity, notional_value, risk_amount,
  margin_required, leverage, is_valid
}
```

**GET `/api/portfolio/summary`** - Get portfolio summary
```typescript
Query: ?wallet_address=string
Response: {
  balance, equity, pnl, open_positions,
  risk_metrics, positions[]
}
```

---

## Data Models Alignment

### ScanResult
**Frontend:** `src/utils/mockData.ts`
**Backend:** `backend/api.py` - `ScanResult` Pydantic model

✅ **Aligned Fields:**
- `id, pair, trendBias, confidenceScore, riskScore`
- `classification, entryZone, stopLoss, takeProfits`
- `orderBlocks[], fairValueGaps[], timestamp`

### BotConfig
**Frontend:** `src/context/ScannerContext.tsx`
**Backend:** `backend/api.py` - `BotConfigRequest` model

✅ **Aligned Fields:**
- `exchange, pair, modes{}, maxTrades, duration, leverage`

### BotActivity
**Frontend:** `src/utils/mockData.ts`
**Backend:** `backend/api.py` - `BotActivity` model

✅ **Aligned Fields:**
- `id, timestamp, action, pair, status`

---

## Integration Steps

### Step 1: Update Frontend to Call Backend

Replace mock data calls in:

**`src/pages/ScannerSetup.tsx`:**
```typescript
// Replace this:
const results = generateMockScanResults(8);

// With this:
const response = await fetch('http://localhost:8000/api/scan', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(scanConfig)
});
const results = await response.json();
```

**`src/pages/BotSetup.tsx`:**
```typescript
// Start bot
await fetch(`http://localhost:8000/api/bot/start?wallet_address=${wallet.address}`, {
  method: 'POST'
});

// Get status
const response = await fetch(`http://localhost:8000/api/bot/status?wallet_address=${wallet.address}`);
const status = await response.json();
```

**`src/pages/BotStatus.tsx`:**
```typescript
// Get activity
const response = await fetch(`http://localhost:8000/api/bot/activity?wallet_address=${wallet.address}&limit=20`);
const activities = await response.json();
```

### Step 2: Add Environment Variables

Create `.env` file:
```env
VITE_API_URL=http://localhost:8000
```

Update `vite.config.ts` to proxy API:
```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

Then use relative URLs:
```typescript
fetch('/api/scan', { ... })  // No need for localhost:8000
```

### Step 3: Implement Real Scanning Logic

Backend TODO in `backend/api.py` -> `run_scan()`:

```python
async def run_scan(config: ScanConfigRequest):
    # 1. Fetch market data
    from backend.data.adapters.binance import BinanceAdapter
    adapter = BinanceAdapter()
    pairs = await adapter.get_top_pairs(config.topPairs)
    
    # 2. Get OHLCV data
    from backend.data.ingestion_pipeline import IngestionPipeline
    pipeline = IngestionPipeline(adapter)
    data = await pipeline.fetch_multi_timeframe(pairs, config.timeframes)
    
    # 3. Run SMC analysis
    from backend.strategy.smc import detect_order_blocks, detect_fvg
    results = []
    for pair, timeframe_data in data.items():
        obs = detect_order_blocks(timeframe_data)
        fvgs = detect_fvg(timeframe_data)
        
        # 4. Calculate confluence
        from backend.strategy.confluence.scorer import ConfluenceScorer
        scorer = ConfluenceScorer()
        score = scorer.calculate_score(obs, fvgs, timeframe_data)
        
        # 5. Create scan result
        results.append(ScanResult(...))
    
    return results
```

### Step 4: Add WebSocket for Real-Time Updates

For live bot activity:

**Backend:**
```python
from fastapi import WebSocket

@app.websocket("/ws/bot/activity/{wallet_address}")
async def websocket_activity(websocket: WebSocket, wallet_address: str):
    await websocket.accept()
    while True:
        # Send new activities
        activities = bot_activities.get(wallet_address, [])[:5]
        await websocket.send_json(activities)
        await asyncio.sleep(1)
```

**Frontend:**
```typescript
const ws = new WebSocket(`ws://localhost:8000/ws/bot/activity/${wallet.address}`);
ws.onmessage = (event) => {
  const activities = JSON.parse(event.data);
  setActivities(activities);
};
```

---

## Testing Integration

### 1. Test API Health
```bash
curl http://localhost:8000/
```

### 2. Test Scan Endpoint
```bash
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "Binance",
    "topPairs": 20,
    "timeframes": ["1H", "4H"],
    "leverage": 1
  }'
```

### 3. Test Position Calculator
```bash
curl -X POST http://localhost:8000/api/position/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "accountBalance": 10000,
    "pair": "BTC/USDT",
    "currentPrice": 50000,
    "stopLossPrice": 49000,
    "riskPercentage": 1.0,
    "leverage": 1
  }'
```

### 4. Test with Frontend
1. Start backend: `python -m backend.api`
2. Start frontend: `npm run dev`
3. Navigate to scanner setup
4. Verify API calls in browser DevTools Network tab

---

## Current Implementation Status

✅ **Completed:**
- Backend API structure with all endpoints
- Pydantic models matching UI TypeScript interfaces
- Position sizer integration
- Risk manager integration
- Paper executor integration
- Activity logging system
- **Real market data fetching** (`/api/scan` via Phemex, Bybit, OKX, Bitget)
- **SMC analysis integration** (OB, FVG, BOS/CHoCH detection)
- **Confluence scoring** (multi-factor weighted scoring)
- **Trade plan generation** (entries, stops, targets, R:R)
- **Telemetry system** (real-time event logging)

⏳ **TODO:**
- Live trading executor (paper trading works)
- WebSocket real-time updates (polling implemented)

🎯 **Next Steps:**
1. Add WebSocket for live activity feed
2. Implement live trading executor with exchange APIs
3. Add exchange API keys management UI
