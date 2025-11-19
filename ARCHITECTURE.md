# SniperSight Architecture

## System Overview

SniperSight is a modular, institutional-grade crypto market scanner built on strict separation of concerns, contract-driven interfaces, and verification-first design principles. The system processes multi-timeframe market data through a deterministic pipeline to generate complete, actionable trade signals.

**SniperSight operates in two primary modes:**

1. **Scanner Mode (Recon)** - User-triggered scans for manual review and trading decisions
2. **SniperBot Mode (Automated)** - Scheduled/continuous scanning with optional automated execution

Both modes share the same core engine pipeline and data models; the difference is operational control and execution authority.

## Global Operation Modes

### Scanner Mode (Recon / Manual)

**Purpose**: Recon-only mode for manual operators to review signals and trade independently.

**Characteristics**:
- **User-triggered** - Scan runs on-demand via CLI, API, or UI action
- **Read-only exchange access** - Consumes market data only; no API keys required for execution
- **Manual trading** - User reviews "Target Board" and "Target Intel" before making trade decisions
- **No automated execution** - System generates signals; human decides and executes
- **Exchange profile for data only** - Specifies which exchange to pull data from (e.g., Binance, Bybit)

**API Endpoints**:
- `POST /api/scan` - Initiate a new scan with specified profile, symbols, timeframes
- `GET /api/signals/{run_id}` - Retrieve all signals from a specific scan run
- `GET /api/signal/{signal_id}` - Get detailed trade plan for a single signal
- `POST /api/backtest` - Run historical simulation on past data
- `GET /api/history` - View past scan runs and results

**Data Flow**:
```
User triggers scan
  ↓
Engine pipeline executes (data → indicators → SMC → confluence → planner → risk)
  ↓
Returns SignalPayload[] with run_id, timestamp, profile metadata
  ↓
User reviews signals in UI
  ↓
User manually trades via their own exchange interface
```

**Use Cases**:
- Discretionary traders seeking institutional-quality signal generation
- Portfolio managers reviewing opportunities across multiple assets
- Educational use for learning Smart-Money Concepts
- Backtesting and strategy verification

---

### SniperBot Mode (Automated Operator)

**Purpose**: Automated scanning and optional execution with strict risk controls and safeguards.

**Characteristics**:
- **Scheduled/continuous** - Bot runs scan loops on configurable intervals
- **Quality-gated execution** - Only signals passing multi-layer quality gates proceed
- **Risk-controlled** - Enforces max risk per trade, max open positions, daily loss limits
- **Three operation modes**:
  - **OFF** - Bot inactive; no scans, no execution
  - **PAPER** ("Training Mode") - Full pipeline + simulated execution; no real orders
  - **LIVE** ("Live Ammunition") - Full pipeline + real exchange execution (requires API keys)
- **Server-side API keys** - Exchange credentials never exposed to frontend
- **Comprehensive telemetry** - Logs all decisions, quality gate results, execution attempts

**API Endpoints**:
- `POST /api/bot/start` - Deploy SniperBot with specified mode (OFF/PAPER/LIVE) and profile
- `POST /api/bot/stop` - Cease bot operation and clean shutdown
- `GET /api/bot/status` - Current bot state: mode, profile, active positions, health status
- `GET /api/bot/positions` - List all open positions managed by bot
- `GET /api/bot/logs` - Retrieve bot activity log (scans, signals, discards, executions, errors)
- `POST /api/bot/close-position/{position_id}` - Manually close a bot-managed position
- `PATCH /api/bot/move-sl/{position_id}` - Adjust stop loss (e.g., to breakeven)

**Data Flow**:
```
Bot loop starts (every N minutes)
  ↓
Engine pipeline executes → generates signals
  ↓
Quality gates filter signals
  ↓
Risk manager validates position sizing and exposure
  ↓
Bot executor stages orders (paper or live)
  ↓
Telemetry logs all decisions
  ↓
Notifications sent (optional)
  ↓
Loop repeats
```

**Use Cases**:
- Fully automated trading within strict institutional risk parameters
- Paper trading for strategy validation and performance tracking
- 24/7 market monitoring with immediate execution capability
- Disciplined execution removing emotional discretion

---

### Shared Pipeline Architecture

**Both Scanner and Bot modes use identical core components:**

- **Same `SniperContext` model** - All pipeline stages populate the same context object
- **Same `SignalPayload` output** - Consistent signal structure regardless of mode
- **Same quality gates** - HTF alignment, freshness, displacement, confluence thresholds
- **Same risk validation** - Position sizing, exposure limits, compliance checks
- **Same SMC detection** - Order blocks, FVGs, BOS/CHoCH, liquidity sweeps

**The only differences:**
- **Trigger mechanism**: User action (Scanner) vs scheduled loop (Bot)
- **Execution authority**: Human (Scanner) vs automated (Bot with safeguards)
- **API key requirement**: None (Scanner data-only) vs required for LIVE mode (Bot)
- **Operational endpoints**: `/api/scan` vs `/api/bot/*`

This shared architecture ensures:
- Signals in Scanner Mode are identical to signals Bot would act on
- Users can validate strategies manually before enabling automation
- Backtests accurately represent bot behavior
- No "works in Scanner but not in Bot" discrepancies

## Core Architecture Principles

### 1. Preserve Smart-Money Edge
Every component honors multi-timeframe context, order blocks, FVGs, liquidity sweeps, BTC impulse gates, regime filters, and institutional heuristics that drive edge retention.

### 2. No-Null, Actionable Outputs
All outputs must be complete—no missing fields, no "TBD" placeholders, no null sections. Signals include full trade plans with populated rationale.

### 3. Verification-Ready
Deterministic fixtures, strong typing, schema validation, and comprehensive test coverage make backtests and validation trivial to execute.

### 4. Zero Silent Failures
Missing indicators, incomplete SMC data, or blank rationale trigger hard errors via `error_policy.py`. No half-formed signals reach notifications.

### 5. Plugin-Friendly & ML-Ready
Pluggable indicators, strategies, and hooks support future ML scoring and new feature integration without core refactoring.

