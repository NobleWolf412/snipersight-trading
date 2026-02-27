# Telemetry System User Guide

## Overview

The SniperSight telemetry system provides complete observability into scanner operations, allowing you to:

- **Track every decision** made by the scanner (signals generated, rejected, reasons)
- **Monitor performance** with real-time analytics and metrics
- **Debug issues** by reviewing the complete event timeline
- **Analyze patterns** in rejection reasons and signal quality over time

## Architecture

```
┌─────────────────┐
│   Scanner Run   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Orchestrator (Instrumented)        │
│  • Scan started                     │
│  • Signal generated (with details)  │
│  • Signal rejected (with reason)    │
│  • Scan completed                   │
│  • Errors                           │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Telemetry Logger                   │
│  • In-memory cache (last 100)       │
│  • SQLite persistence (unlimited)   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  API Endpoints                      │
│  • /api/telemetry/recent            │
│  • /api/telemetry/events            │
│  • /api/telemetry/analytics         │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Frontend UI                        │
│  • Activity Feed (real-time)        │
│  • Analytics Dashboard              │
│  • Filters & Search                 │
└─────────────────────────────────────┘
```

## Quick Start

### 1. Start the Backend

```bash
python -m uvicorn backend.api_server:app --reload
```

The telemetry system is automatically initialized when the API server starts.

### 2. Start the Frontend

```bash
npm run dev
```

### 3. View Telemetry

Navigate to the **Bot Status** page in the UI to see:
- **Real-time activity feed** - Events as they happen
- **Analytics dashboard** - Metrics and statistics
- **Event filtering** - Filter by type, symbol, time range

### 4. Run a Scan

From the **Scanner Setup** page:
1. Configure your scan parameters
2. Click "ARM THE SCANNER"
3. Watch events appear in real-time on Bot Status page!

## Event Types

### Scanner Events

**`scan_started`**
- Emitted when a scan begins
- Data: symbols, profile, symbol count

**`scan_completed`**
- Emitted when a scan finishes
- Data: symbols scanned, signals generated/rejected, duration

### Signal Events

**`signal_generated`**
- Emitted when a high-quality signal passes all gates
- Data: symbol, direction, confidence score, setup type, entry price, R:R ratio

**`signal_rejected`**
- Emitted when a signal fails quality gates
- Data: symbol, reason, gate name, score, threshold

### System Events

**`error_occurred`**
- Emitted when an error happens during scanning
- Data: error message, error type, traceback, symbol

**`quality_gate_passed` / `quality_gate_failed`**
- Emitted at each quality gate check
- Data: gate name, details

## Using the Activity Feed

### Real-time Monitoring

The Activity Feed automatically polls for new events every 3 seconds and displays them in reverse chronological order (newest first).

**Features:**
- ✅ Auto-scroll to show latest events
- ✅ Pause/Resume button to freeze the feed
- ✅ Event type filtering
- ✅ Color-coded event cards
- ✅ Time-ago timestamps

### Event Card Details

Each event card shows:
- **Icon & Color** - Visual indication of event type
- **Title** - Event type in human-readable format
- **Description** - Key details and metrics
- **Symbol Badge** - Trading pair (if applicable)
- **Timestamp** - "2 minutes ago" format

### Filtering Events

Use the filter dropdown to show only specific event types:
- All Events
- Scans Started
- Scans Completed
- Signals Generated
- Signals Rejected
- Errors

### Pausing Updates

Click the **Pause** button to:
- Stop polling for new events
- Freeze the current view
- Review historical events without auto-scrolling

Click **Resume** to continue real-time updates.

## Analytics Dashboard

The analytics dashboard shows aggregated metrics:

### Metrics Cards

1. **Total Scans**
   - Number of completed scan runs
   - Updates in real-time

2. **Signals Generated**
   - Count of high-conviction setups that passed all gates
   - Green color indicates success

3. **Signals Rejected**
   - Count of setups that failed quality gates
   - Orange color indicates filtering in action

4. **Success Rate**
   - `signals_generated / (signals_generated + signals_rejected) * 100`
   - Indicates signal quality and gate effectiveness

