"""
FastAPI server for SniperSight trading bot.

Provides REST API endpoints for the frontend UI.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import logging

from backend.risk.position_sizer import PositionSizer
from backend.risk.risk_manager import RiskManager
from backend.bot.executor.paper_executor import PaperExecutor, OrderType, OrderSide
from backend.data.adapters.phemex import PhemexAdapter
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import EventType
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, list_modes

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SniperSight API",
    description="Crypto trading scanner and bot API",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class Exchange(str, Enum):
    """Supported exchanges."""
    PHEMEX = "phemex"
    BINANCE = "binance"
    BYBIT = "bybit"


class Timeframe(str, Enum):
    """Supported timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class ScannerConfig(BaseModel):
    """Scanner configuration."""
    exchange: Exchange
    symbols: List[str]
    timeframes: List[Timeframe]
    min_score: float = Field(ge=0, le=100)
    indicators: Dict[str, bool]


class BotConfig(BaseModel):
    """Bot trading configuration."""
    exchange: Exchange
    leverage: int = Field(ge=1, le=100)
    risk_per_trade: float = Field(gt=0, le=100)
    max_positions: int = Field(ge=1, le=10)
    stop_loss_pct: float = Field(gt=0, le=100)
    take_profit_pct: float = Field(gt=0, le=1000)


class Signal(BaseModel):
    """Trading signal."""
    symbol: str
    direction: str
    score: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timeframe: str
    timestamp: datetime
    analysis: Dict[str, Any]


class Position(BaseModel):
    """Active position."""
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    opened_at: datetime


class OrderRequest(BaseModel):
    """Order placement request."""
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    leverage: Optional[int] = 1


# Global state (in production, use proper state management/database)
scanner_configs: Dict[str, ScannerConfig] = {}
bot_configs: Dict[str, BotConfig] = {}
active_scanners: Dict[str, bool] = {}
active_bots: Dict[str, bool] = {}

# Initialize trading components
position_sizer = PositionSizer(account_balance=10000, max_risk_pct=2.0)
risk_manager = RiskManager(account_balance=10000, max_open_positions=5)
paper_executor = PaperExecutor(initial_balance=10000, fee_rate=0.001)
exchange_adapter = PhemexAdapter(testnet=False)

# Initialize orchestrator with default config
default_config = ScanConfig(
    profile="balanced",
    timeframes=["1h", "4h", "1d"],
    min_confluence_score=70.0,
    max_risk_pct=2.0
)
orchestrator = Orchestrator(
    config=default_config,
    exchange_adapter=exchange_adapter,
    risk_manager=risk_manager,
    position_sizer=position_sizer
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "version": "1.0.0",
        "message": "SniperSight API is running"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "scanner": "ready",
            "bot": "ready",
            "risk_manager": "ready",
            "executor": "ready"
        }
    }


# Scanner endpoints
@app.post("/api/scanner/config")
async def create_scanner_config(config: ScannerConfig):
    """Create or update scanner configuration."""
    config_id = f"scanner_{len(scanner_configs) + 1}"
    scanner_configs[config_id] = config
    return {"config_id": config_id, "status": "created"}


@app.get("/api/scanner/config/{config_id}")
async def get_scanner_config(config_id: str):
    """Get scanner configuration."""
    if config_id not in scanner_configs:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return scanner_configs[config_id]


@app.post("/api/scanner/{config_id}/start")
async def start_scanner(config_id: str):
    """Start scanner."""
    if config_id not in scanner_configs:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    active_scanners[config_id] = True
    return {"status": "started", "config_id": config_id}


@app.post("/api/scanner/{config_id}/stop")
async def stop_scanner(config_id: str):
    """Stop scanner."""
    if config_id not in active_scanners:
        raise HTTPException(status_code=404, detail="Scanner not found")
    
    active_scanners[config_id] = False
    return {"status": "stopped", "config_id": config_id}


