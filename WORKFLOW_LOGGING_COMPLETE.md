# Detailed Workflow Logging Implementation

## Overview
Enhanced the scanner orchestrator with comprehensive workflow logging that streams real-time progress from backend to frontend console. Users can now see exactly what's happening during each scan: mode configuration, timeframe data, indicator values, SMC pattern detections, confluence scoring, and quality gate decisions.

## Changes Summary

### Backend Enhancements

#### 1. **Orchestrator Logging** (`backend/engine/orchestrator.py`)
Added detailed logging at each pipeline stage:

- **Mode Initialization**:
  ```
  🚀 Orchestrator initialized: mode=SURGICAL | workers=4
  📋 Mode config: MinScore=70.0% | MinRR=2.5:1 | CriticalTFs=1h,4h
  ⏱️ TF Responsibility: Entry=1h,4h | Structure=1h,4h
  ```

- **Data Ingestion**:
  ```
  📊 BTC/USDT data: TFs=1h,4h,1d | Candles={'1h': 100, '4h': 100, '1d': 100}
  ```

- **Indicator Computation** (per timeframe):
  ```
  📊 1h indicators: RSI=52.3 | MFI=48.7 | ATR=450.25 (1.05%) | BB(42800-43000-43200) | VolSpike=False
  ```

- **SMC Pattern Detection** (per timeframe):
  ```
  🎯 4h SMC: OB=3 | FVG=2 | BOS/CHoCH=1 | Sweeps=0
  ```

- **Direction Selection**:
  ```
  ⚖️  Direction eval: LONG=78.5 vs SHORT=62.3
  ✅ Direction: LONG selected (score 78.5 > 62.3)
  ```
  
  Or with tie-breaking:
  ```
  🔄 TIE (70.0) broken by regime: LONG (bullish regime)
  ```

- **Quality Gates**:
  ```
  ❌ GATE FAIL (confluence) | Score=58.2 < 65.0 | Top: OB_HTF=25.0 | FVG_FRESH=18.0 | MACD_BULLISH=15.2
  ✅ GATE PASS (risk) | R:R=2.8
  ```

#### 2. **Log Streaming Infrastructure** (`backend/api_server.py`)

**Custom Log Handler**:
```python
class ScanJobLogHandler(logging.Handler):
    """Captures logs from orchestrator and appends to current ScanJob."""
    
    def emit(self, record: logging.LogRecord):
        if self.current_job and record.name.startswith('backend.engine'):
            msg = self.format(record)
            self.current_job.logs.append(msg)
```

**ScanJob Enhancement**:
- Added `logs: List[str]` field to capture workflow messages
- Logs returned in `/api/scanner/runs/{run_id}` response (last 100 entries)
- Handler attached to orchestrator logger, activated per scan job

**Lifecycle Management**:
```python
async def _execute_scan_job(job: ScanJob):
    scan_job_log_handler.set_current_job(job)  # Activate logging
    try:
        # Run scan...
    finally:
        scan_job_log_handler.set_current_job(None)  # Cleanup
```

### Frontend Enhancements

#### 1. **Real-Time Log Display** (`src/pages/ScannerSetup.tsx`)
Poll loop enhanced to display backend logs:

```typescript
// Track displayed logs
let lastLogCount = 0;

// In polling loop
if (job.logs && job.logs.length > lastLogCount) {
  const newLogs = job.logs.slice(lastLogCount);
  newLogs.forEach((logMsg: string) => {
    const [level, ...msgParts] = logMsg.split(' | ');
    const msg = msgParts.join(' | ');
    
    if (level === 'INFO') debugLogger.info(msg, 'scanner');
    else if (level === 'WARNING') debugLogger.warning(msg, 'scanner');
    else if (level === 'ERROR') debugLogger.error(msg, 'scanner');
  });
  lastLogCount = job.logs.length;
}
```

**Result**: Backend workflow logs stream to frontend console in real-time, replacing simulated placeholder messages.

#### 2. **API Type Updates** (`src/utils/api.ts`)
```typescript
async getScanRun(runId: string, options?: { silent?: boolean }) {
  return this.request<{
    // ... existing fields
    logs?: string[]; // Backend workflow logs from orchestrator
    // ...
  }>(`/scanner/runs/${runId}`, { ...options });
}

// Fixed getPrices to accept silent option
async getPrices(symbols: string[], exchange?: string, options?: { silent?: boolean })
```

## Example Console Output

When scanning in SURGICAL mode:

