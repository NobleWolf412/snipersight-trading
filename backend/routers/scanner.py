"""
Scanner Router - Extracted from api_server.py

Contains scanner-related endpoints:
- /api/scanner/modes - List available scanner modes
- /api/scanner/pairs - Preview pairs for scanning
- /api/scanner/signals - Execute synchronous scan
- /api/scanner/mode_active - Get active mode state
- /api/scanner/config - Scanner configuration CRUD
- /api/scanner/diagnostics - Debug diagnostics
- /api/config/smc - SMC config get/update

Background scan endpoints:
- /api/scan - Create background scan job
- /api/scan/{run_id} - Get/cancel scan job

Dependencies are injected via get_* functions to avoid circular imports.
"""

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from datetime import datetime, timezone, timedelta
import logging
import asyncio
import threading
from dataclasses import asdict

from backend.services.scanner_service import get_scanner_service
from backend.shared.config.scanner_modes import get_mode, list_modes

from backend.shared.config.smc_config import SMCConfig
from backend.analysis.pair_selection import select_symbols

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scanner"])


# =============================================================================
# Pydantic Models (moved from api_server.py)
# =============================================================================

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



# Copied from api_server.py for consolidation
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



# =============================================================================
# Dependency Injection - Shared state access
# =============================================================================

# These will be set by api_server.py at startup
_shared_state: Dict[str, Any] = {}


def configure_scanner_router(
    orchestrator,
    orchestrator_lock,
    exchange_adapters: Dict,
    scanner_configs: Dict,
    active_scanners: Dict,
    scan_jobs: Dict,
    scan_jobs_lock,
    ingestion_pipeline_class,
    cleanup_old_scan_jobs_fn,
):
    """Configure router with shared dependencies from api_server.py"""
    _shared_state['orchestrator'] = orchestrator
    _shared_state['orchestrator_lock'] = orchestrator_lock
    _shared_state['exchange_adapters'] = exchange_adapters
    _shared_state['scanner_configs'] = scanner_configs
    _shared_state['active_scanners'] = active_scanners
    _shared_state['scan_jobs'] = scan_jobs
    _shared_state['scan_jobs_lock'] = scan_jobs_lock
    _shared_state['IngestionPipeline'] = ingestion_pipeline_class
    _shared_state['cleanup_old_scan_jobs'] = cleanup_old_scan_jobs_fn


def get_orchestrator():
    return _shared_state.get('orchestrator')


def get_orchestrator_lock():
    return _shared_state.get('orchestrator_lock')


def get_exchange_adapters():
    return _shared_state.get('exchange_adapters', {})


def get_scanner_configs():
    return _shared_state.get('scanner_configs', {})


def get_active_scanners():
    return _shared_state.get('active_scanners', {})


# =============================================================================
# Scanner Mode Endpoints
# =============================================================================

@router.get("/api/scanner/modes")
async def get_scanner_modes():
    """List available scanner modes and their characteristics."""
    return {"modes": list_modes(), "total": len(list_modes())}


@router.get("/api/scanner/recommendation")
async def get_scanner_recommendation():
    """Get AI-driven mode recommendation based on market regime."""
    service = get_scanner_service()
    
    # Fallback if dependency injection failed (rare race condition)
    if not service:
        from backend.services.scanner_service import get_scanner_service as fetch_service
        service = fetch_service()
    
    if not service:
        raise HTTPException(status_code=500, detail="Scanner service not initialized")
    
    return await service.get_global_regime_recommendation()


