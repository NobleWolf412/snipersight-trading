# Phase 4 Step-by-Step Implementation Guide

This guide provides copy-paste-ready code and exact prompts for implementing Phase 4 using GitHub Copilot or manual coding.

---

## Part 1: Risk Management Module

### Step 1.1: Position Sizing

**File:** `backend/risk/position_sizing.py`

**Copilot Prompt:**
```
Create backend/risk/position_sizing.py following PROJECT_STRUCTURE.md:

Functions needed:
1. calculate_position_size(account_balance: float, risk_pct: float, entry: float, stop: float, leverage: float = 1.0) -> float
   - Formula: (account_balance * risk_pct) / abs(entry - stop) * leverage
   - Validate: account_balance > 0, 0 < risk_pct <=1, entry != stop, leverage >= 1
   - Raise ValueError for invalid inputs

2. adjust_for_volatility(base_size: float, atr_ratio: float, reduction_factor: float = 0.5) -> float
   - If ATR ratio > 1.5 (high volatility), reduce position size
   - Formula: base_size * (1 - (atr_ratio - 1.0) * reduction_factor)
   - Minimum 50% of base size

3. validate_position_constraints(position_size: float, min_size: float, max_size: float) -> float
   - Clamp position size to min/max bounds
   - Return clamped value

Include:
- Type hints throughout
- Docstrings with examples
- Error handling with descriptive messages
- Unit test cases in docstrings
```

**Expected Output Structure:**
```python
from typing import Optional

def calculate_position_size(
    account_balance: float,
    risk_pct: float,
    entry: float,
    stop: float,
    leverage: float = 1.0
) -> float:
    """
    Calculate position size based on fixed risk percentage.
    
    Args:
        account_balance: Total account value in quote currency
        risk_pct: Risk as decimal (0.01 = 1%)
        entry: Entry price
        stop: Stop loss price
        leverage: Trading leverage multiplier
    
    Returns:
        Position size in base currency
    
    Raises:
        ValueError: If parameters are invalid
    
    Example:
        >>> calculate_position_size(10000, 0.01, 100, 95, 1.0)
        20.0  # Risk $100 (1%), $5 distance, no leverage = 20 units
    """
    if account_balance <= 0:
        raise ValueError(f"Account balance must be positive, got {account_balance}")
    if not 0 < risk_pct <= 1:
        raise ValueError(f"Risk % must be between 0 and 1, got {risk_pct}")
    if entry == stop:
        raise ValueError("Entry and stop cannot be equal")
    if leverage < 1:
        raise ValueError(f"Leverage must be >= 1, got {leverage}")
    
    risk_amount = account_balance * risk_pct
    price_distance = abs(entry - stop)
    position_size = (risk_amount / price_distance) * leverage
    
    return position_size


def adjust_for_volatility(
    base_size: float,
    atr_ratio: float,
    reduction_factor: float = 0.5
) -> float:
    """
    Reduce position size in high volatility environments.
    
    Args:
        base_size: Original calculated position size
        atr_ratio: Current ATR / Average ATR (>1 = higher volatility)
        reduction_factor: How aggressively to reduce (0.5 = moderate)
    
    Returns:
        Adjusted position size
    
    Example:
        >>> adjust_for_volatility(100, 2.0, 0.5)
        50.0  # 2x volatility with 0.5 factor = 50% reduction
    """
    if atr_ratio <= 1.0:
        return base_size
    
    volatility_penalty = (atr_ratio - 1.0) * reduction_factor
    adjusted_size = base_size * (1 - volatility_penalty)
    
    # Never reduce below 50% of base size
    min_size = base_size * 0.5
    return max(adjusted_size, min_size)


def validate_position_constraints(
    position_size: float,
    min_size: float,
    max_size: float
) -> float:
    """
    Clamp position size to exchange/strategy limits.
    
    Args:
        position_size: Calculated position size
        min_size: Minimum order size (exchange limit)
        max_size: Maximum order size (risk limit)
    
    Returns:
        Clamped position size
    
    Example:
        >>> validate_position_constraints(0.005, 0.01, 1.0)
        0.01  # Below minimum, clamped up
    """
    return max(min_size, min(position_size, max_size))
```

---

### Step 1.2: Exposure Management

