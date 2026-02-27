# SniperSight API Contract

This document specifies all HTTP API endpoints for both Scanner Mode and SniperBot Mode.

## Base URL

```
http://localhost:8000  (development)
https://api.snipersight.example.com  (production)
```

## Authentication

All endpoints require authentication via JWT bearer token or session cookie.

```http
Authorization: Bearer <token>
```

---

## Scanner Mode Endpoints

### POST /api/scan

Initiates a new market scan.

**Request Body**:
```json
{
  "profile": "balanced",
  "exchange_profile": "Binance_Data",
  "universe": "top20",
  "symbols": ["BTC/USDT", "ETH/USDT"],
  "timeframes": ["1W", "1D", "4H", "1H", "15m", "5m"],
  "filters": {
    "min_score": 70,
    "min_rr": 2.0,
    "directions": ["LONG", "SHORT"]
  }
}
```

**Response** (200 OK):
```json
{
  "run_id": "scan_2024-01-15_123456",
  "timestamp": "2024-01-15T12:34:56Z",
  "profile": "balanced",
  "exchange_profile": "Binance_Data",
  "symbols_scanned": 20,
  "signals_generated": 5,
  "signals_discarded": 8,
  "signals": [
    {
      "signal_id": "sig_abc123",
      "symbol": "BTC/USDT",
      "direction": "LONG",
      "score": 78.5,
      "risk_reward": 3.2,
      "setup_type": "swing",
      "entry_zone": {
        "near_entry": 42150,
        "far_entry": 41800
      },
      "stop_loss": 41200,
      "targets": [43500, 44800, 46200],
      "timestamp": "2024-01-15T12:34:56Z"
    }
  ],
  "summary": {
    "longs": 3,
    "shorts": 2,
    "avg_score": 78.5,
    "avg_rr": 3.2
  }
}
```

---

### GET /api/signals/{run_id}

Retrieves all signals from a specific scan run.

**Path Parameters**:
- `run_id` (string): The scan run identifier

**Response** (200 OK):
```json
{
  "run_id": "scan_2024-01-15_123456",
  "signals": [/* Array of SignalPayload objects */],
  "metadata": {
    "profile": "balanced",
    "timestamp": "2024-01-15T12:34:56Z"
  }
}
```

---

### GET /api/signal/{signal_id}

Retrieves detailed trade plan for a single signal.

**Path Parameters**:
- `signal_id` (string): The signal identifier

**Response** (200 OK):
```json
{
  "signal_id": "sig_abc123",
  "symbol": "BTC/USDT",
  "direction": "LONG",
  "setup_type": "swing",
  "score": 78.5,
  "risk_score": "medium",
  "entry_zone": {
    "near_entry": 42150,
    "far_entry": 41800,
    "rationale": "Entry anchored to bullish OB on 4H with FVG confluence"
  },
  "stop_loss": {
    "level": 41200,
    "distance_atr": 1.8,
    "rationale": "Below 4H OB invalidation level"
  },
  "targets": [
    {
      "level": 43500,
      "percentage": 50,
      "rationale": "Previous 4H high"
    },
    {
      "level": 44800,
      "percentage": 30,
      "rationale": "1W resistance zone"
    },
    {
      "level": 46200,
      "percentage": 20,
      "rationale": "Extended FVG fill"
    }
  ],
  "risk_reward": 3.2,
  "confluence_breakdown": {
    "total_score": 78.5,
    "factors": [
      {
        "name": "structure",
        "score": 25.0,
        "weight": 0.3
      },
      {
        "name": "htf_alignment",
        "score": 30.0,
        "weight": 0.35
      },
      {
        "name": "smc_confluence",
        "score": 23.5,
        "weight": 0.35
      }
    ]
  },
  "smc_geometry": {
    "order_blocks": [
      {
        "timeframe": "4H",
        "type": "bullish",
        "price": 41850,
        "low": 41800,
        "high": 41900,
        "timestamp": "2024-01-14T08:00:00Z",
        "freshness_score": 0.92
      }
    ],
    "fvgs": [
      {
        "timeframe": "1H",
        "type": "bullish",
        "low": 42000,
        "high": 42100,
        "timestamp": "2024-01-15T10:00:00Z"
      }
    ],
    "bos_choch": [
      {
        "timeframe": "4H",
        "type": "BOS",
        "level": 42300,
        "timestamp": "2024-01-15T12:00:00Z",
        "direction": "bullish"
      }
    ],
    "liquidity_sweeps": [
      {
        "timeframe": "1H",
        "level": 41700,
        "timestamp": "2024-01-15T09:00:00Z",
        "type": "low_sweep"
      }
    ]
  },
  "analysis": {
    "risk_reward": 3.2,
    "confluence_score": 78.5,
    "expected_value": 2.51,
    "order_blocks": 1,
    "fvgs": 1,
    "structural_breaks": 1,
    "liquidity_sweeps": 1,
    "trend": "long"
        "score": 85,
        "weight": 0.3,
        "rationale": "HTF aligned BOS"
      },
      {
        "name": "smc",
        "score": 90,
        "weight": 0.25,
        "rationale": "Fresh OB + FVG confluence"
      },
      {
        "name": "momentum",
        "score": 75,
        "weight": 0.2,
        "rationale": "RSI recovery from oversold"
      },
      {
        "name": "volatility",
        "score": 70,
        "weight": 0.15,
        "rationale": "ATR expansion"
      },
      {
        "name": "regime",
        "score": 80,
        "weight": 0.1,
        "rationale": "Trend mode, BTC impulse aligned"
      }
    ],
    "synergy_bonus": 5,
    "conflict_penalty": -2,
    "regime": "trend",
    "htf_aligned": true,
    "btc_impulse_gate": true
  },
  "rationale": "Multi-paragraph human-readable explanation of the setup...",
  "timestamp": "2024-01-15T12:34:56Z",
  "metadata": {
    "profile": "balanced",
    "run_id": "scan_2024-01-15_123456"
  }
}
```