def _generate_demo_signals(symbols: List[str], min_score: float) -> List:
    """
    Generate demo trading signals for UI testing when live data is unavailable.
    Used as fallback when exchange is geo-restricted or offline.
    """
    from backend.shared.models.planner import TradePlan, EntryZone, StopLoss, TakeProfit
    
    demo_plans = []
    base_prices = {
        'BTC/USDT': 43500.0,
        'ETH/USDT': 2280.0,
        'BNB/USDT': 315.0,
        'SOL/USDT': 98.5,
        'XRP/USDT': 0.62,
        'ADA/USDT': 0.58,
        'AVAX/USDT': 38.2,
        'MATIC/USDT': 0.89,
        'DOT/USDT': 7.45,
        'LINK/USDT': 15.2,
    }
    
    for i, symbol in enumerate(symbols[:5]):  # Generate 5 demo signals
        base_price = base_prices.get(symbol, 100.0)
        direction = "LONG" if i % 2 == 0 else "SHORT"
        score = min_score + (i * 5) % 25  # Vary scores above min_score
        
        if direction == "LONG":
            near_entry = base_price * 0.995
            far_entry = base_price * 0.99
            stop = base_price * 0.97
            tp1 = base_price * 1.02
            tp2 = base_price * 1.04
        else:
            near_entry = base_price * 1.005
            far_entry = base_price * 1.01
            stop = base_price * 1.03
            tp1 = base_price * 0.98
            tp2 = base_price * 0.96
        
        plan = TradePlan(
            symbol=symbol,
            direction=direction,
            setup_type="demo_smc_confluence",
            confidence_score=score,
            entry_zone=EntryZone(near_entry=near_entry, far_entry=far_entry),
            stop_loss=StopLoss(level=stop, rationale="Demo stop"),
            take_profits=[
                TakeProfit(level=tp1, percentage=50.0, rationale="Demo TP1"),
                TakeProfit(level=tp2, percentage=50.0, rationale="Demo TP2")
            ],
            risk_reward_ratio=2.5,
            primary_timeframe="4h",
            rationale=f"DEMO: {symbol} shows potential {direction} setup with SMC confluence. Exchange data unavailable.",
            smc_context={"demo": True, "order_blocks": 2, "fvgs": 1}
        )
        demo_plans.append(plan)
    
    return demo_plans


@app.get("/api/scanner/modes")
async def get_scanner_modes():
    """List available scanner modes and their characteristics."""
    return {"modes": list_modes(), "total": len(list_modes())}


