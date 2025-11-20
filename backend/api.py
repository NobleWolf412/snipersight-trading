"""
FastAPI Backend Server

REST API endpoints for SniperSight frontend integration.
Provides market scanning, bot control, and risk management.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uvicorn

from backend.risk.position_sizer import PositionSizer
from backend.risk.risk_manager import RiskManager
from backend.bot.executor.paper_executor import PaperExecutor, OrderSide, OrderType

# Initialize FastAPI app
app = FastAPI(
    title="SniperSight API",
    description="Crypto trading scanner and automation API",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# REQUEST/RESPONSE MODELS (Matching UI TypeScript interfaces)
# ============================================================================

class TrendBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Classification(str, Enum):
    SWING = "SWING"
    SCALP = "SCALP"


class OrderBlockType(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class ScanConfigRequest(BaseModel):
    """Scanner configuration from UI"""
    exchange: str = "Binance"
    topPairs: int = Field(default=20, ge=1, le=100)
    customPairs: List[str] = []
    categories: Dict[str, bool] = {
        "majors": True,
        "altcoins": True,
        "memeMode": False
    }
    timeframes: List[str] = ["1D", "4H", "1H"]
    leverage: int = Field(default=1, ge=1, le=125)


class EntryZone(BaseModel):
    low: float
    high: float


class OrderBlock(BaseModel):
    type: OrderBlockType
    price: float
    timeframe: str


class FairValueGap(BaseModel):
    low: float
    high: float
    type: OrderBlockType


class ScanResult(BaseModel):
    """Scan result matching UI ScanResult interface"""
    id: str
    pair: str
    trendBias: TrendBias
    confidenceScore: float = Field(ge=0, le=100)
    riskScore: float = Field(ge=0, le=10)
    classification: Classification
    entryZone: EntryZone
    stopLoss: float
    takeProfits: List[float]
    orderBlocks: List[OrderBlock]
    fairValueGaps: List[FairValueGap]
    timestamp: str


class BotConfigRequest(BaseModel):
    """Bot configuration from UI"""
    exchange: str = "Binance"
    pair: str = "BTC/USDT"
    modes: Dict[str, bool] = {"swing": True, "scalp": False}
    maxTrades: int = Field(default=3, ge=1, le=10)
    duration: int = Field(default=24, ge=1)  # hours
    leverage: int = Field(default=1, ge=1, le=125)


class BotStatus(BaseModel):
    """Bot status response"""
    isActive: bool
    currentTrades: int
    totalTrades: int
    profit: float
    winRate: float
    uptime: int  # seconds
    lastActivity: Optional[str]


class ActivityStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"
    ERROR = "error"


class BotActivity(BaseModel):
    """Bot activity log entry"""
    id: str
    timestamp: str
    action: str
    pair: str
    status: ActivityStatus
    details: Optional[Dict[str, Any]] = None


class TradeRequest(BaseModel):
    """Manual trade execution request"""
    pair: str
    side: str  # BUY or SELL
    orderType: str = "MARKET"  # MARKET, LIMIT
    quantity: float
    price: Optional[float] = None
    stopLoss: Optional[float] = None
    takeProfit: Optional[float] = None


class PositionSizeRequest(BaseModel):
    """Position size calculation request"""
    accountBalance: float
    pair: str
    currentPrice: float
    stopLossPrice: float
    riskPercentage: float = Field(default=1.0, ge=0.1, le=5.0)
    leverage: int = Field(default=1, ge=1, le=125)


# ============================================================================
# GLOBAL STATE (In production, use database)
# ============================================================================

# Active executors per user (keyed by wallet address)
active_executors: Dict[str, PaperExecutor] = {}
active_risk_managers: Dict[str, RiskManager] = {}
bot_activities: Dict[str, List[BotActivity]] = {}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_or_create_executor(wallet_address: str, initial_balance: float = 10000) -> PaperExecutor:
    """Get or create paper executor for user"""
    if wallet_address not in active_executors:
        active_executors[wallet_address] = PaperExecutor(
            initial_balance=initial_balance,
            fee_rate=0.001,
            slippage_bps=5.0
        )
    return active_executors[wallet_address]


def get_or_create_risk_manager(wallet_address: str, account_balance: float = 10000) -> RiskManager:
    """Get or create risk manager for user"""
    if wallet_address not in active_risk_managers:
        active_risk_managers[wallet_address] = RiskManager(
            account_balance=account_balance,
            max_open_positions=5,
            max_daily_loss_pct=5.0
        )
    return active_risk_managers[wallet_address]


def log_activity(wallet_address: str, action: str, pair: str, status: ActivityStatus, details: Dict = None):
    """Log bot activity"""
    if wallet_address not in bot_activities:
        bot_activities[wallet_address] = []
    
    activity = BotActivity(
        id=f"activity-{datetime.now().timestamp()}",
        timestamp=datetime.now().isoformat(),
        action=action,
        pair=pair,
        status=status,
        details=details
    )
    
    bot_activities[wallet_address].insert(0, activity)
    # Keep only last 100 activities
    bot_activities[wallet_address] = bot_activities[wallet_address][:100]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """API health check"""
    return {
        "name": "SniperSight API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.post("/api/scan", response_model=List[ScanResult])
async def run_scan(config: ScanConfigRequest):
    """
    Execute market scan with given configuration.
    
    This endpoint will:
    1. Fetch market data for specified pairs/categories
    2. Run SMC analysis (Order Blocks, FVG, Liquidity Sweeps)
    3. Calculate confluence scores
    4. Return trade setups with entry/exit levels
    """
    # TODO: Implement actual scanning logic
    # For now, return empty list - frontend uses mock data
    # In future, integrate with:
    # - backend/data/ingestion_pipeline.py for market data
    # - backend/strategy/smc/ modules for analysis
    # - backend/strategy/confluence/scorer.py for scoring
    
    return []


@app.get("/api/scan/results", response_model=List[ScanResult])
async def get_scan_results():
    """Get latest scan results (cached)"""
    # TODO: Implement result caching
    return []


@app.post("/api/bot/configure")
async def configure_bot(config: BotConfigRequest, wallet_address: str = "default"):
    """
    Configure bot parameters.
    Validates configuration and prepares bot for deployment.
    """
    # Validate exchange connection would happen here
    # For now, just acknowledge configuration
    
    return {
        "success": True,
        "message": f"Bot configured for {config.pair} on {config.exchange}",
        "config": config.dict()
    }


@app.post("/api/bot/start")
async def start_bot(wallet_address: str = "default"):
    """Start automated trading bot"""
    executor = get_or_create_executor(wallet_address)
    risk_manager = get_or_create_risk_manager(wallet_address)
    
    log_activity(
        wallet_address,
        "Bot started - monitoring markets",
        "N/A",
        ActivityStatus.SUCCESS
    )
    
    return {
        "success": True,
        "message": "Trading bot activated",
        "balance": executor.get_balance()
    }


@app.post("/api/bot/stop")
async def stop_bot(wallet_address: str = "default"):
    """Stop automated trading bot"""
    log_activity(
        wallet_address,
        "Bot stopped by user",
        "N/A",
        ActivityStatus.INFO
    )
    
    return {"success": True, "message": "Trading bot deactivated"}


@app.get("/api/bot/status", response_model=BotStatus)
async def get_bot_status(wallet_address: str = "default"):
    """Get current bot status and statistics"""
    executor = get_or_create_executor(wallet_address)
    stats = executor.get_statistics()
    
    # Calculate win rate from fill history
    total_trades = stats['filled_orders']
    winning_trades = 0  # TODO: Calculate from actual PnL
    
    return BotStatus(
        isActive=False,  # TODO: Track active state
        currentTrades=len(executor.get_open_orders()),
        totalTrades=total_trades,
        profit=0.0,  # TODO: Calculate from trade history
        winRate=winning_trades / total_trades * 100 if total_trades > 0 else 0,
        uptime=0,  # TODO: Track uptime
        lastActivity=bot_activities.get(wallet_address, [{}])[0].timestamp if bot_activities.get(wallet_address) else None
    )


@app.get("/api/bot/activity", response_model=List[BotActivity])
async def get_bot_activity(wallet_address: str = "default", limit: int = 50):
    """Get bot activity log"""
    activities = bot_activities.get(wallet_address, [])
    return activities[:limit]


@app.post("/api/trade/execute")
async def execute_trade(trade: TradeRequest, wallet_address: str = "default"):
    """
    Execute manual trade (paper or live based on configuration).
    
    Flow:
    1. Validate trade request
    2. Calculate position size using risk parameters
    3. Check risk manager approval
    4. Execute through paper/live executor
    5. Log activity
    """
    executor = get_or_create_executor(wallet_address)
    risk_manager = get_or_create_risk_manager(wallet_address)
    
    try:
        # Calculate position size
        position_value = trade.quantity * trade.price if trade.price else trade.quantity
        
        # Check risk approval
        risk_check = risk_manager.validate_new_trade(
            symbol=trade.pair,
            direction="LONG" if trade.side.upper() == "BUY" else "SHORT",
            position_value=position_value,
            risk_amount=position_value * 0.01  # Assume 1% risk
        )
        
        if not risk_check.passed:
            log_activity(
                wallet_address,
                f"Trade rejected: {risk_check.reason}",
                trade.pair,
                ActivityStatus.WARNING,
                {"limits_hit": risk_check.limits_hit}
            )
            raise HTTPException(status_code=400, detail=risk_check.reason)
        
        # Place order
        order = executor.place_order(
            symbol=trade.pair,
            side=trade.side.upper(),
            order_type=trade.orderType.upper(),
            quantity=trade.quantity,
            price=trade.price
        )
        
        # Execute if market order
        if trade.orderType.upper() == "MARKET" and trade.price:
            fill = executor.execute_market_order(order.order_id, trade.price)
            
            if fill:
                # Update risk manager
                risk_manager.add_position(
                    symbol=trade.pair,
                    direction="LONG" if trade.side.upper() == "BUY" else "SHORT",
                    quantity=fill.quantity,
                    entry_price=fill.price,
                    current_price=fill.price
                )
                
                log_activity(
                    wallet_address,
                    f"Order filled: {trade.side} {trade.quantity} {trade.pair}",
                    trade.pair,
                    ActivityStatus.SUCCESS,
                    {"order_id": order.order_id, "fill_price": fill.price}
                )
                
                return {
                    "success": True,
                    "order_id": order.order_id,
                    "fill": {
                        "quantity": fill.quantity,
                        "price": fill.price,
                        "fee": fill.fee
                    }
                }
        
        log_activity(
            wallet_address,
            f"Order placed: {trade.side} {trade.quantity} {trade.pair}",
            trade.pair,
            ActivityStatus.INFO,
            {"order_id": order.order_id}
        )
        
        return {
            "success": True,
            "order_id": order.order_id,
            "status": order.status.value
        }
        
    except ValueError as e:
        log_activity(
            wallet_address,
            f"Trade failed: {str(e)}",
            trade.pair,
            ActivityStatus.ERROR
        )
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/position/calculate")
async def calculate_position_size(request: PositionSizeRequest):
    """
    Calculate optimal position size based on risk parameters.
    Uses PositionSizer backend component.
    """
    sizer = PositionSizer(
        account_balance=request.accountBalance,
        max_risk_pct=request.riskPercentage
    )
    
    # Calculate stop distance in dollars
    stop_distance = abs(request.currentPrice - request.stopLossPrice)
    
    # Use fixed fractional sizing
    position = sizer.calculate_fixed_fractional(
        entry_price=request.currentPrice,
        stop_loss=request.stopLossPrice,
        leverage=request.leverage
    )
    
    return {
        "quantity": position.quantity,
        "notional_value": position.notional_value,
        "risk_amount": position.risk_amount,
        "margin_required": position.margin_required,
        "leverage": position.leverage,
        "is_valid": position.is_valid,
        "validation_message": position.validation_message
    }


@app.get("/api/portfolio/summary")
async def get_portfolio_summary(wallet_address: str = "default"):
    """Get portfolio summary including positions and risk metrics"""
    executor = get_or_create_executor(wallet_address)
    risk_manager = get_or_create_risk_manager(wallet_address)
    
    # Get current market prices (mock for now)
    market_prices = {}
    for symbol in executor.positions.keys():
        market_prices[symbol] = 50000.0  # TODO: Fetch real prices
    
    risk_summary = risk_manager.get_risk_summary()
    
    return {
        "balance": executor.get_balance(),
        "equity": executor.get_equity(market_prices),
        "pnl": executor.get_pnl(market_prices),
        "open_positions": len(executor.get_open_orders()),
        "risk_metrics": risk_summary,
        "positions": [
            {
                "symbol": symbol,
                "quantity": qty,
                "value": qty * market_prices.get(symbol, 0)
            }
            for symbol, qty in executor.positions.items()
            if qty != 0
        ]
    }


# ============================================================================
# SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