## System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI/REST)                       │
│                                                                    │
│  Scanner Endpoints          │         Bot Endpoints               │
│  • POST /api/scan           │         • POST /api/bot/start       │
│  • GET /api/signals/{id}    │         • POST /api/bot/stop        │
│  • GET /api/signal/{id}     │         • GET /api/bot/status       │
│  • POST /api/backtest       │         • GET /api/bot/positions    │
│  • GET /api/history         │         • GET /api/bot/logs         │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                      Engine Orchestrator                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │   Pipeline   │  │   Context    │  │    Hooks     │            │
│  │  Controller  │  │   Manager    │  │   System     │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                    │
│  ┌──────────────────────────────────────────────────┐            │
│  │           Bot Loop Scheduler (if Bot Mode)       │            │
│  │  • Interval-based scan triggers                  │            │
│  │  • Quality gate filtering                        │            │
│  │  • Position state management                     │            │
│  └──────────────────────────────────────────────────┘            │
└────────────────────────────┬───────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────┐      ┌─────────────┐    ┌─────────────┐
│    Data     │      │ Indicators  │    │  Strategy   │
│   Package   │      │   Package   │    │   Package   │
│             │      │             │    │             │
│ • Adapters  │      │ • Momentum  │    │ • SMC       │
│ • Cache     │      │ • Mean Rev  │    │ • Confluence│
│ • Pipeline  │      │ • Volume    │    │ • Planner   │
└─────────────┘      └─────────────┘    └─────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
         ┌──────────────────────────────────────┐
         │         Risk Package                 │
         │ • Position Sizing                    │
         │ • Exposure Limits                    │
         │ • Compliance Checks                  │
         │ • Daily Loss Failsafe                │
         └──────────────────┬───────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▓
┌─────────────┐      ┌─────────────┐    ┌─────────────┐
│     Bot     │      │ Telemetry   │    │   Audit     │
│  Executor   │      │  Analytics  │    │  Pipeline   │
│             │      │             │    │             │
│ • Paper/Live│      │ • Logging   │    │ • Quality   │
│ • Telegram  │      │ • Events    │    │   Gates     │
│ • Charts    │      │ • Stats     │    │ • Reporting │
│ • Orders    │      │             │    │             │
└─────────────┘      └─────────────┘    └─────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│            Exchange Profile Manager                    │
│  • Server-side API key storage                         │
│  • Profile definitions (Binance_Live, Bybit_Paper)     │
│  • Capability flags (live_enabled, paper_enabled)      │
│  • Rate limiting & retry logic                         │
└────────────────────────────────────────────────────────┘
```

## Data Flow Pipeline

```
Symbol Selection
      ↓
Multi-TF Data Ingestion (1W → 5m)
      ↓
Indicator Computation (per TF)
      ↓
SMC Detection (OB, FVG, BOS, CHoCH, Liquidity Sweeps)
      ↓
Regime Detection (Trend/Range, BTC Impulse)
      ↓
Confluence Scoring (Multi-factor + Synergy/Conflict)
      ↓
Quality Gates (HTF Alignment, Freshness, Displacement)
      ↓
Trade Plan Generation (Entry, Stops, Targets, RR)
      ↓
Risk Validation (Position Size, Exposure, Compliance)
      ↓
Notification / Execution (Telegram, Bot, Audit)
```

## Exchange Profiles & Security

### Exchange Profile System

**Purpose**: Manage exchange API credentials and capabilities server-side with zero client exposure.

**Profile Structure**:
```python
@dataclass
class ExchangeProfile:
    name: str  # e.g., "Binance_Live", "Bybit_Paper"
    exchange: str  # "binance", "bybit", "okx"
    mode: str  # "live" | "paper"
    env_vars: Dict[str, str]  # Maps to environment variable names
    capabilities: ProfileCapabilities
    rate_limits: RateLimitConfig

@dataclass
class ProfileCapabilities:
    data_enabled: bool  # Can fetch market data
    paper_enabled: bool  # Can run paper trading
    live_enabled: bool  # Can execute live trades
    keys_valid: bool  # API keys present and validated
```

**Example Profiles**:

| Profile Name       | Exchange | Mode  | Data | Paper | Live | Requires Keys |
|--------------------|----------|-------|------|-------|------|---------------|
| `Binance_Data`     | Binance  | data  | ✓    | ✗     | ✗    | ✗             |
| `Binance_Paper`    | Binance  | paper | ✓    | ✓     | ✗    | ✗             |
| `Binance_Live`     | Binance  | live  | ✓    | ✓     | ✓    | ✓             |
| `Bybit_Data`       | Bybit    | data  | ✓    | ✗     | ✗    | ✗             |
| `Bybit_Live`       | Bybit    | live  | ✓    | ✓     | ✓    | ✓             |

**Environment Variables**:
```bash
# Binance
BINANCE_API_KEY=<key>
BINANCE_API_SECRET=<secret>

# Bybit
BYBIT_API_KEY=<key>
BYBIT_API_SECRET=<secret>

# OKX
OKX_API_KEY=<key>
OKX_API_SECRET=<secret>
OKX_PASSPHRASE=<passphrase>
```

**Security Principles**:
1. ✅ **Server-side only** - API keys never sent to frontend or stored in browser
2. ✅ **Environment-based** - Keys loaded from environment variables or secure vault
3. ✅ **Profile abstraction** - Frontend only sees profile names and capability flags
4. ✅ **Validation on startup** - Keys validated during server initialization
5. ✅ **Read-only for Scanner** - Scanner Mode uses public data endpoints (no keys needed)
6. ✅ **Explicit LIVE confirmation** - UI requires additional confirmation for LIVE mode activation

**API Response to Frontend**:
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
      "name": "Binance_Live",
      "exchange": "binance",
      "mode": "live",
      "data_enabled": true,
      "paper_enabled": true,
      "live_enabled": true
    }
  ]
}
```

Frontend only knows:
- Profile exists
- What capabilities it has
- Cannot see or access keys

See `docs/exchange_profiles.md` and `docs/security.md` for comprehensive specifications.

---

## Scanner Flow (Recon Mode) - Full Backend + UI

### Backend: Scanner API

**Endpoint: `POST /api/scan`**

**Request**:
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

**Response**:
```json
{
  "run_id": "scan_2024-01-15_123456",
  "timestamp": "2024-01-15T12:34:56Z",
  "profile": "balanced",
  "exchange_profile": "Binance_Data",
  "symbols_scanned": 20,
  "signals_generated": 5,
  "signals_discarded": 8,
  "signals": [/* SignalPayload[] */],
  "summary": {
    "longs": 3,
    "shorts": 2,
    "avg_score": 78.5,
    "avg_rr": 3.2
  }
}
```

**Endpoint: `GET /api/signals/{run_id}`**

Returns all signals for a specific scan run.

**Endpoint: `GET /api/signal/{signal_id}`**

Returns detailed `SignalPayload` for a single signal.

---

### Frontend: Scanner Mode UI ("Recon UI")