**File:** `backend/risk/exposure_limits.py`

**Copilot Prompt:**
```
Create backend/risk/exposure_limits.py with ExposureManager class following ARCHITECTURE.md risk management principles:

Class ExposureManager:
  Attributes:
    - max_per_asset_pct: float (e.g., 0.05 = 5% max per symbol)
    - max_total_exposure_pct: float (e.g., 0.10 = 10% max total)
    - current_positions: Dict[str, float] (symbol -> position value)
  
  Methods:
    1. check_per_asset_limit(symbol: str, proposed_value: float, account_balance: float) -> bool
       - Return True if (current[symbol] + proposed_value) / account_balance <= max_per_asset_pct
    
    2. check_total_exposure(proposed_value: float, account_balance: float) -> bool
       - Return True if (sum(current_positions) + proposed_value) / account_balance <= max_total_exposure_pct
    
    3. get_available_capacity(symbol: str, account_balance: float) -> float
       - Return remaining $ capacity for symbol before hitting per-asset limit
    
    4. add_position(symbol: str, value: float) -> None
       - Add to current_positions tracking
    
    5. remove_position(symbol: str) -> None
       - Remove from tracking

Include:
- Type hints and docstrings
- Thread-safe operations (use threading.Lock if needed)
- Logging when limits are hit
```

**Manual Implementation:**
```python
from typing import Dict, Optional
import logging
from threading import Lock

logger = logging.getLogger(__name__)


class ExposureManager:
    """
    Manages portfolio exposure limits to prevent over-allocation.
    
    Enforces:
    - Per-asset limit: No more than X% in any single symbol
    - Total exposure limit: Total portfolio risk ≤ Y%
    """
    
    def __init__(
        self,
        max_per_asset_pct: float = 0.05,
        max_total_exposure_pct: float = 0.10
    ):
        """
        Initialize exposure manager.
        
        Args:
            max_per_asset_pct: Maximum % of portfolio per symbol (default 5%)
            max_total_exposure_pct: Maximum total exposure % (default 10%)
        """
        self.max_per_asset_pct = max_per_asset_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.current_positions: Dict[str, float] = {}
        self._lock = Lock()
    
    def check_per_asset_limit(
        self,
        symbol: str,
        proposed_value: float,
        account_balance: float
    ) -> bool:
        """
        Check if proposed position would exceed per-asset limit.
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            proposed_value: Position value in quote currency
            account_balance: Total account balance
        
        Returns:
            True if within limits, False if would exceed
        """
        with self._lock:
            current_value = self.current_positions.get(symbol, 0.0)
            total_value = current_value + proposed_value
            exposure_pct = total_value / account_balance
            
            if exposure_pct > self.max_per_asset_pct:
                logger.warning(
                    f"Per-asset limit exceeded for {symbol}: "
                    f"{exposure_pct:.2%} > {self.max_per_asset_pct:.2%}"
                )
                return False
            
            return True
    
    def check_total_exposure(
        self,
        proposed_value: float,
        account_balance: float
    ) -> bool:
        """
        Check if proposed position would exceed total exposure limit.
        
        Args:
            proposed_value: Position value to add
            account_balance: Total account balance
        
        Returns:
            True if within limits, False if would exceed
        """
        with self._lock:
            current_total = sum(self.current_positions.values())
            new_total = current_total + proposed_value
            exposure_pct = new_total / account_balance
            
            if exposure_pct > self.max_total_exposure_pct:
                logger.warning(
                    f"Total exposure limit exceeded: "
                    f"{exposure_pct:.2%} > {self.max_total_exposure_pct:.2%}"
                )
                return False
            
            return True
    
    def get_available_capacity(
        self,
        symbol: str,
        account_balance: float
    ) -> float:
        """
        Get remaining position capacity for symbol.
        
        Args:
            symbol: Trading symbol
            account_balance: Total account balance
        
        Returns:
            Available $ capacity before hitting per-asset limit
        """
        with self._lock:
            current_value = self.current_positions.get(symbol, 0.0)
            max_value = account_balance * self.max_per_asset_pct
            return max(0, max_value - current_value)
    
    def add_position(self, symbol: str, value: float) -> None:
        """Add position to tracking."""
        with self._lock:
            current = self.current_positions.get(symbol, 0.0)
            self.current_positions[symbol] = current + value
            logger.info(f"Added position: {symbol} = ${value:.2f}")
    
    def remove_position(self, symbol: str) -> None:
        """Remove position from tracking."""
        with self._lock:
            if symbol in self.current_positions:
                del self.current_positions[symbol]
                logger.info(f"Removed position: {symbol}")
    
    def get_current_exposure(self, account_balance: float) -> Dict[str, any]:
        """Get current exposure summary."""
        with self._lock:
            total_value = sum(self.current_positions.values())
            return {
                "positions": dict(self.current_positions),
                "total_value": total_value,
                "total_exposure_pct": total_value / account_balance if account_balance > 0 else 0,
                "max_total_exposure_pct": self.max_total_exposure_pct,
                "remaining_capacity": account_balance * self.max_total_exposure_pct - total_value
            }
```

