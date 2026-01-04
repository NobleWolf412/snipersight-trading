"""
FastAPI server for SniperSight trading bot.

Provides REST API endpoints for the frontend UI.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging
import asyncio
import time
import threading
import pandas as pd

from backend.risk.position_sizer import PositionSizer
from backend.risk.risk_manager import RiskManager
from backend.bot.executor.paper_executor import PaperExecutor
from backend.bot.paper_trading_service import (
    get_paper_trading_service,
    PaperTradingConfig,
    PaperBotStatus,
)
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.adapters.bybit import BybitAdapter
from backend.data.adapters.okx import OKXAdapter
from backend.data.adapters.bitget import BitgetAdapter
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import EventType
from backend.engine.orchestrator import Orchestrator
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.analysis.pair_selection import select_symbols
from backend.analysis.dominance_service import get_current_dominance, get_dominance_for_macro
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
from backend.routers.scanner import router as scanner_router, configure_scanner_router
from backend.routers.data import router as data_router, configure_data_router
from backend.shared.cache import get_cache_manager
from backend.services.scanner_service import configure_scanner_service, get_scanner_service

logger = logging.getLogger(__name__)


# Custom logging handler to capture orchestrator logs for ScanJob
class ScanJobLogHandler(logging.Handler):
    """Captures logs from orchestrator and appends to current ScanJob."""
    
    def __init__(self):
        super().__init__()
        self.current_job: Optional['ScanJob'] = None
        self._lock = threading.Lock()
        
    def set_current_job(self, job: Optional['ScanJob']):
        """Set the current job to receive logs."""
        with self._lock:
            self.current_job = job
    
    def emit(self, record: logging.LogRecord):
        """Capture log record and append to current job."""
        try:
            with self._lock:
                if self.current_job and record.name.startswith('backend.engine'):
                    # Format the log message
                    msg = self.format(record)
                    # Add to job's log list
                    self.current_job.logs.append(msg)
        except Exception:
            # Never let logging errors break the scanner
            pass


# Global log handler for orchestrator logs
scan_job_log_handler = ScanJobLogHandler()
scan_job_log_handler.setFormatter(logging.Formatter('%(levelname)s | %(message)s'))

# Attach handler to orchestrator logger
orchestrator_logger = logging.getLogger('backend.engine.orchestrator')
orchestrator_logger.addHandler(scan_job_log_handler)
orchestrator_logger.setLevel(logging.INFO)
# Prevent duplicate logs by not propagating to root logger
orchestrator_logger.propagate = False

# Thread-safe price cache with TTL to reduce exchange API load
# Now uses unified CacheManager internally
import threading
from collections import OrderedDict

class ThreadSafeCache:
    """
    Thread-safe LRU cache with TTL support.
    
    LEGACY FACADE: This class now delegates to CacheManager for consistency.
    Kept for backward compatibility with existing code.
    """
    def __init__(self, max_size: int = 1000, ttl: int = 5, namespace: str = 'generic'):
        self._namespace = namespace
        self._cache_mgr = get_cache_manager()
        self._ttl = ttl
        # For backward compatibility, also maintain local storage for non-CacheManager usage patterns
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            if time.time() - entry.get('_cached_at', 0) > self._ttl:
                del self._cache[key]
                return None
            # Move to end (LRU)
            self._cache.move_to_end(key)
            return entry
    
    def set(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            value['_cached_at'] = time.time()
            self._cache[key] = value
            self._cache.move_to_end(key)
            # Evict oldest if over capacity
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

# Use unified cache manager namespaces internally
_cache_manager = get_cache_manager()

# Legacy cache instances for backward compatibility
# These delegate to CacheManager namespaces
PRICE_CACHE = ThreadSafeCache(max_size=1000, ttl=5, namespace='price')
PRICE_CACHE_TTL = 5  # seconds (for backward compat references)

# Cache for expensive landing page endpoints
CYCLES_CACHE = ThreadSafeCache(max_size=50, ttl=300, namespace='cycles')  # 5 minute TTL for cycle data
REGIME_CACHE = ThreadSafeCache(max_size=10, ttl=60, namespace='regime')   # 1 minute TTL for regime data


# Initialize FastAPI app
app = FastAPI(
    title="SniperSight API",
    description="Crypto trading scanner and bot API",
    version="1.0.0"
)

# Enable live symbol classification on startup
from backend.analysis.symbol_classifier import get_classifier

@app.on_event("startup")
async def startup_event():
    """Initialize background services on startup."""
    logger.info("Starting up SniperSight API...")
    
    # Enable live symbol classification (CoinGecko)
    # We do this in a background thread to avoid blocking startup
    classifier = get_classifier()
    classifier.enable_auto_fetch()
    
    def refresh_classifier_cache():
        try:
            logger.info("Initializing symbol classifier cache (live data)...")
            classifier.refresh_cache()
            logger.info("Symbol classifier cache initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize symbol classifier: {e}")
            
    # Run in background to not block server startup
    threading.Thread(target=refresh_classifier_cache, daemon=True).start()

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


# Models moved to routers/scanner.py and shared/models, but Bot models remain here
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
    W1 = "1w"


class BotConfig(BaseModel):
    """Bot trading configuration."""
    exchange: Exchange
    leverage: int = Field(ge=1, le=100)
    risk_per_trade: float = Field(gt=0, le=100)
    max_positions: int = Field(ge=1, le=10)
    stop_loss_pct: float = Field(gt=0, le=100)
    take_profit_pct: float = Field(gt=0, le=1000)


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
scanner_configs: Dict[str, Any] = {}
bot_configs: Dict[str, Any] = {}
active_scanners: Dict[str, bool] = {}
active_bots: Dict[str, bool] = {}

# Background scan job tracking
import asyncio
import uuid
from typing import Literal

ScanJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

# Scan job configuration
SCAN_JOB_MAX_AGE_SECONDS = 3600  # Cleanup jobs older than 1 hour
SCAN_JOB_MAX_COMPLETED = 100  # Keep at most this many completed jobs

# Legacy scan job tracking - Decommissioned in favor of ScannerService
# scan_jobs dict kept for router compatibility but will remain empty
scan_jobs: Dict[str, Any] = {}

scan_jobs_lock = threading.Lock()

# Global orchestrator lock for thread-safe config mutations
orchestrator_lock = threading.Lock()

def cleanup_old_scan_jobs() -> int:
    """Remove completed/failed jobs older than SCAN_JOB_MAX_AGE_SECONDS.
    
    Returns number of jobs cleaned up.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=SCAN_JOB_MAX_AGE_SECONDS)
    cleaned = 0
    
    with scan_jobs_lock:
        # Collect jobs to remove
        to_remove = []
        completed_jobs = []
        
        for run_id, job in scan_jobs.items():
            if job.status in ('completed', 'failed', 'cancelled'):
                completed_jobs.append((job.completed_at or job.created_at, run_id))
                if job.completed_at and job.completed_at < cutoff:
                    to_remove.append(run_id)
                elif job.created_at < cutoff:
                    to_remove.append(run_id)
        
        # Also remove oldest completed if over limit
        completed_jobs.sort()
        if len(completed_jobs) > SCAN_JOB_MAX_COMPLETED:
            excess = len(completed_jobs) - SCAN_JOB_MAX_COMPLETED
            for _, run_id in completed_jobs[:excess]:
                if run_id not in to_remove:
                    to_remove.append(run_id)
        
        for run_id in to_remove:
            del scan_jobs[run_id]
            cleaned += 1
    
    if cleaned > 0:
        logger.info("Cleaned up %d old scan jobs", cleaned)
    
    return cleaned

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