The Scanner UI uses sniper-themed terminology while maintaining clean architectural separation.

#### Screen 1: Acquire Targets (Scan Control Panel)

**Purpose**: Configure and trigger scans.

**Components**:
- **Profile Selector** (dropdown): balanced, trend, range, aggressive, mobile
- **Exchange Profile** (dropdown): Binance_Data, Bybit_Data, etc. (data-only profiles)
- **Universe Selection**: 
  - Radio: Top 10, Top 20, Top 50, Custom
  - If Custom: Multi-select symbol picker
- **Timeframes** (checkboxes): 1W, 1D, 4H, 1H, 15m, 5m (default: all)
- **Filters** (optional):
  - Min Precision Rating (score slider: 0-100)
  - Min R:R (number input)
  - Direction filter: Longs Only, Shorts Only, Both

**Primary Action**:
- Button: **"Sweep the Field"** (accent color, prominent)
  - Triggers `POST /api/scan`
  - Shows loading state with scan progress
  - Transitions to Target Board on completion

**Scan Summary Card** (appears after scan):
- Symbols scanned: 20
- Targets acquired: 5
- Targets discarded: 8
- Avg Precision Rating: 78.5
- Avg R:R: 3.2

---

#### Screen 2: Target Board (Signals List / Leaderboard)

**Purpose**: High-level view of all signals from a scan run.

**Layout**: Sortable, filterable table

**Columns**:
- **Symbol** (e.g., BTC/USDT)
- **Direction** (LONG/SHORT with color coding)
- **Precision Rating** (score with visual bar)
- **R:R** (risk-reward ratio)
- **Engagement Type** (setup style: scalp, swing, intraday)
- **Regime Tags** (badges: trend/range, risk-on/off)
- **Timestamp**

**Interactions**:
- **Sort**: By score, R:R, timestamp, symbol
- **Filter**: 
  - Direction (LONG/SHORT)
  - Min score
  - Min R:R
  - Profile
  - Symbol search
- **Row click**: Opens Target Intel drawer/dialog for selected signal

**Empty State**: "No targets acquired. Sweep the field to identify opportunities."

---

#### Screen 3: Target Intel (Signal Detail View)

**Purpose**: Complete trade plan for a single signal.

**Layout**: Drawer or dialog with tabbed/sectioned content

**Section 1: Overview**
- **Symbol**: BTC/USDT
- **Direction**: LONG (with icon)
- **Engagement Type**: Swing
- **Precision Rating**: 78.5 (with visual indicator)
- **Threat Index** (risk score): Medium (color-coded badge)
- **Timestamp**: 2024-01-15 12:34:56 UTC

**Section 2: Tactical Plan**
- **Entry Zones** (near/far entries):
  - Near Entry: $42,150
  - Far Entry: $41,800
  - Rationale: "Entry anchored to bullish OB on 4H with FVG confluence"
  
- **Extraction Point** (stop loss):
  - SL: $41,200
  - Distance: 1.8 ATR
  - Rationale: "Below 4H OB invalidation level"
  
- **Impact Points** (targets):
  - TP1: $43,500 (50%) - "Previous 4H high"
  - TP2: $44,800 (30%) - "1W resistance zone"
  - TP3: $46,200 (20%) - "Extended FVG fill"

- **Risk:Reward**: 3.2:1

**Section 3: Confluence Breakdown**
Visual breakdown of scoring factors:
- Structure: 85 (weight 0.3) - "HTF aligned BOS"
- SMC: 90 (weight 0.25) - "Fresh OB + FVG confluence"
- Momentum: 75 (weight 0.2) - "RSI recovery from oversold"
- Volatility: 70 (weight 0.15) - "ATR expansion"
- Regime: 80 (weight 0.1) - "Trend mode, BTC impulse aligned"

Synergy Bonus: +5
Conflict Penalty: -2
**Total Score**: 78.5

**Section 4: Reasoning** (full narrative)
Multi-paragraph human-readable explanation of the setup.

**Section 5: Raw Data** (collapsible/toggle)
JSON view of complete `SignalPayload` for debugging/verification.

**Actions**:
- **Export JSON** (download signal data)
- **Copy to Clipboard** (formatted text)
- **Close**

---

#### Screen 4: Recon History

**Purpose**: View past scan runs and reload old signals.

**Layout**: List/table of historical scan runs

**Columns**:
- **Run ID**
- **Timestamp**
- **Profile**
- **Exchange Profile**
- **Symbols Scanned**
- **Targets Acquired**
- **Avg Score**

**Interactions**:
- **Row click**: Loads that run's Target Board
- **Filter**: By date range, profile, exchange

**Storage**: Backend stores scan results; frontend fetches via `GET /api/history`.

---

## Bot System (SniperBot Mode) - Backend + UI

### Backend: Bot Architecture

**Bot Operational Modes**:

| Mode       | Scan Loop | Signal Gen | Paper Exec | Live Exec | Requires Keys |
|------------|-----------|------------|------------|-----------|---------------|
| OFF        | ✗         | ✗          | ✗          | ✗         | ✗             |
| PAPER      | ✓         | ✓          | ✓          | ✗         | ✗             |
| LIVE       | ✓         | ✓          | ✓          | ✓         | ✓             |

**Bot Safeguards & Rules**:

1. **Risk Limits** (enforced per trade and aggregate):
   - Max risk per engagement (% of equity)
   - Max active engagements (open position count)
   - Leverage cap
   - Daily loss failsafe (stop all trading if hit)

2. **Quality Gates** (same as Scanner Mode):
   - HTF alignment required
   - Minimum confluence score
   - Freshness requirements
   - Displacement thresholds

3. **Error Policy**:
   - Zero silent failures
   - All errors logged to telemetry
   - Critical errors halt bot and send alert
   - Invalid signals discarded with reason logged

**Bot Loop**:
```
Timer triggers (every N minutes)
  ↓
Check bot status (running? mode? health?)
  ↓
Run engine pipeline (same as Scanner Mode)
  ↓
Quality gates filter signals
  ↓
For each passing signal:
  - Check risk limits
  - Check for existing conflicting positions
  - If approved: bot/executor stages order (paper or live)
  - Log all decisions to telemetry
  ↓
Monitor existing positions
  ↓
Check if daily loss limit hit
  ↓
Log cycle completion
  ↓
Wait for next interval
```