@app.get("/api/scanner/signals")
async def get_signals(
    limit: int = Query(default=10, ge=1, le=100),
    min_score: float = Query(default=0, ge=0, le=100),  # 0 allows mode baseline logic
    sniper_mode: str = Query(default="recon")
):
    """Generate trading signals applying selected sniper mode configuration.

    Mode logic:
    - Resolve mode (case-insensitive) via scanner_modes mapping.
    - Apply its timeframes & baseline min_confluence_score.
    - If caller supplies min_score > 0 it overrides upward; else baseline used.
    - Profile updated to mode.profile for downstream heuristics.
    Falls back to demo signals if exchange data unavailable.
    """
    try:
        # Resolve requested mode (fallback handled by exception)
        try:
            mode = get_mode(sniper_mode)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Determine effective threshold
        effective_min = max(min_score, mode.min_confluence_score) if min_score > 0 else mode.min_confluence_score

        # Update orchestrator config in-place
        orchestrator.config.timeframes = mode.timeframes
        orchestrator.config.min_confluence_score = effective_min
        orchestrator.config.profile = mode.profile

        # Acquire symbols (fallback list on failure)
        try:
            symbols = exchange_adapter.get_top_symbols(n=min(limit * 2, 20), quote_currency='USDT')
        except Exception as exchange_error:
            logger.warning(f"Exchange unavailable (geo-restriction or network issue): {exchange_error}")
            symbols = []

        if not symbols:
            symbols = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                'ADA/USDT', 'AVAX/USDT', 'MATIC/USDT', 'DOT/USDT', 'LINK/USDT'
            ]

        # Run scan pipeline
        trade_plans = orchestrator.scan(symbols[:limit])

        # Transform TradePlans for response
        signals = []
        for plan in trade_plans:
            signal = {
                "symbol": plan.symbol.replace('/', ''),
                "direction": plan.direction,
                "score": plan.confidence_score,
                "entry_near": plan.entry_zone.near_entry,
                "entry_far": plan.entry_zone.far_entry,
                "stop_loss": plan.stop_loss.level,
                "targets": [
                    {"level": tp.level, "percentage": tp.percentage}
                    for tp in plan.targets
                ],
                # Provide highest frequency timeframe (last element) as representative
                "primary_timeframe": mode.timeframes[-1] if mode.timeframes else "",
                "current_price": plan.entry_zone.near_entry,
                "analysis": {
                    "order_blocks": plan.metadata.get('order_blocks', 0),
                    "fvgs": plan.metadata.get('fvgs', 0),
                    "structural_breaks": plan.metadata.get('structural_breaks', 0),
                    "liquidity_sweeps": plan.metadata.get('liquidity_sweeps', 0),
                    "trend": plan.direction.lower(),
                    "risk_reward": plan.risk_reward
                },
                "rationale": plan.rationale,
                "setup_type": plan.setup_type
            }
            signals.append(signal)

        return {
            "signals": signals,
            "total": len(signals),
            "scanned": len(symbols),
            "mode": mode.name,
            "applied_timeframes": mode.timeframes,
            "effective_min_score": effective_min,
            "baseline_min_score": mode.min_confluence_score,
            "profile": mode.profile
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating signals: {e}")
        from backend.bot.telemetry.events import create_error_event
        telemetry = get_telemetry_logger()
        telemetry.log_event(create_error_event(
            error_message=str(e),
            error_type=type(e).__name__,
            run_id=None
        ))
        raise HTTPException(status_code=500, detail=str(e))


# Bot endpoints
@app.post("/api/bot/config")
async def create_bot_config(config: BotConfig):
    """Create or update bot configuration."""
    config_id = f"bot_{len(bot_configs) + 1}"
    bot_configs[config_id] = config
    
    # Update risk manager with new config
    risk_manager.max_open_positions = config.max_positions
    
    return {"config_id": config_id, "status": "created"}


@app.get("/api/bot/config/{config_id}")
async def get_bot_config(config_id: str):
    """Get bot configuration."""
    if config_id not in bot_configs:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return bot_configs[config_id]


@app.post("/api/bot/{config_id}/start")
async def start_bot(config_id: str):
    """Start trading bot."""
    if config_id not in bot_configs:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    active_bots[config_id] = True
    return {"status": "started", "config_id": config_id}


@app.post("/api/bot/{config_id}/stop")
async def stop_bot(config_id: str):
    """Stop trading bot."""
    if config_id not in active_bots:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    active_bots[config_id] = False
    return {"status": "stopped", "config_id": config_id}


@app.get("/api/bot/status")
async def get_bot_status():
    """Get bot status and statistics."""
    stats = paper_executor.get_statistics()
    
    return {
        "active": len([v for v in active_bots.values() if v]) > 0,
        "balance": paper_executor.get_balance(),
        "equity": paper_executor.get_equity({}),
        "positions": stats['active_positions'],
        "total_trades": stats['total_fills'],
        "win_rate": 0.0,  # TODO: Calculate from trade history
        "pnl": paper_executor.get_pnl({}),
        "statistics": stats
    }


@app.get("/api/bot/positions")
async def get_positions():
    """Get active positions."""
    positions = []
    for symbol, quantity in paper_executor.positions.items():
        if quantity != 0:
            positions.append({
                "symbol": symbol,
                "direction": "LONG" if quantity > 0 else "SHORT",
                "quantity": abs(quantity),
                "entry_price": 0,  # TODO: Track from fills
                "current_price": 0,  # TODO: Get from market data
                "pnl": 0,
                "pnl_pct": 0,
                "opened_at": datetime.now(timezone.utc).isoformat()
            })
    
    return {"positions": positions, "total": len(positions)}


@app.post("/api/bot/order")
async def place_order(order: OrderRequest):
    """Place a trading order."""
    try:
        # Validate with risk manager
        risk_check = risk_manager.validate_new_trade(
            symbol=order.symbol,
            direction=order.side,
            position_value=order.quantity * (order.price or 0),
            risk_amount=order.quantity * (order.price or 0) * 0.02  # 2% risk
        )
        
        if not risk_check.passed:
            raise HTTPException(status_code=400, detail=risk_check.reason)
        
        # Place order with paper executor
        placed_order = paper_executor.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price
        )
        
        # For market orders, execute immediately
        if order.order_type.upper() == "MARKET" and order.price:
            fill = paper_executor.execute_market_order(
                placed_order.order_id,
                order.price
            )
            
            if fill:
                return {
                    "order_id": placed_order.order_id,
                    "status": "filled",
                    "filled_quantity": fill.quantity,
                    "average_price": fill.price
                }
        
        return {
            "order_id": placed_order.order_id,
            "status": placed_order.status.value,
            "message": "Order placed successfully"
        }
        
    except Exception as e:
        logger.error(f"Order placement failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bot/trades")
async def get_trade_history(
    limit: int = Query(default=50, ge=1, le=100)
):
    """Get trade history."""
    trades = paper_executor.get_trade_history()
    
    trade_list = [
        {
            "symbol": trade.symbol,
            "direction": trade.direction,
            "pnl": trade.pnl,
            "closed_at": trade.closed_at.isoformat()
        }
        for trade in trades[-limit:]
    ]
    
    return {"trades": trade_list, "total": len(trade_list)}


@app.get("/api/risk/summary")
async def get_risk_summary():
    """Get risk management summary."""
    summary = risk_manager.get_risk_summary()
    return summary