---

### GET /api/history

Retrieves past scan runs.

**Query Parameters**:
- `limit` (number, optional): Max number of runs to return (default: 50)
- `offset` (number, optional): Pagination offset (default: 0)
- `profile` (string, optional): Filter by profile name
- `start_date` (string, optional): Filter by start date (ISO 8601)
- `end_date` (string, optional): Filter by end date (ISO 8601)

**Response** (200 OK):
```json
{
  "runs": [
    {
      "run_id": "scan_2024-01-15_123456",
      "timestamp": "2024-01-15T12:34:56Z",
      "profile": "balanced",
      "exchange_profile": "Binance_Data",
      "symbols_scanned": 20,
      "signals_generated": 5,
      "avg_score": 78.5,
      "avg_rr": 3.2
    }
  ],
  "pagination": {
    "total": 127,
    "limit": 50,
    "offset": 0
  }
}
```

---

### POST /api/backtest

Runs a historical backtest simulation.

**Request Body**:
```json
{
  "profile": "balanced",
  "exchange_profile": "Binance_Data",
  "symbols": ["BTC/USDT", "ETH/USDT"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "initial_balance": 10000,
  "risk_per_trade": 1.0
}
```

**Response** (200 OK):
```json
{
  "backtest_id": "bt_xyz789",
  "summary": {
    "total_trades": 87,
    "winning_trades": 52,
    "losing_trades": 35,
    "win_rate": 59.77,
    "avg_rr_achieved": 2.8,
    "total_pnl": 2340.50,
    "max_drawdown": -450.20,
    "sharpe_ratio": 1.85
  },
  "trades": [/* Array of simulated trade results */],
  "equity_curve": [/* Array of equity snapshots */]
}
```

---

## SniperBot Mode Endpoints

### POST /api/bot/start

Deploys the SniperBot with specified configuration.

**Request Body**:
```json
{
  "mode": "PAPER",
  "profile": "balanced",
  "exchange_profile": "Binance_Paper",
  "risk_config": {
    "max_risk_per_trade": 1.0,
    "max_active_engagements": 3,
    "daily_loss_limit": 5.0,
    "leverage_cap": 3.0
  },
  "scan_interval_minutes": 15,
  "filters": {
    "allow_longs": true,
    "allow_shorts": true,
    "min_score": 70,
    "min_rr": 2.0
  }
}
```

**Response** (200 OK):
```json
{
  "status": "started",
  "bot_status": {
    "mode": "PAPER",
    "profile": "balanced",
    "exchange_profile": "Binance_Paper",
    "is_running": true,
    "started_at": "2024-01-15T12:00:00Z",
    "last_cycle": null,
    "next_cycle": "2024-01-15T12:15:00Z",
    "active_positions": 0,
    "daily_pnl": 0,
    "daily_loss_limit_hit": false,
    "health": "healthy",
    "warnings": []
  },
  "message": "SniperBot deployed in PAPER mode"
}
```

