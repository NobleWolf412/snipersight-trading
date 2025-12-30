"""
Scanner Service - Extracted from api_server.py

Contains scan job management and execution logic:
- ScanJob class for tracking background scans
- ScannerService for job lifecycle management
- Scan execution with orchestrator integration

This centralizes all scan-related logic previously scattered in api_server.py.
"""

import asyncio
import uuid
import threading
import logging
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

from backend.shared.config.scanner_modes import get_mode
from backend.analysis.pair_selection import select_symbols
from backend.data.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


# Type alias for job status
ScanJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


# Configuration constants
SCAN_JOB_MAX_AGE_SECONDS = 3600  # Cleanup jobs older than 1 hour
SCAN_JOB_MAX_COMPLETED = 100  # Keep at most this many completed jobs


@dataclass
class ScanJob:
    """
    Represents a background scan job with full lifecycle tracking.
    
    Attributes:
        run_id: Unique identifier for this scan run
        status: Current job status
        progress: Number of symbols processed
        total: Total symbols to scan
        signals: Generated trading signals (when complete)
        rejections: Rejection summary from orchestrator
        metadata: Additional scan metadata
        error: Error message if failed
        logs: Captured workflow logs for frontend display
    """
    run_id: str
    params: Dict[str, Any]
    status: ScanJobStatus = "queued"
    progress: int = 0
    total: int = 0
    current_symbol: Optional[str] = None
    signals: List[Dict] = field(default_factory=list)
    rejections: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    task: Optional[asyncio.Task] = None
    logs: List[str] = field(default_factory=list)
    
    def to_response(self, include_results: bool = True) -> Dict[str, Any]:
        """Convert to API response format."""
        response = {
            "run_id": self.run_id,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "current_symbol": self.current_symbol,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "logs": self.logs[-100:]  # Return last 100 log entries
        }
        
        if include_results:
            if self.status == "completed":
                response["signals"] = self.signals
                response["metadata"] = self.metadata
                response["rejections"] = self.rejections
            elif self.status == "failed":
                response["error"] = self.error
        
        return response