# Market data endpoints (mock for now)
@app.get("/api/market/price/{symbol}")
async def get_price(symbol: str):
    """Get current price for symbol."""
    # Mock data - will be replaced with exchange integration
    mock_prices = {
        "BTC/USDT": 50000,
        "ETH/USDT": 3000,
        "SOL/USDT": 100
    }
    
    price = mock_prices.get(symbol, 0)
    return {
        "symbol": symbol,
        "price": price,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/market/candles/{symbol}")
async def get_candles(
    symbol: str,
    timeframe: Timeframe = Query(default=Timeframe.H1),
    limit: int = Query(default=100, ge=1, le=1000)
):
    """Get candlestick data."""
    # Mock data - will be replaced with exchange integration
    return {
        "symbol": symbol,
        "timeframe": timeframe.value,
        "candles": [],
        "message": "Mock data - exchange integration pending"
    }


# ============================================================================
# Telemetry Endpoints
# ============================================================================

@app.get("/api/telemetry/recent")
async def get_recent_telemetry(
    limit: int = Query(default=100, ge=1, le=1000),
    since_id: Optional[int] = Query(default=None)
):
    """
    Get recent telemetry events for real-time updates.
    
    Args:
        limit: Maximum events to return
        since_id: Only return events with ID > this value (for polling)
        
    Returns:
        List of event dictionaries with 'id' field
    """
    try:
        telemetry = get_telemetry_logger()
        events = telemetry.get_recent_with_id(limit=limit, since_id=since_id)
        
        return {
            "events": events,
            "count": len(events)
        }
    except Exception as e:
        logger.error(f"Error fetching recent telemetry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telemetry/events")
async def get_telemetry_events(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    event_type: Optional[str] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
    run_id: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None)
):
    """
    Query telemetry events with filters.
    
    Args:
        limit: Maximum events to return
        offset: Pagination offset
        event_type: Filter by event type (e.g., "scan_completed", "signal_generated")
        symbol: Filter by symbol
        run_id: Filter by scan run ID
        start_time: Filter events after this time (ISO 8601)
        end_time: Filter events before this time (ISO 8601)
        
    Returns:
        Filtered list of events with pagination info
    """
    try:
        telemetry = get_telemetry_logger()
        
        # Convert event_type string to enum if provided
        event_type_enum = None
        if event_type:
            try:
                event_type_enum = EventType(event_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid event_type: {event_type}")
        
        events = telemetry.get_events(
            limit=limit,
            offset=offset,
            event_type=event_type_enum,
            symbol=symbol,
            run_id=run_id,
            start_time=start_time,
            end_time=end_time
        )
        
        total_count = telemetry.get_event_count(
            event_type=event_type_enum,
            symbol=symbol,
            start_time=start_time,
            end_time=end_time
        )
        
        return {
            "events": events,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(events)) < total_count
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying telemetry events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telemetry/analytics")
async def get_telemetry_analytics(
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None)
):
    """
    Get aggregated telemetry analytics/metrics.
    
    Args:
        start_time: Calculate metrics from this time (ISO 8601)
        end_time: Calculate metrics until this time (ISO 8601)
        
    Returns:
        Analytics dashboard metrics
    """
    try:
        telemetry = get_telemetry_logger()
        
        # Get counts for each event type
        total_scans = telemetry.get_event_count(
            event_type=EventType.SCAN_COMPLETED,
            start_time=start_time,
            end_time=end_time
        )
        
        total_signals = telemetry.get_event_count(
            event_type=EventType.SIGNAL_GENERATED,
            start_time=start_time,
            end_time=end_time
        )
        
        total_rejected = telemetry.get_event_count(
            event_type=EventType.SIGNAL_REJECTED,
            start_time=start_time,
            end_time=end_time
        )
        
        total_errors = telemetry.get_event_count(
            event_type=EventType.ERROR_OCCURRED,
            start_time=start_time,
            end_time=end_time
        )
        
        # Get rejection breakdown
        rejected_events = telemetry.get_events(
            limit=1000,
            event_type=EventType.SIGNAL_REJECTED,
            start_time=start_time,
            end_time=end_time
        )
        
        rejection_reasons = {}
        for event in rejected_events:
            reason = event.get('data', {}).get('reason', 'Unknown')
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        
        return {
            "metrics": {
                "total_scans": total_scans,
                "total_signals_generated": total_signals,
                "total_signals_rejected": total_rejected,
                "total_errors": total_errors,
                "signal_success_rate": round((total_signals / max(total_signals + total_rejected, 1)) * 100, 2)
            },
            "rejection_breakdown": rejection_reasons,
            "time_range": {
                "start": start_time,
                "end": end_time
            }
        }
    except Exception as e:
        logger.error(f"Error calculating analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
