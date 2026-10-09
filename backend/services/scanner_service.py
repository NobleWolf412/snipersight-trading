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
from backend.shared.utils.signal_transform import _sanitize_for_json

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
            "logs": self.logs[-100:],  # Return last 100 log entries
        }

        if include_results:
            if self.status == "completed":
                response["signals"] = self.signals
                response["metadata"] = self.metadata
                response["rejections"] = self.rejections
            elif self.status == "failed":
                response["error"] = self.error

        # Rejection metadata contains NumPy scalars as well as transformed signals.
        # Sanitize the complete publication boundary, not just successful plans.
        return _sanitize_for_json(response)


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
        log_handler=None,
        orchestrator_lock=None,
        regime_reader=None,
    ):
        """
        Initialize the scanner service.

        Args:
            orchestrator: Orchestrator instance for running scans
            exchange_adapters: Dict of exchange adapter factories
            log_handler: Optional log handler to capture scan logs
        """
        self._orchestrator = orchestrator
        self._orchestrator_lock = orchestrator_lock if orchestrator_lock is not None else threading.Lock()
        self._exchange_adapters = exchange_adapters
        self._log_handler = log_handler
        self._regime_reader = regime_reader
        # Do not fill the shared thread pool with workers waiting for one engine.
        self._worker_slots = asyncio.Semaphore(1)

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
        sniper_mode: str = "stealth",
        majors: bool = True,
        altcoins: bool = True,
        meme_mode: bool = False,
        exchange: str = "phemex",
        leverage: int = 1,
        macro_overlay: bool = False,
        market_type: Optional[str] = None,
        target_symbol: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ScanJob:
        """
        Create and start a new background scan job.

        Returns the created ScanJob immediately. The scan runs in background.
        """
        run_id = str(uuid.UUID(request_id)) if request_id else str(uuid.uuid4())
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
            "market_type": market_type or "swap",  # Default to swap for backward compatibility
            "target_symbol": target_symbol,
        }

        job = ScanJob(run_id=run_id, params=params)

        with self._jobs_lock:
            existing = self._jobs.get(run_id)
            if existing is not None:
                if existing.params != params:
                    raise ValueError("Scan request identity already belongs to different parameters")
                return existing
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
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return jobs[:limit]

    def cancel_job(self, run_id: str) -> bool:
        """Cancel publication immediately without releasing an active worker's lock."""
        with self._jobs_lock:
            job = self._jobs.get(run_id)
            if not job or job.status in ("completed", "failed", "cancelled"):
                return False
            if job.task and not job.task.done():
                job.status = "cancelled"
                job.completed_at = datetime.now(timezone.utc)
                job.task.cancel()
                return True
        return False

    def cleanup_old_jobs(self):
        """Remove old completed jobs to prevent memory leaks."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=SCAN_JOB_MAX_AGE_SECONDS)

        with self._jobs_lock:
            # Remove jobs older than cutoff
            old_ids = [
                run_id
                for run_id, job in self._jobs.items()
                if job.status in ["completed", "failed", "cancelled"]
                and job.completed_at
                and job.completed_at < cutoff
            ]
            for run_id in old_ids:
                del self._jobs[run_id]

            # Also limit total completed jobs
            completed = [
                j for j in self._jobs.values() if j.status in ["completed", "failed", "cancelled"]
            ]
            if len(completed) > SCAN_JOB_MAX_COMPLETED:
                # Sort by completed_at and remove oldest
                completed.sort(key=lambda j: j.completed_at or now)
                for job in completed[:-SCAN_JOB_MAX_COMPLETED]:
                    if job.run_id in self._jobs:
                        del self._jobs[job.run_id]

    async def _execute_scan(self, job: ScanJob):
        """Cancelled callers leave admission and engine ownership with the worker."""
        try:
            await self._worker_slots.acquire()
            try:
                worker = asyncio.get_running_loop().run_in_executor(None, self._run_scan, job)
            except BaseException:
                self._worker_slots.release()
                raise

            def worker_finished(future):
                self._worker_slots.release()
                if not future.cancelled() and future.exception() is not None:
                    logger.error("Scan worker %s failed: %s", job.run_id, future.exception())

            worker.add_done_callback(worker_finished)
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            with self._jobs_lock:
                job.status = "cancelled"
                job.completed_at = datetime.now(timezone.utc)
            raise
        except Exception as exc:
            logger.error("Scan job %s could not run: %s", job.run_id, exc)
            with self._jobs_lock:
                if job.status != "cancelled":
                    job.status = "failed"
                    job.error = str(exc)
                    job.completed_at = datetime.now(timezone.utc)

    def _run_scan(self, job: ScanJob):
        """Serialize configuration, selection, execution and publication."""
        with self._orchestrator_lock:
            # This worker owns the shared engine until physical execution finishes.
            with self._jobs_lock:
                if job.status == "cancelled":
                    return
                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
            # Set this job as the current log recipient
            if self._log_handler:
                self._log_handler.set_current_job(job)

            try:
                params = job.params

                # Resolve exchange adapter
                exchange_key = params["exchange"].lower()
                if exchange_key not in self._exchange_adapters:
                    raise ValueError(f"Unsupported exchange: {exchange_key}")

                current_adapter = self._exchange_adapters[exchange_key]()

                # Configure adapter for market type (if supported)
                market_type = params.get("market_type", "swap")
                if callable(getattr(current_adapter, "set_market_type", None)):
                    current_adapter.set_market_type(market_type)
                elif hasattr(current_adapter, "default_type"):
                    current_adapter.default_type = market_type
                    logger.info(f"Configured {exchange_key} adapter for {market_type} markets")

                # Resolve mode
                try:
                    mode = get_mode(params["sniper_mode"])
                except ValueError as e:
                    raise ValueError(f"Invalid mode: {e}") from e

                effective_min = max(params["min_score"], mode.min_confluence_score)

                # Apply mode to orchestrator
                self._orchestrator.apply_mode(mode)
                self._orchestrator.config.min_confluence_score = effective_min
                self._orchestrator.config.macro_overlay_enabled = params["macro_overlay"]
                # Inject leverage for proper stop validation
                try:
                    setattr(self._orchestrator.config, "leverage", params["leverage"])
                except Exception as e:
                    logger.warning(
                        "Failed to inject leverage=%s into orchestrator config: %s. "
                        "Defaulting to 1x to prevent incorrect stop sizing.",
                        params.get("leverage"),
                        e,
                    )
                    try:
                        setattr(self._orchestrator.config, "leverage", 1)
                    except Exception:
                        pass
                self._orchestrator.exchange_adapter = current_adapter
                self._orchestrator.ingestion_pipeline = IngestionPipeline(current_adapter)

                # Resolve symbols via centralized selector (or use target_symbol if provided)
                target_symbol = params.get("target_symbol")
                if target_symbol:
                    logger.info(f"Targeted scan for single symbol: {target_symbol}")
                    symbols = [target_symbol]
                else:
                    symbols = select_symbols(
                        current_adapter,
                        params["limit"],
                        params["majors"],
                        params["altcoins"],
                        params["meme_mode"],
                        params["leverage"],
                        market_type,
                    )

                if not symbols:
                    raise ValueError("No symbols selected for scanning")
                job.total = len(symbols)

                # Define progress callback to update job state
                def update_progress(completed: int, total: int, current_symbol: str):
                    with self._jobs_lock:
                        if job.status == "cancelled":
                            return
                        job.progress = completed
                        job.current_symbol = current_symbol
                    logger.debug("Scan progress: %d/%d - %s", completed, total, current_symbol)

                with self._jobs_lock:
                    if job.status == "cancelled":
                        return
                trade_plans, rejection_summary = self._orchestrator.scan(symbols, update_progress)

                # Transform results to API format with live price validation
                signals, rejected_signals = self._transform_signals(trade_plans, mode, current_adapter)

                # Merge late rejections (e.g. price validation)
                stale_filtered_count = len(rejected_signals)

                if stale_filtered_count > 0:
                    rejection_summary["total_rejected"] += stale_filtered_count
                    # Ensure risk_validation key exists
                    if "risk_validation" not in rejection_summary["by_reason"]:
                        rejection_summary["by_reason"]["risk_validation"] = 0
                    rejection_summary["by_reason"]["risk_validation"] += stale_filtered_count

                    if "risk_validation" in rejection_summary["details"]:
                        rejection_summary["details"]["risk_validation"].extend(rejected_signals)

                with self._jobs_lock:
                    if job.status == "cancelled":
                        return
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
                        "leverage": params["leverage"],
                    }
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc)
                    job.progress = job.total

            except Exception as e:
                logger.error("Scan job %s failed: %s", job.run_id, e)
                with self._jobs_lock:
                    if job.status != "cancelled":
                        job.status = "failed"
                        job.error = str(e)
                        job.completed_at = datetime.now(timezone.utc)
            finally:
                # Clear the current job from log handler
                if self._log_handler:
                    self._log_handler.set_current_job(None)

    def _transform_signals(self, trade_plans: List, mode, adapter=None) -> tuple:
        """
        Transform TradePlan objects to API response format.

        Delegates to shared utility for consistent behavior across endpoints.
        """
        from backend.shared.utils.signal_transform import transform_trade_plans_to_signals

        return transform_trade_plans_to_signals(trade_plans, mode, adapter)

    async def get_global_regime_recommendation(self) -> Dict[str, Any]:
        """Recommend a mode using a private fixed-source market context."""
        if self._regime_reader is None:
            from backend.services.market_regime_service import MarketRegimeService
            factory = self._exchange_adapters.get("phemex")
            if factory is None:
                from backend.analysis.mode_recommendation import unavailable_recommendation
                return unavailable_recommendation("Market reader is not configured.")
            self._regime_reader = MarketRegimeService(factory)
        return await self._regime_reader.get_recommendation()


# Singleton instance
_scanner_service: Optional[ScannerService] = None


def get_scanner_service() -> Optional[ScannerService]:
    """Get the singleton ScannerService instance."""
    return _scanner_service


def configure_scanner_service(
    orchestrator, exchange_adapters: Dict[str, Any], log_handler=None, orchestrator_lock=None,
    regime_reader=None,
) -> ScannerService:
    """Configure the service with the same ownership lock as synchronous callers."""
    global _scanner_service
    _scanner_service = ScannerService(
        orchestrator=orchestrator, exchange_adapters=exchange_adapters,
        log_handler=log_handler, orchestrator_lock=orchestrator_lock, regime_reader=regime_reader,
    )
    return _scanner_service