# Configure and include routers with shared dependencies
configure_scanner_router(
    orchestrator=orchestrator,
    orchestrator_lock=orchestrator_lock,
    exchange_adapters=EXCHANGE_ADAPTERS,
    scanner_configs=scanner_configs,
    active_scanners=active_scanners,
    scan_jobs=scan_jobs,
    scan_jobs_lock=scan_jobs_lock,
    ingestion_pipeline_class=IngestionPipeline,
    cleanup_old_scan_jobs_fn=cleanup_old_scan_jobs,
)

configure_data_router(
    exchange_adapters=EXCHANGE_ADAPTERS,
    price_cache=PRICE_CACHE,
    price_cache_ttl=PRICE_CACHE_TTL,
    cycles_cache=CYCLES_CACHE,
    regime_cache=REGIME_CACHE,
    regime_detector=None,  # Will be set on first regime request
    orchestrator=orchestrator,
)

# Configure scanner service for background scan job management
scanner_service = configure_scanner_service(
    orchestrator=orchestrator,
    exchange_adapters=EXCHANGE_ADAPTERS,
    log_handler=scan_job_log_handler
)

app.include_router(scanner_router)
app.include_router(data_router)



import asyncio
import httpx

# ... existing imports ...

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

@app.get("/api/market/btc-ticker")
async def get_btc_ticker_proxy():
    """
    Proxy endpoint to fetch BTC/USDT 24hr ticker from Binance.
    Avoids CORS issues in frontend.
    """
    url = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            # Return normalized data
            return {
                "symbol": "BTCUSDT",
                "lastPrice": data.get("lastPrice", "0"),
                "priceChange": data.get("priceChange", "0"),
                "priceChangePercent": data.get("priceChangePercent", "0"),
                "highPrice": data.get("highPrice", "0"),
                "lowPrice": data.get("lowPrice", "0"),
                "volume": data.get("volume", "0"),
                "quoteVolume": data.get("quoteVolume", "0"),
            }
    except Exception as e:
        print(f"BTC Ticker Error: {e}")
        # Return Fail-Safe Data (don't block UI)
        return {
            "symbol": "BTCUSDT",
            "lastPrice": "0.00",
            "priceChange": "0.00",
            "priceChangePercent": "0.00",
            "highPrice": "0.00",
            "lowPrice": "0.00",
            "volume": "0",
            "quoteVolume": "0",
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
# Scanner endpoints moved to backend/routers/scanner.py



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


# ---------------------------------------------------------------------------
# Paper Trading Endpoints (Training Ground)
# ---------------------------------------------------------------------------

class PaperTradingConfigRequest(BaseModel):
    """Request model for paper trading configuration."""
    exchange: str = "phemex"
    sniper_mode: str = "stealth"
    initial_balance: float = Field(default=10000.0, ge=100, le=1000000)
    risk_per_trade: float = Field(default=2.0, ge=0.1, le=10)
    max_positions: int = Field(default=3, ge=1, le=10)
    leverage: int = Field(default=1, ge=1, le=100)
    duration_hours: int = Field(default=24, ge=0, le=168)  # 0 = manual, max 1 week
    scan_interval_minutes: int = Field(default=5, ge=1, le=60)
    trailing_stop: bool = True
    trailing_activation: float = Field(default=1.5, ge=1.0, le=5.0)
    breakeven_after_target: int = Field(default=1, ge=1, le=3)
    min_confluence: Optional[float] = Field(default=None, ge=0, le=100)
    symbols: List[str] = []
    exclude_symbols: List[str] = []
    slippage_bps: float = Field(default=5.0, ge=0, le=50)
    fee_rate: float = Field(default=0.001, ge=0, le=0.01)


@app.post("/api/paper-trading/start")
async def start_paper_trading(config: PaperTradingConfigRequest):
    """
    Start a paper trading session.
    
    This starts the autonomous paper trading bot which:
    - Runs the scanner at specified intervals
    - Automatically executes trades based on signals
    - Manages positions with SL/TP/trailing stops
    - Tracks P&L and statistics
    """
    try:
        service = get_paper_trading_service()
        
        paper_config = PaperTradingConfig(
            exchange=config.exchange,
            sniper_mode=config.sniper_mode,
            initial_balance=config.initial_balance,
            risk_per_trade=config.risk_per_trade,
            max_positions=config.max_positions,
            leverage=config.leverage,
            duration_hours=config.duration_hours,
            scan_interval_minutes=config.scan_interval_minutes,
            trailing_stop=config.trailing_stop,
            trailing_activation=config.trailing_activation,
            breakeven_after_target=config.breakeven_after_target,
            min_confluence=config.min_confluence,
            symbols=config.symbols,
            exclude_symbols=config.exclude_symbols,
            slippage_bps=config.slippage_bps,
            fee_rate=config.fee_rate
        )
        
        result = await service.start(paper_config)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/paper-trading/stop")
async def stop_paper_trading():
    """
    Stop the paper trading session.
    
    Closes all open positions and returns final statistics.
    """
    try:
        service = get_paper_trading_service()
        result = await service.stop()
        return result
        
    except Exception as e:
        logger.error(f"Failed to stop paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/status")
async def get_paper_trading_status():
    """
    Get current paper trading status.
    
    Returns comprehensive status including:
    - Bot status (running/stopped/idle)
    - Current balance and equity
    - Active positions with P&L
    - Session statistics
    - Recent activity log
    """
    try:
        service = get_paper_trading_service()
        return service.get_status()
        
    except Exception as e:
        logger.error(f"Failed to get paper trading status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/positions")
async def get_paper_trading_positions():
    """Get active paper trading positions."""
    try:
        service = get_paper_trading_service()
        positions = service.get_positions()
        return {"positions": positions, "total": len(positions)}
        
    except Exception as e:
        logger.error(f"Failed to get paper trading positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/history")
async def get_paper_trading_history(limit: int = Query(default=50, ge=1, le=200)):
    """
    Get paper trading trade history.
    
    Returns completed trades with entry/exit details, P&L, and more.
    """
    try:
        service = get_paper_trading_service()
        trades = service.get_trade_history(limit=limit)
        return {"trades": trades, "total": len(trades)}
        
    except Exception as e:
        logger.error(f"Failed to get paper trading history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/activity")
async def get_paper_trading_activity(limit: int = Query(default=100, ge=1, le=500)):
    """
    Get paper trading activity log.
    
    Returns all events: scans, trades opened/closed, errors, etc.
    """
    try:
        service = get_paper_trading_service()
        activity = service.get_activity_log(limit=limit)
        return {"activity": activity, "total": len(activity)}
        
    except Exception as e:
        logger.error(f"Failed to get paper trading activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/paper-trading/reset")
async def reset_paper_trading():
    """
    Reset paper trading to fresh state.
    
    Clears all data including trades, positions, and statistics.
    Must be stopped first.
    """
    try:
        service = get_paper_trading_service()
        result = service.reset()
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reset paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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






# Legacy scan execution logic removed - use ScannerService



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
        # Use adapter's fetch_ticker - adapters handle symbol format internally
        ticker = adapter.fetch_ticker(symbol)
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
                # Use adapter's fetch_ticker - adapters handle symbol format internally
                # Run blocking fetch_ticker in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                ticker = await loop.run_in_executor(None, adapter.fetch_ticker, symbol)
                
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
                PRICE_CACHE.set(cache_key, {
                    'data': result,
                    'cached_at': time.time()
                })
                
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

        # Fetch candles - OKX adapter handles symbol format conversion internally
        df = adapter.fetch_ohlcv(symbol, timeframe.value, limit=limit)
        candles = []
        if not df.empty:
            for _, row in df.iterrows():
                candles.append({
                    'timestamp': row['timestamp'].to_pydatetime().isoformat(),
                    'open': float(row['open']),
                    'high': float(row['high']),
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
async def get_market_regime(symbol: Optional[str] = Query(None, description="Optional symbol for symbol-specific regime (returns global + symbol context)")):
    """
    Get current market regime, optionally for a specific symbol.
    
    Analyzes BTC/USDT market data to determine regime state across
    trend, volatility, liquidity, risk appetite, and derivatives dimensions.
    If symbol is provided, returns global regime with symbol-specific context.
    
    Returns:
        MarketRegime with composite label, score, and dimension breakdown
    """
    # Check cache first (1 minute TTL)
    cache_key = f"regime:{symbol or 'global'}"
    cached = REGIME_CACHE.get(cache_key)
    if cached:
        logger.debug("Returning cached regime data for %s", cache_key)
        return cached
    
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
        
        # Get dominance data
        try:
            btc_dom, alt_dom, stable_dom = get_dominance_for_macro()
        except Exception as dom_err:
            logger.warning("Dominance fetch failed: %s", dom_err)
            btc_dom, alt_dom, stable_dom = 50.0, 35.0, 15.0  # Fallback values
        
        result = {
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
            "dominance": {
                "btc_d": round(btc_dom, 2),
                "alt_d": round(alt_dom, 2),
                "stable_d": round(stable_dom, 2)
            },
            "timestamp": regime.timestamp.isoformat()
        }
        
        # Cache the result
        REGIME_CACHE.set(cache_key, result)
        return result
        
    except Exception as e:
        logger.error("Market regime detection failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Regime detection error: {str(e)}") from e


@app.get("/api/market/fear-greed")
async def get_fear_greed_index():
    """
    Get the Crypto Fear & Greed Index from alternative.me API.
    
    The index ranges from 0 (Extreme Fear) to 100 (Extreme Greed).
    This is a key sentiment indicator for crypto market timing.
    
    Returns:
        value: 0-100 index value
        classification: Extreme Fear / Fear / Neutral / Greed / Extreme Greed
        bottom_line: Trading guidance text based on the index
        timestamp: When the index was last updated
    """
    import httpx
    
    # Check cache first (15 minute TTL - index updates daily but we don't want stale data)
    cache_key = "fear_greed_index"
    cached = REGIME_CACHE.get(cache_key)
    if cached:
        logger.debug("Returning cached fear & greed data")
        return cached
    
    try:
        # Fetch from alternative.me API (free, no key required)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.alternative.me/fng/?limit=1")
            response.raise_for_status()
            data = response.json()
        
        if not data.get("data") or len(data["data"]) == 0:
            raise HTTPException(status_code=502, detail="No data from Fear & Greed API")
        
        fng = data["data"][0]
        value = int(fng.get("value", 50))
        classification = fng.get("value_classification", "Neutral")
        timestamp = fng.get("timestamp")
        
        # Map value to bottom line text
        if value <= 24:
            bottom_line = "Extreme fear presents opportunity. Smart money accumulates when retail panics."
            risk_text = "capitulation selling creating value opportunities"
            sentiment = "EXTREME_FEAR"
        elif value <= 45:
            bottom_line = "Fear persists. The path of least resistance is down until proven otherwise."
            risk_text = "short squeezes on relief rallies"
            sentiment = "FEAR"
        elif value <= 54:
            bottom_line = "Neutral positioning. Wait for directional clarity before committing size."
            risk_text = "choppy price action and false breakouts"
            sentiment = "NEUTRAL"
        elif value <= 75:
            bottom_line = "Greed building. Trail stops tight and reduce leverage on euphoric moves."
            risk_text = "over-leveraged longs getting liquidated on pullbacks"
            sentiment = "GREED"
        else:
            bottom_line = "Extreme greed signals distribution. This is where tops are made."
            risk_text = "a major correction as smart money exits"
            sentiment = "EXTREME_GREED"
        
        result = {
            "value": value,
            "classification": classification,
            "sentiment": sentiment,
            "bottom_line": bottom_line,
            "risk_text": risk_text,
            "timestamp": datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat() if timestamp else datetime.now(timezone.utc).isoformat(),
            "source": "alternative.me"
        }
        
        # Cache the result (15 min TTL)
        REGIME_CACHE.set(cache_key, result)
        return result
        
    except httpx.HTTPError as e:
        logger.error("Fear & Greed API request failed: %s", e)
        # Return fallback neutral value on API failure
        return {
            "value": 50,
            "classification": "Neutral",
            "sentiment": "NEUTRAL",
            "bottom_line": "Sentiment data unavailable. Trade based on price structure.",
            "risk_text": "unknown market conditions",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "fallback",
            "error": str(e)
        }
    except Exception as e:
        logger.error("Fear & Greed processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Fear & Greed error: {str(e)}") from e


@app.get("/api/market/cycles")
async def get_market_cycles(symbol: str = Query("BTC/USDT", description="Symbol to analyze cycles for")):
    """
    Get cycle timing context for a symbol (DCL/WCL tracking).
    
    Analyzes daily/weekly candles to determine:
    - Days since last Daily Cycle Low (DCL) 
    - Days since last Weekly Cycle Low (WCL)
    - Expected windows for next cycle lows
    - Cycle phase (accumulation/markup/distribution/markdown)
    - Cycle translation (LTR/MTR/RTR) - bearish/neutral/bullish bias
    - Stochastic RSI zones for cycle confirmation
    
    Uses Camel Finance methodology:
    - DCL: ~18-28 days typical for crypto
    - WCL: ~35-50 days (nests 2-3 DCLs)
    
    Returns:
        Cycle context with timing, phase, translation, and trade bias
    """
    # Check cache first (5 minute TTL - cycles don't change rapidly)
    cache_key = f"cycles:{symbol}"
    cached = CYCLES_CACHE.get(cache_key)
    if cached:
        logger.debug("Returning cached cycles data for %s", symbol)
        return cached
    
    from backend.strategy.smc.cycle_detector import detect_cycle_context, CycleConfig
    from backend.indicators.momentum import compute_stoch_rsi
    
    try:
        # Use shared ingestion pipeline to leverage cache and global rate limiting
        # instead of spinning up a new uncoordinated adapter instance
        from backend.services.scanner_service import get_scanner_service
        
        pipeline = None
        service = get_scanner_service()
        if service and service._orchestrator:
             pipeline = service._orchestrator.ingestion_pipeline
        
        # Fallback if service not ready (should generally be ready)
        if pipeline:
             # Fetch daily and weekly data efficiently
             # Use 500 limit to hit standard cache tiers
             daily_data = pipeline.fetch_multi_timeframe(
                 symbol, 
                 ["1d"], 
                 limit=500 
             )
             daily_df = daily_data.timeframes.get("1d")
        else:
             # Fallback to direct adapter if no pipeline available (e.g. startup)
             logger.warning("Using direct adapter for cycles (pipeline unavailable)")
             adapter = PhemexAdapter()
             daily_df = adapter.fetch_ohlcv(symbol, "1d", limit=500)
        
        if daily_df is None or len(daily_df) < 50:
            return {
                "symbol": symbol,
                "error": "Insufficient data for cycle analysis",
                "dcl": None,
                "wcl": None,
                "phase": "unknown",
                "translation": "unknown",
                "trade_bias": "NEUTRAL",
                "confidence": 0
            }
        
        # Convert timestamp column to DatetimeIndex (required by cycle_detector)
        if 'timestamp' in daily_df.columns and not isinstance(daily_df.index, pd.DatetimeIndex):
            daily_df = daily_df.set_index('timestamp', drop=False)
        
        # Detect cycle context
        config = CycleConfig()
        cycle_ctx = detect_cycle_context(daily_df, config)
        
        # Also compute stochastic RSI for weekly timeframe to add zone info
        stoch_rsi_k = None
        stoch_rsi_d = None
        stoch_zone = "neutral"
        
        try:
            # Fetch weekly data using pipeline if available
            if pipeline:
                weekly_data = pipeline.fetch_multi_timeframe(symbol, ["1w"], limit=500)
                weekly_df = weekly_data.timeframes.get("1w")
            else:
                # Fallback
                if 'adapter' not in locals():
                    adapter = PhemexAdapter()
                weekly_df = adapter.fetch_ohlcv(symbol, "1w", limit=100)

            if weekly_df is not None and len(weekly_df) >= 34:  # Need enough data for stoch RSI
                # Ensure index for computation
                if 'timestamp' in weekly_df.columns and not isinstance(weekly_df.index, pd.DatetimeIndex):
                    weekly_df = weekly_df.set_index('timestamp', drop=False)
                    
                k_series, d_series = compute_stoch_rsi(weekly_df)
                # Get latest values
                stoch_rsi_k = float(k_series.iloc[-1]) if not k_series.empty else None
                stoch_rsi_d = float(d_series.iloc[-1]) if not d_series.empty else None
                
                if stoch_rsi_k is not None and stoch_rsi_d is not None:
                    # Both lines below 20 = oversold (bullish zone)
                    if stoch_rsi_k < 20 and stoch_rsi_d < 20:
                        stoch_zone = "oversold"
                    # Both lines above 80 = overbought (bearish zone)
                    elif stoch_rsi_k > 80 and stoch_rsi_d > 80:
                        stoch_zone = "overbought"
                    # One or both in middle
                    else:
                        stoch_zone = "neutral"
        except Exception as stoch_err:
            logger.warning("Failed to compute weekly stochRSI: %s", stoch_err)
        
        # Calculate expected windows
        dcl_expected_min = max(0, config.dcl_min_days - (cycle_ctx.dcl_days_since or 0))
        dcl_expected_max = max(0, config.dcl_max_days - (cycle_ctx.dcl_days_since or 0))
        wcl_expected_min = max(0, config.wcl_min_days - (cycle_ctx.wcl_days_since or 0))
        wcl_expected_max = max(0, config.wcl_max_days - (cycle_ctx.wcl_days_since or 0))
        
        # Map enums to strings for JSON
        phase_map = {
            "accumulation": "ACCUMULATION",
            "markup": "MARKUP", 
            "distribution": "DISTRIBUTION",
            "markdown": "MARKDOWN",
            "unknown": "UNKNOWN"
        }
        translation_map = {
            "left_translated": "LEFT_TRANSLATED",
            "mid_translated": "MID_TRANSLATED",
            "right_translated": "RIGHT_TRANSLATED",
            "unknown": "UNKNOWN"
        }
        
        phase_str = phase_map.get(cycle_ctx.phase.value, "UNKNOWN") if cycle_ctx.phase else "UNKNOWN"
        translation_str = translation_map.get(cycle_ctx.translation.value, "UNKNOWN") if cycle_ctx.translation else "UNKNOWN"
        
        result = {
            "symbol": symbol,
            "dcl": {
                "days_since": cycle_ctx.dcl_days_since,
                "price": cycle_ctx.dcl_price,
                "timestamp": cycle_ctx.dcl_timestamp.isoformat() if cycle_ctx.dcl_timestamp else None,
                "confirmation": cycle_ctx.dcl_confirmation.value if cycle_ctx.dcl_confirmation else "unconfirmed",
                "in_zone": cycle_ctx.in_dcl_zone,
                "expected_window": {
                    "min_days": dcl_expected_min,
                    "max_days": dcl_expected_max
                },
                "typical_range": {
                    "min": config.dcl_min_days,
                    "max": config.dcl_max_days
                }
            },
            "wcl": {
                "days_since": cycle_ctx.wcl_days_since,
                "price": cycle_ctx.wcl_price,
                "timestamp": cycle_ctx.wcl_timestamp.isoformat() if cycle_ctx.wcl_timestamp else None,
                "confirmation": cycle_ctx.wcl_confirmation.value if cycle_ctx.wcl_confirmation else "unconfirmed",
                "in_zone": cycle_ctx.in_wcl_zone,
                "expected_window": {
                    "min_days": wcl_expected_min,
                    "max_days": wcl_expected_max
                },
                "typical_range": {
                    "min": config.wcl_min_days,
                    "max": config.wcl_max_days
                }
            },
            "cycle_high": {
                "price": cycle_ctx.cycle_high_price,
                "timestamp": cycle_ctx.cycle_high_timestamp.isoformat() if cycle_ctx.cycle_high_timestamp else None,
                "midpoint_price": cycle_ctx.cycle_midpoint_price
            },
            "phase": phase_str,
            "translation": translation_str,
            "trade_bias": cycle_ctx.trade_bias,
            "confidence": round(cycle_ctx.confidence, 1),
            "stochastic_rsi": {
                "k": round(stoch_rsi_k, 2) if stoch_rsi_k is not None else None,
                "d": round(stoch_rsi_d, 2) if stoch_rsi_d is not None else None,
                "zone": stoch_zone
            },
            "temporal": {
                "score": round(cycle_ctx.temporal_score, 1),
                "is_active_window": cycle_ctx.timing_window_active,
                "day_of_week": datetime.now(timezone.utc).strftime('%A')
            },
            "interpretation": _get_cycle_interpretation(cycle_ctx, stoch_zone),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Cache the result
        CYCLES_CACHE.set(cache_key, result)
        return result
        
    except Exception as e:
        logger.error("Cycle detection failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Cycle detection error: {str(e)}") from e


def _get_cycle_interpretation(cycle_ctx, stoch_zone: str) -> dict:
    """Generate human-readable interpretation of cycle context."""
    messages = []
    severity = "neutral"  # neutral, bullish, bearish, caution
    
    # DCL timing
    if cycle_ctx.dcl_days_since is not None:
        if cycle_ctx.in_dcl_zone:
            messages.append(f"📍 In DCL timing window ({cycle_ctx.dcl_days_since} days into cycle)")
            if cycle_ctx.dcl_confirmation and cycle_ctx.dcl_confirmation.value == "confirmed":
                messages.append("✅ DCL confirmed - accumulation opportunity")
                severity = "bullish"
            else:
                messages.append("⏳ Watching for DCL confirmation")
        elif cycle_ctx.dcl_days_since < 15:
            messages.append(f"🔄 Early in daily cycle ({cycle_ctx.dcl_days_since} days)")
        elif cycle_ctx.dcl_days_since > 28:
            messages.append(f"⚠️ Extended daily cycle ({cycle_ctx.dcl_days_since} days - overdue for DCL)")
            severity = "caution"
    
    # WCL timing  
    if cycle_ctx.wcl_days_since is not None:
        if cycle_ctx.in_wcl_zone:
            messages.append(f"📍 In WCL timing window ({cycle_ctx.wcl_days_since} days)")
            severity = "bullish" if severity != "caution" else "caution"
        elif cycle_ctx.wcl_days_since > 50:
            messages.append(f"⚠️ Extended weekly cycle ({cycle_ctx.wcl_days_since} days)")
    
    # Translation
    if cycle_ctx.translation:
        trans_val = cycle_ctx.translation.value
        if trans_val == "left_translated":
            messages.append("🔴 Left-translated cycle (bearish bias)")
            severity = "bearish"
        elif trans_val == "right_translated":
            messages.append("🟢 Right-translated cycle (bullish bias)")
            severity = "bullish" if severity != "bearish" else "caution"
        elif trans_val == "mid_translated":
            messages.append("🟡 Mid-translated cycle (neutral)")
    
    # Stochastic zone
    if stoch_zone == "oversold":
        messages.append("📉 Weekly StochRSI oversold (both K & D < 20)")
        if severity not in ["bearish", "caution"]:
            severity = "bullish"
    elif stoch_zone == "overbought":
        messages.append("📈 Weekly StochRSI overbought (both K & D > 80)")
        if severity != "bullish":
            severity = "bearish"
    
    # Trade bias
    bias_msg = {
        "LONG": "🎯 Cycle favors LONG entries",
        "SHORT": "🎯 Cycle favors SHORT entries", 
        "NEUTRAL": "⚖️ No clear directional bias from cycles"
    }
    messages.append(bias_msg.get(cycle_ctx.trade_bias, ""))
    
    return {
        "messages": [m for m in messages if m],
        "severity": severity,
        "summary": messages[0] if messages else "Insufficient cycle data"
    }


# ============================================================================
# Symbol Cycle Intelligence Endpoints (Cycle Translation System)
# ============================================================================

@app.get("/api/market/symbol-cycles")
async def get_symbol_cycles(
    symbol: str = Query("BTC/USDT", description="Symbol to analyze"),
    exchange: str = Query("phemex", description="Exchange to fetch data from")
):
    """
    Get cycle intelligence for a specific symbol.
    
    Returns DCL (Daily Cycle Low) and WCL (Weekly Cycle Low) states
    with translation analysis (RTR/MTR/LTR) based on Camel Finance methodology.
    """
    # Check cache first (5 minute TTL)
    cache_key = f"symbol_cycles:{symbol}:{exchange}"
    cached = CYCLES_CACHE.get(cache_key)
    if cached:
        logger.debug("Returning cached symbol cycles for %s", symbol)
        return cached
    
    try:
        from backend.strategy.smc.symbol_cycle_detector import (
            detect_symbol_cycles,
            check_cycle_alerts
        )
        from backend.services.scanner_service import get_scanner_service
        
        # Use shared pipeline for rate limiting
        pipeline = None
        service = get_scanner_service()
        if service and service._orchestrator:
            pipeline = service._orchestrator.ingestion_pipeline
        
        # Fetch daily data (need ~100 days for cycle analysis)
        if pipeline:
            daily_data = pipeline.fetch_multi_timeframe(symbol, ["1d"], limit=500)
            daily_df = daily_data.timeframes.get("1d")
        else:
            logger.warning("Using direct adapter for symbol cycles (pipeline unavailable)")
            adapter = PhemexAdapter()
            daily_df = adapter.fetch_ohlcv(symbol, "1d", limit=120)
        
        if daily_df is None or len(daily_df) < 60:
            return {
                "status": "error",
                "error": f"Insufficient data for {symbol} cycle analysis",
                "data": None
            }
        
        # Ensure proper index
        if 'timestamp' in daily_df.columns and not isinstance(daily_df.index, pd.DatetimeIndex):
            daily_df = daily_df.set_index('timestamp', drop=False)
        
        cycles = detect_symbol_cycles(daily_df, symbol)
        alerts = check_cycle_alerts(cycles)
        
        result = {
            "status": "success",
            "data": {
                **cycles.to_dict(),
                "alerts": [
                    {
                        "type": a.alert_type,
                        "cycle": a.cycle,
                        "message": a.message,
                        "details": a.details
                    }
                    for a in alerts
                ]
            }
        }
        
        # Cache the result
        CYCLES_CACHE.set(cache_key, result)
        return result
        
    except Exception as e:
        logger.error("Symbol cycle detection failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Cycle detection error: {str(e)}") from e


@app.get("/api/market/btc-cycle-context")
async def get_btc_cycle_context():
    """
    Get complete BTC cycle context across all timeframes.
    
    Returns DCL, WCL, and 4-Year Macro Cycle states with alignment assessment.
    BTC serves as the market leader - use this for macro context on any trade.
    """
    # Check cache first (5 minute TTL)
    cache_key = "btc_cycle_context:global"
    cached = CYCLES_CACHE.get(cache_key)
    if cached:
        logger.debug("Returning cached BTC cycle context")
        return cached
    
    try:
        from backend.strategy.smc.symbol_cycle_detector import detect_symbol_cycles
        from backend.strategy.smc.four_year_cycle import (
            get_four_year_cycle_context,
            get_halving_info
        )
        from backend.services.scanner_service import get_scanner_service
        
        # Use shared pipeline for rate limiting
        pipeline = None
        service = get_scanner_service()
        if service and service._orchestrator:
            pipeline = service._orchestrator.ingestion_pipeline
        
        # Fetch BTC daily data
        symbol = "BTC/USDT"
        if pipeline:
            daily_data = pipeline.fetch_multi_timeframe(symbol, ["1d"], limit=500)
            daily_df = daily_data.timeframes.get("1d")
        else:
            logger.warning("Using direct adapter for BTC cycle context (pipeline unavailable)")
            adapter = PhemexAdapter()
            daily_df = adapter.fetch_ohlcv(symbol, "1d", limit=120)
        
        if daily_df is None or len(daily_df) < 60:
            raise HTTPException(status_code=500, detail="Failed to fetch BTC data")
        
        # Ensure proper index
        if 'timestamp' in daily_df.columns and not isinstance(daily_df.index, pd.DatetimeIndex):
            daily_df = daily_df.set_index('timestamp', drop=False)
        
        cycles = detect_symbol_cycles(daily_df, "BTC/USDT")
        fyc = get_four_year_cycle_context()
        halving = get_halving_info()
        
        result = {
            "status": "success",
            "data": {
                "symbol": "BTC/USDT",
                "dcl": cycles.dcl.to_dict(),
                "wcl": cycles.wcl.to_dict(),
                "four_year_cycle": {
                    "days_since_low": fyc.days_since_fyc_low,
                    "cycle_position_pct": round(fyc.cycle_position_pct, 1),
                    "phase": fyc.phase.value.upper(),
                    "phase_progress_pct": round(fyc.phase_progress_pct, 1),
                    "translation": "RTR", # 4YC is structurally Right Translated (Post-Halving Peak)
                    # Apply WCL confirmation filter for macro bias
                    # Don't flip bearish until WCL confirms with LTR + 3-week buffer
                    "macro_bias": _confirm_macro_bias_with_wcl(fyc.macro_bias, cycles.wcl, cycles.dcl),
                    "confidence": round(fyc.confidence, 1),
                    "last_low": {
                        "date": fyc.last_fyc_low_date.isoformat(),
                        "price": fyc.last_fyc_low_price
                    },
                    "expected_next_low": fyc.expected_next_low_date.isoformat(),
                    "is_danger_zone": fyc.is_in_danger_zone,
                    "is_opportunity_zone": fyc.is_in_opportunity_zone
                },
                "halving": {
                    "last_halving_date": halving['last_halving']['date'],
                    "next_halving_date": halving['next_halving']['estimated_date'],
                    "days_since_halving": halving['last_halving']['days_since'],
                    "days_until_halving": halving['next_halving']['days_until'],
                    "halving_history": halving.get('halving_history', [])
                },
                "overall": {
                    "dcl_bias": cycles.dcl.bias,
                    "wcl_bias": cycles.wcl.bias,
                    "macro_bias": fyc.macro_bias,
                    "alignment": _get_btc_alignment(cycles, fyc),
                    "warnings": cycles.warnings
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        # Cache the result
        CYCLES_CACHE.set(cache_key, result)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("BTC cycle context failed: %s", e)
        raise HTTPException(status_code=500, detail=f"BTC cycle error: {str(e)}") from e


def _confirm_macro_bias_with_wcl(raw_macro_bias: str, wcl, dcl) -> str:
    """
    Apply WCL confirmation filter for macro bias.
    
    Rules:
    1. If DCL is RTR (bullish) and WCL is not LTR, stay BULLISH even if 4YC says BEARISH
    2. Only flip to BEARISH if WCL is LTR (left-translated) for at least 3 weeks
    3. Use 3-week buffer (~21 days past the week midpoint) for confirmation
    
    This prevents premature bearish calls when daily cycle is still bullish.
    """
    from backend.strategy.smc.symbol_cycle_detector import Translation
    
    # If raw bias is already BULLISH or NEUTRAL, just return it
    if raw_macro_bias != "BEARISH":
        return raw_macro_bias
    
    # For BEARISH bias, check WCL confirmation
    wcl_is_ltr = wcl.translation == Translation.LTR
    dcl_is_rtr = dcl.translation == Translation.RTR
    
    # 3-week buffer: WCL must be past midpoint by ~21 days AND be LTR
    wcl_midpoint = wcl.midpoint  # typically ~42.5 days
    wcl_buffer_threshold = wcl_midpoint + 21  # ~63.5 days
    wcl_confirmed_ltr = wcl_is_ltr and wcl.bars_since_low >= wcl_buffer_threshold
    
    # If WCL hasn't confirmed LTR with buffer, defer to DCL
    if not wcl_confirmed_ltr:
        # DCL still RTR = stay BULLISH (benefit of the doubt during bull runs)
        if dcl_is_rtr:
            return "BULLISH"
        # DCL is MTR = NEUTRAL
        elif dcl.translation == Translation.MTR:
            return "NEUTRAL"
        # DCL is also LTR = confirm BEARISH (both timeframes agree)
        else:
            return "BEARISH"
    
    # WCL confirmed LTR with buffer → trust the bearish call
    return "BEARISH"


def _get_btc_alignment(cycles, fyc) -> str:
    """Determine alignment of all BTC cycle timeframes."""
    biases = [cycles.dcl.bias, cycles.wcl.bias]
    macro_signal = "LONG" if fyc.macro_bias == "BULLISH" else ("SHORT" if fyc.macro_bias == "BEARISH" else "NEUTRAL")
    biases.append(macro_signal)
    
    long_count = biases.count("LONG")
    short_count = biases.count("SHORT")
    
    if long_count == 3:
        return "ALL_BULLISH"
    elif short_count == 3:
        return "ALL_BEARISH"
    elif long_count >= 2:
        return "MOSTLY_BULLISH"
    elif short_count >= 2:
        return "MOSTLY_BEARISH"
    else:
        return "MIXED"


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


# ============================================================
# OHLCV Cache Management Endpoints
# ============================================================

@app.get("/api/cache/stats")
async def get_cache_stats():
    """
    Get OHLCV cache statistics.
    
    Returns cache hit rate, entry count, and memory usage estimates.
    Useful for monitoring cache effectiveness.
    """
    from backend.data.ohlcv_cache import get_ohlcv_cache
    
    cache = get_ohlcv_cache()
    stats = cache.get_stats()
    
    return {
        "status": "ok",
        "cache": stats,
        "description": (
            f"Cache has {stats['entries']} entries with {stats['hit_rate_pct']}% hit rate. "
            f"Caching {stats['total_candles_cached']} candles across "
            f"{stats['symbols_cached']} symbols and {stats['timeframes_cached']} timeframes."
        )
    }


@app.get("/api/cache/entries")
async def get_cache_entries():
    """
    Get detailed info about each cached entry and when it expires.
    
    Returns list of cached symbol/timeframe pairs with expiration times.
    """
    from backend.data.ohlcv_cache import get_ohlcv_cache
    
    cache = get_ohlcv_cache()
    entries = cache.get_expiration_info()
    
    return {
        "status": "ok",
        "count": len(entries),
        "entries": entries
    }


@app.delete("/api/cache/clear")
async def clear_cache():
    """
    Clear all OHLCV cached data.
    
    Use this to force fresh data fetches on next scan.
    """
    from backend.data.ohlcv_cache import get_ohlcv_cache
    
    cache = get_ohlcv_cache()
    stats_before = cache.get_stats()
    cache.clear()
    
    return {
        "status": "ok",
        "message": f"Cache cleared. Removed {stats_before['entries']} entries."
    }


@app.delete("/api/cache/invalidate/{symbol}")
async def invalidate_symbol_cache(
    symbol: str,
    timeframe: Optional[str] = Query(default=None)
):
    """
    Invalidate cache for a specific symbol.
    
    Args:
        symbol: Symbol to invalidate (e.g., "BTC/USDT")
        timeframe: Optional specific timeframe to invalidate
        
    Use this after a significant price event to ensure fresh data.
    """
    from backend.data.ohlcv_cache import get_ohlcv_cache
    
    # URL decode symbol (/ becomes %2F)
    symbol = symbol.replace("%2F", "/")
    
    cache = get_ohlcv_cache()
    invalidated = cache.invalidate(symbol, timeframe)
    
    if timeframe:
        msg = f"Invalidated {invalidated} cache entry for {symbol} {timeframe}"
    else:
        msg = f"Invalidated {invalidated} cache entries for {symbol}"
    
    return {
        "status": "ok",
        "message": msg,
        "invalidated_count": invalidated
    }


# Serve built frontend at root (only if dist exists - for production)
# IMPORTANT: This MUST be at the end, after all API routes, otherwise it catches /api/* requests
import os
if os.path.exists("dist"):
    app.mount("/", StaticFiles(directory="dist", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    # Serve API + frontend on port 5000
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
