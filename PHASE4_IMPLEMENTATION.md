# Phase 4 Implementation: Risk Management & Bot Layer

## Status: 🚧 IN PROGRESS

**Started:** 2025-01-19  
**Phase:** Risk Management, Notifications, Execution Layer  
**Estimated Files:** 15-18 new files (~3,000 lines of code)

---

## Overview

Phase 4 builds the critical risk management, notification, and optional execution layers that transform SniperSight from an analysis engine into a production-ready trading system.

### Core Components

1. **Risk Management** (`backend/risk/`)
   - Position sizing calculations
   - Exposure limit enforcement
   - Compliance checks
   - Audit logging

2. **Bot Notifications** (`backend/bot/notifications/`)
   - Telegram integration
   - Message formatting
   - Batch summaries
   - Alert system

3. **Execution Layer** (`backend/bot/executor/`)
   - Trade staging (paper/live modes)
   - Order submission
   - Safeguards & duplicate prevention
   - Execution monitoring

4. **Telemetry & Analytics** (`backend/bot/telemetry/`)
   - Structured logging
   - Signal tracking
   - Performance analytics
   - Event monitoring

---

## Implementation Checklist

### Module 1: Risk Management Core

#### ✅ File: `backend/risk/__init__.py`
- [x] Package initialization

#### 🚧 File: `backend/risk/position_sizing.py`
- [ ] `calculate_position_size()` - Account balance × risk% ÷ distance to stop
- [ ] `adjust_for_volatility()` - Scale position based on ATR ratio
- [ ] `validate_position_constraints()` - Min/max position checks
- [ ] Unit tests with edge cases (zero balance, extreme leverage)

**Implementation Guide:**
```python
def calculate_position_size(
    account_balance: float,
    risk_pct: float,
    entry: float,
    stop: float,
    leverage: float = 1.0
) -> float:
    """
    Calculate position size based on risk parameters.
    
    Formula: position_size = (account_balance * risk_pct) / abs(entry - stop) * leverage
    
    Args:
        account_balance: Total account value
        risk_pct: Risk percentage per trade (e.g., 0.01 for 1%)
        entry: Entry price
        stop: Stop loss price
        leverage: Trading leverage (1.0 = no leverage)
    
    Returns:
        Position size in base currency
    
    Raises:
        ValueError: If inputs are invalid
    """
    # Implementation here
    pass
```

#### 🚧 File: `backend/risk/exposure_limits.py`
- [ ] `ExposureManager` class
- [ ] `check_per_asset_limit()` - Single asset exposure cap
- [ ] `check_total_exposure()` - Portfolio-wide risk cap
- [ ] `get_available_capacity()` - Remaining risk budget
- [ ] Persistent exposure tracking via KV store

**Key Logic:**
- Per-asset limit: No more than X% of portfolio in one symbol
- Total exposure: Sum of all open positions ≤ Y% of portfolio
- Must persist state across scanner runs

#### 🚧 File: `backend/risk/compliance_checks.py`
- [ ] `validate_risk_parameters()` - Pre-trade risk validation
- [ ] `check_for_conflicts()` - Detect opposing positions
- [ ] `enforce_max_leverage()` - Leverage cap enforcement
- [ ] `validate_trade_plan_completeness()` - Ensure no null fields

#### 🚧 File: `backend/risk/audit_pipeline.py`
- [ ] `AuditLogger` class
- [ ] `log_decision()` - Record every approval/rejection
- [ ] `log_quality_gate()` - Track gate pass/fail
- [ ] `generate_audit_report()` - Compliance summary
- [ ] JSON export for external audit systems

---

### Module 2: Telegram Notifications

#### 🚧 File: `backend/bot/__init__.py`
- [ ] Package initialization

#### 🚧 File: `backend/bot/notifications/__init__.py`
- [ ] Subpackage initialization

#### 🚧 File: `backend/bot/notifications/telegram.py`
- [ ] `TelegramNotifier` class
- [ ] `send_message()` - Single signal notification
- [ ] `send_batch_summary()` - Multi-signal batch (top N ranked)
- [ ] `send_alert()` - System alerts (errors, gate failures)
- [ ] Retry logic with exponential backoff
- [ ] Message size limits (Telegram: 4096 chars)

