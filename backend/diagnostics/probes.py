"""
Diagnostic Probes for SniperSight Backtest

Defines all 60+ diagnostic probes across 13 pipeline stages.
Each probe validates a specific aspect of the scanner pipeline.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List
import pandas as pd

from .logger import DiagnosticLogger, ProbeCategory, Severity


class ProbeResult(Enum):
    """Result of a probe check."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"  # Not applicable in current context


@dataclass
class ProbeConfig:
    """Configuration for a single probe."""

    id: str
    category: ProbeCategory
    description: str
    severity: Severity
    mode_specific: bool = False
    # Thresholds (optional, probe-specific)
    thresholds: Dict[str, Any] = None


# =============================================================================
# PROBE DEFINITIONS
# =============================================================================

PROBES: Dict[str, ProbeConfig] = {
    # Stage 1: API & Data Fetching
    "API_001": ProbeConfig(
        "API_001", ProbeCategory.API_ERROR, "Phemex rate limit not exceeded", Severity.ERROR
    ),
    "API_002": ProbeConfig(
        "API_002", ProbeCategory.API_SLOW, "API response time < 5s", Severity.WARNING
    ),
    "API_003": ProbeConfig(
        "API_003", ProbeCategory.API_ERROR, "No 5xx errors from exchange", Severity.ERROR
    ),
    "API_004": ProbeConfig(
        "API_004",
        ProbeCategory.DATA_MISSING,
        "Returned candle count matches requested",
        Severity.WARNING,
    ),
    "API_005": ProbeConfig(
        "API_005", ProbeCategory.API_ERROR, "Symbol exists on exchange", Severity.ERROR
    ),
    "API_006": ProbeConfig(
        "API_006",
        ProbeCategory.DATA_INVALID,
        "Ticker price matches latest candle close",
        Severity.WARNING,
    ),
    # Stage 2: Data Ingestion
    "DATA_001": ProbeConfig(
        "DATA_001",
        ProbeCategory.DATA_MISSING,
        "Sufficient candles per TF (min 200)",
        Severity.WARNING,
        mode_specific=True,
    ),
    "DATA_002": ProbeConfig(
        "DATA_002", ProbeCategory.DATA_INVALID, "No gaps > 3 candles in sequence", Severity.WARNING
    ),
    "DATA_003": ProbeConfig(
        "DATA_003",
        ProbeCategory.DATA_INVALID,
        "Timestamps monotonically increasing",
        Severity.ERROR,
    ),
    "DATA_004": ProbeConfig(
        "DATA_004", ProbeCategory.DATA_INVALID, "OHLC validity (high >= low)", Severity.ERROR
    ),
    "DATA_005": ProbeConfig(
        "DATA_005", ProbeCategory.DATA_INVALID, "Volume > 0 for each candle", Severity.WARNING
    ),
    "DATA_006": ProbeConfig(
        "DATA_006",
        ProbeCategory.DATA_STALE,
        "Latest candle within expected window",
        Severity.WARNING,
    ),
    "DATA_007": ProbeConfig(
        "DATA_007", ProbeCategory.DATA_INVALID, "No duplicate timestamps", Severity.ERROR
    ),
    "DATA_008": ProbeConfig(
        "DATA_008", ProbeCategory.DATA_INVALID, "Multi-TF data aligned", Severity.WARNING
    ),
    # Stage 3: Regime Detection
    "REG_001": ProbeConfig(
        "REG_001",
        ProbeCategory.REGIME_INSUFFICIENT_DATA,
        "Candle count >= 200 for regime",
        Severity.WARNING,
        mode_specific=True,
    ),
    "REG_002": ProbeConfig(
        "REG_002",
        ProbeCategory.INDICATOR_OUT_OF_RANGE,
        "Regime score in valid range (0-100)",
        Severity.ERROR,
    ),
    "REG_003": ProbeConfig(
        "REG_003", ProbeCategory.REGIME_UNKNOWN, "Composite regime not UNKNOWN", Severity.WARNING
    ),
    "REG_004": ProbeConfig(
        "REG_004",
        ProbeCategory.DATA_MISSING,
        "Trend/volatility dimensions populated",
        Severity.WARNING,
    ),
    "REG_005": ProbeConfig(
        "REG_005", ProbeCategory.DATA_MISSING, "BTC dominance factored in", Severity.INFO
    ),
    "REG_006": ProbeConfig(
        "REG_006",
        ProbeCategory.MODE_TF_MISMATCH,
        "Regime calc uses correct TF",
        Severity.WARNING,
        mode_specific=True,
    ),
    # Stage 4: Indicators
    "IND_001": ProbeConfig(
        "IND_001", ProbeCategory.INDICATOR_NAN, "ATR > 0 and not NaN", Severity.ERROR
    ),
    "IND_002": ProbeConfig(
        "IND_002", ProbeCategory.INDICATOR_NAN, "EMA values not NaN", Severity.WARNING
    ),
    "IND_003": ProbeConfig(
        "IND_003", ProbeCategory.INDICATOR_OUT_OF_RANGE, "RSI in range 0-100", Severity.ERROR
    ),
    "IND_004": ProbeConfig(
        "IND_004", ProbeCategory.INDICATOR_NAN, "MACD histogram calculated", Severity.WARNING
    ),
    "IND_005": ProbeConfig(
        "IND_005",
        ProbeCategory.INDICATOR_OUT_OF_RANGE,
        "Volume profile POC within range",
        Severity.WARNING,
    ),
    "IND_006": ProbeConfig(
        "IND_006",
        ProbeCategory.INDICATOR_OUT_OF_RANGE,
        "Stochastic RSI in range 0-100",
        Severity.WARNING,
    ),
    "IND_007": ProbeConfig(
        "IND_007", ProbeCategory.INDICATOR_OUT_OF_RANGE, "ADX in range 0-100", Severity.WARNING
    ),
    # Stage 5: SMC Detection
    "SMC_001": ProbeConfig(
        "SMC_001", ProbeCategory.SMC_EMPTY, "OB list not empty when score > 0", Severity.WARNING
    ),
    "SMC_002": ProbeConfig(
        "SMC_002",
        ProbeCategory.SMC_WRONG_TF,
        "OB timeframes match mode config",
        Severity.WARNING,
        mode_specific=True,
    ),
    "SMC_003": ProbeConfig(
        "SMC_003",
        ProbeCategory.SMC_WRONG_TF,
        "BOS/CHoCH on correct TFs",
        Severity.WARNING,
        mode_specific=True,
    ),
    "SMC_004": ProbeConfig(
        "SMC_004",
        ProbeCategory.SMC_HTF_MISMATCH,
        "HTF structure uses HTF data only",
        Severity.ERROR,
        mode_specific=True,
    ),
    "SMC_005": ProbeConfig(
        "SMC_005",
        ProbeCategory.SMC_NOISE,
        "Liquidity sweeps filtered by TF",
        Severity.WARNING,
        mode_specific=True,
    ),
    "SMC_006": ProbeConfig(
        "SMC_006", ProbeCategory.DATA_INVALID, "FVG zones have valid bounds", Severity.ERROR
    ),
    "SMC_007": ProbeConfig(
        "SMC_007", ProbeCategory.LOGIC_ERROR, "OB direction matches structure", Severity.WARNING
    ),
    "SMC_008": ProbeConfig(
        "SMC_008", ProbeCategory.SMC_EMPTY, "Equal highs/lows detection working", Severity.INFO
    ),
    "SMC_009": ProbeConfig(
        "SMC_009", ProbeCategory.SMC_NOISE, "Sweep magnitude significant (>0.2%)", Severity.WARNING
    ),
    "SMC_010": ProbeConfig(
        "SMC_010",
        ProbeCategory.SMC_EMPTY,
        "OB proximity check",
        Severity.WARNING,
        mode_specific=True,
    ),
    # Stage 6: Multi-TF Alignment
    "MTF_001": ProbeConfig(
        "MTF_001",
        ProbeCategory.MTF_CONFLICT,
        "HTF/LTF trend agreement logged",
        Severity.INFO,
        mode_specific=True,
    ),
    "MTF_002": ProbeConfig(
        "MTF_002",
        ProbeCategory.MTF_MISSING_CRITICAL,
        "Critical TF data present",
        Severity.ERROR,
        mode_specific=True,
    ),
    "MTF_003": ProbeConfig(
        "MTF_003",
        ProbeCategory.MODE_TF_MISMATCH,
        "Entry TF <= structure TF",
        Severity.WARNING,
        mode_specific=True,
    ),
    "MTF_004": ProbeConfig(
        "MTF_004",
        ProbeCategory.MODE_TF_MISMATCH,
        "Stop TF appropriate for setup",
        Severity.WARNING,
        mode_specific=True,
    ),
    "MTF_005": ProbeConfig(
        "MTF_005", ProbeCategory.MTF_CONFLICT, "No conflicting signals across TFs", Severity.INFO
    ),
    # Stage 7: Confluence Scoring
    "CONF_001": ProbeConfig(
        "CONF_001", ProbeCategory.CONF_WEIGHT_ERROR, "Factor weights sum to ~100", Severity.ERROR
    ),
    "CONF_002": ProbeConfig(
        "CONF_002", ProbeCategory.CONF_NEGATIVE_SCORE, "No negative factor scores", Severity.ERROR
    ),
    "CONF_003": ProbeConfig(
        "CONF_003",
        ProbeCategory.CONF_BREAKDOWN_MISMATCH,
        "Synergy bonus in range 0-25",
        Severity.WARNING,
    ),
    "CONF_004": ProbeConfig(
        "CONF_004", ProbeCategory.LOGIC_ERROR, "Empty factors penalized", Severity.WARNING
    ),
    "CONF_005": ProbeConfig(
        "CONF_005",
        ProbeCategory.MODE_TF_MISMATCH,
        "Mode threshold applied correctly",
        Severity.WARNING,
        mode_specific=True,
    ),
    "CONF_006": ProbeConfig(
        "CONF_006",
        ProbeCategory.CONF_BREAKDOWN_MISMATCH,
        "Breakdown matches final score",
        Severity.WARNING,
    ),
    "CONF_007": ProbeConfig(
        "CONF_007",
        ProbeCategory.CONF_BREAKDOWN_MISMATCH,
        "HTF alignment bonus applied",
        Severity.INFO,
        mode_specific=True,
    ),
    # Stage 8: Entry Zone
    "ENTRY_001": ProbeConfig(
        "ENTRY_001",
        ProbeCategory.ENTRY_TOO_WIDE,
        "Entry zone width < 2%",
        Severity.WARNING,
        mode_specific=True,
    ),
    "ENTRY_002": ProbeConfig(
        "ENTRY_002",
        ProbeCategory.ENTRY_MISSING,
        "Entry_near and entry_far populated",
        Severity.ERROR,
    ),
    "ENTRY_003": ProbeConfig(
        "ENTRY_003",
        ProbeCategory.ENTRY_OBSOLETE,
        "Entry zone within current range",
        Severity.WARNING,
    ),
    "ENTRY_004": ProbeConfig(
        "ENTRY_004",
        ProbeCategory.ENTRY_OB_VIOLATION,
        "Entry zone respects OB boundaries",
        Severity.WARNING,
    ),
    "ENTRY_005": ProbeConfig(
        "ENTRY_005", ProbeCategory.LOGIC_ERROR, "Entry zone not inside FVG", Severity.INFO
    ),
    "ENTRY_006": ProbeConfig(
        "ENTRY_006", ProbeCategory.ENTRY_OBSOLETE, "Price proximity to entry (< 2%)", Severity.INFO
    ),
    "ENTRY_007": ProbeConfig(
        "ENTRY_007",
        ProbeCategory.MODE_TF_MISMATCH,
        "Entry zone on appropriate TF",
        Severity.WARNING,
        mode_specific=True,
    ),
    "ENTRY_008": ProbeConfig(
        "ENTRY_008", ProbeCategory.ENTRY_OBSOLETE, "Pending entry not triggered", Severity.INFO
    ),
    # Stage 9: Trade Planning
    "PLAN_001": ProbeConfig(
        "PLAN_001",
        ProbeCategory.PLAN_STOP_ENTRY_ERROR,
        "LONG: stop < entry < targets",
        Severity.CRITICAL,
    ),
    "PLAN_002": ProbeConfig(
        "PLAN_002",
        ProbeCategory.PLAN_STOP_ENTRY_ERROR,
        "SHORT: stop > entry > targets",
        Severity.CRITICAL,
    ),
    "PLAN_003": ProbeConfig(
        "PLAN_003",
        ProbeCategory.PLAN_RR_LOW,
        "R:R meets mode minimum",
        Severity.WARNING,
        mode_specific=True,
    ),
    "PLAN_004": ProbeConfig(
        "PLAN_004",
        ProbeCategory.LOGIC_ERROR,
        "ATR-based stop within limits",
        Severity.WARNING,
        mode_specific=True,
    ),
    "PLAN_005": ProbeConfig(
        "PLAN_005",
        ProbeCategory.ENTRY_TOO_WIDE,
        "Entry zone width reasonable",
        Severity.WARNING,
        mode_specific=True,
    ),
    "PLAN_006": ProbeConfig(
        "PLAN_006", ProbeCategory.PLAN_MISSING_TARGETS, "All 3 targets populated", Severity.WARNING
    ),
    "PLAN_007": ProbeConfig(
        "PLAN_007",
        ProbeCategory.PLAN_TARGET_ORDER_ERROR,
        "Targets in correct order",
        Severity.ERROR,
    ),
    "PLAN_008": ProbeConfig(
        "PLAN_008", ProbeCategory.LOGIC_ERROR, "Stop distance >= 0.5 ATR", Severity.WARNING
    ),
    "PLAN_009": ProbeConfig(
        "PLAN_009", ProbeCategory.LOGIC_ERROR, "Stop not inside entry zone", Severity.ERROR
    ),
    "PLAN_010": ProbeConfig(
        "PLAN_010",
        ProbeCategory.MODE_SETUP_MISMATCH,
        "Setup type matches mode",
        Severity.WARNING,
        mode_specific=True,
    ),
    # Stage 10: Risk Validation
    "RISK_001": ProbeConfig(
        "RISK_001",
        ProbeCategory.RISK_REJECTION_UNCLEAR,
        "Rejection reason logged",
        Severity.WARNING,
    ),
    "RISK_002": ProbeConfig(
        "RISK_002", ProbeCategory.RISK_NEAR_MISS, "Near-miss signals tracked", Severity.INFO
    ),
    "RISK_003": ProbeConfig(
        "RISK_003", ProbeCategory.LOGIC_ERROR, "Gate order correct", Severity.ERROR
    ),
    "RISK_004": ProbeConfig(
        "RISK_004",
        ProbeCategory.LOGIC_ERROR,
        "Position size calculated correctly",
        Severity.WARNING,
    ),
    "RISK_005": ProbeConfig(
        "RISK_005",
        ProbeCategory.MODE_SETUP_MISMATCH,
        "Leverage within mode limits",
        Severity.WARNING,
        mode_specific=True,
    ),
    # Stage 11: Mode Enforcement
    "MODE_001": ProbeConfig(
        "MODE_001",
        ProbeCategory.MODE_TF_MISMATCH,
        "Timeframes match mode config",
        Severity.ERROR,
        mode_specific=True,
    ),
    "MODE_002": ProbeConfig(
        "MODE_002",
        ProbeCategory.MTF_MISSING_CRITICAL,
        "Critical TFs being used",
        Severity.ERROR,
        mode_specific=True,
    ),
    "MODE_003": ProbeConfig(
        "MODE_003",
        ProbeCategory.MODE_TF_MISMATCH,
        "Entry TF appropriate for mode",
        Severity.WARNING,
        mode_specific=True,
    ),
    "MODE_004": ProbeConfig(
        "MODE_004",
        ProbeCategory.MODE_SETUP_MISMATCH,
        "Min confluence matches mode",
        Severity.WARNING,
        mode_specific=True,
    ),
    "MODE_005": ProbeConfig(
        "MODE_005",
        ProbeCategory.MODE_SETUP_MISMATCH,
        "Setup type matches mode intent",
        Severity.WARNING,
        mode_specific=True,
    ),
    # Stage 12: Performance
    "PERF_001": ProbeConfig(
        "PERF_001", ProbeCategory.PERF_SLOW_SCAN, "Total scan time < 120s", Severity.WARNING
    ),
    "PERF_002": ProbeConfig(
        "PERF_002", ProbeCategory.PERF_SLOW_SCAN, "SMC detection time < 30s", Severity.WARNING
    ),
    "PERF_003": ProbeConfig(
        "PERF_003", ProbeCategory.API_SLOW, "API fetch time logged", Severity.INFO
    ),
    "PERF_004": ProbeConfig(
        "PERF_004", ProbeCategory.PERF_MEMORY, "Memory usage stable", Severity.WARNING
    ),
    # Stage 13: Execution Simulation
    "EXEC_001": ProbeConfig(
        "EXEC_001", ProbeCategory.EXEC_NO_FILL, "Entry would have filled", Severity.INFO
    ),
    "EXEC_002": ProbeConfig(
        "EXEC_002",
        ProbeCategory.EXEC_NO_FILL,
        "Time to fill reasonable",
        Severity.WARNING,
        mode_specific=True,
    ),
    "EXEC_003": ProbeConfig(
        "EXEC_003", ProbeCategory.EXEC_SLIPPAGE, "Slippage estimate logged", Severity.INFO
    ),
    "EXEC_004": ProbeConfig(
        "EXEC_004", ProbeCategory.LOGIC_ERROR, "TP/SL hit detection accurate", Severity.WARNING
    ),
    "EXEC_005": ProbeConfig(
        "EXEC_005", ProbeCategory.LOGIC_ERROR, "Partial exit logic correct", Severity.WARNING
    ),
}


