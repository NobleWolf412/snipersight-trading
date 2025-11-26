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
from backend.bot.executor.paper_executor import PaperExecutor
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.adapters.bybit import BybitAdapter
from backend.data.adapters.okx import OKXAdapter
from backend.data.adapters.bitget import BitgetAdapter
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import EventType
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.smc_config import SMCConfig
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

# Exchange adapters factory - Tier 1 exchanges only
EXCHANGE_ADAPTERS = {
    'bybit': lambda: BybitAdapter(testnet=False),      # #1 Best overall (may be geo-blocked)
    'phemex': lambda: PhemexAdapter(testnet=False),     # No geo-blocking, fast
    'okx': lambda: OKXAdapter(testnet=False),           # Institutional-tier
    'bitget': lambda: BitgetAdapter(testnet=False),     # Bot-friendly
}

# Default to Phemex (no geo-blocking)
exchange_adapter = PhemexAdapter(testnet=False)

# Initialize orchestrator with default config
default_config = ScanConfig(
    profile="recon",  # Valid mode from scanner_modes.py
    timeframes=("1h", "4h", "1d"),
    min_confluence_score=70.0,
    max_risk_pct=2.0
)
orchestrator = Orchestrator(
    config=default_config,
    exchange_adapter=exchange_adapter,
    risk_manager=risk_manager,
    position_sizer=position_sizer,
    concurrency_workers=4
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
    from backend.shared.models.planner import TradePlan, EntryZone, StopLoss, Target
    from backend.shared.models.scoring import ConfluenceBreakdown
    
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
        
        # Calculate risk:reward ratio
        risk = abs(near_entry - stop)
        reward = abs((tp1 + tp2) / 2 - near_entry)
        rr_ratio = reward / risk if risk > 0 else 2.5
        
        # Create mock confluence breakdown with proper structure
        from backend.shared.models.scoring import ConfluenceFactor
        confluence = ConfluenceBreakdown(
            total_score=score,
            factors=[
                ConfluenceFactor(name="HTF Trend", score=score * 0.3, weight=0.3, rationale="Demo HTF alignment"),
                ConfluenceFactor(name="SMC Patterns", score=score * 0.4, weight=0.4, rationale="Demo order blocks"),
                ConfluenceFactor(name="Indicators", score=score * 0.3, weight=0.3, rationale="Demo indicators")
            ],
            synergy_bonus=2.0,
            conflict_penalty=0.0,
            regime="trend",
            htf_aligned=True,
            btc_impulse_gate=True
        )
        
        plan = TradePlan(
            symbol=symbol,
            direction=direction,
            setup_type="swing",
            confidence_score=score,
            entry_zone=EntryZone(
                near_entry=near_entry,
                far_entry=far_entry,
                rationale=f"Demo entry zone for {direction} setup"
            ),
            stop_loss=StopLoss(
                level=stop,
                distance_atr=2.0,
                rationale="Demo stop based on structure"
            ),
            targets=[
                Target(level=tp1, percentage=50.0, rationale="Demo TP1 at resistance"),
                Target(level=tp2, percentage=50.0, rationale="Demo TP2 at extension")
            ],
            risk_reward=rr_ratio,
            confluence_breakdown=confluence,
            rationale=f"DEMO: {symbol} shows potential {direction} setup with SMC confluence. Exchange data unavailable.",
            metadata={"demo": True, "primary_timeframe": "4h"}
        )
        demo_plans.append(plan)
    
    return demo_plans


@app.get("/api/scanner/modes")
async def get_scanner_modes():
    """List available scanner modes and their characteristics."""
    return {"modes": list_modes(), "total": len(list_modes())}


class SMCConfigUpdate(BaseModel):
    """Partial update model for SMCConfig values."""
    min_wick_ratio: Optional[float] = None
    min_displacement_atr: Optional[float] = None
    ob_lookback_candles: Optional[int] = None
    ob_volume_threshold: Optional[float] = None
    ob_max_mitigation: Optional[float] = None
    ob_min_freshness: Optional[float] = None
    fvg_min_gap_atr: Optional[float] = None
    fvg_max_overlap: Optional[float] = None
    structure_swing_lookback: Optional[int] = None
    structure_min_break_distance_atr: Optional[float] = None
    sweep_swing_lookback: Optional[int] = None
    sweep_max_sweep_candles: Optional[int] = None
    sweep_min_reversal_atr: Optional[float] = None
    sweep_require_volume_spike: Optional[bool] = None


@app.get("/api/config/smc")
async def get_smc_config():
    """Get current Smart Money Concepts detector configuration."""
    return {"smc_config": orchestrator.smc_config.to_dict()}


@app.put("/api/config/smc")
async def update_smc_config(update: SMCConfigUpdate):
    """Update SMC detector configuration at runtime."""
    current = orchestrator.smc_config.to_dict()
    overrides = {k: v for k, v in update.dict().items() if v is not None}
    if not overrides:
        return {"status": "no_changes", "smc_config": current}
    merged = {**current, **overrides}
    try:
        new_cfg = SMCConfig.from_dict(merged)
        orchestrator.update_smc_config(new_cfg)
        return {"status": "updated", "smc_config": new_cfg.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/scanner/signals")
async def get_signals(
    limit: int = Query(default=10, ge=1, le=100),
    min_score: float = Query(default=0, ge=0, le=100),  # 0 allows mode baseline logic
    sniper_mode: str = Query(default="recon"),
    majors: bool = Query(default=True),
    altcoins: bool = Query(default=True),
    meme_mode: bool = Query(default=False),
    exchange: str = Query(default="phemex"),
    leverage: int = Query(default=1, ge=1, le=125)
):
    """Generate trading signals applying selected sniper mode configuration.

    Mode logic:
    - Resolve mode (case-insensitive) via scanner_modes mapping.
    - Apply its timeframes & baseline min_confluence_score.
    - If caller supplies min_score > 0 it overrides upward; else baseline used.
    - Profile updated to mode.profile for downstream heuristics.
    
    Category filtering:
    - majors: BTC, ETH, BNB
    - altcoins: SOL, XRP, ADA, AVAX, MATIC, DOT, LINK, etc.
    - meme_mode: DOGE, SHIB, PEPE, etc.
    
    Exchange & Leverage:
    - exchange: bybit (default), phemex, okx, bitget
    - leverage: Position leverage (1x-125x, affects position sizing)
    """
    try:
        # Resolve requested exchange adapter
        exchange_key = exchange.lower()
        if exchange_key not in EXCHANGE_ADAPTERS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported exchange: {exchange}. Supported: {', '.join(EXCHANGE_ADAPTERS.keys())}"
            )
        
        # Create fresh adapter instance for this scan
        current_adapter = EXCHANGE_ADAPTERS[exchange_key]()
        
        # Resolve requested mode (fallback handled by exception)
        try:
            mode = get_mode(sniper_mode)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Determine effective threshold
        effective_min = max(min_score, mode.min_confluence_score) if min_score > 0 else mode.min_confluence_score

        logger.info("Scan request: mode=%s, exchange=%s, leverage=%dx, categories=(majors=%s, alts=%s, meme=%s)", 
                   mode.name, exchange, leverage, majors, altcoins, meme_mode)

        # Update orchestrator config in-place
        orchestrator.config.timeframes = mode.timeframes
        orchestrator.config.min_confluence_score = effective_min
        orchestrator.config.profile = mode.profile
        
        # Update orchestrator's exchange adapter
        orchestrator.exchange_adapter = current_adapter
        orchestrator.ingestion_pipeline = IngestionPipeline(current_adapter)

        # Acquire symbols (fallback list on failure)
        try:
            all_symbols = current_adapter.get_top_symbols(n=min(limit * 3, 50), quote_currency='USDT')
        except Exception as exchange_error:  # pyright: ignore - intentional broad catch for fallback
            logger.warning("Exchange unavailable (geo-restriction or network issue): %s", exchange_error)
            all_symbols = []

        if not all_symbols:
            all_symbols = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                'ADA/USDT', 'AVAX/USDT', 'MATIC/USDT', 'DOT/USDT', 'LINK/USDT',
                'DOGE/USDT', 'SHIB/USDT', 'PEPE/USDT'
            ]
        
        # Filter symbols by category
        major_coins = {'BTC/USDT', 'ETH/USDT', 'BNB/USDT'}
        meme_coins = {'DOGE/USDT', 'SHIB/USDT', 'PEPE/USDT', 'BONK/USDT', 'FLOKI/USDT', 'WIF/USDT'}
        
        symbols = []
        for symbol in all_symbols:
            if symbol in major_coins and majors:
                symbols.append(symbol)
            elif symbol in meme_coins and meme_mode:
                symbols.append(symbol)
            elif symbol not in major_coins and symbol not in meme_coins and altcoins:
                symbols.append(symbol)
        
        # If no categories selected, use all
        if not symbols:
            symbols = all_symbols
            
        symbols = symbols[:limit]
        logger.info("Filtering %d symbols by categories (majors=%s, altcoins=%s, meme=%s)", 
                   len(symbols), majors, altcoins, meme_mode)

        # Run scan pipeline
        trade_plans, rejection_summary = orchestrator.scan(symbols)

        rejected_count = len(symbols) - len(trade_plans)
        logger.info("Scan completed: %d signals generated, %d rejected from %d symbols", 
                   len(trade_plans), rejected_count, len(symbols))
        
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
            "rejected": rejected_count,
            "mode": mode.name,
            "applied_timeframes": mode.timeframes,
            "effective_min_score": effective_min,
            "baseline_min_score": mode.min_confluence_score,
            "profile": mode.profile,
            "exchange": exchange,
            "leverage": leverage,
            "categories": {
                "majors": majors,
                "altcoins": altcoins,
                "meme_mode": meme_mode
            },
            "rejections": rejection_summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating signals: %s", e)
        from backend.bot.telemetry.events import create_error_event
        telemetry = get_telemetry_logger()
        telemetry.log_event(create_error_event(
            error_message=str(e),
            error_type=type(e).__name__,
            run_id=None
        ))
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        "win_rate": 0.0,  # Calculated from trade history
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
                "entry_price": 0,  # Tracked from fills
                "current_price": 0,  # Retrieved from market data
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
        logger.error("Order placement failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/bot/trades")
