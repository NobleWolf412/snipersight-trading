"""
SniperSight Diagnostic Backtest System

Provides comprehensive diagnostic logging, checkpointing, and reporting
for autonomous backtest runs with anomaly detection.
"""

from .logger import DiagnosticLogger, DiagnosticEntry, ProbeCategory, Severity
from .checkpoint import CheckpointManager, Checkpoint
from .probes import ProbeRunner, ProbeResult, ProbeConfig, PROBES, get_probe_config, get_all_probes
from .report import ReportGenerator, ModeStats

__all__ = [
    # Logger
    "DiagnosticLogger",
    "DiagnosticEntry", 
    "ProbeCategory",
    "Severity",
    # Checkpoint
    "CheckpointManager",
    "Checkpoint",
    # Probes
    "ProbeRunner",
    "ProbeResult",
    "ProbeConfig",
    "PROBES",
    "get_probe_config",
    "get_all_probes",
    # Report
    "ReportGenerator",
    "ModeStats",
]