---

### POST /api/bot/stop

Ceases bot operation and performs graceful shutdown.

**Response** (200 OK):
```json
{
  "status": "stopped",
  "message": "Bot ceased operation. All positions remain open.",
  "final_stats": {
    "total_scans": 48,
    "signals_generated": 12,
    "engagements_opened": 5,
    "engagements_closed": 3,
    "daily_pnl": 145.30
  }
}
```

---

### GET /api/bot/status

Retrieves current bot operational status.

**Response** (200 OK):
```json
{
  "mode": "PAPER",
  "profile": "balanced",
  "exchange_profile": "Binance_Paper",
  "is_running": true,
  "started_at": "2024-01-15T12:00:00Z",
  "last_cycle": "2024-01-15T14:30:00Z",
  "next_cycle": "2024-01-15T14:45:00Z",
  "active_positions": 2,
  "daily_pnl": 145.30,
  "daily_loss_limit_hit": false,
  "health": "healthy",
  "warnings": [],
  "stats": {
    "scans_today": 48,
    "targets_acquired_today": 12,
    "targets_discarded_today": 28,
    "engagements_opened_today": 5,
    "win_rate_today": 60.0
  }
}
```

---

### GET /api/bot/positions

Retrieves all open positions managed by the bot.

**Response** (200 OK):
```json
{
  "positions": [
    {
      "id": "pos_123",
      "symbol": "BTC/USDT",
      "side": "LONG",
      "entry_price": 42150,
      "size": 0.05,
      "leverage": 3.0,
      "extraction_point": 41200,
      "impact_points": [43500, 44800, 46200],
      "current_price": 42800,
      "pnl": 97.50,
      "pnl_percent": 1.54,
      "rr": 3.2,
      "opened_at": "2024-01-15T14:20:00Z",
      "status": "open",
      "partials_taken": 0
    },
    {
      "id": "pos_124",
      "symbol": "ETH/USDT",
      "side": "SHORT",
      "entry_price": 2250,
      "size": 2.0,
      "leverage": 2.0,
      "extraction_point": 2285,
      "impact_points": [2200, 2150, 2100],
      "current_price": 2230,
      "pnl": 40.00,
      "pnl_percent": 0.89,
      "rr": 2.5,
      "opened_at": "2024-01-15T15:10:00Z",
      "status": "open",
      "partials_taken": 0
    }
  ],
  "summary": {
    "total_positions": 2,
    "total_exposure": 450.50,
    "unrealized_pnl": 137.50
  }
}
```

---

### POST /api/bot/close-position/{position_id}

Manually closes a bot-managed position.

**Path Parameters**:
- `position_id` (string): Position identifier

**Request Body** (optional):
```json
{
  "reason": "Manual intervention"
}
```

**Response** (200 OK):
```json
{
  "status": "closed",
  "position_id": "pos_123",
  "close_price": 42800,
  "pnl": 97.50,
  "pnl_percent": 1.54,
  "closed_at": "2024-01-15T16:00:00Z"
}
```

---

### PATCH /api/bot/move-sl/{position_id}

Adjusts stop loss for a bot-managed position.

**Path Parameters**:
- `position_id` (string): Position identifier

**Request Body**:
```json
{
  "new_sl": 42000,
  "reason": "Move to breakeven"
}
```

**Response** (200 OK):
```json
{
  "status": "updated",
  "position_id": "pos_123",
  "old_sl": 41200,
  "new_sl": 42000,
  "updated_at": "2024-01-15T16:05:00Z"
}
```

---

### GET /api/bot/logs

Retrieves bot activity log events.

**Query Parameters**:
- `limit` (number, optional): Max events to return (default: 100)
- `offset` (number, optional): Pagination offset (default: 0)
- `event_type` (string, optional): Filter by event type
- `start_time` (string, optional): Start timestamp (ISO 8601)
- `end_time` (string, optional): End timestamp (ISO 8601)
- `symbol` (string, optional): Filter by symbol