class ScannerService:
    """
    Manages scan job lifecycle and execution.
    
    This service encapsulates:
    - Job creation and tracking
    - Background scan execution
    - Orchestrator configuration for each scan
    - Cleanup of old jobs
    
    Usage:
        service = ScannerService(
            orchestrator=orchestrator,
            exchange_adapters=EXCHANGE_ADAPTERS,
            log_handler=scan_job_log_handler
        )
        
        # Create a new scan job
        job = await service.create_scan(params)
        
        # Get job status
        job = service.get_job(run_id)
        
        # Cancel a running job
        service.cancel_job(run_id)
    """
    
    def __init__(
        self,
        orchestrator,
        exchange_adapters: Dict[str, Any],
        log_handler = None,
    ):
        """
        Initialize the scanner service.
        
        Args:
            orchestrator: Orchestrator instance for running scans
            exchange_adapters: Dict of exchange adapter factories
            log_handler: Optional log handler to capture scan logs
        """
        self._orchestrator = orchestrator
        self._exchange_adapters = exchange_adapters
        self._log_handler = log_handler
        
        # Job tracking
        self._jobs: Dict[str, ScanJob] = {}
        self._jobs_lock = threading.Lock()
        
        logger.info("ScannerService initialized")
    
    # =========================================================================
    # Job Management
    # =========================================================================
    
    async def create_scan(
        self,
        limit: int = 10,
        min_score: float = 0,
        sniper_mode: str = "recon",
        majors: bool = True,
        altcoins: bool = True,
        meme_mode: bool = False,
        exchange: str = "phemex",
        leverage: int = 1,
        macro_overlay: bool = False,
        market_type: Optional[str] = None
    ) -> ScanJob:
        """
        Create and start a new background scan job.
        
        Returns the created ScanJob immediately. The scan runs in background.
        """
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
            "macro_overlay": macro_overlay,
            "market_type": market_type or "swap" # Default to swap for backward compatibility
        }
        
        job = ScanJob(run_id=run_id, params=params)
        
        with self._jobs_lock:
            self._jobs[run_id] = job
        
        # Start background task
        job.task = asyncio.create_task(self._execute_scan(job))
        
        return job

    def get_job(self, run_id: str) -> Optional[ScanJob]:
        """Get a scan job by ID."""
        with self._jobs_lock:
            return self._jobs.get(run_id)
    
    def list_jobs(self, limit: int = 20) -> List[ScanJob]:
        """List recent scan jobs."""
        with self._jobs_lock:
            jobs = sorted(
                self._jobs.values(),
                key=lambda j: j.created_at,
                reverse=True
            )
            return jobs[:limit]
    
    def cancel_job(self, run_id: str) -> bool:
        """Cancel a running scan job."""
        job = self.get_job(run_id)
        if not job:
            return False
        
        if job.task and not job.task.done():
            job.task.cancel()
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)
            return True
        return False
    
    def cleanup_old_jobs(self):
        """Remove old completed jobs to prevent memory leaks."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=SCAN_JOB_MAX_AGE_SECONDS)
        
        with self._jobs_lock:
            # Remove jobs older than cutoff
            old_ids = [
                run_id for run_id, job in self._jobs.items()
                if job.status in ["completed", "failed", "cancelled"]
                and job.completed_at and job.completed_at < cutoff
            ]
            for run_id in old_ids:
                del self._jobs[run_id]
            
            # Also limit total completed jobs
            completed = [
                j for j in self._jobs.values()
                if j.status in ["completed", "failed", "cancelled"]
            ]
            if len(completed) > SCAN_JOB_MAX_COMPLETED:
                # Sort by completed_at and remove oldest
                completed.sort(key=lambda j: j.completed_at or now)
                for job in completed[:-SCAN_JOB_MAX_COMPLETED]:
                    if job.run_id in self._jobs:
                        del self._jobs[job.run_id]

    async def _execute_scan(self, job: ScanJob):
        """Execute scan in background, updating job status as it progresses."""
        # Set this job as the current log recipient
        if self._log_handler:
            self._log_handler.set_current_job(job)
        
        try:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            
            params = job.params
            
            # Resolve exchange adapter
            exchange_key = params["exchange"].lower()
            if exchange_key not in self._exchange_adapters:
                raise ValueError(f"Unsupported exchange: {exchange_key}")
            
            current_adapter = self._exchange_adapters[exchange_key]()
            
            # Configure adapter for market type (if supported)
            market_type = params.get("market_type", "swap")
            if hasattr(current_adapter, 'default_type'):
                 current_adapter.default_type = market_type
                 logger.info(f"Configured {exchange_key} adapter for {market_type} markets")

            # Resolve mode
            try:
                mode = get_mode(params["sniper_mode"])
            except ValueError as e:
                raise ValueError(f"Invalid mode: {e}") from e
            
            effective_min = (
                max(params["min_score"], mode.min_confluence_score) 
                if params["min_score"] > 0 
                else mode.min_confluence_score
            )
            
            # Apply mode to orchestrator
            self._orchestrator.apply_mode(mode)
            self._orchestrator.config.min_confluence_score = effective_min
            self._orchestrator.config.macro_overlay_enabled = params["macro_overlay"]
            # Inject leverage for proper stop validation
            try:
                setattr(self._orchestrator.config, 'leverage', params["leverage"])
            except Exception:
                pass
            self._orchestrator.exchange_adapter = current_adapter
            self._orchestrator.ingestion_pipeline = IngestionPipeline(current_adapter)
            
            # Resolve symbols via centralized selector
            # Note: select_symbols currently doesn't accept market_type explicitly, 
            # but it uses adapter.get_top_symbols which we updated in IngestionPipeline
            # Wait, select_symbols is a standalone function. We should verify if it uses IngestionPipeline or adapter directly.
            # It uses adapter directly. So we rely on adapter configuration OR pass it if we update select_symbols.
            # For now, let's update select_symbols call to be safe IF we update that function,
            # OR rely on the fact that IngestionPipeline uses adapter.get_top_symbols...
            # Actually, `select_symbols` calls `adapter.get_top_symbols`.
            # We updated `IngestionPipeline` but `select_symbols` is usually separate.
            # Let's check `select_symbols` signature or just configure the adapter (done above).
            # If adapter.default_type is set, get_top_symbols (without args) should use it? 
            # PhemexAdapter.get_top_symbols uses `market_type or self.default_type`. 
            # So setting `current_adapter.default_type = market_type` ABOVE is crucial and sufficient!
            
            # Run symbol selection in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            symbols = await loop.run_in_executor(
                None,
                select_symbols,
                current_adapter,
                params["limit"],
                params["majors"],
                params["altcoins"],
                params["meme_mode"],
                params["leverage"],
                market_type
            )
            job.total = len(symbols)
            
            # Run scan in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            trade_plans, rejection_summary = await loop.run_in_executor(
                None,  # Uses default ThreadPoolExecutor
                self._orchestrator.scan,
                symbols
            )
            
            # Transform results to API format with live price validation
            signals = self._transform_signals(trade_plans, mode, current_adapter)
            
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
        finally:
            # Clear the current job from log handler
            if self._log_handler:
                self._log_handler.set_current_job(None)
    
    def _transform_signals(self, trade_plans: List, mode, adapter=None) -> List[Dict]:
        """
        Transform TradePlan objects to API response format.
        
        Delegates to shared utility for consistent behavior across endpoints.
        """
        from backend.shared.utils.signal_transform import transform_trade_plans_to_signals
        return transform_trade_plans_to_signals(trade_plans, mode, adapter)

    async def get_global_regime_recommendation(self) -> Dict[str, Any]:
        """
        Fetch BTC data and detect global regime to recommend scanner mode.
        """
        from backend.analysis.regime_detector import get_regime_detector
        from backend.strategy.planner.regime_engine import get_mode_recommendation
        from backend.indicators.wrapper import calculate_all_indicators
        
        try:
            # 1. Fetch BTC Data (Market Leader)
            # Use Phemex as reliable default for BTC data
            exchange_key = 'phemex'
            if exchange_key not in self._exchange_adapters:
                # Fallback to first available
                exchange_key = list(self._exchange_adapters.keys())[0]
            
            adapter = self._exchange_adapters[exchange_key]()
            pipeline = IngestionPipeline(adapter)
            
            # Fetch BTC/USDT data (HTF needed for regime)
            # Standardizing on BTC/USDT perps or spot
            symbol = "BTC/USDT"
            btc_data = await asyncio.to_thread(
                pipeline.fetch_multi_timeframe, 
                symbol, 
                ['1d', '4h', '1h', '15m']
            )
            
            if not btc_data or not btc_data.timeframes:
                 return {
                     "mode": "stealth", 
                     "reason": "Market data unavailable.", 
                     "warning": "Could not fetch BTC data for analysis.",
                     "confidence": "low"
                 }
    
            # 2. Calculate Indicators (ATR for volatility)
            # Use local IndicatorService to compute required metrics
            from backend.services.indicator_service import IndicatorService
            ind_service = IndicatorService()
            btc_indicators = ind_service.compute(btc_data)
            
            # 3. Detect Global Regime
            detector = get_regime_detector()
            regime = detector.detect_global_regime(btc_data, btc_indicators)
            
            # 4. Get Recommendation
            rec = get_mode_recommendation(
                 btc_trend=regime.dimensions.trend,
                 btc_volatility=regime.dimensions.volatility,
                 risk_appetite=regime.dimensions.risk_appetite
            )
            
            # Add regime details to response for frontend display
            rec['regime'] = {
                'trend': regime.dimensions.trend,
                'volatility': regime.dimensions.volatility,
                'risk': regime.dimensions.risk_appetite,
                'score': regime.score,
                'composite': regime.composite
            }
            
            return rec
            
        except Exception as e:
            logger.error("Failed to generate regime recommendation: %s", e)
            return {
                "mode": "stealth",
                "reason": "Analysis failed.",
                "warning": str(e),
                "confidence": "low"
            }



# Singleton instance
_scanner_service: Optional[ScannerService] = None


def get_scanner_service() -> Optional[ScannerService]:
    """Get the singleton ScannerService instance."""
    return _scanner_service


def configure_scanner_service(
    orchestrator,
    exchange_adapters: Dict[str, Any],
    log_handler = None
) -> ScannerService:
    """Configure and return the singleton ScannerService."""
    global _scanner_service
    _scanner_service = ScannerService(
        orchestrator=orchestrator,
        exchange_adapters=exchange_adapters,
        log_handler=log_handler
    )
    return _scanner_service