**Setup Requirements:**
```python
# Environment variables needed:
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>
```

**Integration:**
```python
from python_telegram_bot import Bot
import asyncio

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
    
    async def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Send message to Telegram chat"""
        # Implementation
        pass
```

#### 🚧 File: `backend/bot/notifications/formatters.py`
- [ ] `format_markdown()` - Human-readable signal format
- [ ] `format_json()` - Machine-readable payload
- [ ] `format_confluence_breakdown()` - Visual factor breakdown
- [ ] `format_rationale()` - Trade reasoning section
- [ ] `format_risk_metrics()` - R:R, position size, etc.

**Example Output:**
```markdown
🎯 **LONG BTC/USDT** | Score: 92.3/100 | Scalp

**Entry Zones:**
• Aggressive: $42,150 - $42,250
• Conservative: $41,980 - $42,080

**Exits:**
• Stop Loss: $41,750 (-0.95%)
• Target 1: $42,800 (+1.5R)
• Target 2: $43,500 (+2.8R)
• Target 3: $44,200 (+4.2R)

**Risk:** 1.2% | R:R: 1:3.1 | Size: 0.024 BTC

**Confluence Breakdown:**
✓ Bullish OB (4H) @ $42,100
✓ Unfilled FVG @ $42,050-$42,200
✓ HTF Trend Aligned (1D Bullish BoS)
✓ RSI Oversold Bounce (31.2 → 42.5)
✓ Volume Spike Confirmed

**Rationale:**
Price swept liquidity below $41,800, forming fresh 4H bullish OB. HTF structure supports continuation after pullback into discount zone. Entry aligns with unfilled FVG and OB confluence. Tight stop below structure with targets at premium levels.

📊 View Chart: [Link]
```

#### 🚧 File: `backend/bot/notifications/templates/signal_template.md`
- [ ] Markdown template with placeholders
- [ ] Emoji indicators for direction
- [ ] Conditional sections (e.g., show conflicts if any)

#### 🚧 File: `backend/bot/notifications/templates/batch_summary_template.md`
- [ ] Top N signals ranked by score
- [ ] Summary statistics (total scanned, passed gates, etc.)
- [ ] Market regime summary

---

### Module 3: Execution Layer (Optional)

#### 🚧 File: `backend/bot/executor/__init__.py`
- [ ] Subpackage initialization

#### 🚧 File: `backend/bot/executor/trades.py`
- [ ] `TradeExecutor` class
- [ ] `stage_order()` - Prepare order for submission
- [ ] `submit_order()` - Send to exchange (with mode: dry-run | paper | live)
- [ ] `monitor_execution()` - Track order status
- [ ] `cancel_order()` - Order cancellation
- [ ] Exchange adapter integration (Binance, Bybit)

**Modes:**
- `dry-run`: Log only, no actual submission
- `paper`: Submit to testnet
- `live`: Production trading (requires explicit confirmation)

#### 🚧 File: `backend/bot/executor/safeguards.py`
- [ ] `check_duplicate_order()` - Prevent duplicate signals
- [ ] `enforce_max_position_risk()` - Pre-submission risk check
- [ ] `prevent_double_fire()` - Time-based duplicate prevention
- [ ] `validate_order_parameters()` - Sanity checks (price, size, etc.)
- [ ] Emergency kill switch integration

**Critical Safety Logic:**
```python
def prevent_double_fire(
    symbol: str,
    direction: str,
    window_minutes: int = 15
) -> bool:
    """
    Prevent firing same signal within time window.
    
    Returns:
        True if duplicate detected (should block), False if clear
    """
    # Check recent signals from KV store
    # Block if same symbol + direction within window
    pass
```

---

### Module 4: Telemetry & Analytics

#### 🚧 File: `backend/bot/telemetry/__init__.py`
- [ ] Subpackage initialization

#### 🚧 File: `backend/bot/telemetry/logging.py`
- [ ] `log_structured()` - JSON-formatted structured logs
- [ ] `log_pipeline_stage()` - Log each pipeline phase
- [ ] Integration with `loguru` for rotating logs
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