---

### Step 1.3: Compliance Checks

**File:** `backend/risk/compliance_checks.py`

**Copilot Prompt:**
```
Create backend/risk/compliance_checks.py following ARCHITECTURE.md "Zero Silent Failures" principle:

Functions:
1. validate_risk_parameters(plan: TradePlan, account_balance: float, max_risk_pct: float) -> Tuple[bool, str]
   - Check if plan.risk_pct <= max_risk_pct
   - Check if plan has all required fields (entry, stop, targets not None)
   - Return (is_valid, reason_if_invalid)

2. check_for_conflicts(symbol: str, direction: str, existing_positions: List[dict]) -> Tuple[bool, str]
   - Check if opposite direction already open
   - Return (has_conflict, description)

3. enforce_max_leverage(proposed_leverage: float, max_allowed: float) -> bool
   - Return True if proposed <= max_allowed

4. validate_trade_plan_completeness(plan: TradePlan) -> List[str]
   - Return list of missing/null required fields
   - Required: symbol, direction, entry_near, entry_far, stop_loss, targets (min 1)

Import from shared.models.trading import TradePlan
Use type hints and descriptive error messages
```

---

### Step 1.4: Audit Logging

**File:** `backend/risk/audit_pipeline.py`

**Copilot Prompt:**
```
Create backend/risk/audit_pipeline.py for compliance audit trail:

Class AuditLogger:
  Attributes:
    - log_file: str (path to audit log JSON file)
    - events: List[AuditEvent]
  
  Methods:
    1. log_decision(symbol: str, decision: str, reason: str, context: dict) -> None
       - Append event to audit log
       - decision: "APPROVED" | "REJECTED"
    
    2. log_quality_gate(gate_name: str, passed: bool, details: dict) -> None
       - Log quality gate results
    
    3. generate_audit_report(start_time: datetime, end_time: datetime) -> dict
       - Return summary of all decisions in time range
       - Include: total signals, approved, rejected, rejection reasons breakdown
    
    4. export_to_json(filepath: str) -> None
       - Export all events to JSON file

Use dataclass for AuditEvent with timestamp, event_type, details
Make thread-safe
Include structured logging with loguru
```

---

## Part 2: Telegram Notifications

### Step 2.1: Telegram Client

**File:** `backend/bot/notifications/telegram.py`

**Setup First:**
```bash
pip install python-telegram-bot
```

**Copilot Prompt:**
```
Create backend/bot/notifications/telegram.py using python-telegram-bot library:

Class TelegramNotifier:
  Attributes:
    - bot_token: str
    - chat_id: str
    - bot: telegram.Bot
  
  Async Methods:
    1. send_message(message: str, parse_mode: str = "Markdown") -> bool
       - Send to self.chat_id
       - Handle errors gracefully (return False on failure)
       - Respect Telegram 4096 char limit (truncate if needed)
       - Add retry logic: 3 attempts with exponential backoff
    
    2. send_batch_summary(plans: List[TradePlan], limit: int = 5) -> bool
       - Send top N signals ranked by score
       - Use batch_summary_template.md format
    
    3. send_alert(alert_type: str, message: str) -> bool
       - Send system alert (errors, warnings)
       - Use distinct formatting (⚠️ prefix)

Include:
- Error handling
- Rate limit respect
- Logging with loguru
- Type hints and docstrings
```

