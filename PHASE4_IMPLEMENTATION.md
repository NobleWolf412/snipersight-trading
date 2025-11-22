# Phase 4 Implementation: Risk Management & Bot Layer

## Status: 🚧 IN PROGRESS

**Estimated Files:** 15-1
---
## Overview

###

   - Exposu

2. **Bot Notifications** (`backend/bot/notifications/`)

   - Alert system

   - Order submission
   - Execution monitoring
4. **Telemetry & Analytics** (`
   - Signal tracking
   - Event monitor

## Implementation Checklist
### Module 1: Risk Manage
#### ✅ File: `backend/r

- [ ] `calculate_


```python
    account_balance: 
    entry: float,
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

```markdown

• Aggressive: $42,150 - $42,250

• Stop Loss: $41,750 (-0.95%)
• T


✓ Bullish
✓ HTF Trend Aligned (1D Bullish BoS
✓ Volume Spike


```
#### 🚧 File: `backend/bot/notification
- [ ] Emoji indicators for dir

- [ ] Top N signals ranked by score
- [ ] Market regime summary
---
### Module 3
###

- [ ] `TradeExecutor` class
- [ ] `submit_order()` - Send to exchange (with mode: dr
- [ ] `cancel_order()` - Order cancellation

- `dry-run`: Log only, no actual submission
- `live`: Production trading (requires explicit confirma

- [ ] `enforce_max_
- [ ] `vali


    symbol: str,
    window_minutes: int = 15
    """

        Tr
    # Check recent signals fr
    pass



- [ ] Subpackage initialization

- [ ] `log_pipeline_stage
- [ ] Log levels: DEBUG, IN
**Structured Logging Example:**
{
    "level": "INFO",
    "symbol": "BTC/USDT"

}


- [ ] `track_signal_r
- [

- Total signals generated
- Rejection reasons (risk, confluence, co
- Hit rate (if backtested)


- [ ] Event queue for async processing




fro



    risk_pct=0.01,
    stop=plan.stop_loss.price,

# Check exposure limits
if not exposure_mgr.check_p
    audit_logger.log_decision(context, "REJECTED", "
```
### 2. Notifications ↔ Trade Planner
# After risk approval
from backend.bot.notifications.formatters import fo


```
### 3. Telemetry ↔ All Modul
# Throughout pipeline

log_pipeline_stage("confluence_scoring", context)
analytics = Analytics()
    analytics.track_signal_generated(plan)
    analytics.track_signal_rejected(rejection_reason)



- [ ] `tests/unit/risk/tes
- [ ] `te
- [ ] `tests/unit/bot/te
### Integration 
- [ ] `tests/integr

- [ ] Mock
- [ ] M



```bash
DEFAULT
MAX_TOTAL_EXPOSURE=0.10

TELEGRAM


BIN

ANALYTICS_ENABLED=true




python-telegram-bot>=20.0
# Async support
asyncio>=3.4.3
# Environment



```bash
`
---
## Example CLI Integ
Update `sniper_sight_cli.py`:
@app.command()
    profile: str =
    notify: bool = Tr
):
 
   

    for plan in plans:
            approved_pl
    # Notifications (Phase 4)
        asyncio.run(send_notifications(approved_plans))
    # Execution (Phase 4 - Optional)
        for plan in approved_plans:
    

---
## Success Criteria
### Risk Module
- [x] Exposure limits prevent over-allocation
- [x] Audit trail c
### Notifications
- [x] Batch summaries include top N ranked s

### Execution (Optional)
- [x] Paper mode uses testnet su
- [x] Emergency kill switch works
### Telemetry
- [x] Analytics track signal performance



- Wire all modules in


- Compreh
- Performance benchmarks



```bash

touch backend/risk/ex
touch backend/risk/audit_pipeline.py

Start with `backen
### Step 3: Set Up Telegra
2. Get bot token
4. Add to `.env`
#


Update orchestrator to call risk
---
## Timeline Estimat
- **Week 1**: Risk management module (4-5 files)
- **Week 3**: E




- **Option A**: Build
- **Recommendation**: Option B - Notifications are sufficient f
### 2. Telegram vs Other Channels?


- **Option A**: In-memory (simp

---
**P

























































































































































































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