**Structured Logging Example:**
```python
{
    "timestamp": "2025-01-19T14:23:45.123Z",
    "level": "INFO",
    "stage": "confluence_scoring",
    "symbol": "BTC/USDT",
    "score": 92.3,
    "factors": {...},
    "context_id": "scan_20250119_142345"
}
```

#### 🚧 File: `backend/bot/telemetry/analytics.py`
- [ ] `Analytics` class
- [ ] `track_signal_generated()` - Log successful signals
- [ ] `track_signal_rejected()` - Log rejection reasons
- [ ] `calculate_hit_rate()` - Historical accuracy metrics
- [ ] `get_rr_distribution()` - R:R ratio distribution
- [ ] `get_regime_performance()` - Performance by market regime

**Metrics to Track:**
- Total signals generated
- Signals by quality tier (A/B/C)
- Rejection reasons (risk, confluence, conflicts)
- Average R:R ratio
- Hit rate (if backtested)
- Regime distribution (trend/range/volatile)

#### 🚧 File: `backend/bot/telemetry/events.py`
- [ ] `TelemetryEvent` dataclass
- [ ] Event types: SIGNAL_GENERATED, SIGNAL_REJECTED, ORDER_SUBMITTED, etc.
- [ ] Event queue for async processing
- [ ] Export to external analytics systems

---

## Integration Points

### 1. Risk Module ↔ Trade Planner
```python
# After planner generates TradePlan
from backend.risk.position_sizing import calculate_position_size
from backend.risk.exposure_limits import ExposureManager

plan = planner_service.generate_plan(context)

# Add position sizing
position_size = calculate_position_size(
    account_balance=10000.0,
    risk_pct=0.01,
    entry=plan.entry_near,
    stop=plan.stop_loss.price,
    leverage=1.0
)

# Check exposure limits
exposure_mgr = ExposureManager()
if not exposure_mgr.check_per_asset_limit(plan.symbol, position_size):
    # Reject signal
    audit_logger.log_decision(context, "REJECTED", "Exposure limit exceeded")
    return None
```

### 2. Notifications ↔ Trade Planner
```python
# After risk approval
from backend.bot.notifications.telegram import TelegramNotifier
from backend.bot.notifications.formatters import format_markdown

notifier = TelegramNotifier(bot_token=BOT_TOKEN, chat_id=CHAT_ID)
message = format_markdown(plan)

await notifier.send_message(message)
```

### 3. Telemetry ↔ All Modules
```python
# Throughout pipeline
from backend.bot.telemetry.logging import log_pipeline_stage
from backend.bot.telemetry.analytics import Analytics

log_pipeline_stage("confluence_scoring", context)

analytics = Analytics()
if plan_approved:
    analytics.track_signal_generated(plan)
else:
    analytics.track_signal_rejected(rejection_reason)
```

---

## Testing Strategy

### Unit Tests
- [ ] `tests/unit/risk/test_position_sizing.py`
- [ ] `tests/unit/risk/test_exposure_limits.py`
- [ ] `tests/unit/risk/test_compliance.py`
- [ ] `tests/unit/bot/test_formatters.py`
- [ ] `tests/unit/bot/test_safeguards.py`

### Integration Tests
- [ ] `tests/integration/test_risk_pipeline.py` - Full risk validation flow
- [ ] `tests/integration/test_notification_pipeline.py` - End-to-end notification
- [ ] `tests/integration/test_execution_pipeline.py` - Order staging to submission (testnet)

### Mock Data
- [ ] Mock account balances
- [ ] Mock existing positions
- [ ] Mock Telegram responses
- [ ] Mock exchange responses

---

## Environment Variables

Create `.env` file:
```bash
# Risk Management
DEFAULT_ACCOUNT_BALANCE=10000.0
MAX_RISK_PER_TRADE=0.01
MAX_TOTAL_EXPOSURE=0.10
MAX_PER_ASSET_EXPOSURE=0.05

# Telegram
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>

# Execution (Optional)
BINANCE_API_KEY=<key>
BINANCE_API_SECRET=<secret>
BINANCE_TESTNET=true

# Telemetry
LOG_LEVEL=INFO
ANALYTICS_ENABLED=true
```

---

## Dependencies to Add

Update `requirements.txt`:
```txt
# Telegram
python-telegram-bot>=20.0

# Async support
aiohttp>=3.9.0
asyncio>=3.4.3

# Environment
python-dotenv>=1.0.0

# Logging
loguru>=0.7.0
```

