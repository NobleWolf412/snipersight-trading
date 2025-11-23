# Scanner Integration Debug Checklist

## Current Issues
1. ✅ **Backend Running**: FastAPI server on port 5000 (confirmed working - logs show scan processing)
2. ✅ **Frontend Running**: Vite dev server on port 5173 (configured correctly)
3. ❓ **Sniper Modes Loading Slowly**: Multiple `/api/scanner/modes` calls being made
4. ❓ **Status Page Empty**: No telemetry events showing in ActivityFeed
5. ❓ **Dropdown Not Working**: Filter dropdown not responding

## Debug Steps

### 1. Check Browser Console
Open browser DevTools (F12) and check:
- [ ] Are there any errors in Console tab?
- [ ] Are API calls succeeding? (Network tab → look for `/api/scanner/modes`, `/api/scanner/signals`, `/api/telemetry/recent`)
- [ ] What do the console.log statements show? Look for:
  - `[SniperModeSelector] Fetching scanner modes...`
  - `[ScannerSetup] Starting scan...`
  - `[ScannerSetup] Received signals:`
  - `[ActivityFeed] Loading initial events`

### 2. Test API Endpoints Directly
```bash
# Test scanner modes endpoint
curl http://localhost:5000/api/scanner/modes

# Test telemetry recent events
curl http://localhost:5000/api/telemetry/recent?limit=10

# Test telemetry analytics
curl http://localhost:5000/api/telemetry/analytics
```

### 3. Check Backend Logs
Look in the backend terminal for:
- [ ] Are telemetry events being logged? Look for `telemetry.log_event()`
- [ ] Are scans completing successfully?
- [ ] Any errors or warnings?

### 4. Frontend State Inspection
In React DevTools:
- [ ] Check ScannerContext - is state being updated?
- [ ] Check useKV state for 'scan-results' and 'scan-metadata'
- [ ] Check ActivityFeed component state - are events array populated?

## Known Working Components
- ✅ Backend scan pipeline (data ingestion, SMC detection, confluence scoring)
- ✅ API signal generation endpoint
- ✅ Frontend navigation between pages
- ✅ ScannerSetup form controls

## Suspected Issues

### Issue #1: Repeated Mode Fetching
**Symptom**: `/api/scanner/modes` called 7 times in backend logs
**Possible Cause**: Component re-rendering or multiple instances
**Fix**: Add React.memo() or useMemo() to cache modes

### Issue #2: No Telemetry Events
**Symptom**: ActivityFeed shows "No activity yet"
**Possible Causes**:
1. Backend not logging telemetry events
2. Telemetry logger not initialized
3. API endpoint returning empty array
4. Frontend not parsing response correctly

**Debug**: Check if backend telemetry logger is being called during scans

### Issue #3: Vite Proxy Configuration
**Current Config**:
```typescript
server: {
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://localhost:5000',
      changeOrigin: true,
    }
  }
}
```

**Verify**: API calls to `/api/*` are being proxied to backend correctly

## Quick Test Script

Run this in browser console after starting both servers:

```javascript
// Test API connectivity
fetch('/api/scanner/modes')
  .then(r => r.json())
  .then(d => console.log('Modes:', d))
  .catch(e => console.error('Modes error:', e));

// Test telemetry
fetch('/api/telemetry/recent?limit=10')
  .then(r => r.json())
  .then(d => console.log('Telemetry:', d))
  .catch(e => console.error('Telemetry error:', e));

// Test signals (this will trigger a real scan)
fetch('/api/scanner/signals?limit=5&min_score=70')
  .then(r => r.json())
  .then(d => console.log('Signals:', d))
  .catch(e => console.error('Signals error:', e));
```

## Next Steps

1. **Open browser DevTools** and check Console + Network tabs
2. **Run a scan** from /scanner/setup
3. **Watch console logs** for the debug statements added
4. **Check backend terminal** for telemetry event logs
5. **Navigate to /scanner/status** and see if events appear
6. **Report back** what you see in:
   - Browser console logs
   - Network tab (which API calls succeed/fail)
   - Backend terminal (telemetry events being logged?)