**Bot State Management**:
```python
@dataclass
class BotStatus:
    mode: str  # "OFF" | "PAPER" | "LIVE"
    profile: str  # Strategy profile
    exchange_profile: str  # Exchange profile name
    is_running: bool
    started_at: Optional[datetime]
    last_cycle: Optional[datetime]
    next_cycle: Optional[datetime]
    active_positions: int
    daily_pnl: float
    daily_loss_limit_hit: bool
    health: str  # "healthy" | "warning" | "error"
    warnings: List[str]
```

**Bot Executor** (`bot/executor/trades.py`):
```python
class BotExecutor:
    def stage_order(plan: TradePlan, mode: str) -> Order:
        """
        Creates order object for paper or live execution.
        - PAPER: Simulates order locally, no exchange API call
        - LIVE: Submits to exchange via exchange profile
        """
    
    def execute_order(order: Order, exchange_profile: ExchangeProfile) -> ExecutionResult:
        """
        For PAPER: Updates internal paper account
        For LIVE: Calls exchange API, handles errors
        """
    
    def monitor_positions(positions: List[Position]) -> List[PositionUpdate]:
        """
        Checks stop loss hits, take profit fills, partial exits
        """
```

**Bot API Endpoints**:

#### `POST /api/bot/start`
**Request**:
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
    "min_score": 70
  }
}
```

**Response**:
```json
{
  "status": "started",
  "bot_status": { /* BotStatus */ },
  "message": "SniperBot deployed in PAPER mode"
}
```

#### `POST /api/bot/stop`
**Response**:
```json
{
  "status": "stopped",
  "message": "Bot ceased operation. All positions remain open.",
  "final_stats": {
    "total_scans": 48,
    "signals_generated": 12,
    "engagements_opened": 5,
    "daily_pnl": 2.3
  }
}
```

#### `GET /api/bot/status`
**Response**: `BotStatus` object

#### `GET /api/bot/positions`
**Response**:
```json
{
  "positions": [
    {
      "id": "pos_123",
      "symbol": "BTC/USDT",
      "side": "LONG",
      "entry_price": 42150,
      "size": 0.05,
      "extraction_point": 41200,
      "impact_points": [43500, 44800, 46200],
      "current_price": 42800,
      "pnl": 32.5,
      "pnl_percent": 1.54,
      "rr": 3.2,
      "opened_at": "2024-01-15T14:20:00Z",
      "status": "open"
    }
  ]
}
```

#### `GET /api/bot/logs`
**Request**: `?limit=100&event_type=all&start_time=...`

**Response**:
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
        "size": 0.05
      }
    },
    {
      "timestamp": "2024-01-15T13:50:00Z",
      "event_type": "target_discarded",
      "data": {
        "symbol": "ETH/USDT",
        "reason": "Failed HTF alignment gate"
      }
    }
  ]
}
```

**Event Types**:
- `scan_completed`
- `target_acquired` (signal generated)
- `target_discarded` (signal rejected with reason)
- `engagement_opened` (position opened)
- `partial_taken` (TP hit)
- `extraction_triggered` (SL hit)
- `engagement_closed` (position fully closed)
- `risk_limit_hit` (trade blocked by risk rules)
- `daily_loss_limit_hit` (bot auto-paused)
- `error_occurred`

---

### Frontend: SniperBot UI ("Command Center")

#### Screen 1: SniperBot Command Center (Control Panel)

**Purpose**: Deploy and configure the bot.

**Section 1: Mode Selection**

**Mode Selector** (radio buttons with descriptions):
- ⚪ **Safety** (OFF) - "Bot inactive"
- ⚪ **Training Mode** (PAPER) - "Simulated execution, no real orders"
- ⚪ **Live Ammunition** (LIVE) - "⚠️ Real trades with real funds"
  - Requires confirmation dialog
  - Only enabled if `exchange_profile.live_enabled === true`

**Section 2: Configuration**

- **Strategy Profile** (dropdown): balanced, trend, range, aggressive
- **Exchange Profile** (dropdown): Shows only profiles with appropriate capabilities
  - If PAPER mode: Show all paper-enabled profiles
  - If LIVE mode: Show only live-enabled profiles with valid keys
  
- **Risk Controls**:
  - Max Risk Per Engagement: [1.0]% (slider 0.5-5%)
  - Max Active Engagements: [3] (number input)
  - Daily Loss Failsafe: [5.0]% (slider 2-10%)
  - Leverage Cap: [3]x (slider 1-10x)

- **Filters** (optional):
  - ☑ Allow Longs
  - ☑ Allow Shorts
  - Min Precision Rating: [70] (slider)

- **Scan Interval**: [15] minutes (dropdown: 5, 15, 30, 60)

**Section 3: Deployment**

**Buttons**:
- **"Deploy SniperBot"** (primary action, accent color)
  - If LIVE mode: Shows confirmation dialog with checklist:
    - ☑ I understand real funds will be used
    - ☑ I have verified exchange API keys
    - ☑ I have set appropriate risk limits
  - Calls `POST /api/bot/start`
  
- **"Cease Operation"** (secondary, destructive color)
  - Only enabled if bot is running
  - Calls `POST /api/bot/stop`

**Status Indicator**:
- 🔴 Inactive (OFF)
- 🟡 Training (PAPER)
- 🟢 Live (LIVE)

---

#### Screen 2: Active Engagements (Open Positions)

**Purpose**: Monitor bot-managed positions.

**Layout**: Table of open positions

**Columns**:
- **Symbol**
- **Side** (LONG/SHORT)
- **Entry** (entry price)
- **Extraction Point** (SL price)
- **Impact Points** (TP levels)
- **Size**
- **R:R**
- **PnL** ($)
- **PnL%** (color-coded)
- **Status** (open, partial, closing)

**Row Actions** (dropdown menu):
- **View Full Intel** (opens signal detail)
- **Move SL to Breakeven** (backend updates SL)
- **Close Engagement** (manually close position)

**Data Source**: `GET /api/bot/positions` with polling/websocket updates

---

#### Screen 3: Mission Log (Bot Activity Log)

**Purpose**: Timeline of bot decisions and actions.

**Layout**: Reverse chronological event feed

**Event Cards**:

**Scan Completed**:
```
[14:20:00] Scan Completed
• Symbols scanned: 20
• Targets acquired: 3
• Targets discarded: 5
```

**Target Acquired**:
```
[14:20:15] Target Acquired: BTC/USDT LONG
• Precision Rating: 78.5
• R:R: 3.2
• Engagement Type: Swing
```

**Target Discarded**:
```
[14:20:10] Target Discarded: ETH/USDT
• Reason: Failed HTF alignment gate
• Score: 65 (below threshold)
```