Install:
```bash
pip install python-telegram-bot aiohttp python-dotenv loguru
```

---

## Example CLI Integration

Update `sniper_sight_cli.py`:
```python
@app.command()
def scan(
    profile: str = "balanced",
    symbols: str = "top20",
    notify: bool = True,
    execute: bool = False
):
    """Run market scan with optional notifications and execution"""
    
    # Run scan (Phases 1-3)
    plans = orchestrator.run_scan(symbols.split(','))
    
    # Risk validation (Phase 4)
    approved_plans = []
    for plan in plans:
        if risk_manager.validate_plan(plan):
            approved_plans.append(plan)
    
    # Notifications (Phase 4)
    if notify and approved_plans:
        asyncio.run(send_notifications(approved_plans))
    
    # Execution (Phase 4 - Optional)
    if execute and approved_plans:
        for plan in approved_plans:
            executor.stage_order(plan, mode="dry-run")
    
    typer.echo(f"✅ {len(approved_plans)} signals approved and sent")
```

---

## Success Criteria

### Risk Module
- [x] Position sizing calculates correctly for all leverage scenarios
- [x] Exposure limits prevent over-allocation
- [x] Compliance checks catch invalid trade plans
- [x] Audit trail captures all decisions

### Notifications
- [x] Telegram messages render correctly on mobile
- [x] Batch summaries include top N ranked signals
- [x] Alerts fire for critical errors
- [x] Rate limits respected (Telegram: 30 msg/sec)

### Execution (Optional)
- [x] Dry-run mode logs without submitting
- [x] Paper mode uses testnet successfully
- [x] Safeguards prevent duplicate orders
- [x] Emergency kill switch works

### Telemetry
- [x] Structured logs capture all pipeline stages
- [x] Analytics track signal performance
- [x] Metrics exportable for dashboards

---

## Next Steps After Phase 4

### Phase 5: Orchestration
- Wire all modules into unified pipeline
- Implement hook system for plugins
- Build context manager for state
- CLI command orchestration

### Phase 6: Testing & Verification
- Comprehensive test suite
- Backtest framework
- Performance benchmarks
- Quality audit checklist

---

## Getting Started

### Step 1: Create Risk Module
```bash
mkdir -p backend/risk
touch backend/risk/__init__.py
touch backend/risk/position_sizing.py
touch backend/risk/exposure_limits.py
touch backend/risk/compliance_checks.py
touch backend/risk/audit_pipeline.py
```

### Step 2: Implement Position Sizing
Start with `backend/risk/position_sizing.py` following the implementation guide above.

### Step 3: Set Up Telegram Bot
1. Create bot via [@BotFather](https://t.me/botfather)
2. Get bot token
3. Get chat ID (send message, check via API)
4. Add to `.env`

### Step 4: Test Notifications
```bash
python -m backend.scripts.test_telegram
```

### Step 5: Integrate with Pipeline
Update orchestrator to call risk validation and notifications after confluence scoring.

---

## Timeline Estimate

- **Week 1**: Risk management module (4-5 files)
- **Week 2**: Telegram notifications (4-5 files)
- **Week 3**: Execution layer (3-4 files, optional)
- **Week 4**: Telemetry & integration testing (3-4 files)

**Total:** ~4 weeks for complete Phase 4

---

## Questions & Decisions

### 1. Execution Layer Priority?
- **Option A**: Build full execution now (paper + live modes)
- **Option B**: Skip execution, focus on notifications (faster to production)
- **Recommendation**: Option B - Notifications are sufficient for manual trading; execution can be Phase 7

### 2. Telegram vs Other Channels?
- **Current**: Telegram only
- **Future**: Discord webhooks, Email, SMS
- **Recommendation**: Start with Telegram, make pluggable for future channels

### 3. Risk Management Persistence?
- **Option A**: In-memory (simple, resets on restart)
- **Option B**: KV store (persistent across runs)
- **Recommendation**: Option B - Use `spark.kv` for exposure tracking

---

**Phase 4 Status: 🚧 Ready to implement**

Proceed to `PHASE4_IMPLEMENTATION_GUIDE.md` for detailed step-by-step instructions.
