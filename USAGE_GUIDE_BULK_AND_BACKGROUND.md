# Quick Start: Using Bulk Prices & Background Scans

## For End Users

### Background Scans (No More Timeouts!)

**How it works now**:
1. Click "Arm Scanner" in Scanner Setup
2. See instant response with progress: "Scanning 5/20 • BTC/USDT"
3. Progress bar updates every 2 seconds
4. Results appear when complete

**What changed**:
- ❌ **Old**: Wait 60+ seconds → see "504 Gateway Timeout"
- ✅ **New**: Instant response → watch progress → get results

**Benefits**:
- No more timeout errors
- See which symbol is being analyzed
- Can close tab and come back (job keeps running)
- Cancel mid-scan if needed (coming soon via UI button)

### Bulk Prices (Faster Watchlists)

**Automatic optimization** - no user action needed!

- Watchlists with 4+ symbols now fetch all prices in one request
- 20x faster loading for large watchlists
- Less strain on exchange APIs (fewer rate limits)

---

## For Developers

### Testing Bulk Prices

**Backend endpoint**:
```bash
curl "http://localhost:5000/api/market/prices?symbols=BTC/USDT,ETH/USDT,SOL/USDT&exchange=phemex"
```

**Response**:
```json
{
  "prices": [
    {"symbol": "BTC/USDT", "price": 91379.30, "timestamp": "2025-11-27T03:06:00Z"},
    {"symbol": "ETH/USDT", "price": 3037.79, "timestamp": "2025-11-27T03:06:00Z"}
  ],
  "total": 2,
  "errors": null,
  "exchange": "phemex"
}
```

**Frontend usage**:
```typescript
import { api } from '@/utils/api';

// Fetch multiple symbols
const { data, error } = await api.getPrices(
  ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
  'phemex'
);

if (data) {
  data.prices.forEach(p => console.log(`${p.symbol}: $${p.price}`));
}
```

**Price service auto-batches**:
```typescript
import { priceService } from '@/services/priceService';

// Automatically uses bulk endpoint for 4+ symbols
const prices = await priceService.fetchMultiplePrices([
  'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT'
]);
```

### Testing Background Scans

**Start a scan job**:
```bash
curl -X POST "http://localhost:5000/api/scanner/runs?limit=5&sniper_mode=surgical&exchange=phemex"
```

**Response**:
```json
{
  "run_id": "62d793e7-0961-4f72-8db2-2c31ba359857",
  "status": "running",
  "created_at": "2025-11-27T03:06:00Z"
}
```

**Poll for status**:
```bash
curl "http://localhost:5000/api/scanner/runs/62d793e7-0961-4f72-8db2-2c31ba359857"
```

**Response (in progress)**:
```json
{
  "run_id": "...",
  "status": "running",
  "progress": 3,
  "total": 5,
  "current_symbol": "SOL/USDT",
  "created_at": "...",
  "started_at": "..."
}
```

**Response (completed)**:
```json
{
  "run_id": "...",
  "status": "completed",
  "progress": 5,
  "total": 5,
  "signals": [...],
  "metadata": {
    "mode": "surgical",
    "scanned": 5,
    "total": 2,
    "rejected": 3
  },
  "rejections": {...}
}
```

**Frontend usage**:
```typescript
import { api } from '@/utils/api';

// Start scan
const createResp = await api.createScanRun({
  limit: 10,
  sniper_mode: 'recon',
  exchange: 'phemex'
});

const runId = createResp.data.run_id;

// Poll for completion
const interval = setInterval(async () => {
  const statusResp = await api.getScanRun(runId);
  const job = statusResp.data;
  
  console.log(`Progress: ${job.progress}/${job.total} | ${job.current_symbol}`);
  
  if (job.status === 'completed') {
    clearInterval(interval);
    console.log('Signals:', job.signals);
  }
}, 2000);
```

### Running the Test Suite

```bash
# Start backend
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 5000

# In another terminal, run tests
python test_new_endpoints.py
```

**Expected output**:
```
🧪 Testing bulk prices endpoint...
✅ Received 5 prices:
   BTC/USDT: $91,379.30
   ETH/USDT: $3,037.79
   BNB/USDT: $896.41

🧪 Testing background scan job system...
✅ Job created: 62d793e7-...
[1] Status: completed | Progress: 2/2
✅ Scan completed!
   Signals: 0
   Metadata: {...}

✅ All tests completed!
```

---

## API Reference

### Bulk Prices

**Endpoint**: `GET /api/market/prices`

**Query Parameters**:
- `symbols` (required): Comma-separated list (max 50)
- `exchange` (optional): `phemex`, `bybit`, `okx`, `bitget` (default: `phemex`)

**Response**:
```typescript
{
  prices: Array<{ symbol: string; price: number; timestamp: string }>;
  total: number;
  errors?: Array<{ symbol: string; error: string }>;
  exchange: string;
}
```

### Background Scan Jobs

**Create**: `POST /api/scanner/runs?limit=10&sniper_mode=recon&exchange=phemex&...`

**Get Status**: `GET /api/scanner/runs/{run_id}`

**Cancel**: `DELETE /api/scanner/runs/{run_id}`

**Job States**: `queued` → `running` → `completed | failed | cancelled`

**Status Response**:
```typescript
{
  run_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  total: number;
  current_symbol?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  signals?: Signal[];      // When completed
  metadata?: object;       // When completed
  rejections?: object;     // When completed
  error?: string;          // When failed
}
```

---

## Troubleshooting

### Bulk Prices

**Problem**: Some symbols return errors

**Solution**: Check `errors` array in response:
```typescript
if (data.errors && data.errors.length > 0) {
  data.errors.forEach(err => {
    console.warn(`${err.symbol}: ${err.error}`);
  });
}
```

**Problem**: OKX symbols fail

**Solution**: Backend auto-handles `:USDT` suffix for OKX. Use standard `BTC/USDT` format.

### Background Scans

**Problem**: Job stuck in "running" state

**Solution**: Check backend logs for errors. Job may have crashed without updating status.

**Problem**: Progress not updating in UI

**Solution**: Ensure polling interval is running. Check browser console for errors.

**Problem**: Job ID not found

**Solution**: Jobs are in-memory. Server restart clears all jobs. Use Redis/DB for persistence.

---

## Performance Tips

1. **Batch wisely**: Use bulk prices for lists >3 symbols; individual requests are faster for 1-2
2. **Poll interval**: 2-3 seconds balances responsiveness vs. load
3. **Cleanup jobs**: Delete completed jobs after processing to free memory
4. **WebSocket upgrade**: For production, replace polling with WebSocket push

---

## Next Steps

- [ ] Add job cleanup (TTL: 1 hour)
- [ ] Persist jobs to Redis/DB
- [ ] Add WebSocket endpoint for real-time updates
- [ ] UI button to cancel running scans
- [ ] Job history page to view past scans
