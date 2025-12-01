"""
FastAPI server for SniperSight trading bot.

Provides REST API endpoints for the frontend UI.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import logging
import asyncio
import time

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
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.analysis.pair_selection import select_symbols
from backend.shared.config.smc_config import SMCConfig
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, list_modes
from backend.bot.notifications.notification_manager import (
    notification_manager,
    NotificationPriority,
    NotificationType,
    NotificationEvent,
)
from backend.routers.htf_opportunities import router as htf_router

logger = logging.getLogger(__name__)

# In-memory price cache with TTL to reduce exchange API load
PRICE_CACHE: Dict[str, Dict[str, Any]] = {}
PRICE_CACHE_TTL = 5  # seconds

# Initialize FastAPI app
app = FastAPI(
    title="SniperSight API",
    description="Crypto trading scanner and bot API",
    version="1.0.0"
)

# Include routers
app.include_router(htf_router)

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


class NotificationPayload(BaseModel):
    """Inbound notification payload for generic event creation."""
    type: str
    priority: str = "normal"
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None

    def to_event(self) -> NotificationEvent:
        # Map enums safely; fallback to SYSTEM/NORMAL
        try:
            n_type = NotificationType(self.type.lower())
        except Exception:
            n_type = NotificationType.SYSTEM
        try:
            n_priority = NotificationPriority(self.priority.lower())
        except Exception:
            n_priority = NotificationPriority.NORMAL
        return NotificationEvent(
            id=f"custom-{int(datetime.now(timezone.utc).timestamp())}-{n_type.value}",
            type=n_type,
            priority=n_priority,
            timestamp=datetime.now(timezone.utc),
            title=self.title,
            body=self.message,
            data=self.data,
        )


# Global state (in production, use proper state management/database)
scanner_configs: Dict[str, ScannerConfig] = {}
bot_configs: Dict[str, BotConfig] = {}
active_scanners: Dict[str, bool] = {}
active_bots: Dict[str, bool] = {}

# Background scan job tracking
import asyncio
import uuid
from typing import Literal

ScanJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

class ScanJob:
    def __init__(self, run_id: str, params: dict):
        self.run_id = run_id
        self.status: ScanJobStatus = "queued"
        self.progress = 0
        self.total = 0
        self.current_symbol: Optional[str] = None
        self.signals: List[dict] = []
        self.rejections: dict = {}
        self.metadata: dict = {}
        self.error: Optional[str] = None
        self.params = params
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.task: Optional[asyncio.Task] = None

scan_jobs: Dict[str, ScanJob] = {}

# Initialize trading components
position_sizer = PositionSizer(account_balance=10000, max_risk_pct=2.0)
risk_manager = RiskManager(
    account_balance=10000,
    max_open_positions=5,
    max_asset_exposure_pct=50.0  # Increased for intraday tight-stop strategies
)
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


# Serve built frontend at root (only if dist exists - for production)
import os
if os.path.exists("dist"):
    app.mount("/", StaticFiles(directory="dist", html=True), name="frontend")


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

@app.get("/api/scanner/mode_active")
async def get_active_mode():
    """Return current active scanner mode state with critical timeframe expectations."""
    try:
        mode = orchestrator.scanner_mode
        return {
            "active_mode": {
                "name": mode.name,
                "profile": mode.profile,
                "timeframes": mode.timeframes,
                "critical_timeframes": mode.critical_timeframes,
                "baseline_min_confluence": mode.min_confluence_score,
                "current_effective_min_confluence": getattr(orchestrator.config, 'min_confluence_score', mode.min_confluence_score)
            }
        }
    except Exception as e:
        logger.error("Failed to get active mode: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


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


@app.get("/api/scanner/pairs")
async def get_scanner_pairs(
    limit: int = Query(default=10, ge=1, le=100),
    majors: bool = Query(default=True),
    altcoins: bool = Query(default=True),
    meme_mode: bool = Query(default=False),
    exchange: str = Query(default="phemex"),
    leverage: int = Query(default=1, ge=1, le=125),
):
    """Preview pairs the scanner would use without running a scan.

    Reuses adapter + centralized selection logic, returns symbols and filter context.
    """
    try:
        exchange_key = exchange.lower()
        if exchange_key not in EXCHANGE_ADAPTERS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported exchange: {exchange}. Supported: {', '.join(EXCHANGE_ADAPTERS.keys())}",
            )

        adapter = EXCHANGE_ADAPTERS[exchange_key]()
        symbols = select_symbols(
            adapter=adapter,
            limit=limit,
            majors=majors,
            altcoins=altcoins,
            meme_mode=meme_mode,
            leverage=leverage,
        )

        return {
            "exchange": exchange_key,
            "limit": limit,
            "filters": {
                "majors": majors,
                "altcoins": altcoins,
                "meme_mode": meme_mode,
            },
            "symbols": symbols,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error resolving scanner pairs: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


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
    leverage: int = Query(default=1, ge=1, le=125),
    macro_overlay: bool = Query(default=False)
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

        # Apply mode safely (profile, timeframes, critical TFs, regime policy)
        orchestrator.apply_mode(mode)
        # If caller provided a higher override score, update after mode baseline applied
        orchestrator.config.min_confluence_score = effective_min
        # Inject leverage into config for planner adaptive logic
        try:
            setattr(orchestrator.config, 'leverage', leverage)
        except Exception:
            pass
        # Enable macro overlay if requested
        orchestrator.config.macro_overlay_enabled = macro_overlay
        
        # Update orchestrator's exchange adapter
        orchestrator.exchange_adapter = current_adapter
        orchestrator.ingestion_pipeline = IngestionPipeline(current_adapter)

        # Resolve symbols via centralized selector
        symbols = select_symbols(
            adapter=current_adapter,
            limit=limit,
            majors=majors,
            altcoins=altcoins,
            meme_mode=meme_mode,
            leverage=leverage,
        )
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
                    "risk_reward": plan.risk_reward,
                    "confluence_score": plan.confluence_breakdown.total_score if hasattr(plan, 'confluence_breakdown') else plan.confidence_score,
                    "expected_value": plan.metadata.get('expected_value')
                },
                "liquidation": plan.metadata.get('liquidation'),
                "atr_regime": plan.metadata.get('atr_regime'),
                "alt_stop": plan.metadata.get('alt_stop'),
                # Optional SMC geometry for chart overlays (if provided by pipeline)
                "smc_geometry": {
                    "order_blocks": plan.metadata.get('order_blocks_list'),
                    "fvgs": plan.metadata.get('fvgs_list'),
                    "bos_choch": plan.metadata.get('structural_breaks_list'),
                    "liquidity_sweeps": plan.metadata.get('liquidity_sweeps_list')
                },
                "rationale": plan.rationale,
                "setup_type": plan.setup_type,
                # Enrichment for frontend contract alignment
                "plan_type": getattr(plan, 'plan_type', 'SMC'),
                "conviction_class": getattr(plan, 'conviction_class', None),
                "missing_critical_timeframes": plan.metadata.get('missing_critical_timeframes', []),
                "regime": plan.metadata.get('regime'),
                # Optional macro overlay metadata (if computed and enabled)
                "macro": plan.metadata.get('macro')
            }
            signals.append(signal)

        return {
            "signals": signals,
            "total": len(signals),
            "scanned": len(symbols),
            "rejected": rejected_count,
            "mode": mode.name,
            "applied_timeframes": mode.timeframes,
            "critical_timeframes": mode.critical_timeframes,
            "active_mode": {
                "name": orchestrator.scanner_mode.name,
                "profile": orchestrator.scanner_mode.profile,
                "timeframes": orchestrator.scanner_mode.timeframes,
                "critical_timeframes": orchestrator.scanner_mode.critical_timeframes,
                "baseline_min_confluence": orchestrator.scanner_mode.min_confluence_score
            },
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


@app.get("/api/debug/signals_schema")
async def debug_signals_schema(
    limit: int = Query(default=3, ge=1, le=10),
    sniper_mode: str = Query(default="recon"),
    exchange: str = Query(default="phemex")
):
    """
    Debug endpoint to verify signals payload schema without verbose logs.
    
    Returns compact summary of signals with smc_geometry and analysis keys present.
    Use to confirm backend enrichment contract without pipeline noise.
    """
    try:
        # Get signals using main endpoint logic but return minimal schema summary
        from backend.analysis.pair_selection import select_symbols
        
        exchange_key = exchange.lower()
        if exchange_key not in EXCHANGE_ADAPTERS:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange}")
        
        current_adapter = EXCHANGE_ADAPTERS[exchange_key]()
        mode = get_mode(sniper_mode)
        orchestrator.apply_mode(mode)
        orchestrator.exchange_adapter = current_adapter
        orchestrator.ingestion_pipeline = IngestionPipeline(current_adapter)
        
        symbols = select_symbols(adapter=current_adapter, limit=limit, majors=True, altcoins=True, meme_mode=False, leverage=1)
        trade_plans, _ = orchestrator.scan(symbols)
        
        # Extract schema info
        schema_summary = []
        for plan in trade_plans:
            schema_summary.append({
                "symbol": plan.symbol,
                "has_smc_geometry": all([
                    plan.metadata.get('order_blocks_list') is not None,
                    plan.metadata.get('fvgs_list') is not None,
                    plan.metadata.get('structural_breaks_list') is not None,
                    plan.metadata.get('liquidity_sweeps_list') is not None
                ]),
                "smc_geometry_keys": [
                    k for k in ['order_blocks_list', 'fvgs_list', 'structural_breaks_list', 'liquidity_sweeps_list']
                    if plan.metadata.get(k) is not None
                ],
                "smc_geometry_counts": {
                    "order_blocks": len(plan.metadata.get('order_blocks_list', [])),
                    "fvgs": len(plan.metadata.get('fvgs_list', [])),
                    "bos_choch": len(plan.metadata.get('structural_breaks_list', [])),
                    "liquidity_sweeps": len(plan.metadata.get('liquidity_sweeps_list', []))
                },
                "has_analysis": all([
                    'risk_reward' in [plan.risk_reward],
                    hasattr(plan, 'confluence_breakdown') or plan.confidence_score is not None
                ]),
                "analysis_keys": ["risk_reward", "confluence_score", "expected_value"]
            })
        
        return {
            "count": len(schema_summary),
            "mode": mode.name,
            "exchange": exchange,
            "signals": schema_summary
        }
    except Exception as e:
        logger.error("Debug schema error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/scanner/diagnostics")
async def get_scanner_diagnostics():
    """
    Get detailed diagnostics and rejection breakdowns from orchestrator.
    
    Useful for debugging zero-signal scans and understanding quality gate failures.
    Returns per-stage rejection counts and sample failures for deep analysis.
    """
    try:
        # Get orchestrator pipeline status including diagnostics
        status = orchestrator.get_pipeline_status()
        
        # Build breakdown summary
        diagnostics_data = status.get('diagnostics', {})
        
        return {
            "debug_mode": status.get('debug_mode', False),
            "config": status.get('config', {}),
            "rejection_breakdown": {
                "data_failures": {
                    "count": len(diagnostics_data.get('data_failures', [])),
                    "samples": diagnostics_data.get('data_failures', [])[:5]
                },
                "indicator_failures": {
                    "count": len(diagnostics_data.get('indicator_failures', [])),
                    "samples": diagnostics_data.get('indicator_failures', [])[:5]
                },
                "smc_rejections": {
                    "count": len(diagnostics_data.get('smc_rejections', [])),
                    "samples": diagnostics_data.get('smc_rejections', [])[:5]
                },
                "confluence_rejections": {
                    "count": len(diagnostics_data.get('confluence_rejections', [])),
                    "samples": diagnostics_data.get('confluence_rejections', [])[:5]
                },
                "planner_rejections": {
                    "count": len(diagnostics_data.get('planner_rejections', [])),
                    "samples": diagnostics_data.get('planner_rejections', [])[:5]
                },
                "risk_rejections": {
                    "count": len(diagnostics_data.get('risk_rejections', [])),
                    "samples": diagnostics_data.get('risk_rejections', [])[:5]
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "help": "Enable SS_DEBUG=1 environment variable for debug bundle export"
        }
    except Exception as e:
        logger.error("Error retrieving diagnostics: %s", e)
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


# ---------------------------------------------------------------------------
# Notification Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/notifications")
async def list_notifications(limit: int = Query(default=50, ge=1, le=200)):
    """Return recent notification events (newest first)."""
    events = notification_manager.get_recent_events(limit=limit)
    return {"notifications": events, "total": len(events)}


@app.post("/api/notifications/send")
async def send_notification(payload: NotificationPayload):
    """Create and store a notification event.

    For type 'signal' attempts to use signal notification formatting when possible.
    Returns the created notification event.
    """
    try:
        if payload.type.lower() == "signal" and payload.data and "symbol" in payload.data:
            # Adapt incoming data to signal_data expected fields.
            confidence_field = payload.data.get("confidence")
            if isinstance(confidence_field, float) and confidence_field <= 1.0:
                confidence = int(confidence_field * 100)
            else:
                confidence = int(confidence_field or 50)
            signal_data = {
                "symbol": payload.data.get("symbol"),
                "direction": payload.data.get("direction", "LONG"),
                "confidence": confidence,
                "risk_reward": payload.data.get("risk_reward") or payload.data.get("rr", 0),
            }
            event_id = notification_manager.send_signal_notification(signal_data)
            event = notification_manager.get_event_by_id(event_id)
            return {"event_id": event_id, "notification": event}
        # Generic path
        event = payload.to_event()
        notification_manager._add_event(event)  # internal add to preserve data
        return {"event_id": event.id, "notification": event.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send notification: {e}") from e


# Background scan endpoints
@app.post("/api/scanner/runs")
async def create_scan_run(
    limit: int = Query(default=10, ge=1, le=100),
    min_score: float = Query(default=0, ge=0, le=100),
    sniper_mode: str = Query(default="recon"),
    majors: bool = Query(default=True),
    altcoins: bool = Query(default=True),
    meme_mode: bool = Query(default=False),
    exchange: str = Query(default="phemex"),
    leverage: int = Query(default=1, ge=1, le=125),
    macro_overlay: bool = Query(default=False)
):
    """Start a background scan job and return immediately with run_id."""
    run_id = str(uuid.uuid4())
    params = {
        "limit": limit,
        "min_score": min_score,
        "sniper_mode": sniper_mode,
        "majors": majors,
        "altcoins": altcoins,
        "meme_mode": meme_mode,
        "exchange": exchange,
        "leverage": leverage,
        "macro_overlay": macro_overlay
    }
    
    job = ScanJob(run_id, params)
    scan_jobs[run_id] = job
    
    # Start background task
    job.task = asyncio.create_task(_execute_scan_job(job))
    
    return {
        "run_id": run_id,
        "status": job.status,
        "created_at": job.created_at.isoformat()
    }


@app.get("/api/scanner/runs/{run_id}")
async def get_scan_run(run_id: str):
    """Get status and results of a scan job."""
    if run_id not in scan_jobs:
        raise HTTPException(status_code=404, detail="Scan job not found")
    
    job = scan_jobs[run_id]
    
    response = {
        "run_id": job.run_id,
        "status": job.status,
        "progress": job.progress,
        "total": job.total,
        "current_symbol": job.current_symbol,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    
    if job.status == "completed":
        response["signals"] = job.signals
        response["metadata"] = job.metadata
        response["rejections"] = job.rejections
    elif job.status == "failed":
        response["error"] = job.error
    
    return response


@app.delete("/api/scanner/runs/{run_id}")
async def cancel_scan_run(run_id: str):
    """Cancel a running scan job."""
    if run_id not in scan_jobs:
        raise HTTPException(status_code=404, detail="Scan job not found")
    
    job = scan_jobs[run_id]
    
    if job.status in ["completed", "failed", "cancelled"]:
        return {"message": f"Job already {job.status}"}
    
    if job.task and not job.task.done():
        job.task.cancel()
    
    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    
    return {"message": "Job cancelled", "run_id": run_id}


async def _execute_scan_job(job: ScanJob):
    """Execute scan in background, updating job status as it progresses."""
    try:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        
        params = job.params
        
        # Resolve exchange adapter
        exchange_key = params["exchange"].lower()
        if exchange_key not in EXCHANGE_ADAPTERS:
            raise ValueError(f"Unsupported exchange: {exchange_key}")
        
        current_adapter = EXCHANGE_ADAPTERS[exchange_key]()
        
        # Resolve mode
        try:
            mode = get_mode(params["sniper_mode"])
        except ValueError as e:
            raise ValueError(f"Invalid mode: {e}") from e
        
        effective_min = max(params["min_score"], mode.min_confluence_score) if params["min_score"] > 0 else mode.min_confluence_score
        
        # Apply mode to orchestrator
        orchestrator.apply_mode(mode)
        orchestrator.config.min_confluence_score = effective_min
        orchestrator.config.macro_overlay_enabled = params["macro_overlay"]
        orchestrator.exchange_adapter = current_adapter
        orchestrator.ingestion_pipeline = IngestionPipeline(current_adapter)
        
        # Resolve symbols via centralized selector
        symbols = select_symbols(
            adapter=current_adapter,
            limit=params["limit"],
            majors=params["majors"],
            altcoins=params["altcoins"],
            meme_mode=params["meme_mode"],
            leverage=params["leverage"],
        )
        job.total = len(symbols)
        
        # Run scan in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        trade_plans, rejection_summary = await loop.run_in_executor(
            None,  # Uses default ThreadPoolExecutor
            orchestrator.scan,
            symbols
        )
        
        # Transform results
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
                "primary_timeframe": mode.timeframes[-1] if mode.timeframes else "",
                "current_price": plan.entry_zone.near_entry,
                "analysis": {
                    "order_blocks": plan.metadata.get('order_blocks', 0),
                    "fvgs": plan.metadata.get('fvgs', 0),
                    "structural_breaks": plan.metadata.get('structural_breaks', 0),
                    "liquidity_sweeps": plan.metadata.get('liquidity_sweeps', 0),
                    "trend": plan.direction.lower(),
                    "risk_reward": plan.risk_reward,
                    "confluence_score": plan.confluence_breakdown.total_score if hasattr(plan, 'confluence_breakdown') else plan.confidence_score,
                    "expected_value": plan.metadata.get('expected_value')
                },
                "rationale": plan.rationale,
                "setup_type": plan.setup_type,
                "plan_type": getattr(plan, 'plan_type', 'SMC'),
                "conviction_class": getattr(plan, 'conviction_class', None),
                "missing_critical_timeframes": plan.metadata.get('missing_critical_timeframes', []),
                "regime": plan.metadata.get('regime'),
                "macro": plan.metadata.get('macro')
            }
            signals.append(signal)
        
        job.signals = signals
        job.rejections = rejection_summary
        job.metadata = {
            "total": len(signals),
            "scanned": len(symbols),
            "rejected": len(symbols) - len(signals),
            "mode": mode.name,
            "applied_timeframes": mode.timeframes,
            "effective_min_score": effective_min,
            "exchange": exchange_key,
            "leverage": params["leverage"]
        }
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.progress = job.total
        
    except asyncio.CancelledError:
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        raise
    except Exception as e:
        logger.error("Scan job %s failed: %s", job.run_id, e)
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc)


# Market data endpoints (mock for now)
@app.get("/api/market/price/{symbol}")
async def get_price(symbol: str, exchange: str | None = Query(default=None)):
    """Get current price for symbol via selected exchange adapter.

    Falls back to Phemex if no exchange provided. Uses ccxt under the hood.
    """
    try:
        exchange_key = (exchange or 'phemex').lower()
        if exchange_key not in EXCHANGE_ADAPTERS:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange_key}")

        adapter = EXCHANGE_ADAPTERS[exchange_key]()

        request_symbol = symbol
        fetch_symbol = symbol
        # OKX uses suffix ":USDT" for swap markets in ccxt
        if exchange_key == 'okx' and '/USDT' in symbol and ':USDT' not in symbol:
            fetch_symbol = symbol.replace('/USDT', '/USDT:USDT')

        # Use ccxt to fetch ticker
        ticker = adapter.exchange.fetch_ticker(fetch_symbol)
        last_price = ticker.get('last') or ticker.get('close') or 0.0
        ts_ms = ticker.get('timestamp')
        if ts_ms is None:
            # Some exchanges include 'datetime' or none; fallback to now
            dt_iso = datetime.now(timezone.utc).isoformat()
        else:
            try:
                dt_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
            except Exception:
                dt_iso = datetime.now(timezone.utc).isoformat()

        return {
            "symbol": request_symbol,
            "price": float(last_price) if last_price is not None else 0.0,
            "timestamp": dt_iso,
        }

    except HTTPException:
        raise
    except Exception as e:  # Exchange could be geo-blocked or network error
        logger.error("Failed to fetch price for %s on %s: %s", symbol, exchange or 'phemex', e)
        raise HTTPException(status_code=502, detail="Failed to fetch price from exchange") from e


@app.get("/api/market/prices")
async def get_prices(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., BTC/USDT,ETH/USDT)"),
    exchange: str | None = Query(default=None)
):
    """Get current prices for multiple symbols in one request.
    
    Reduces N requests to 1 for watchlists. Returns partial results if some symbols fail.
    """
    try:
        exchange_key = (exchange or 'phemex').lower()
        if exchange_key not in EXCHANGE_ADAPTERS:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange_key}")

        adapter = EXCHANGE_ADAPTERS[exchange_key]()
        symbol_list = [s.strip() for s in symbols.split(',') if s.strip()]
        
        if not symbol_list:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        if len(symbol_list) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 symbols per request")

        results = []
        errors = []
        
        # Parallelize ticker fetches using asyncio
        async def fetch_one(symbol: str):
            # Check cache first
            cache_key = f"{exchange_key}:{symbol}"
            cached = PRICE_CACHE.get(cache_key)
            if cached and (time.time() - cached['cached_at']) < PRICE_CACHE_TTL:
                logger.debug(f"Cache hit for {cache_key}")
                return cached['data'], None
            
            try:
                fetch_symbol = symbol
                # OKX uses suffix ":USDT" for swap markets
                if exchange_key == 'okx' and '/USDT' in symbol and ':USDT' not in symbol:
                    fetch_symbol = symbol.replace('/USDT', '/USDT:USDT')
                
                # Run blocking fetch_ticker in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                ticker = await loop.run_in_executor(None, adapter.exchange.fetch_ticker, fetch_symbol)
                
                last_price = ticker.get('last') or ticker.get('close') or 0.0
                ts_ms = ticker.get('timestamp')
                
                if ts_ms is None:
                    dt_iso = datetime.now(timezone.utc).isoformat()
                else:
                    try:
                        dt_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                    except Exception:
                        dt_iso = datetime.now(timezone.utc).isoformat()
                
                result = {
                    "symbol": symbol,
                    "price": float(last_price) if last_price is not None else 0.0,
                    "timestamp": dt_iso,
                }
                
                # Store in cache
                PRICE_CACHE[cache_key] = {
                    'data': result,
                    'cached_at': time.time()
                }
                
                return result, None
            except Exception as e:
                logger.warning("Failed to fetch price for %s: %s", symbol, e)
                return None, {
                    "symbol": symbol,
                    "error": str(e)
                }
        
        # Fetch all tickers in parallel
        fetch_results = await asyncio.gather(*[fetch_one(sym) for sym in symbol_list])
        
        for result, error in fetch_results:
            if result:
                results.append(result)
            if error:
                errors.append(error)
        
        return {
            "prices": results,
            "total": len(results),
            "errors": errors if errors else None,
            "exchange": exchange_key
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Bulk price fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch prices from exchange") from e


@app.get("/api/market/candles/{symbol}")
async def get_candles(
    symbol: str,
    timeframe: Timeframe = Query(default=Timeframe.H1),
    limit: int = Query(default=100, ge=1, le=1000),
    exchange: str | None = Query(default=None)
):
    """Get candlestick data via selected exchange adapter."""
    try:
        exchange_key = (exchange or 'phemex').lower()
        if exchange_key not in EXCHANGE_ADAPTERS:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange_key}")

        adapter = EXCHANGE_ADAPTERS[exchange_key]()

        fetch_symbol = symbol
        if exchange_key == 'okx' and '/USDT' in symbol and ':USDT' not in symbol:
            fetch_symbol = symbol.replace('/USDT', '/USDT:USDT')

        df = adapter.fetch_ohlcv(fetch_symbol, timeframe.value, limit=limit)
        candles = []
        if not df.empty:
            for _, row in df.iterrows():
                candles.append({
                    'timestamp': row['timestamp'].to_pydatetime().isoformat(),
                    'open': float(row['open']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                })

        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "candles": candles,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch candles for %s on %s: %s", symbol, exchange or 'phemex', e)
        raise HTTPException(status_code=502, detail="Failed to fetch candles from exchange") from e


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
    # Serve API + frontend on port 5000
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
