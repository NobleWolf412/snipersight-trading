"""
Diagnostic Logger for SniperSight Backtest System

Provides structured logging with categories for anomaly detection,
JSONL output for streaming, and context capture for debugging.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading


class Severity(Enum):
    """Log severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProbeCategory(Enum):
    """Categories of diagnostic probes."""
    # API & Data
    API_ERROR = "api_error"
    API_SLOW = "api_slow"
    DATA_MISSING = "data_missing"
    DATA_INVALID = "data_invalid"
    DATA_STALE = "data_stale"
    
    # Regime
    REGIME_UNKNOWN = "regime_unknown"
    REGIME_INSUFFICIENT_DATA = "regime_insufficient_data"
    
    # Indicators
    INDICATOR_NAN = "indicator_nan"
    INDICATOR_OUT_OF_RANGE = "indicator_out_of_range"
    
    # SMC
    SMC_EMPTY = "smc_empty"
    SMC_WRONG_TF = "smc_wrong_tf"
    SMC_NOISE = "smc_noise"
    SMC_HTF_MISMATCH = "smc_htf_mismatch"
    
    # Multi-TF
    MTF_CONFLICT = "mtf_conflict"
    MTF_MISSING_CRITICAL = "mtf_missing_critical"
    
    # Confluence
    CONF_WEIGHT_ERROR = "conf_weight_error"
    CONF_NEGATIVE_SCORE = "conf_negative_score"
    CONF_BREAKDOWN_MISMATCH = "conf_breakdown_mismatch"
    
    # Entry Zone
    ENTRY_TOO_WIDE = "entry_too_wide"
    ENTRY_OBSOLETE = "entry_obsolete"
    ENTRY_OB_VIOLATION = "entry_ob_violation"
    ENTRY_MISSING = "entry_missing"
    
    # Trade Planning
    PLAN_STOP_ENTRY_ERROR = "plan_stop_entry_error"
    PLAN_TARGET_ORDER_ERROR = "plan_target_order_error"
    PLAN_RR_LOW = "plan_rr_low"
    PLAN_MISSING_TARGETS = "plan_missing_targets"
    
    # Risk
    RISK_REJECTION_UNCLEAR = "risk_rejection_unclear"
    RISK_NEAR_MISS = "risk_near_miss"
    
    # Mode
    MODE_TF_MISMATCH = "mode_tf_mismatch"
    MODE_SETUP_MISMATCH = "mode_setup_mismatch"
    
    # Performance
    PERF_SLOW_SCAN = "perf_slow_scan"
    PERF_MEMORY = "perf_memory"
    
    # Execution
    EXEC_NO_FILL = "exec_no_fill"
    EXEC_SLIPPAGE = "exec_slippage"
    
    # Generic
    LOGIC_ERROR = "logic_error"
    UNEXPECTED = "unexpected"


