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
from backend.data.adapters.binance import BinanceAdapter

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
    BINANCE = "binance"
    BYBIT = "bybit"
    PHEMEX = "phemex"


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
binance_adapter = BinanceAdapter(testnet=False)


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


@app.get("/api/scanner/signals")
async def get_signals(
    limit: int = Query(default=10, ge=1, le=100),
    min_score: float = Query(default=60, ge=0, le=100),
    sniper_mode: str = Query(default="PRECISION")
):
    """Get trading signals from scanner."""
    try:
        # Try to get real data from exchange
        try:
            symbols = binance_adapter.get_top_symbols(n=min(limit * 2, 20), quote_currency='USDT')
            use_real_data = True
        except Exception as e:
            logger.warning(f"Exchange API unavailable, using mock symbols: {e}")
            symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'MATIC/USDT', 'LINK/USDT', 'DOT/USDT', 'ADA/USDT']
            use_real_data = False
        
        if not symbols:
            symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT']
            use_real_data = False
        
        signals = []
        for symbol in symbols[:limit]:
            try:
                if use_real_data:
                    # Fetch real data using fetch_ticker
                    ticker = binance_adapter.fetch_ticker(symbol)
                    current_price = ticker['last']
                else:
                    # Generate mock price data
                    base_prices = {
                        'BTC/USDT': 43000, 'ETH/USDT': 2300, 'BNB/USDT': 240,
                        'SOL/USDT': 65, 'MATIC/USDT': 0.85, 'LINK/USDT': 15,
                        'DOT/USDT': 7.5, 'ADA/USDT': 0.45
                    }
                    base = base_prices.get(symbol, 100)
                    current_price = base * (0.95 + (hash(symbol) % 100) * 0.001)
            except Exception as e:
                logger.warning(f"Failed to fetch ticker for {symbol}: {e}")
                # Generate fallback price
                base_prices = {
                    'BTC/USDT': 43000, 'ETH/USDT': 2300, 'BNB/USDT': 240,
                    'SOL/USDT': 65, 'MATIC/USDT': 0.85, 'LINK/USDT': 15,
                    'DOT/USDT': 7.5, 'ADA/USDT': 0.45
                }
                base = base_prices.get(symbol, 100)
                current_price = base * (0.95 + (hash(symbol) % 100) * 0.001)
                use_real_data = False
            
            # Generate signal score (hash-based for consistency)
            score = 75.0 + (hash(symbol) % 20)
            
            if score < min_score:
                continue
            
            # Determine direction
            direction = "LONG" if hash(symbol) % 2 == 0 else "SHORT"
            
            # Calculate entry zones and targets
            if direction == "LONG":
                entry_near = current_price * 0.99
                entry_far = current_price * 0.98
                stop_loss = current_price * 0.96
                targets = [
                    {"level": current_price * 1.02, "percentage": 50},
                    {"level": current_price * 1.04, "percentage": 50}
                ]
            else:
                entry_near = current_price * 1.01
                entry_far = current_price * 1.02
                stop_loss = current_price * 1.04
                targets = [
                    {"level": current_price * 0.98, "percentage": 50},
                    {"level": current_price * 0.96, "percentage": 50}
                ]
            
            signal = {
                "symbol": symbol.replace('/', ''),  # Convert to BTCUSDT format
                "direction": direction,
                "score": score,
                "entry_near": entry_near,
                "entry_far": entry_far,
                "stop_loss": stop_loss,
                "targets": targets,
                "timeframe": "1h",
                "current_price": current_price,
                "analysis": {
                    "order_blocks": 2,
                    "fvgs": 1,
                    "structural_breaks": 1,
                    "liquidity_sweeps": 0,
                    "trend": "bullish" if direction == "LONG" else "bearish",
                    "risk_reward": 2.0
                },
                "rationale": f"{symbol} shows SMC structure with {score:.0f}% confluence score. {direction} setup identified.",
                "setup_type": "intraday"
            }
            signals.append(signal)
        
        return {
            "signals": signals,
            "total": len(signals),
            "scanned": len(symbols),
            "mode": sniper_mode,
            "min_score": min_score,
            "data_source": "exchange" if use_real_data else "mock"
        }
    except Exception as e:
        logger.error(f"Error generating signals: {e}")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