### Time Range

Analytics are calculated for the last 24 hours by default. You can query different time ranges via the API (see API Reference below).

## API Reference

### Get Recent Events

**Endpoint:** `GET /api/telemetry/recent`

**Query Parameters:**
- `limit` (optional, default: 100) - Maximum events to return
- `since_id` (optional) - Only return events with ID > this value

**Response:**
```json
{
  "events": [
    {
      "id": 123,
      "event_type": "signal_generated",
      "timestamp": "2024-01-15T14:20:00Z",
      "run_id": "abc123",
      "symbol": "BTC/USDT",
      "data": {
        "direction": "LONG",
        "confidence_score": 85.5,
        "setup_type": "OB_FVG_Confluence",
        "entry_price": 42150.0,
        "risk_reward_ratio": 3.2
      }
    }
  ],
  "count": 1
}
```

**Use Case:** Real-time polling. First call without `since_id`, subsequent calls with the last event ID to get only new events.

### Query Events with Filters

**Endpoint:** `GET /api/telemetry/events`

**Query Parameters:**
- `limit` (optional, default: 100) - Max results
- `offset` (optional, default: 0) - Pagination offset
- `event_type` (optional) - Filter by type (e.g., "signal_generated")
- `symbol` (optional) - Filter by symbol (e.g., "BTC/USDT")
- `run_id` (optional) - Filter by scan run ID
- `start_time` (optional) - ISO 8601 timestamp (e.g., "2024-01-15T00:00:00Z")
- `end_time` (optional) - ISO 8601 timestamp

**Response:**
```json
{
  "events": [...],
  "pagination": {
    "total": 245,
    "limit": 100,
    "offset": 0,
    "has_more": true
  }
}
```

**Example:**
```bash
# Get all signal rejections for BTC/USDT
curl "http://localhost:8000/api/telemetry/events?event_type=signal_rejected&symbol=BTC/USDT"

# Get events from the last hour
curl "http://localhost:8000/api/telemetry/events?start_time=2024-01-15T13:00:00Z"
```

### Get Analytics

**Endpoint:** `GET /api/telemetry/analytics`

**Query Parameters:**
- `start_time` (optional) - Calculate from this time (default: 24 hours ago)
- `end_time` (optional) - Calculate until this time (default: now)

**Response:**
```json
{
  "metrics": {
    "total_scans": 15,
    "total_signals_generated": 8,
    "total_signals_rejected": 12,
    "total_errors": 0,
    "signal_success_rate": 40.0
  },
  "rejection_breakdown": {
    "Below minimum confluence threshold": 7,
    "Failed risk validation": 3,
    "No data available": 2
  },
  "time_range": {
    "start": "2024-01-14T14:00:00Z",
    "end": "2024-01-15T14:00:00Z"
  }
}
```

## Backend Usage (Programmatic)

### Logging Custom Events

```python
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import create_scan_started_event

# Get telemetry logger instance
telemetry = get_telemetry_logger()

# Log an event
event = create_scan_started_event(
    run_id="my_scan_001",
    symbols=['BTC/USDT', 'ETH/USDT'],
    profile="balanced"
)
telemetry.log_event(event)
```

### Querying Events

```python
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import EventType

telemetry = get_telemetry_logger()

# Get recent events from cache
cached = telemetry.get_cached_events(limit=50)

# Query events from database
events = telemetry.get_events(
    event_type=EventType.SIGNAL_GENERATED,
    symbol="BTC/USDT",
    limit=100
)

# Count events
count = telemetry.get_event_count(
    event_type=EventType.SIGNAL_REJECTED
)
```

### Analytics

```python
from backend.bot.telemetry.analytics import get_analytics
from datetime import datetime, timedelta, timezone

analytics = get_analytics()

# Get summary stats
stats = analytics.get_summary_stats()
print(f"Total scans: {stats['scans']['total']}")
print(f"Signal rate: {stats['signals']['signal_rate']}%")

# Get rejection breakdown
rejections = analytics.get_rejection_breakdown(limit=10)
for item in rejections:
    print(f"{item['reason']}: {item['count']} ({item['percentage']}%)")

# Get confidence distribution
distribution = analytics.get_confidence_distribution()
print(f"Average confidence: {distribution['avg']}")
print(f"Buckets: {distribution['buckets']}")
```