async def get_trade_history(
    limit: int = Query(default=50, ge=1, le=100)
):
    """Get trade history (recent fills)."""
    fills = paper_executor.get_trade_history()
    
    # Note: Fill objects contain: order_id, quantity, price, fee, timestamp
    # For proper trade history, we'd need to track closed positions separately
    fill_list = [
        {
            "order_id": fill.order_id,
            "quantity": fill.quantity,
            "price": fill.price,
            "fee": fill.fee,
            "timestamp": fill.timestamp.isoformat()
        }
        for fill in fills[-limit:]
    ]
    
    return {"fills": fill_list, "total": len(fill_list)}


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


@app.get("/api/market/regime")
async def get_market_regime():
    """
    Get current global market regime.
    
    Analyzes BTC/USDT market data to determine regime state across
    trend, volatility, liquidity, risk appetite, and derivatives dimensions.
    
    Returns:
        MarketRegime with composite label, score, and dimension breakdown
    """
    try:
        # Detect global regime via orchestrator
        regime = orchestrator._detect_global_regime()
        
        if not regime:
            # Return neutral regime if detection fails
            return {
                "composite": "neutral",
                "score": 50.0,
                "dimensions": {
                    "trend": "sideways",
                    "volatility": "normal",
                    "liquidity": "normal",
                    "risk_appetite": "neutral",
                    "derivatives": "balanced"
                },
                "trend_score": 50.0,
                "volatility_score": 50.0,
                "liquidity_score": 50.0,
                "risk_score": 50.0,
                "derivatives_score": 50.0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "composite": regime.composite,
            "score": regime.score,
            "dimensions": {
                "trend": regime.dimensions.trend,
                "volatility": regime.dimensions.volatility,
                "liquidity": regime.dimensions.liquidity,
                "risk_appetite": regime.dimensions.risk_appetite,
                "derivatives": regime.dimensions.derivatives
            },
            "trend_score": regime.trend_score,
            "volatility_score": regime.volatility_score,
            "liquidity_score": regime.liquidity_score,
            "risk_score": regime.risk_score,
            "derivatives_score": regime.derivatives_score,
            "timestamp": regime.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error("Market regime detection failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Regime detection error: {str(e)}") from e


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
        logger.error("Error fetching recent telemetry: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


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
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=f"Invalid event_type: {event_type}") from ve
        
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
        logger.error("Error querying telemetry events: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        logger.error("Error calculating analytics: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