**Manual Implementation:**
```python
import asyncio
import logging
from typing import List, Optional
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Telegram bot integration for trade signal notifications.
    """
    
    MAX_MESSAGE_LENGTH = 4096
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Target chat/channel ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
    
    async def send_message(
        self,
        message: str,
        parse_mode: str = "Markdown"
    ) -> bool:
        """
        Send message to Telegram chat with retry logic.
        
        Args:
            message: Message text (supports Markdown)
            parse_mode: Parse mode ("Markdown" or "HTML")
        
        Returns:
            True if sent successfully, False otherwise
        """
        if len(message) > self.MAX_MESSAGE_LENGTH:
            logger.warning(
                f"Message too long ({len(message)} chars), truncating to {self.MAX_MESSAGE_LENGTH}"
            )
            message = message[:self.MAX_MESSAGE_LENGTH - 100] + "\n\n...[truncated]"
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
                logger.info(f"Message sent successfully to {self.chat_id}")
                return True
            
            except TelegramError as e:
                logger.error(f"Telegram error (attempt {attempt}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY * attempt)
                else:
                    return False
        
        return False
    
    async def send_batch_summary(
        self,
        plans: List[any],
        limit: int = 5
    ) -> bool:
        """
        Send summary of top N trade signals.
        
        Args:
            plans: List of TradePlan objects
            limit: Maximum signals to include
        
        Returns:
            True if sent successfully
        """
        if not plans:
            logger.warning("No plans to send in batch summary")
            return False
        
        # Sort by score (assuming plans have .confluence_score attr)
        sorted_plans = sorted(
            plans,
            key=lambda p: getattr(p, 'confluence_score', 0),
            reverse=True
        )[:limit]
        
        summary = self._format_batch_summary(sorted_plans)
        return await self.send_message(summary)
    
    async def send_alert(self, alert_type: str, message: str) -> bool:
        """
        Send system alert.
        
        Args:
            alert_type: Alert category (ERROR, WARNING, INFO)
            message: Alert message
        
        Returns:
            True if sent successfully
        """
        emoji_map = {
            "ERROR": "🚨",
            "WARNING": "⚠️",
            "INFO": "ℹ️"
        }
        emoji = emoji_map.get(alert_type.upper(), "📢")
        
        alert_text = f"{emoji} **{alert_type.upper()}**\n\n{message}"
        return await self.send_message(alert_text)
    
    def _format_batch_summary(self, plans: List[any]) -> str:
        """Format batch summary message."""
        lines = ["📊 **Scan Results Summary**\n"]
        lines.append(f"Total Signals: {len(plans)}\n")
        
        for i, plan in enumerate(plans, 1):
            direction_emoji = "🟢" if plan.direction == "LONG" else "🔴"
            lines.append(
                f"{i}. {direction_emoji} **{plan.symbol}** | "
                f"Score: {getattr(plan, 'confluence_score', 0):.1f}/100"
            )
        
        lines.append("\n💡 View individual signals for full details")
        return "\n".join(lines)
```

---

### Step 2.2: Message Formatters

**File:** `backend/bot/notifications/formatters.py`

**Copilot Prompt:**
```
Create backend/bot/notifications/formatters.py for formatting trade signals as Markdown:

Functions:
1. format_markdown(plan: TradePlan) -> str
   - Format complete signal with all details
   - Include: direction emoji, symbol, score, entries, stops, targets, R:R, rationale
   - Use Markdown bold, bullets, spacing for readability
   - Max ~1500 chars to fit Telegram limits with room for other info

2. format_json(plan: TradePlan) -> dict
   - Export machine-readable JSON
   - Include all plan fields

3. format_confluence_breakdown(breakdown: ConfluenceBreakdown) -> str
   - List each factor with checkmark/X
   - Show weights and scores

4. format_rationale(plan: TradePlan) -> str
   - Extract and format rationale section
   - 2-3 sentence summary

Import from shared.models.trading, shared.models.scoring
Use emoji for visual clarity
```