## Data Storage

### SQLite Database

**Location:** `backend/cache/telemetry.db`

**Schema:**
```sql
CREATE TABLE telemetry_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    run_id TEXT,
    symbol TEXT,
    data_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indices for fast queries
CREATE INDEX idx_event_type ON telemetry_events(event_type);
CREATE INDEX idx_timestamp ON telemetry_events(timestamp DESC);
CREATE INDEX idx_symbol ON telemetry_events(symbol);
CREATE INDEX idx_run_id ON telemetry_events(run_id);
```

### In-Memory Cache

- Stores last **100 events** for instant API response
- Thread-safe implementation
- Automatically updated when events are logged
- Used for first poll in real-time updates

### Retention Policy

**Default:** Events are kept indefinitely

**Cleanup:** Use CLI command to remove old events:
```bash
python -m backend.cli telemetry-cleanup --older-than 30d
```

Or programmatically:
```python
from backend.bot.telemetry.storage import get_storage

storage = get_storage()
deleted = storage.cleanup_old_events(older_than_days=30)
print(f"Deleted {deleted} old events")
```

## Common Use Cases

### 1. Debugging Why Signals Were Rejected

**Problem:** Scanner isn't generating many signals

**Solution:**
1. Go to Bot Status page
2. Filter events to "Signals Rejected"
3. Review rejection reasons
4. Common reasons:
   - "Below minimum confluence threshold" → Lower `min_confluence_score` in config
   - "Failed risk validation" → Check risk parameters
   - "No data available" → Exchange connectivity issue

### 2. Analyzing Signal Quality Over Time

**Problem:** Want to track if signal quality is improving

**Solution:**
```python
from backend.bot.telemetry.analytics import get_analytics
from datetime import datetime, timedelta, timezone

analytics = get_analytics()

# Compare this week vs last week
now = datetime.now(timezone.utc)
week_ago = now - timedelta(days=7)
two_weeks_ago = now - timedelta(days=14)

# This week
this_week = analytics.get_summary_stats(start_time=week_ago, end_time=now)

# Last week
last_week = analytics.get_summary_stats(start_time=two_weeks_ago, end_time=week_ago)

print(f"This week signal rate: {this_week['signals']['signal_rate']}%")
print(f"Last week signal rate: {last_week['signals']['signal_rate']}%")
```

### 3. Monitoring for Errors

**Problem:** Want to be alerted when errors occur

**Solution:**
```python
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import EventType

telemetry = get_telemetry_logger()

# Check for recent errors
errors = telemetry.get_events(
    event_type=EventType.ERROR_OCCURRED,
    limit=10
)

if errors:
    print(f"⚠️  {len(errors)} errors detected!")
    for event in errors:
        print(f"  - {event['data'].get('error_message')}")
```

### 4. Tracking Specific Symbol Performance

**Problem:** Want to see how often BTC/USDT generates signals

**Solution:**
```python
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import EventType

telemetry = get_telemetry_logger()

symbol = "BTC/USDT"

# Count signals generated
generated = telemetry.get_event_count(
    event_type=EventType.SIGNAL_GENERATED,
    symbol=symbol
)

# Count signals rejected
rejected = telemetry.get_event_count(
    event_type=EventType.SIGNAL_REJECTED,
    symbol=symbol
)

total = generated + rejected
success_rate = (generated / total * 100) if total > 0 else 0

print(f"{symbol} Signal Success Rate: {success_rate:.1f}%")
print(f"  Generated: {generated}")
print(f"  Rejected: {rejected}")
```

## Best Practices

### 1. Regular Monitoring

- Check the Activity Feed regularly to ensure scanner is working correctly
- Review analytics dashboard to track performance trends
- Set up periodic checks for errors