**Response** (200 OK):
```json
{
  "logs": [
    {
      "timestamp": "2024-01-15T14:20:00Z",
      "event_type": "scan_completed",
      "data": {
        "symbols_scanned": 20,
        "signals_generated": 3,
        "signals_discarded": 5
      }
    },
    {
      "timestamp": "2024-01-15T14:21:00Z",
      "event_type": "engagement_opened",
      "data": {
        "symbol": "BTC/USDT",
        "side": "LONG",
        "entry": 42150,
        "size": 0.05,
        "position_id": "pos_123"
      }
    },
    {
      "timestamp": "2024-01-15T13:50:00Z",
      "event_type": "target_discarded",
      "data": {
        "symbol": "ETH/USDT",
        "reason": "Failed HTF alignment gate",
        "score": 65
      }
    },
    {
      "timestamp": "2024-01-15T15:45:00Z",
      "event_type": "partial_taken",
      "data": {
        "symbol": "BTC/USDT",
        "position_id": "pos_123",
        "tp_level": 43500,
        "percentage": 50,
        "pnl": 67.50
      }
    },
    {
      "timestamp": "2024-01-15T16:10:00Z",
      "event_type": "extraction_triggered",
      "data": {
        "symbol": "SOL/USDT",
        "position_id": "pos_125",
        "sl_level": 95.50,
        "loss": -22.80
      }
    },
    {
      "timestamp": "2024-01-15T14:22:00Z",
      "event_type": "risk_limit_hit",
      "data": {
        "symbol": "SOL/USDT",
        "reason": "Max active engagements (3) reached",
        "action": "Signal discarded"
      }
    }
  ],
  "pagination": {
    "total": 245,
    "limit": 100,
    "offset": 0
  }
}
```

**Event Types**:
- `scan_completed` - Scan cycle finished
- `target_acquired` - Signal generated and passed gates
- `target_discarded` - Signal rejected with reason
- `engagement_opened` - Position opened
- `partial_taken` - Take profit level hit
- `extraction_triggered` - Stop loss hit
- `engagement_closed` - Position fully closed
- `risk_limit_hit` - Trade blocked by risk rules
- `daily_loss_limit_hit` - Bot auto-paused
- `error_occurred` - System error

---

## Exchange Profile Endpoints

### GET /api/profiles

Retrieves available exchange profiles with capability flags.

**Response** (200 OK):
```json
{
  "profiles": [
    {
      "name": "Binance_Data",
      "exchange": "binance",
      "mode": "data",
      "data_enabled": true,
      "paper_enabled": false,
      "live_enabled": false
    },
    {
      "name": "Binance_Paper",
      "exchange": "binance",
      "mode": "paper",
      "data_enabled": true,
      "paper_enabled": true,
      "live_enabled": false
    },
    {
      "name": "Binance_Live",
      "exchange": "binance",
      "mode": "live",
      "data_enabled": true,
      "paper_enabled": true,
      "live_enabled": true
    },
    {
      "name": "Bybit_Data",
      "exchange": "bybit",
      "mode": "data",
      "data_enabled": true,
      "paper_enabled": false,
      "live_enabled": false
    }
  ]
}
```

**Security Note**: This endpoint NEVER returns API keys or secrets. It only exposes profile names and capability flags.

---

## Error Responses

All endpoints may return standard HTTP error responses:

### 400 Bad Request
```json
{
  "error": "Invalid request",
  "details": "Field 'profile' is required"
}
```

### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "details": "Valid authentication token required"
}
```

### 403 Forbidden
```json
{
  "error": "Forbidden",
  "details": "Live mode requires valid exchange API keys"
}
```

### 404 Not Found
```json
{
  "error": "Not found",
  "details": "Signal with ID 'sig_abc123' not found"
}
```

### 429 Too Many Requests
```json
{
  "error": "Rate limit exceeded",
  "details": "Maximum 10 scans per minute",
  "retry_after": 30
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "details": "An unexpected error occurred",
  "request_id": "req_xyz789"
}
```

---

## WebSocket API (Optional Real-Time Updates)

### Connection

```
ws://localhost:8000/ws
```

### Subscribe to Bot Status

**Send**:
```json
{
  "type": "subscribe",
  "channel": "bot_status"
}
```

**Receive** (every 5 seconds):
```json
{
  "type": "bot_status",
  "data": { /* BotStatus object */ }
}
```

### Subscribe to Bot Logs

**Send**:
```json
{
  "type": "subscribe",
  "channel": "bot_logs"
}
```

**Receive** (on each new event):
```json
{
  "type": "bot_log",
  "data": { /* LogEvent object */ }
}
```

### Subscribe to Position Updates

**Send**:
```json
{
  "type": "subscribe",
  "channel": "positions"
}
```

**Receive** (on position change):
```json
{
  "type": "position_update",
  "data": { /* Position object */ }
}
```