```
━━━ SCAN INITIATED ━━━
Mode: SURGICAL
Exchange: phemex | Leverage: 10x
Categories: Majors=true, Alts=true, Meme=false
Target pairs: 20 | Min Score: 70
━━━ STARTING ANALYSIS PIPELINE ━━━
INFO | 🚀 Orchestrator initialized: mode=SURGICAL | workers=4
INFO | 📋 Mode config: MinScore=70.0% | MinRR=2.5:1 | CriticalTFs=1h,4h
INFO | ⏱️ TF Responsibility: Entry=1h,4h | Structure=1h,4h
INFO | 🎯 Starting scan abc123 for 20 symbols
INFO | 🌍 Global regime: BTC_DRIVE (score=82.5)
⏳ Scanning... 2s elapsed
INFO | 📊 BTC/USDT data: TFs=1h,4h,1d | Candles={'1h': 100, '4h': 100, '1d': 100}
INFO | 📊 1h indicators: RSI=52.3 | MFI=48.7 | ATR=450.25 (1.05%) | BB(42800-43000-43200) | VolSpike=False
INFO | 📊 4h indicators: RSI=58.1 | MFI=55.2 | ATR=750.50 (1.75%) | BB(42500-43500-44500) | VolSpike=True
INFO | 🎯 1h SMC: OB=2 | FVG=1 | BOS/CHoCH=1 | Sweeps=0
INFO | 🎯 4h SMC: OB=3 | FVG=2 | BOS/CHoCH=1 | Sweeps=1
INFO | ⚖️  Direction eval: LONG=78.5 vs SHORT=62.3
INFO | ✅ Direction: LONG selected (score 78.5 > 62.3)
INFO | ✅ GATE PASS (risk) | R:R=2.8
✅ BTC/USDT: Signal generated (78.5%) - LONG
⏳ Scanning... 4s elapsed
INFO | 📊 ETH/USDT data: TFs=1h,4h,1d | Candles={'1h': 100, '4h': 100, '1d': 100}
INFO | 📊 1h indicators: RSI=45.2 | MFI=42.1 | ATR=25.30 (0.95%) | BB(2680-2700-2720) | VolSpike=False
INFO | ❌ GATE FAIL (confluence) | Score=58.2 < 70.0 | Top: OB_HTF=25.0 | FVG_FRESH=18.0 | MACD_BULLISH=15.2
⚪ ETH/USDT: No qualifying setup
━━━ ANALYSIS COMPLETE ━━━
✓ Signals Generated: 1
📊 Symbols Scanned: 20
🚫 Rejected: 19
```

## Benefits

1. **Full Pipeline Transparency**: See exactly what the orchestrator is doing at each step
2. **Mode Verification**: Confirm correct timeframes, thresholds, and configuration
3. **Debugging**: Immediately spot data issues, missing TFs, or threshold problems
4. **Educational**: Learn how SMC patterns are detected and scored
5. **Quality Assurance**: Verify gate logic is working correctly
6. **Performance Monitoring**: Track which stages take longest

## Technical Details

### Log Flow Architecture
```
Orchestrator (Python)
  → logger.info() calls
    → ScanJobLogHandler
      → Appends to ScanJob.logs[]
        → FastAPI /scanner/runs/{run_id} endpoint
          → Frontend poll loop
            → debugLogger (browser console)
```

### Log Levels
- **INFO**: Normal workflow steps (data fetches, detections, gate passes)
- **WARNING**: Non-critical issues (regime penalties, missing optional data)
- **ERROR**: Critical failures (data unavailable, exceptions)

### Performance Impact
- **Backend**: Minimal - uses standard Python logging (thread-safe, buffered)
- **Frontend**: Log array size capped at 100 entries in API response
- **Network**: ~50-200 bytes per log message, sent with existing 1s poll

### Cleanup
- Log handler cleared after each scan job (`finally` block)
- Old scan jobs (with logs) cleaned up after 5 minutes
- No persistent storage - logs are ephemeral per run

## Testing

### Backend Syntax
```bash
python -m py_compile backend/api_server.py backend/engine/orchestrator.py
```

### Frontend Types
```bash
npx tsc --noEmit --skipLibCheck
```

### Manual Test
1. Start backend: `python -m uvicorn backend.api_server:app --reload`
2. Start frontend: `npm run dev:frontend`
3. Navigate to Scanner Setup
4. Initiate scan in any mode
5. Watch browser console for detailed workflow logs
6. Verify logs show: mode config, TF data, indicators, SMC counts, direction eval, gate decisions

## Future Enhancements

1. **Log Filtering**: Frontend UI to filter by log level or stage
2. **Log Persistence**: Optional save-to-file for debugging complex issues
3. **Progress Visualization**: Parse structured logs to show visual pipeline stages
4. **Telemetry Integration**: Mirror logs to telemetry system for historical analysis
5. **Performance Profiling**: Add timing data to each stage log

## Files Modified

### Backend
- `backend/engine/orchestrator.py` - Enhanced with detailed workflow logging
- `backend/api_server.py` - Added ScanJobLogHandler, logs field to ScanJob, log streaming

### Frontend
- `src/pages/ScannerSetup.tsx` - Display backend logs in polling loop
- `src/utils/api.ts` - Added logs field to getScanRun response type, fixed getPrices signature

## Compatibility

- **Python**: 3.10+ (uses modern logging features)
- **TypeScript**: 5.x (uses optional chaining, nullish coalescing)
- **Browsers**: All modern browsers (Chrome, Firefox, Safari, Edge)
- **Backward Compatible**: Log field optional - existing clients won't break