**Manual Implementation:**
```python
from typing import Dict, Any


def format_markdown(plan: any) -> str:
    """
    Format TradePlan as Telegram Markdown message.
    
    Args:
        plan: TradePlan object
    
    Returns:
        Formatted Markdown string
    """
    direction_emoji = "🟢" if plan.direction == "LONG" else "🔴"
    style = getattr(plan, 'style', 'Unknown')
    score = getattr(plan, 'confluence_score', 0)
    
    lines = [
        f"{direction_emoji} **{plan.direction} {plan.symbol}** | Score: {score:.1f}/100 | {style}",
        "",
        "**Entry Zones:**",
        f"• Aggressive: ${plan.entry_near:,.2f}",
        f"• Conservative: ${plan.entry_far:,.2f}",
        "",
        "**Exits:**",
        f"• Stop Loss: ${plan.stop_loss.price:,.2f} ({plan.stop_loss.distance_pct:+.2f}%)",
    ]
    
    # Targets
    for i, target in enumerate(plan.targets, 1):
        lines.append(f"• Target {i}: ${target.price:,.2f} (+{target.rr_multiple:.1f}R)")
    
    # Risk metrics
    lines.extend([
        "",
        f"**Risk:** {getattr(plan, 'risk_pct', 0):.1f}% | "
        f"R:R: 1:{getattr(plan, 'rr_ratio', 0):.1f} | "
        f"Size: {getattr(plan, 'position_size', 0):.4f}",
        ""
    ])
    
    # Confluence (if available)
    if hasattr(plan, 'confluence_factors'):
        lines.append("**Confluence:**")
        for factor in plan.confluence_factors[:5]:  # Top 5
            lines.append(f"✓ {factor}")
        lines.append("")
    
    # Rationale
    if hasattr(plan, 'rationale') and plan.rationale:
        lines.append("**Rationale:**")
        lines.append(plan.rationale[:300])  # Truncate if too long
    
    return "\n".join(lines)


def format_json(plan: any) -> Dict[str, Any]:
    """
    Export TradePlan as JSON dictionary.
    
    Args:
        plan: TradePlan object
    
    Returns:
        JSON-serializable dict
    """
    return {
        "symbol": plan.symbol,
        "direction": plan.direction,
        "entry_near": plan.entry_near,
        "entry_far": plan.entry_far,
        "stop_loss": {
            "price": plan.stop_loss.price,
            "distance_pct": plan.stop_loss.distance_pct
        },
        "targets": [
            {
                "price": t.price,
                "rr_multiple": t.rr_multiple
            }
            for t in plan.targets
        ],
        "confluence_score": getattr(plan, 'confluence_score', None),
        "rationale": getattr(plan, 'rationale', None)
    }


def format_confluence_breakdown(breakdown: any) -> str:
    """
    Format confluence factor breakdown.
    
    Args:
        breakdown: ConfluenceBreakdown object
    
    Returns:
        Formatted string with checkmarks
    """
    lines = ["**Confluence Breakdown:**"]
    
    factors = getattr(breakdown, 'factors', [])
    for factor in factors:
        check = "✓" if factor.score > 0.5 else "✗"
        lines.append(f"{check} {factor.name}: {factor.score:.1f} (weight: {factor.weight:.2f})")
    
    return "\n".join(lines)
```

---

## Part 3: Testing

### Step 3.1: Unit Tests

**File:** `backend/tests/unit/risk/test_position_sizing.py`

```python
import pytest
from backend.risk.position_sizing import (
    calculate_position_size,
    adjust_for_volatility,
    validate_position_constraints
)


def test_calculate_position_size_basic():
    # 1% risk, $100 entry, $95 stop, $10k account
    # Risk = $100, Distance = $5, Size = $100/$5 = 20 units
    size = calculate_position_size(10000, 0.01, 100, 95, 1.0)
    assert size == 20.0


def test_calculate_position_size_with_leverage():
    size = calculate_position_size(10000, 0.01, 100, 95, 2.0)
    assert size == 40.0  # 2x leverage = 2x position


def test_calculate_position_size_invalid_account():
    with pytest.raises(ValueError):
        calculate_position_size(-1000, 0.01, 100, 95)


def test_adjust_for_volatility_high():
    # 2x volatility should reduce position by ~50% with default factor
    adjusted = adjust_for_volatility(100, 2.0, 0.5)
    assert adjusted == 50.0


def test_adjust_for_volatility_normal():
    # Normal volatility (ATR ratio = 1.0) should not adjust
    adjusted = adjust_for_volatility(100, 1.0)
    assert adjusted == 100.0


def test_validate_position_constraints():
    # Below minimum
    assert validate_position_constraints(0.005, 0.01, 1.0) == 0.01
    # Above maximum
    assert validate_position_constraints(2.0, 0.01, 1.0) == 1.0
    # Within range
    assert validate_position_constraints(0.5, 0.01, 1.0) == 0.5
```