**Engagement Opened**:
```
[14:21:00] Engagement Opened: BTC/USDT LONG
• Entry: $42,150
• Size: 0.05 BTC
• SL: $41,200 | TPs: $43,500 / $44,800 / $46,200
```

**Partial Taken**:
```
[15:45:00] Impact Point 1 Hit: BTC/USDT
• TP1 filled at $43,500 (50% position)
• Realized PnL: +$67.50
```

**Extraction Triggered**:
```
[16:10:00] Extraction Triggered: ETH/USDT SHORT
• SL hit at $2,285
• Loss: -$22.80 (-1.1%)
```

**Risk Limit Hit**:
```
[14:22:00] Engagement Blocked: SOL/USDT
• Reason: Max active engagements (3) reached
• Queued signal discarded
```

**Filters**:
- Event type (all, scans, engagements, targets discarded, errors)
- Symbol search
- Time range

**Data Source**: `GET /api/bot/logs` with real-time updates

---

#### Screen 4: Bot Status Overview

**Purpose**: At-a-glance bot health and performance.

**Status Card**:
```
╔══════════════════════════════════════════╗
║ SniperBot Status                         ║
╠══════════════════════════════════════════╣
║ Mode: 🟢 Live Ammunition                 ║
║ Profile: Balanced                        ║
║ Exchange: Binance_Live                   ║
║ Status: Running                          ║
║                                          ║
║ Active Engagements: 2 / 3 max            ║
║ Today's PnL: +$145.30 (+2.1%)            ║
║                                          ║
║ Last Scan: 2 minutes ago                 ║
║ Next Scan: in 13 minutes                 ║
║                                          ║
║ Health: ✓ Operational                    ║
╚══════════════════════════════════════════╝
```

**Health Warnings** (if any):
- ⚠️ Daily loss limit: 80% consumed
- ⚠️ Exchange API rate limit approaching
- ⚠️ Position monitoring delayed

**Quick Stats**:
- Total scans today: 48
- Targets acquired: 12
- Targets discarded: 28
- Engagements opened: 5
- Win rate: 60%
- Avg R:R achieved: 2.8

**Data Source**: `GET /api/bot/status` with polling

---

## Package Responsibilities

### shared/
**Purpose**: Cross-cutting models, configurations, and utilities used by all packages.

**Key Modules**:
- `config/`: Centralized defaults, profile-based tuning (balanced, trend, range, aggressive, mobile)
- `models/`: Typed dataclasses for OHLCV, indicators, SMC, scoring, plans, notifications
- `utils/`: Schema validation, serialization, caching primitives, error enforcement

**Contracts**: Defines canonical data shapes; all packages import from `shared.models`.

### contracts/
**Purpose**: API boundary definitions that enforce consistent interfaces across packages.

**Key Files**:
- `indicators_contract.py`: Indicator function signatures and output schemas
- `strategy_contract.py`: Strategy engine input/output specifications
- `risk_contract.py`: Risk calculation and validation interfaces
- `notification_contract.py`: Message payload structure requirements

**Usage**: Spark/Copilot must respect these contracts when modifying package internals.

### data/
**Purpose**: Multi-exchange data ingestion, caching, and normalization.

**Key Modules**:
- `adapters/`: Exchange-specific wrappers (Binance, Bybit, mocks) with retry/rate-limit handling
- `cache.py`: Persistent HTF candle storage and order-book snapshots
- `ingestion_pipeline.py`: Universe selection, parallel multi-TF downloads, DataFrame → dataclass conversion

**Output**: Produces `shared.models.data.MultiTimeframeData` objects.

### indicators/
**Purpose**: Technical analysis computation across all timeframes.

**Key Modules**:
- `momentum.py`: RSI, Stoch RSI, MFI
- `mean_reversion.py`: Bollinger Bands, z-scores
- `volatility.py`: ATR, realized volatility
- `volume.py`: Volume spikes, OBV
- `registry.py`: Plugin factory for extensible indicator bundles

**Output**: Produces `shared.models.indicators.IndicatorSet` keyed by timeframe.

### strategy/
**Purpose**: Smart-Money Concept detection, confluence scoring, and trade planning.

**Sub-packages**:

#### strategy/smc/
- `order_blocks.py`: OB detection with displacement, mitigation, freshness tracking
- `fvg.py`: Fair value gap identification with size/overlap analysis
- `bos_choch.py`: Structural breaks, CHoCH, BOS with HTF alignment
- `liquidity_sweeps.py`: Wick/close sweeps around key levels

#### strategy/confluence/
- `scorer.py`: Multi-factor aggregation with synergy bonuses and conflict penalties
- `regime_detection.py`: Trend/range, risk-on/off, BTC impulse classification
- `plugins.py`: Extensible scoring factor system

#### strategy/planner/
- `entry.py`: Dual entry zone calculation (near/far)
- `stops_targets.py`: ATR and structure-based stop/target generation
- `style_classifier.py`: Scalp/swing/intraday classification
- `planner_service.py`: Complete plan assembly with rationale synthesis

**Output**: Produces `shared.models.planner.TradePlan` with zero null fields.

### risk/
**Purpose**: Position sizing, exposure control, and compliance validation.

**Key Modules**:
- `position_sizing.py`: Account risk % → position size calculation
- `exposure_limits.py`: Per-asset, per-exchange, aggregate caps
- `compliance_checks.py`: Pre-execution sanity checks
- `audit_pipeline.py`: Decision logging for "proof of discipline"

**Output**: Produces `shared.models.risk.RiskPlan` or rejection with reason.

### bot/
**Purpose**: Bot automation, notification delivery, execution (paper/live), charting, and telemetry.

**Sub-packages**:

#### bot/executor/
- `trades.py`: Order staging, paper simulation, live execution via exchange adapters
  - `stage_order()`: Creates Order object
  - `execute_paper()`: Simulates execution without exchange API
  - `execute_live()`: Submits real orders to exchange
  - `monitor_positions()`: Tracks SL/TP fills and position updates
  
- `safeguards.py`: Pre-execution validation and safety checks
  - `check_duplicate_order()`: Prevents double-firing same signal
  - `enforce_max_risk()`: Blocks trades exceeding risk limits
  - `check_daily_loss_limit()`: Halts bot if daily loss threshold hit
  - `prevent_conflicting_positions()`: Avoids opposing positions in same symbol

- `bot_controller.py`: Bot lifecycle management
  - `start_bot()`: Initializes bot loop with config
  - `stop_bot()`: Graceful shutdown
  - `get_status()`: Returns current BotStatus
  - `update_config()`: Hot-reload risk parameters