@dataclass
class DiagnosticEntry:
    """A single diagnostic log entry."""
    timestamp: str
    probe_id: str
    category: str
    severity: str
    mode: str
    symbol: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    checkpoint_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class DiagnosticLogger:
    """
    Structured diagnostic logger with JSONL output.
    
    Thread-safe and supports:
    - Category-based filtering
    - JSONL streaming output
    - In-memory stats tracking
    - Severity filtering
    """
    
    def __init__(
        self,
        output_dir: Path,
        min_severity: Severity = Severity.INFO,
        console_output: bool = True
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.min_severity = min_severity
        self.console_output = console_output
        
        # Output files
        self.anomalies_file = self.output_dir / "anomalies.jsonl"
        self.trades_file = self.output_dir / "trades.jsonl"
        
        # In-memory tracking
        self._entries: List[DiagnosticEntry] = []
        self._stats: Dict[str, int] = {
            "total": 0,
            "info": 0,
            "warning": 0,
            "error": 0,
            "critical": 0,
        }
        self._category_counts: Dict[str, int] = {}
        self._mode_counts: Dict[str, Dict[str, int]] = {}
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Current context
        self._current_checkpoint_id: Optional[str] = None
        self._current_mode: Optional[str] = None
        self._current_symbol: Optional[str] = None
        
        # Console logger
        self._logger = logging.getLogger("diagnostics")
        if console_output and not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            ))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)
    
    def set_context(
        self,
        checkpoint_id: Optional[str] = None,
        mode: Optional[str] = None,
        symbol: Optional[str] = None
    ):
        """Set current context for subsequent logs."""
        if checkpoint_id is not None:
            self._current_checkpoint_id = checkpoint_id
        if mode is not None:
            self._current_mode = mode
        if symbol is not None:
            self._current_symbol = symbol
    
    def log(
        self,
        probe_id: str,
        category: ProbeCategory,
        severity: Severity,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> DiagnosticEntry:
        """
        Log a diagnostic entry.
        
        Args:
            probe_id: Unique probe identifier (e.g., "PLAN_001")
            category: Category from ProbeCategory enum
            severity: Severity level
            message: Human-readable description
            context: Additional context data
            mode: Override current mode context
            symbol: Override current symbol context
            
        Returns:
            The created DiagnosticEntry
        """
        # Check severity filter
        severity_order = {
            Severity.INFO: 0,
            Severity.WARNING: 1,
            Severity.ERROR: 2,
            Severity.CRITICAL: 3
        }
        if severity_order[severity] < severity_order[self.min_severity]:
            return None
        
        entry = DiagnosticEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            probe_id=probe_id,
            category=category.value,
            severity=severity.value,
            mode=mode or self._current_mode or "unknown",
            symbol=symbol or self._current_symbol or "unknown",
            message=message,
            context=context or {},
            checkpoint_id=self._current_checkpoint_id
        )
        
        with self._lock:
            # Track entry
            self._entries.append(entry)
            
            # Update stats
            self._stats["total"] += 1
            self._stats[severity.value] += 1
            
            # Category counts
            cat_key = category.value
            self._category_counts[cat_key] = self._category_counts.get(cat_key, 0) + 1
            
            # Mode-specific counts
            mode_key = entry.mode
            if mode_key not in self._mode_counts:
                self._mode_counts[mode_key] = {"total": 0, "warning": 0, "error": 0}
            self._mode_counts[mode_key]["total"] += 1
            if severity in (Severity.WARNING, Severity.ERROR, Severity.CRITICAL):
                self._mode_counts[mode_key][severity.value] = \
                    self._mode_counts[mode_key].get(severity.value, 0) + 1
            
            # Write to file
            with open(self.anomalies_file, "a") as f:
                f.write(entry.to_json() + "\n")
        
        # Console output
        if self.console_output:
            icon = {"info": "ℹ️", "warning": "⚠️", "error": "🔴", "critical": "🚨"}
            self._logger.log(
                getattr(logging, severity.value.upper()),
                f"{icon.get(severity.value, '•')} [{probe_id}] {entry.symbol} | {message}"
            )
        
        return entry
    
    # Convenience methods
    def info(self, probe_id: str, category: ProbeCategory, message: str, **kwargs):
        return self.log(probe_id, category, Severity.INFO, message, **kwargs)
    
    def warning(self, probe_id: str, category: ProbeCategory, message: str, **kwargs):
        return self.log(probe_id, category, Severity.WARNING, message, **kwargs)
    
    def error(self, probe_id: str, category: ProbeCategory, message: str, **kwargs):
        return self.log(probe_id, category, Severity.ERROR, message, **kwargs)
    
    def critical(self, probe_id: str, category: ProbeCategory, message: str, **kwargs):
        return self.log(probe_id, category, Severity.CRITICAL, message, **kwargs)
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """Log a trade entry/exit to the trades file."""
        with self._lock:
            with open(self.trades_file, "a") as f:
                trade_data["logged_at"] = datetime.utcnow().isoformat() + "Z"
                f.write(json.dumps(trade_data) + "\n")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        with self._lock:
            return {
                "counts": self._stats.copy(),
                "by_category": self._category_counts.copy(),
                "by_mode": {k: v.copy() for k, v in self._mode_counts.items()},
                "entries_count": len(self._entries)
            }
    
    def get_entries(
        self,
        category: Optional[ProbeCategory] = None,
        severity: Optional[Severity] = None,
        mode: Optional[str] = None,
        limit: int = 100
    ) -> List[DiagnosticEntry]:
        """Get filtered entries."""
        with self._lock:
            filtered = self._entries
            
            if category:
                filtered = [e for e in filtered if e.category == category.value]
            if severity:
                filtered = [e for e in filtered if e.severity == severity.value]
            if mode:
                filtered = [e for e in filtered if e.mode == mode]
            
            return filtered[-limit:]
    
    def save_stats(self):
        """Save current stats to JSON file."""
        stats_file = self.output_dir / "stats.json"
        with open(stats_file, "w") as f:
            json.dump(self.get_stats(), f, indent=2)
