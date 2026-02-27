"""
Logging utilities for the scanning pipeline.

Provides consistent, structured logging helpers for tracking pipeline flow,
rejections, timing, and debugging information across all components.
"""

import time
from typing import Any, Dict, Optional
from datetime import datetime
from loguru import logger
import json


def log_pipeline_stage(
    stage_name: str,
    symbol: str,
    status: str = "START",
    data: Optional[Dict[str, Any]] = None,
    level: str = "INFO"
) -> None:
    """
    Log a pipeline stage with consistent formatting.
    
    Args:
        stage_name: Name of the pipeline stage (e.g., "DATA_INGESTION", "SMC_DETECTION")
        symbol: Trading symbol being processed
        status: Stage status ("START", "COMPLETE", "FAILED")
        data: Optional additional data to log
        level: Log level ("DEBUG", "INFO", "WARNING", "ERROR")
    """
    log_func = getattr(logger, level.lower(), logger.info)
    
    if status == "START":
        log_func(f"{'─' * 80}")
        log_func(f"🔄 [{stage_name}] Starting for {symbol}")
    elif status == "COMPLETE":
        duration_msg = f" ({data.get('duration_ms', 0):.0f}ms)" if data and 'duration_ms' in data else ""
        log_func(f"✅ [{stage_name}] Completed for {symbol}{duration_msg}")
        if data:
            for key, value in data.items():
                if key != 'duration_ms':
                    log_func(f"   └─ {key}: {value}")
    elif status == "FAILED":
        log_func(f"❌ [{stage_name}] Failed for {symbol}")
        if data:
            log_func(f"   └─ Reason: {data.get('reason', 'Unknown')}")
            if 'error' in data:
                log_func(f"   └─ Error: {data['error']}")


def log_rejection(
    symbol: str,
    stage: str,
    reason: str,
    diagnostics: Optional[Dict[str, Any]] = None,
    level: str = "INFO"
) -> None:
    """
    Log a signal rejection with full diagnostic context.
    
    Args:
        symbol: Trading symbol
        stage: Pipeline stage where rejection occurred
        reason: Human-readable rejection reason
        diagnostics: Detailed diagnostic data
        level: Log level
    """
    log_func = getattr(logger, level.lower(), logger.info)
    
    log_func(f"🚫 REJECTED: {symbol} at {stage}")
    log_func(f"   └─ Reason: {reason}")
    
    if diagnostics:
        log_func(f"   └─ Diagnostics:")
        for key, value in diagnostics.items():
            # Format numbers nicely
            if isinstance(value, float):
                log_func(f"      • {key}: {value:.4f}")
            else:
                log_func(f"      • {key}: {value}")


def log_timing(
    operation_name: str,
    duration_ms: float,
    symbol: Optional[str] = None,
    level: str = "DEBUG"
) -> None:
    """
    Log timing information for performance monitoring.
    
    Args:
        operation_name: Name of the operation being timed
        duration_ms: Duration in milliseconds
        symbol: Optional symbol context
        level: Log level
    """
    log_func = getattr(logger, level.lower(), logger.debug)
    
    symbol_str = f" [{symbol}]" if symbol else ""
    
    if duration_ms < 100:
        emoji = "⚡"  # Fast
    elif duration_ms < 1000:
        emoji = "⏱️"  # Normal
    else:
        emoji = "🐌"  # Slow
    
    log_func(f"{emoji} {operation_name}{symbol_str}: {duration_ms:.0f}ms")


def format_scan_summary(
    symbols_scanned: int,
    signals_generated: int,
    signals_rejected: int,
    duration_sec: float,
    rejection_breakdown: Optional[Dict[str, int]] = None
) -> str:
    """
    Format a scan completion summary.
    
    Args:
        symbols_scanned: Total symbols processed
        signals_generated: Count of signals generated
        signals_rejected: Count of signals rejected
        duration_sec: Total scan duration in seconds
        rejection_breakdown: Optional dict of rejection reasons and counts
    
    Returns:
        Formatted summary string
    """
    pass_rate = (signals_generated / symbols_scanned * 100) if symbols_scanned > 0 else 0
    
    lines = [
        "=" * 80,
        "📊 SCAN SUMMARY",
        "=" * 80,
        f"Symbols Scanned:    {symbols_scanned}",
        f"✅ Signals Generated: {signals_generated} ({pass_rate:.1f}%)",
        f"❌ Signals Rejected:  {signals_rejected} ({100-pass_rate:.1f}%)",
        f"⏱️  Total Duration:    {duration_sec:.2f}s",
        f"⚡ Avg per Symbol:    {duration_sec/symbols_scanned:.2f}s" if symbols_scanned > 0 else "",
    ]
    
    if rejection_breakdown:
        lines.append("")
        lines.append("Rejection Breakdown:")
        for reason, count in sorted(rejection_breakdown.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  • {reason}: {count}")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def log_data_quality(
    symbol: str,
    timeframes_expected: list,
    timeframes_received: list,
    missing_timeframes: list,
    data_completeness: Dict[str, float]
) -> None:
    """
    Log data quality metrics.
    
    Args:
        symbol: Trading symbol
        timeframes_expected: List of expected timeframes
        timeframes_received: List of successfully fetched timeframes
        missing_timeframes: List of missing timeframes
        data_completeness: Dict of timeframe -> completeness percentage
    """
    if missing_timeframes:
        logger.warning(f"⚠️  [{symbol}] Missing timeframes: {', '.join(missing_timeframes)}")
    
    incomplete_tfs = [(tf, pct) for tf, pct in data_completeness.items() if pct < 100]
    if incomplete_tfs:
        logger.warning(f"⚠️  [{symbol}] Incomplete data:")
        for tf, pct in incomplete_tfs:
            logger.warning(f"   └─ {tf}: {pct:.1f}% complete")


def log_pattern_detection_summary(
    symbol: str,
    patterns: Dict[str, int]
) -> None:
    """
    Log SMC pattern detection summary.
    
    Args:
        symbol: Trading symbol
        patterns: Dict of pattern type -> count
    """
    logger.info(f"📐 [{symbol}] Pattern Detection Summary:")
    for pattern_type, count in patterns.items():
        if count > 0:
            logger.info(f"   └─ {pattern_type}: {count}")


def log_confluence_reference(
    symbol: str,
    direction: str,
    final_score: float,
    breakdown_line_number: Optional[int] = None
) -> None:
    """
    Log a reference to the detailed confluence breakdown in the log file.
    
    Args:
        symbol: Trading symbol
        direction: Trade direction
        final_score: Final confluence score
        breakdown_line_number: Optional line number in confluence_breakdown.log
    """
    ref_msg = f" (see line {breakdown_line_number} in confluence_breakdown.log)" if breakdown_line_number else ""
    logger.info(
        f"📊 [{symbol}] Confluence Score: {final_score:.2f}/100 ({direction}){ref_msg}"
    )


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str, symbol: Optional[str] = None):
        self.operation_name = operation_name
        self.symbol = symbol
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        log_timing(self.operation_name, self.duration_ms, self.symbol)
        return False  # Don't suppress exceptions


# Convenience function for timing
def time_operation(operation_name: str, symbol: Optional[str] = None):
    """
    Decorator or context manager for timing operations.
    
    Usage as context manager:
        with time_operation("fetch_data", "BTC/USDT"):
            # ... operation ...
    
    Usage as decorator:
        @time_operation("calculate_indicators")
        def my_function():
            # ... operation ...
    """
    return TimingContext(operation_name, symbol)