# =============================================================================
# PROBE RUNNER
# =============================================================================


class ProbeRunner:
    """
    Runs diagnostic probes and logs results.
    """

    def __init__(self, logger: DiagnosticLogger, mode: str):
        self.logger = logger
        self.mode = mode
        self.mode_config = self._get_mode_config(mode)

    def _get_mode_config(self, mode: str) -> Dict[str, Any]:
        """Get mode-specific configuration."""
        # Import here to avoid circular imports
        try:
            from backend.shared.config.scanner_modes import get_mode

            return get_mode(mode)
        except ImportError:
            return {}

    # -------------------------------------------------------------------------
    # Data Probes
    # -------------------------------------------------------------------------

    def check_data_001(self, df: pd.DataFrame, timeframe: str) -> ProbeResult:
        """Check sufficient candles per timeframe."""
        min_required = 200
        if self.mode in ("overwatch", "strike"):
            min_required = 300  # HTF modes need more

        if len(df) < min_required:
            self.logger.warning(
                "DATA_001",
                ProbeCategory.DATA_MISSING,
                f"Insufficient candles: {len(df)} < {min_required} for {timeframe}",
                context={"count": len(df), "min_required": min_required, "timeframe": timeframe},
            )
            return ProbeResult.FAIL
        return ProbeResult.PASS

    def check_data_004(self, df: pd.DataFrame) -> ProbeResult:
        """Check OHLC validity."""
        invalid_rows = df[
            (df["high"] < df["low"])
            | (df["close"] > df["high"])
            | (df["close"] < df["low"])
            | (df["open"] > df["high"])
            | (df["open"] < df["low"])
        ]

        if len(invalid_rows) > 0:
            self.logger.error(
                "DATA_004",
                ProbeCategory.DATA_INVALID,
                f"Invalid OHLC data: {len(invalid_rows)} rows with high < low or close out of range",
                context={"invalid_count": len(invalid_rows), "total_rows": len(df)},
            )
            return ProbeResult.FAIL
        return ProbeResult.PASS

    # -------------------------------------------------------------------------
    # Trade Plan Probes
    # -------------------------------------------------------------------------

    def check_plan_001(
        self, direction: str, entry: float, stop: float, targets: List[float]
    ) -> ProbeResult:
        """Check LONG: stop < entry < targets."""
        if direction.upper() != "LONG":
            return ProbeResult.SKIP

        if stop >= entry:
            self.logger.critical(
                "PLAN_001",
                ProbeCategory.PLAN_STOP_ENTRY_ERROR,
                f"LONG signal has stop ({stop:.4f}) >= entry ({entry:.4f})",
                context={"stop": stop, "entry": entry, "targets": targets},
            )
            return ProbeResult.FAIL

        for i, tp in enumerate(targets):
            if tp <= entry:
                self.logger.error(
                    "PLAN_001",
                    ProbeCategory.PLAN_TARGET_ORDER_ERROR,
                    f"LONG TP{i+1} ({tp:.4f}) <= entry ({entry:.4f})",
                    context={"target_idx": i, "target": tp, "entry": entry},
                )
                return ProbeResult.FAIL

        return ProbeResult.PASS

    def check_plan_002(
        self, direction: str, entry: float, stop: float, targets: List[float]
    ) -> ProbeResult:
        """Check SHORT: stop > entry > targets."""
        if direction.upper() != "SHORT":
            return ProbeResult.SKIP

        if stop <= entry:
            self.logger.critical(
                "PLAN_002",
                ProbeCategory.PLAN_STOP_ENTRY_ERROR,
                f"SHORT signal has stop ({stop:.4f}) <= entry ({entry:.4f})",
                context={"stop": stop, "entry": entry, "targets": targets},
            )
            return ProbeResult.FAIL

        for i, tp in enumerate(targets):
            if tp >= entry:
                self.logger.error(
                    "PLAN_002",
                    ProbeCategory.PLAN_TARGET_ORDER_ERROR,
                    f"SHORT TP{i+1} ({tp:.4f}) >= entry ({entry:.4f})",
                    context={"target_idx": i, "target": tp, "entry": entry},
                )
                return ProbeResult.FAIL

        return ProbeResult.PASS

    def check_plan_rr(self, rr_ratio: float) -> ProbeResult:
        """Check R:R meets mode minimum."""
        min_rr = {"overwatch": 2.0, "strike": 1.8, "surgical": 2.0, "stealth": 1.5}.get(
            self.mode, 1.5
        )

        if rr_ratio < min_rr:
            self.logger.warning(
                "PLAN_003",
                ProbeCategory.PLAN_RR_LOW,
                f"R:R ({rr_ratio:.2f}) below mode minimum ({min_rr})",
                context={"rr": rr_ratio, "min_rr": min_rr, "mode": self.mode},
            )
            return ProbeResult.FAIL
        return ProbeResult.PASS

    # -------------------------------------------------------------------------
    # SMC Probes
    # -------------------------------------------------------------------------

    def check_smc_ob_empty(self, ob_score: float, ob_list: List) -> ProbeResult:
        """Check OB list not empty when score > 0."""
        if ob_score > 0 and (ob_list is None or len(ob_list) == 0):
            self.logger.warning(
                "SMC_001",
                ProbeCategory.SMC_EMPTY,
                f"OB score is {ob_score} but OB list is empty",
                context={"ob_score": ob_score, "ob_count": 0},
            )
            return ProbeResult.FAIL
        return ProbeResult.PASS

    def check_smc_liquidity_sweep_noise(
        self, sweeps: List[Dict], min_magnitude_pct: float = 0.2
    ) -> ProbeResult:
        """Check liquidity sweeps are significant, not noise."""
        if not sweeps:
            return ProbeResult.PASS

        noise_sweeps = []
        for sweep in sweeps:
            magnitude = sweep.get("magnitude_pct", 0)
            tf = sweep.get("timeframe", "")

            # 5m sweeps in Overwatch/Strike are likely noise
            if self.mode in ("overwatch", "strike") and tf in ("5m", "1m"):
                noise_sweeps.append(sweep)
            elif magnitude < min_magnitude_pct:
                noise_sweeps.append(sweep)

        if noise_sweeps:
            self.logger.warning(
                "SMC_005",
                ProbeCategory.SMC_NOISE,
                f"{len(noise_sweeps)} liquidity sweeps appear to be noise",
                context={"noise_count": len(noise_sweeps), "total": len(sweeps), "mode": self.mode},
            )
            return ProbeResult.FAIL
        return ProbeResult.PASS

    # -------------------------------------------------------------------------
    # Regime Probes
    # -------------------------------------------------------------------------

    def check_regime_candle_count(self, candle_count: int) -> ProbeResult:
        """Check sufficient candles for regime calculation."""
        min_required = 200
        if self.mode in ("overwatch",):
            min_required = 300

        if candle_count < min_required:
            self.logger.warning(
                "REG_001",
                ProbeCategory.REGIME_INSUFFICIENT_DATA,
                f"Regime calc only has {candle_count} candles (need {min_required})",
                context={"count": candle_count, "min_required": min_required},
            )
            return ProbeResult.FAIL
        return ProbeResult.PASS

    def check_regime_unknown(self, regime: str) -> ProbeResult:
        """Check regime is not UNKNOWN after calculation."""
        if regime.upper() == "UNKNOWN":
            self.logger.warning(
                "REG_003",
                ProbeCategory.REGIME_UNKNOWN,
                "Regime is UNKNOWN - insufficient data or calculation error",
                context={"regime": regime},
            )
            return ProbeResult.FAIL
        return ProbeResult.PASS

    # -------------------------------------------------------------------------
    # Entry Zone Probes
    # -------------------------------------------------------------------------

    def check_entry_zone_width(
        self, entry_near: float, entry_far: float, current_price: float
    ) -> ProbeResult:
        """Check entry zone width is reasonable."""
        zone_width_pct = abs(entry_far - entry_near) / current_price * 100

        max_width = {"surgical": 1.0, "overwatch": 2.0, "strike": 1.5, "stealth": 2.0}.get(
            self.mode, 2.0
        )

        if zone_width_pct > max_width:
            self.logger.warning(
                "ENTRY_001",
                ProbeCategory.ENTRY_TOO_WIDE,
                f"Entry zone width {zone_width_pct:.2f}% > max {max_width}%",
                context={"width_pct": zone_width_pct, "max_width": max_width, "mode": self.mode},
            )
            return ProbeResult.FAIL
        return ProbeResult.PASS


def get_probe_config(probe_id: str) -> Optional[ProbeConfig]:
    """Get probe configuration by ID."""
    return PROBES.get(probe_id)


def get_all_probes() -> Dict[str, ProbeConfig]:
    """Get all probe configurations."""
    return PROBES.copy()


def get_mode_specific_probes() -> List[str]:
    """Get list of probe IDs that are mode-specific."""
    return [pid for pid, cfg in PROBES.items() if cfg.mode_specific]