#### bot/notifications/
- `telegram.py`: Message dispatch with retry logic
- `formatters.py`: Plan → Markdown/JSON conversion, sniper-themed formatting
- `templates/`: Reusable message templates

#### bot/ui/
- `charts.py`: Price charts with OB/FVG/entry overlays
- `overlays.py`: SMC and indicator visualization

#### bot/telemetry/
- `analytics.py`: Hit-rate, RR distribution, regime performance
- `logging.py`: Structured stage-by-stage logs
- `events.py`: Typed telemetry events (scan_completed, target_acquired, target_discarded, engagement_opened, partial_taken, extraction_triggered, risk_limit_hit, etc.)
  - All events logged with timestamp, context, metadata
  - Powers Mission Log UI and audit trail

### engine/
**Purpose**: Pipeline orchestration, context management, and plugin coordination.

**Key Modules**:
- `pipeline.py`: DAG execution controller (data → indicators → SMC → confluence → planner → risk → notify)
- `context.py`: `SniperContext` object holding symbol, multi-TF data, indicators, SMC, confluence, plan, risk, metadata
- `orchestrator.py`: High-level entry point for CLI, scripts, APIs
- `hooks.py`: Lifecycle hooks for debugging, tracing, ML integration
- `plugins/`: Base plugin interface and registry

### ml/
**Purpose**: Future ML integration hooks.

**Key Modules**:
- `feature_buffer.py`: Feature extraction from context/indicators/SMC
- `scoring_adapter.py`: ML-based signal re-ranking via hooks

### devtools/
**Purpose**: Development utilities and debugging tools.

**Key Modules**:
- `codegen_tools.py`: Stub generation, refactoring helpers
- `profiling.py`: Pipeline stage performance analysis
- `debug_cli.py`: Ad hoc debug commands

### tests/
**Purpose**: Comprehensive verification and regression testing.

**Structure**:
- `fixtures/`: Deterministic OHLCV and expected signal outputs
- `unit/`: Per-module tests
- `integration/`: Full pipeline tests
- `backtest/`: Historical simulation and validation

---

## Sniper-Themed UI Language Layer

**Purpose**: Apply tactical/sniper terminology to UI elements while preserving technical accuracy in backend code and API contracts.

**Important**: This terminology applies **ONLY** to UI labels, button text, and user-facing messaging. Backend code, API endpoints, type names, and database schemas remain unchanged and use standard technical terminology.

### Terminology Mapping

| Functional Term         | Sniper Term              | Context                          |
|-------------------------|--------------------------|----------------------------------|
| Scan                    | Sweep the Field          | Button label, action             |
| Scanner Mode            | Recon                    | Mode name, tab label             |
| Signals List            | Target Board             | Screen title                     |
| Signal Details          | Target Intel             | Screen title, drawer title       |
| Confluence Score        | Precision Rating         | Metric label                     |
| Risk Score              | Threat Index             | Metric label                     |
| Stop Loss               | Extraction Point         | Trade plan field                 |
| Take Profit / Target    | Impact Point             | Trade plan field                 |
| Entry (near/far)        | Entry Zone               | Trade plan field                 |
| Bot Start               | Deploy SniperBot         | Button label                     |
| Bot Stop                | Cease Operation          | Button label                     |
| Bot Activity Log        | Mission Log              | Screen title                     |
| Signal Rejected         | Target Discarded         | Log event, status                |
| Open Position           | Active Engagement        | Status, table title              |
| Setup Style             | Engagement Type          | Classification (scalp/swing)     |
| Max Open Positions      | Max Active Engagements   | Risk parameter label             |
| Position Size           | Engagement Size          | Order parameter                  |

### Usage Guidelines

1. **UI Only**: Use sniper terms in:
   - Button labels and CTA text
   - Screen titles and navigation labels
   - Status messages and notifications
   - Metric labels in cards and tables
   - User-facing documentation

2. **Backend Unchanged**: Keep technical terms in:
   - API endpoint names (`/api/scan`, not `/api/sweep`)
   - JSON field names (`"stop_loss"`, not `"extraction_point"`)
   - Database column names
   - Python class/function names
   - Internal logs and error messages

3. **Consistency**: 
   - Always use the same sniper term for the same functional concept
   - Document any new terminology additions in `docs/sniper_ui_theme.md`

4. **Accessibility**:
   - Provide tooltips with technical terms for advanced users
   - Include both terms in search/filter functionality

**Example UI Text**:
```
✅ Good (UI):
"Deploy SniperBot in Training Mode"
"Sweep the Field to acquire targets"
"Extraction Point: $41,200"

❌ Bad (API):
POST /api/sniper/deploy  (should be /api/bot/start)
{ "extraction_point": 41200 }  (should be "stop_loss": 41200)
```

See `docs/sniper_ui_theme.md` for complete reference.

---

## SniperSight-UI Repository Structure

**Purpose**: Separate frontend application consuming SniperSight backend APIs.

**Tech Stack** (recommended):
- React/TypeScript or Vue/TypeScript
- TailwindCSS for styling
- Recharts/D3 for visualization
- Axios/Fetch for API calls
- React Query for data fetching and caching

### Repository Structure