Run tests:
```bash
pytest backend/tests/unit/risk/test_position_sizing.py -v
```

---

## Part 4: Integration

### Step 4.1: Wire Risk Module to Orchestrator

**File:** `backend/engine/orchestrator.py` (update)

Add risk validation step:

```python
from backend.risk.position_sizing import calculate_position_size
from backend.risk.exposure_limits import ExposureManager
from backend.risk.compliance_checks import validate_risk_parameters

class Orchestrator:
    def __init__(self, config):
        self.config = config
        self.exposure_manager = ExposureManager(
            max_per_asset_pct=0.05,
            max_total_exposure_pct=0.10
        )
    
    def run_scan(self, symbols: List[str]) -> List[TradePlan]:
        # ... existing code for data, indicators, SMC, confluence, planner ...
        
        # NEW: Risk validation
        approved_plans = []
        for plan in raw_plans:
            # Calculate position size
            position_size = calculate_position_size(
                account_balance=self.config.account_balance,
                risk_pct=self.config.risk_pct,
                entry=plan.entry_near,
                stop=plan.stop_loss.price,
                leverage=1.0
            )
            
            # Check exposure limits
            position_value = position_size * plan.entry_near
            if not self.exposure_manager.check_per_asset_limit(
                plan.symbol, position_value, self.config.account_balance
            ):
                logger.warning(f"Rejected {plan.symbol}: per-asset limit exceeded")
                continue
            
            if not self.exposure_manager.check_total_exposure(
                position_value, self.config.account_balance
            ):
                logger.warning(f"Rejected {plan.symbol}: total exposure limit exceeded")
                continue
            
            # Compliance checks
            is_valid, reason = validate_risk_parameters(
                plan, self.config.account_balance, self.config.max_risk_pct
            )
            if not is_valid:
                logger.warning(f"Rejected {plan.symbol}: {reason}")
                continue
            
            # Add position tracking
            self.exposure_manager.add_position(plan.symbol, position_value)
            plan.position_size = position_size
            approved_plans.append(plan)
        
        return approved_plans
```

---

## Part 5: CLI Integration

**File:** `sniper_sight_cli.py` (update)

Add notification command:

```python
import asyncio
from backend.bot.notifications.telegram import TelegramNotifier
from backend.bot.notifications.formatters import format_markdown

@app.command()
def scan(
    profile: str = "balanced",
    symbols: str = "top20",
    notify: bool = True
):
    """Run scan with risk validation and notifications"""
    
    # Run scan (includes risk validation now)
    orchestrator = Orchestrator(config)
    approved_plans = orchestrator.run_scan(symbols.split(','))
    
    typer.echo(f"✅ {len(approved_plans)} signals approved")
    
    # Send notifications
    if notify and approved_plans:
        asyncio.run(send_telegram_notifications(approved_plans))


async def send_telegram_notifications(plans: List[TradePlan]):
    """Send approved plans to Telegram"""
    notifier = TelegramNotifier(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TELEGRAM_CHAT_ID")
    )
    
    # Send batch summary
    await notifier.send_batch_summary(plans, limit=5)
    
    # Send individual signals (top 3)
    for plan in plans[:3]:
        message = format_markdown(plan)
        await notifier.send_message(message)
        await asyncio.sleep(1)  # Rate limit
```

---

## Summary

**Phase 4 Implementation Complete When:**
- [x] Position sizing calculates correctly
- [x] Exposure limits enforced
- [x] Compliance checks working
- [x] Audit trail captures decisions
- [x] Telegram notifications sending
- [x] Message formatting readable
- [x] Unit tests passing
- [x] Integration with orchestrator working

**Next:** Phase 5 (Orchestration) or Phase 6 (Testing & Verification)

---

**Estimated Time:** 2-3 weeks for complete Phase 4 with testing