@router.get("/api/scanner/mode_active")
async def get_active_mode():
    """Return current active scanner mode state with critical timeframe expectations."""
    orchestrator = get_orchestrator()
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    try:
        mode = orchestrator.scanner_mode
        return {
            "active_mode": {
                "name": mode.name,
                "profile": mode.profile,
                "timeframes": mode.timeframes,
                "critical_timeframes": mode.critical_timeframes,
                "baseline_min_confluence": mode.min_confluence_score,
                "current_effective_min_confluence": getattr(
                    orchestrator.config, 'min_confluence_score', mode.min_confluence_score
                )
            }
        }
    except Exception as e:
        logger.error("Failed to get active mode: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Scanner Pairs Endpoint
# =============================================================================

@router.get("/api/scanner/pairs")
async def get_scanner_pairs(
    limit: int = Query(default=10, ge=1, le=100),
    majors: bool = Query(default=True),
    altcoins: bool = Query(default=True),
    meme_mode: bool = Query(default=False),
    exchange: str = Query(default="phemex"),
    leverage: int = Query(default=1, ge=1, le=125),
    market_type: str = Query(default="swap", regex="^(spot|swap)$"),
):
    """Preview pairs the scanner would use without running a scan.

    Reuses adapter + centralized selection logic, returns symbols and filter context.
    """
    exchange_adapters = get_exchange_adapters()
    
    try:
        exchange_key = exchange.lower()
        if exchange_key not in exchange_adapters:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported exchange: {exchange}. Supported: {', '.join(exchange_adapters.keys())}",
            )

        adapter = exchange_adapters[exchange_key]()
        
        # Configure adapter default type if supported
        if hasattr(adapter, 'default_type'):
            adapter.default_type = market_type

        symbols = select_symbols(
            adapter=adapter,
            limit=limit,
            majors=majors,
            altcoins=altcoins,
            meme_mode=meme_mode,
            leverage=leverage,
            market_type=market_type,
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


# =============================================================================
# SMC Config Endpoints
# =============================================================================

@router.get("/api/config/smc")
async def get_smc_config():
    """Get current Smart Money Concepts detector configuration."""
    orchestrator = get_orchestrator()
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    return {"smc_config": orchestrator.smc_config.to_dict()}


@router.put("/api/config/smc")
async def update_smc_config(update: SMCConfigUpdate):
    """Update SMC detector configuration at runtime."""
    orchestrator = get_orchestrator()
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
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


# =============================================================================
# Scanner Diagnostics
# =============================================================================

@router.get("/api/scanner/diagnostics")
async def get_scanner_diagnostics():
    """
    Get detailed diagnostics and rejection breakdowns from orchestrator.
    
    Useful for debugging zero-signal scans and understanding quality gate failures.
    Returns per-stage rejection counts and sample failures for deep analysis.
    """
    orchestrator = get_orchestrator()
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    diag = orchestrator.diagnostics
    
    return {
        "diagnostics": {
            "data_failures": {
                "count": len(diag.get('data_failures', [])),
                "samples": diag.get('data_failures', [])[:5]
            },
            "indicator_failures": {
                "count": len(diag.get('indicator_failures', [])),
                "samples": diag.get('indicator_failures', [])[:5]
            },
            "smc_rejections": {
                "count": len(diag.get('smc_rejections', [])),
                "samples": diag.get('smc_rejections', [])[:5]
            },
            "confluence_rejections": {
                "count": len(diag.get('confluence_rejections', [])),
                "samples": diag.get('confluence_rejections', [])[:5]
            },
            "planner_rejections": {
                "count": len(diag.get('planner_rejections', [])),
                "samples": diag.get('planner_rejections', [])[:5]
            },
            "risk_rejections": {
                "count": len(diag.get('risk_rejections', [])),
                "samples": diag.get('risk_rejections', [])[:5]
            }
        },
        "current_mode": {
            "name": getattr(orchestrator.scanner_mode, 'name', 'unknown'),
            "profile": orchestrator.config.profile,
            "min_score": getattr(orchestrator.config, 'min_confluence_score', 0),
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/api/debug/smc")
async def debug_smc_patterns(
    symbol: str = Query(default="BTC/USDT"),
    exchange: str = Query(default="phemex"),
):
    """
    Debug endpoint: Show raw SMC pattern detection counts for a single symbol.
    
    Helps diagnose why OB/FVG/BOS aren't appearing in confluence scoring.
    """
    orchestrator = get_orchestrator()
    exchange_adapters = get_exchange_adapters()
    
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    try:
        exchange_key = exchange.lower()
        if exchange_key not in exchange_adapters:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange}")
        
        adapter = exchange_adapters[exchange_key]()
        IngestionPipeline = _shared_state.get('IngestionPipeline')
        
        if not IngestionPipeline:
            raise HTTPException(status_code=500, detail="Ingestion pipeline not initialized")
        
        pipeline = IngestionPipeline(adapter)
        
        # Fetch data
        timeframes = ['15m', '1h', '4h', '1d']
        multi_tf_data = await asyncio.to_thread(pipeline.fetch_multi_timeframe, symbol, timeframes)
        
        if not multi_tf_data or not multi_tf_data.timeframes:
            raise HTTPException(status_code=400, detail=f"No data for {symbol}")
        
        # Get current price
        current_price = 0.0
        for tf in ['15m', '1h', '4h']:
            df = multi_tf_data.timeframes.get(tf)
            if df is not None and len(df) > 0:
                current_price = float(df['close'].iloc[-1])
                break
        
        # Run SMC detection
        from backend.services.smc_service import SMCDetectionService
        smc_service = SMCDetectionService(orchestrator.smc_config)
        smc_snapshot = smc_service.detect(multi_tf_data, current_price)
        
        # Summarize patterns
        ob_by_dir = {'bullish': 0, 'bearish': 0}
        fvg_by_dir = {'bullish': 0, 'bearish': 0}
        bos_by_type = {'BOS': 0, 'CHoCH': 0}
        
        for ob in smc_snapshot.order_blocks:
            ob_by_dir[ob.direction] = ob_by_dir.get(ob.direction, 0) + 1
        
        for fvg in smc_snapshot.fvgs:
            fvg_by_dir[fvg.direction] = fvg_by_dir.get(fvg.direction, 0) + 1
        
        for sb in smc_snapshot.structural_breaks:
            bos_by_type[sb.break_type] = bos_by_type.get(sb.break_type, 0) + 1
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "smc_counts": {
                "order_blocks": {
                    "total": len(smc_snapshot.order_blocks),
                    "bullish": ob_by_dir.get('bullish', 0),
                    "bearish": ob_by_dir.get('bearish', 0),
                },
                "fvgs": {
                    "total": len(smc_snapshot.fvgs),
                    "bullish": fvg_by_dir.get('bullish', 0),
                    "bearish": fvg_by_dir.get('bearish', 0),
                },
                "structural_breaks": {
                    "total": len(smc_snapshot.structural_breaks),
                    "BOS": bos_by_type.get('BOS', 0),
                    "CHoCH": bos_by_type.get('CHoCH', 0),
                },
                "liquidity_sweeps": len(smc_snapshot.liquidity_sweeps),
                "liquidity_pools": len(smc_snapshot.liquidity_pools),
            },
            "swing_structure": smc_snapshot.swing_structure,
            "key_levels": smc_snapshot.key_levels,
            "diagnostics": smc_service.diagnostics,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("SMC debug failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Configuration Endpoints (Moved from api_server.py)
# =============================================================================

@router.post("/api/scanner/config")
async def create_scanner_config(config: ScannerConfig):
    """Create or update scanner configuration."""
    scanner_configs = get_scanner_configs()
    config_id = f"scanner_{len(scanner_configs) + 1}"
    scanner_configs[config_id] = config
    return {"config_id": config_id, "status": "created"}


@router.get("/api/scanner/config/{config_id}")
async def get_scanner_config(config_id: str):
    """Get scanner configuration."""
    scanner_configs = get_scanner_configs()
    if config_id not in scanner_configs:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return scanner_configs[config_id]


@router.post("/api/scanner/{config_id}/start")
async def start_scanner(config_id: str):
    """Start scanner."""
    scanner_configs = get_scanner_configs()
    active_scanners = get_active_scanners()
    
    if config_id not in scanner_configs:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    active_scanners[config_id] = True
    return {"status": "started", "config_id": config_id}


@router.post("/api/scanner/{config_id}/stop")
async def stop_scanner(config_id: str):
    """Stop scanner."""
    active_scanners = get_active_scanners()
    if config_id not in active_scanners:
        raise HTTPException(status_code=404, detail="Scanner not found")
    
    active_scanners[config_id] = False
    return {"status": "stopped", "config_id": config_id}


# =============================================================================
# Background Job Endpoints (Delegating to ScannerService)
# =============================================================================

@router.post("/api/scanner/runs")
async def create_scan_run(
    limit: int = Query(default=10, ge=1, le=100),
    min_score: float = Query(default=0, ge=0, le=100),
    sniper_mode: str = Query(default="recon"),
    majors: bool = Query(default=True),
    altcoins: bool = Query(default=True),
    meme_mode: bool = Query(default=False),
    exchange: str = Query(default="phemex"),
    leverage: int = Query(default=1, ge=1, le=125),
    macro_overlay: bool = Query(default=False),
    market_type: Optional[str] = Query(default="swap")
):
    """Start a background scan job and return immediately with run_id."""
    service = get_scanner_service()
    if not service:
        # Fallback if service not injected yet, try getter
        from backend.services.scanner_service import get_scanner_service as fetch_service
        service = fetch_service()
    
    if not service:
        raise HTTPException(status_code=500, detail="Scanner service not initialized")
    
    job = await service.create_scan(
        limit=limit,
        min_score=min_score,
        sniper_mode=sniper_mode,
        majors=majors,
        altcoins=altcoins,
        meme_mode=meme_mode,
        exchange=exchange,
        leverage=leverage,
        macro_overlay=macro_overlay,
        market_type=market_type
    )
    
    return {
        "run_id": job.run_id,
        "status": job.status,
        "created_at": job.created_at.isoformat()
    }


@router.get("/api/scanner/runs/{run_id}")
async def get_scan_run(run_id: str):
    """Get status and results of a scan job."""
    service = get_scanner_service() or get_scanner_service_fallback()
    if not service:
        raise HTTPException(status_code=500, detail="Scanner service not initialized")
    
    job = service.get_job(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    
    return job.to_response()


@router.delete("/api/scanner/runs/{run_id}")
async def cancel_scan_run(run_id: str):
    """Cancel a running scan job."""
    service = get_scanner_service() or get_scanner_service_fallback()
    if not service:
        raise HTTPException(status_code=500, detail="Scanner service not initialized")
    
    job = service.get_job(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    
    if job.status in ["completed", "failed", "cancelled"]:
        return {"message": f"Job already {job.status}"}
    
    service.cancel_job(run_id)
    return {"message": "Job cancelled", "run_id": run_id}


def get_scanner_service_fallback():
    from backend.services.scanner_service import get_scanner_service as fetch_service
    return fetch_service()


# =============================================================================
# Synchronous Signals Endpoint (Legacy but maintained)
# =============================================================================

@router.get("/api/scanner/signals")
async def get_signals(
    limit: int = Query(default=10, ge=1, le=100),
    min_score: float = Query(default=0, ge=0, le=100),
    sniper_mode: str = Query(default="recon"),
    majors: bool = Query(default=True),
    altcoins: bool = Query(default=True),
    meme_mode: bool = Query(default=False),
    exchange: str = Query(default="phemex"),
    leverage: int = Query(default=1, ge=1, le=125),
    macro_overlay: bool = Query(default=False),
    market_type: str = Query(default="swap", regex="^(spot|swap)$"),
):
    """Generate trading signals synchronously."""
    orchestrator = get_orchestrator()
    orchestrator_lock = get_orchestrator_lock()
    exchange_adapters = get_exchange_adapters()
    cleanup_old_scan_jobs = _shared_state.get('cleanup_old_scan_jobs')
    IngestionPipeline = _shared_state.get('IngestionPipeline')
    
    if not all([orchestrator, orchestrator_lock, exchange_adapters]):
        raise HTTPException(status_code=500, detail="Scanner components not initialized")

    try:
        # Resolve requested exchange adapter
        exchange_key = exchange.lower()
        if exchange_key not in exchange_adapters:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported exchange: {exchange}. Supported: {', '.join(exchange_adapters.keys())}"
            )
        
        # Create fresh adapter instance for this scan
        current_adapter = exchange_adapters[exchange_key]()
        
        # Configure adapter default type
        if hasattr(current_adapter, 'default_type'):
            current_adapter.default_type = market_type
        
        # Resolve requested mode
        try:
            mode = get_mode(sniper_mode)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Determine effective threshold
        effective_min = max(min_score, mode.min_confluence_score) if min_score > 0 else mode.min_confluence_score

        logger.info("Scan request: mode=%s, exchange=%s, leverage=%dx, market=%s", mode.name, exchange, leverage, market_type)

        # Resolve symbols
        symbols = select_symbols(
            adapter=current_adapter,
            limit=limit,
            majors=majors,
            altcoins=altcoins,
            meme_mode=meme_mode,
            leverage=leverage,
            market_type=market_type,
        )

        with orchestrator_lock:
            # Apply mode safely
            orchestrator.apply_mode(mode)
            orchestrator.config.min_confluence_score = effective_min
            # Inject leverage
            try:
                setattr(orchestrator.config, 'leverage', leverage)
            except Exception:
                pass
            orchestrator.config.macro_overlay_enabled = macro_overlay
            
            # Update exchange adapter
            orchestrator.exchange_adapter = current_adapter
            if IngestionPipeline:
                orchestrator.ingestion_pipeline = IngestionPipeline(current_adapter)

            # Run scan pipeline
            trade_plans, rejection_summary = orchestrator.scan(symbols)
        
        if cleanup_old_scan_jobs:
            cleanup_old_scan_jobs()

        # Transform trade plans to API response format using shared utility
        from backend.shared.utils.signal_transform import transform_trade_plans_to_signals
        rejected_count = len(symbols) - len(trade_plans)
        signals = transform_trade_plans_to_signals(trade_plans, mode, current_adapter)
        
        stale_filtered_count = 0  # Already handled in transform utility

        return {
            "signals": signals,
            "total": len(signals),
            "scanned": len(symbols),
            "rejected": rejected_count,
            "stale_filtered": stale_filtered_count,
            "mode": mode.name,
            "rejections": rejection_summary
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