```
SniperSight-UI/
├── README.md
├── package.json
├── tsconfig.json
├── vite.config.ts  (or webpack/next config)
│
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   │
│   ├── api/
│   │   ├── client.ts                  # Axios instance, base config
│   │   ├── scanner.ts                 # Scanner API calls
│   │   ├── bot.ts                     # Bot API calls
│   │   ├── profiles.ts                # Exchange profiles API
│   │   └── types/                     # API request/response types
│   │       ├── scanner.types.ts
│   │       ├── bot.types.ts
│   │       └── signal.types.ts
│   │
│   ├── types/
│   │   ├── signal.ts                  # SignalPayload, TradePlan (mirrors backend)
│   │   ├── context.ts                 # SniperContext (mirrors backend)
│   │   ├── bot.ts                     # BotStatus, Position, BotLogEvent
│   │   └── shared.ts                  # Common types
│   │
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Table.tsx
│   │   │   └── ...
│   │   │
│   │   ├── scanner/
│   │   │   ├── ScanControlPanel.tsx   # "Acquire Targets" screen
│   │   │   ├── TargetBoard.tsx        # Signals table
│   │   │   ├── TargetIntel.tsx        # Signal detail drawer
│   │   │   ├── ReconHistory.tsx       # Past scans
│   │   │   ├── SignalCard.tsx
│   │   │   ├── ConfluenceBreakdown.tsx
│   │   │   └── TradePlanView.tsx
│   │   │
│   │   ├── bot/
│   │   │   ├── CommandCenter.tsx      # Bot control panel
│   │   │   ├── ActiveEngagements.tsx  # Open positions table
│   │   │   ├── MissionLog.tsx         # Bot activity log
│   │   │   ├── BotStatus.tsx          # Status overview card
│   │   │   ├── PositionCard.tsx
│   │   │   ├── LogEventCard.tsx
│   │   │   └── RiskControls.tsx
│   │   │
│   │   ├── charts/
│   │   │   ├── PriceChart.tsx
│   │   │   ├── ConfluenceChart.tsx
│   │   │   └── overlays/
│   │   │       ├── OrderBlockOverlay.tsx
│   │   │       ├── FVGOverlay.tsx
│   │   │       └── EntryStopTargetOverlay.tsx
│   │   │
│   │   └── layout/
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       ├── Footer.tsx
│   │       └── Layout.tsx
│   │
│   ├── routes/ (or pages/)
│   │   ├── Scanner.tsx                # Scanner mode root
│   │   ├── Bot.tsx                    # Bot mode root
│   │   ├── Settings.tsx
│   │   └── ...
│   │
│   ├── hooks/
│   │   ├── useScanner.ts              # Scanner API hooks
│   │   ├── useBot.ts                  # Bot API hooks
│   │   ├── useBotStatus.ts            # Polling/websocket for bot status
│   │   ├── usePositions.ts            # Real-time position updates
│   │   ├── useExchangeProfiles.ts     # Exchange profiles fetching
│   │   └── useWebSocket.ts            # WebSocket connection management
│   │
│   ├── stores/ (or context/)
│   │   ├── scannerStore.ts            # Scanner state (Zustand/Redux/Context)
│   │   ├── botStore.ts                # Bot state
│   │   └── profileStore.ts            # User profile/settings
│   │
│   ├── theme/
│   │   └── sniper/
│   │       ├── colors.ts              # Color definitions
│   │       ├── typography.ts          # Font configs
│   │       ├── terminology.ts         # Sniper term mappings
│   │       └── tailwind.config.ts     # Tailwind customization
│   │
│   ├── utils/
│   │   ├── formatters.ts              # Number, date, currency formatters
│   │   ├── validators.ts              # Form validation
│   │   ├── terminology.ts             # Functional → Sniper term converter
│   │   └── constants.ts
│   │
│   └── assets/
│       ├── icons/
│       ├── images/
│       └── fonts/
│
└── public/
    └── ...
```

### Core Screens/Routes

#### Scanner Mode Routes
- `/scanner` - Default view, Scan Control Panel ("Acquire Targets")
- `/scanner/targets` - Target Board (signals list)
- `/scanner/targets/:signal_id` - Target Intel (signal detail)
- `/scanner/history` - Recon History

#### Bot Mode Routes
- `/bot` - Command Center (bot control panel)
- `/bot/engagements` - Active Engagements (open positions)
- `/bot/log` - Mission Log (activity timeline)
- `/bot/status` - Bot Status Overview

#### Shared Routes
- `/settings` - User settings, API configuration
- `/profiles` - Exchange profile management (view only, no key input)
- `/help` - Documentation, terminology guide

### Key Implementation Principles

1. **Type Safety**: 
   - Mirror backend types exactly in `src/types/`
   - Use code generation from OpenAPI spec if available
   - Never assume field existence; handle null/undefined

2. **Security**:
   - **NEVER** store or request API keys in frontend
   - **NEVER** include exchange credentials in localStorage/sessionStorage
   - Only display profile names and capability flags from backend
   - All sensitive operations via backend API

3. **Real-time Updates**:
   - Use polling (5-10s) or WebSocket for:
     - Bot status
     - Active positions
     - Mission log events
   - Implement reconnection logic with exponential backoff

4. **Terminology Layer**:
   - `utils/terminology.ts` provides `toSniperTerm()` helper:
     ```ts
     toSniperTerm("stop_loss") // → "Extraction Point"
     toSniperTerm("take_profit") // → "Impact Point"
     ```
   - Use consistently across all UI components
   - Preserve technical terms in API calls

5. **Error Handling**:
   - Display user-friendly error messages
   - Log technical errors to console/monitoring
   - Provide actionable next steps on failures
   - Never expose backend stack traces to UI

6. **Responsive Design**:
   - Mobile-first approach
   - Tables → cards on mobile
   - Collapsible sections for dense data
   - Touch-optimized controls

7. **Accessibility**:
   - ARIA labels for screen readers
   - Keyboard navigation support
   - Color-blind friendly color schemes
   - Tooltips explaining sniper terms

### API Integration Pattern

**Example: Triggering a Scan**

```typescript
// src/api/scanner.ts
import { apiClient } from './client'
import type { ScanRequest, ScanResponse } from './types/scanner.types'

export const scannerAPI = {
  async scan(request: ScanRequest): Promise<ScanResponse> {
    const response = await apiClient.post('/api/scan', request)
    return response.data
  },
  
  async getSignals(runId: string): Promise<SignalPayload[]> {
    const response = await apiClient.get(`/api/signals/${runId}`)
    return response.data.signals
  },
  
  async getSignal(signalId: string): Promise<SignalPayload> {
    const response = await apiClient.get(`/api/signal/${signalId}`)
    return response.data
  }
}

// src/hooks/useScanner.ts
import { useMutation, useQuery } from '@tanstack/react-query'
import { scannerAPI } from '@/api/scanner'

export function useScanner() {
  const scanMutation = useMutation({
    mutationFn: scannerAPI.scan,
    onSuccess: (data) => {
      // Navigate to Target Board with run_id
    }
  })
  
  return {
    scan: scanMutation.mutate,
    isScanning: scanMutation.isPending,
    scanResult: scanMutation.data
  }
}

// src/components/scanner/ScanControlPanel.tsx
function ScanControlPanel() {
  const { scan, isScanning } = useScanner()
  
  const handleSweepField = () => {
    scan({
      profile: selectedProfile,
      exchange_profile: selectedExchange,
      universe: 'top20',
      // ...
    })
  }
  
  return (
    <Button onClick={handleSweepField} disabled={isScanning}>
      {isScanning ? 'Sweeping...' : 'Sweep the Field'}
    </Button>
  )
}
```

### Environment Variables

```bash
# .env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
VITE_ENABLE_PAPER_MODE=true
VITE_ENABLE_LIVE_MODE=false  # Gated feature flag
```

### Deployment Notes