### 2. Retention Management

- Clean up old events monthly to keep database size manageable
- Archive important events if needed before cleanup
- Consider exporting analytics data for long-term storage

### 3. Performance

- Use `since_id` parameter for polling to minimize data transfer
- Cache analytics results on frontend for 30 seconds
- Use event filters to reduce query load

### 4. Debugging Workflow

When investigating issues:
1. Check Activity Feed for recent errors
2. Filter to specific event type (e.g., rejections)
3. Review rejection reasons and patterns
4. Query full event details via API for deep dive
5. Check database directly if needed

## Troubleshooting

### Events Not Appearing in UI

**Check:**
1. Backend server is running (`python -m uvicorn backend.api_server:app --reload`)
2. Frontend is running (`npm run dev`)
3. No CORS errors in browser console
4. API endpoint is accessible: `curl http://localhost:8000/api/telemetry/recent`

### Database Locked Error

**Cause:** Multiple processes accessing SQLite simultaneously

**Solution:**
- SQLite supports concurrent reads but limited writes
- Ensure only one API server instance is running
- If issue persists, check for zombie processes

### Missing Events

**Check:**
1. Telemetry logger is initialized: `telemetry = get_telemetry_logger()`
2. Events are being logged: `telemetry.log_event(event)`
3. Database file exists: `backend/cache/telemetry.db`
4. Database file is writable

### Analytics Not Updating

**Possible Causes:**
1. Time range filter excluding new events
2. Frontend polling paused
3. API endpoint error

**Solution:**
1. Check browser network tab for API errors
2. Verify analytics endpoint: `curl http://localhost:8000/api/telemetry/analytics`
3. Clear frontend cache and reload

## Advanced Topics

### Custom Event Types

To add new event types:

1. Add to `EventType` enum in `backend/bot/telemetry/events.py`:
```python
class EventType(str, Enum):
    # ... existing types
    MY_CUSTOM_EVENT = "my_custom_event"
```

2. Create factory function:
```python
def create_my_custom_event(data: dict) -> TelemetryEvent:
    return TelemetryEvent(
        event_type=EventType.MY_CUSTOM_EVENT,
        timestamp=datetime.now(timezone.utc),
        data=data
    )
```

3. Log the event:
```python
telemetry.log_event(create_my_custom_event({"foo": "bar"}))
```

4. Update frontend event display in `ActivityFeed.tsx`:
```typescript
case 'my_custom_event':
  return {
    icon: <CustomIcon />,
    color: 'bg-purple-500/20 text-purple-400',
    title: 'My Custom Event',
    description: data.foo
  };
```

### Exporting Data

Export telemetry data to JSON:

```python
from backend.bot.telemetry.logger import get_telemetry_logger
import json

telemetry = get_telemetry_logger()
events = telemetry.get_events(limit=10000)

with open('telemetry_export.json', 'w') as f:
    json.dump(events, f, indent=2)
```

Export to CSV:

```python
import csv
from backend.bot.telemetry.logger import get_telemetry_logger

telemetry = get_telemetry_logger()
events = telemetry.get_events(limit=10000)

with open('telemetry_export.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['event_type', 'timestamp', 'symbol', 'data'])
    writer.writeheader()
    for event in events:
        writer.writerow({
            'event_type': event['event_type'],
            'timestamp': event['timestamp'],
            'symbol': event.get('symbol', ''),
            'data': str(event.get('data', {}))
        })
```

## Support

For issues or questions:
1. Check this guide first
2. Review the Activity Feed for error events
3. Check API endpoint responses directly
4. Examine SQLite database for data integrity
5. Review backend logs for errors

## Summary

The telemetry system provides:
- ✅ **Complete visibility** into scanner decisions
- ✅ **Real-time monitoring** with live activity feed
- ✅ **Historical analysis** with persistent storage
- ✅ **Performance metrics** via analytics dashboard
- ✅ **Easy debugging** with detailed rejection reasons
- ✅ **Flexible querying** via API and programmatic access

Use it to understand, debug, and optimize your scanner's performance!