- Frontend deployed separately from backend (Vercel, Netlify, S3+CloudFront, etc.)
- Backend API URL configured via environment variables
- CORS properly configured on backend
- API authentication via JWT or session tokens (not API keys)

See `SniperSight-UI/README.md` for setup and development instructions.

---

## docs/
**Purpose**: System documentation and specifications.

**Key Files**:
- `architecture.md`: This document
- `smc_playbook.md`: Smart-Money heuristics and detection rules
- `notification_spec.md`: Message format specifications
- `output_spec.md`: Signal payload schemas
- `quality_gates.md`: Validation criteria for setups
- `verification_checklist.md`: Pre-deployment verification steps
- `versioning.md`: Semantic versioning rules
- `deployment.md`: Deployment guidance

### scripts/
**Purpose**: Operational and maintenance scripts.

**Key Scripts**:
- `run_backtest.py`: Execute historical validation
- `run_quality_audit.py`: Comprehensive quality gate checks
- `sync_cache.py`: HTF data refresh

### examples/
**Purpose**: Usage demonstrations and integration examples.

**Structure**:
- `notebook_scenarios/`: Jupyter notebooks for interactive exploration
- `api_walkthroughs/`: Scripted library usage examples

## Context Object

The `SniperContext` is the central data structure passed through the pipeline:

```python
@dataclass
class SniperContext:
    symbol: str
    profile: str
    run_id: str
    timestamp: datetime
    
    # Pipeline stages populate these
    multi_tf_data: Optional[MultiTimeframeData] = None
    multi_tf_indicators: Optional[Dict[str, IndicatorSet]] = None
    smc_snapshot: Optional[SMCSnapshot] = None
    confluence_breakdown: Optional[ConfluenceBreakdown] = None
    plan: Optional[TradePlan] = None
    risk_plan: Optional[RiskPlan] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
```

Each pipeline stage:
1. Reads from earlier stages in the context
2. Performs its computation
3. Populates its output field in the context
4. Passes context to next stage

## Hook System

Hooks enable extensibility without modifying core logic:

```python
@hook_point("before_indicator_compute")
def compute_indicators(context: SniperContext) -> SniperContext:
    # Core logic
    pass

@hook_point("after_strategy")
def plan_trade(context: SniperContext) -> SniperContext:
    # Core logic
    pass
```

Plugins register callbacks:

```python
def ml_rescoring_hook(context: SniperContext) -> SniperContext:
    if context.confluence_breakdown:
        ml_score = ml_model.predict(context)
        context.confluence_breakdown.ml_adjustment = ml_score
    return context

register_hook("after_strategy", ml_rescoring_hook)
```

## Quality Gates

Quality gates enforce discipline at multiple checkpoints:

### Data Quality Gates
- Complete timeframe coverage (no missing TFs)
- Minimum candle count per TF
- Recent data (no stale cache)
- Valid OHLCV relationships (H≥C≥L, etc.)

### Indicator Quality Gates
- No null/NaN values in recent window
- Indicator computation success
- Reasonable value ranges

### SMC Quality Gates
- Fresh order blocks (not heavily mitigated)
- Sufficient displacement strength
- HTF structural alignment
- Valid liquidity sweep confirmation

### Confluence Quality Gates
- Minimum confluence score threshold
- Low conflict penalty
- Regime alignment
- BTC impulse gate (if enabled)

### Plan Quality Gates
- R:R ratio ≥ minimum threshold
- Stops not in FVG or OB zones
- Targets aligned with structure
- Complete rationale (no empty sections)

### Risk Quality Gates
- Position size within limits
- Total exposure below cap
- No existing conflicting positions
- Compliance check pass

## Error Handling Strategy

### Zero Silent Failures
```python
# BAD - Silent failure
if indicators is None:
    return None  # ❌ Silently propagates incomplete data

# GOOD - Explicit failure
if indicators is None:
    raise IncompleteIndicatorError(
        f"Missing indicators for {symbol} on {timeframe}"
    )  # ✅ Fails loudly with context
```

### Error Policy Enforcement
`shared/utils/error_policy.py` provides validators:

```python
validate_no_nulls(obj, "TradePlan")
validate_schema(obj, TradePlanSchema)
validate_quality_gates(context)
```

All pipeline stages must pass validation before proceeding.

## Extensibility Patterns

### Adding New Indicators
1. Implement in `indicators/` following contract
2. Register in `indicators/registry.py`
3. Add to `shared/models/indicators.py` if new output type
4. Update tests with deterministic fixtures

### Adding New SMC Detectors
1. Implement in `strategy/smc/` following contract
2. Update `shared/models/smc.py` for new detection types
3. Integrate into confluence scoring
4. Add verification fixtures

### Adding New Strategies
1. Create plugin in `strategy/confluence/plugins.py`
2. Define scoring logic
3. Register in plugin registry
4. Document in `smc_playbook.md`

### Adding New Exchanges
1. Implement adapter in `data/adapters/`
2. Follow common interface (rate limits, retry, normalization)
3. Add mock for tests
4. Update ingestion pipeline

## Performance Considerations

### Caching Strategy
- HTF data (1W, 1D) cached for 24h
- LTF data (15m, 5m) cached for 5min
- Indicator results cached per symbol/TF pair
- SMC detections cached with invalidation on new candles

### Parallel Processing
- Symbol scanning parallelized across symbols
- Multi-TF data fetches parallelized within symbol
- Indicator computation parallelized across TFs

### Rate Limit Management
- Adaptive throttling based on exchange limits
- Request batching where supported
- Fallback to cached data on rate limit

## Deployment Architecture

### Mobile (Pydroid)
- Lightweight profile configurations
- Reduced symbol universe
- Extended cache TTLs
- Background notification service

### Server / VPS
- Full symbol universe
- Scheduled scans via cron
- Telegram bot integration
- Persistent audit logging

### Docker
- Multi-stage build for minimal image
- Volume mounts for cache persistence
- Environment-based configuration
- Health check endpoints

### Cloud (AWS/GCP)
- Lambda/Cloud Functions for scheduled scans
- S3/Cloud Storage for cache and audit logs
- SNS/Pub-Sub for notifications
- CloudWatch/Stackdriver for telemetry

## Version Control Strategy

### Semantic Versioning
- **Major**: Breaking contract changes, schema migrations, algorithm overhauls
- **Minor**: New features, new indicators, new strategies (backward compatible)
- **Patch**: Bug fixes, performance improvements, documentation

### Migration Checklist
- Update contracts if interfaces change
- Migrate fixtures and expected outputs
- Run full backtest suite
- Update documentation
- Tag release with changelog
