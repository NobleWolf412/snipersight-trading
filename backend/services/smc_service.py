"""
SMC Detection Service - Smart Money Concepts pattern detection extracted from orchestrator.py

Detects all SMC patterns across timeframes:
- Order Blocks
- Fair Value Gaps (FVGs)
- Structure Breaks (BOS/CHoCH)
- Liquidity Sweeps
- Equal Highs/Lows (Liquidity Pools)
- Swing Structure (HH/HL/LH/LL)
- Premium/Discount Zones
- Key Levels (PDH/PDL/PWH/PWL)

This service encapsulates SMC detection logic previously in
orchestrator._detect_smc_patterns()
"""

import logging
import pandas as pd
from typing import Dict, List, Any, Optional

from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import SMCSnapshot
from backend.shared.config.smc_config import SMCConfig, get_tf_smc_config, MODE_SWEEP_TIMEFRAMES

# SMC Detection functions
from backend.strategy.smc.order_blocks import (
    detect_order_blocks,
    detect_order_blocks_structural,
    detect_obs_from_bos,
    update_ob_lifecycle,
    filter_to_active_obs,
    filter_overlapping_order_blocks,
    filter_obs_by_mode,  # NEW: Mode-specific OB filtering
)
from backend.strategy.smc.fvg import detect_fvgs, merge_consecutive_fvgs
from backend.strategy.smc.bos_choch import (
    detect_structural_breaks,
    _detect_swing_highs,
    _detect_swing_lows,
)
from backend.strategy.smc.liquidity_sweeps import (
    detect_liquidity_sweeps,
    detect_equal_highs_lows,
    track_pool_sweeps,
)
from backend.strategy.smc.swing_structure import detect_swing_structure
from backend.strategy.smc.mitigation_tracker import update_ob_mitigation
from backend.strategy.smc.consolidation_detector import detect_consolidations
from backend.indicators.volatility import compute_atr

# Analysis functions
from backend.analysis.premium_discount import detect_premium_discount
from backend.analysis.key_levels import detect_key_levels

logger = logging.getLogger(__name__)


class SMCDetectionService:
    """
    Service for detecting Smart Money Concepts (SMC) patterns.

    Centralizes all SMC pattern detection with proper error handling
    and consistent return types.

    Usage:
        service = SMCDetectionService(smc_config=config)
        snapshot = service.detect(multi_tf_data, current_price)
    """

    def __init__(self, smc_config: Optional[SMCConfig] = None, mode: str = "strike"):
        """
        Initialize SMC detection service.

        Args:
            smc_config: SMC configuration for detection parameters
            mode: Scanner mode for TF-aware thresholds (strike/surgical/overwatch/stealth)
        """
        self._smc_config = smc_config or SMCConfig()
        self._mode = mode.lower()

        # Map scanner mode to profile for SMC filtering
        MODE_TO_PROFILE = {
            "overwatch": "macro_surveillance",
            "stealth": "stealth_balanced",
            "strike": "intraday_aggressive",
            "surgical": "precision",
        }
        self._mode_profile = MODE_TO_PROFILE.get(self._mode, "stealth_balanced")
        self._diagnostics: Dict[str, list] = {"smc_rejections": []}
        self._filter_stats: Dict[str, int] = {}  # Track filter statistics

    @property
    def diagnostics(self) -> Dict[str, list]:
        """Get diagnostic information from last detection."""
        return self._diagnostics

    def update_config(self, config: SMCConfig, mode: Optional[str] = None):
        """Update SMC configuration dynamically."""
        self._smc_config = config
        if mode:
            self._mode = mode.lower()

    def _create_tf_smc_config(self, tf_config: dict) -> SMCConfig:
        """
        Create a timeframe-specific SMC config by merging base config with TF overrides.

        This ensures TF-specific thresholds (like ob_min_wick_ratio for 15m) actually
        get applied during pattern detection.

        Args:
            tf_config: Dict from get_tf_smc_config() with TF-specific overrides

        Returns:
            SMCConfig with merged values
        """
        from dataclasses import asdict

        # Start with base config values
        base_dict = asdict(self._smc_config)

        # Map TF config keys to SMCConfig field names
        key_mappings = {
            "ob_min_wick_ratio": "min_wick_ratio",
            "ob_min_displacement_atr": "min_displacement_atr",
            "fvg_min_gap_atr": "fvg_min_gap_atr",
            "structure_min_break_distance_atr": "structure_min_break_distance_atr",
            "structure_swing_lookback": "structure_swing_lookback",
            "sweep_min_reversal_atr": "sweep_min_reversal_atr",
        }

        # Apply TF overrides
        for tf_key, config_key in key_mappings.items():
            if tf_key in tf_config:
                base_dict[config_key] = tf_config[tf_key]

        # Create new SMCConfig with merged values
        return SMCConfig(**base_dict)

    def detect(self, multi_tf_data: MultiTimeframeData, current_price: float) -> SMCSnapshot:
        """
        Detect Smart Money Concept patterns across all timeframes.

        Args:
            multi_tf_data: Multi-timeframe OHLCV data
            current_price: Current market price (for P/D and key levels)

        Returns:
            SMCSnapshot with all detected patterns
        """
        self._diagnostics = {"smc_rejections": []}
        self._filter_stats = {}  # Reset filter stats

        # Log SMC config for diagnostics
        logger.info(
            "🔧 SMC Detection Config: mode=%s | OB_wick=%.1f | OB_disp=%.1f ATR | FVG_gap=%.2f ATR | struct_lookback=%d",
            self._mode,
            self._smc_config.min_wick_ratio,
            self._smc_config.min_displacement_atr,
            self._smc_config.fvg_min_gap_atr,
            self._smc_config.structure_swing_lookback,
        )

        # Log data quality
        tf_data_summary = " | ".join(
            [f"{tf}={len(df)} candles" for tf, df in multi_tf_data.timeframes.items()]
        )
        logger.info("📊 Data Quality: %s", tf_data_summary)

        # Aggregate patterns across timeframes
        all_order_blocks = []
        all_fvgs = []
        all_structure_breaks = []
        all_liquidity_sweeps = []
        all_equal_highs = []
        all_equal_lows = []
        all_liquidity_pools: List = []
        all_consolidations: List = []  # NEW
        swing_structure_by_tf = {}
        premium_discount_by_tf = {}

        for timeframe, df in multi_tf_data.timeframes.items():
            if df.empty or len(df) < 20:
                continue

            try:
                # CRITICAL FIX: Global deduplication of columns
                # Prevents "truth value of DataFrame is ambiguous" errors in all detectors
                if not df.columns.is_unique:
                    df = df.loc[:, ~df.columns.duplicated()]

                # CRITICAL: Ensure DataFrame has DatetimeIndex (required for OB detection)
                if not isinstance(df.index, pd.DatetimeIndex):
                    # Auto-fix: Set timestamp column as index if available
                    if "timestamp" in df.columns:
                        # Convert timestamp column to datetime and set as index
                        df = df.copy()  # Avoid modifying original
                        df["timestamp"] = pd.to_datetime(
                            df["timestamp"], unit="ms", errors="coerce"
                        )
                        df = df.set_index("timestamp")
                        logger.info(
                            "🔧 SMC %s: Converted timestamp column to DatetimeIndex", timeframe
                        )
                    else:
                        # Try to infer datetime from numeric index
                        logger.warning(
                            "⚠️ SMC %s: No timestamp column, skipping (index type: %s)",
                            timeframe,
                            type(df.index).__name__,
                        )
                        continue

                # Detect core SMC patterns
                patterns = self._detect_timeframe_patterns(timeframe, df, current_price)

                all_order_blocks.extend(patterns["order_blocks"])
                all_fvgs.extend(patterns["fvgs"])
                all_structure_breaks.extend(patterns["structure_breaks"])
                all_liquidity_sweeps.extend(patterns["liquidity_sweeps"])
                all_equal_highs.extend(patterns["equal_highs"])
                all_equal_lows.extend(patterns["equal_lows"])
                all_liquidity_pools.extend(patterns["liquidity_pools"])
                all_consolidations.extend(patterns["consolidations"])  # NEW

                if patterns["swing_structure"]:
                    swing_structure_by_tf[timeframe] = patterns["swing_structure"]
                if patterns["premium_discount"]:
                    premium_discount_by_tf[timeframe] = patterns["premium_discount"]

                # Log SMC detections per timeframe with grade breakdown
                ob_by_grade = self._count_by_grade(patterns["order_blocks"])
                fvg_by_grade = self._count_by_grade(patterns["fvgs"])
                struct_by_grade = self._count_by_grade(patterns["structure_breaks"])
                sweep_by_grade = self._count_by_grade(patterns["liquidity_sweeps"])

                logger.info(
                    "📦 %s OBs: %d total (A=%d B=%d C=%d)",
                    timeframe,
                    len(patterns["order_blocks"]),
                    ob_by_grade["A"],
                    ob_by_grade["B"],
                    ob_by_grade["C"],
                )
                logger.info(
                    "🔲 %s FVGs: %d total (A=%d B=%d C=%d)",
                    timeframe,
                    len(patterns["fvgs"]),
                    fvg_by_grade["A"],
                    fvg_by_grade["B"],
                    fvg_by_grade["C"],
                )
                logger.info(
                    "📐 %s Structure: %d total (BOS=%d CHoCH=%d)",
                    timeframe,
                    len(patterns["structure_breaks"]),
                    sum(1 for s in patterns["structure_breaks"] if s.break_type == "BOS"),
                    sum(1 for s in patterns["structure_breaks"] if s.break_type == "CHoCH"),
                )
                logger.info(
                    "💧 %s Sweeps: %d total (A=%d B=%d C=%d)",
                    timeframe,
                    len(patterns["liquidity_sweeps"]),
                    sweep_by_grade["A"],
                    sweep_by_grade["B"],
                    sweep_by_grade["C"],
                )

            except Exception as e:
                logger.warning("SMC detection failed for %s: %s", timeframe, e)
                self._diagnostics["smc_rejections"].append(
                    {"timeframe": timeframe, "error": str(e)}
                )
                continue

        # --- Post-Detection Filters ---

        # 1. Filter LTF Order Blocks without HTF Backing (Fix #2)
        # Prevents "floating" 5m/15m OBs in empty space being used for signals
        # SKIP for Surgical mode - precision entries can use isolated LTF OBs
        # (confluence scoring will still penalize weak setups)
        skip_htf_backing_filter = self._mode in ("surgical", "precision")

        if skip_htf_backing_filter:
            logger.debug("⏭️ HTF backing filter SKIPPED for %s mode", self._mode)
        else:
            ltf_tfs = {"1m", "5m", "15m"}
            htf_tfs = {"1h", "1H", "4h", "4H", "1d", "1D", "1w", "1W"}

            # Build HTF zones index for fast lookup
            htf_zones = []
            for ob in all_order_blocks:
                if ob.timeframe in htf_tfs:
                    # HTF OB Zone
                    htf_zones.append(
                        {"min": ob.low, "max": ob.high, "dir": ob.direction, "type": "OB"}
                    )
            for fvg in all_fvgs:
                if fvg.timeframe in htf_tfs:
                    # HTF FVG Zone
                    top = fvg.top
                    bottom = fvg.bottom
                    htf_zones.append(
                        {
                            "min": min(top, bottom),
                            "max": max(top, bottom),
                            "dir": fvg.direction,
                            "type": "FVG",
                        }
                    )

            validated_obs = []
            for ob in all_order_blocks:
                # If it's an LTF OB, require backing
                if ob.timeframe in ltf_tfs:
                    has_backing = False
                    for zone in htf_zones:
                        # Must match direction (Bullish OB inside Bullish HTF Zone)
                        if zone["dir"] == ob.direction:
                            # Check for overlap (even partial)
                            # Zone Min <= OB High AND Zone Max >= OB Low
                            if zone["min"] <= ob.high and zone["max"] >= ob.low:
                                has_backing = True
                                break

                    if has_backing:
                        validated_obs.append(ob)
                    else:
                        # Log rejection debug (reduced noise)
                        # logger.debug("Refined: Rejected isolated %s %s OB at %s (no HTF backing)",
                        #             ob.timeframe, ob.direction, ob.low)
                        pass
                else:
                    # HTF/MTF OBs pass through
                    validated_obs.append(ob)

            all_order_blocks = validated_obs

        # Deduplicate equal highs/lows
        unique_equal_highs = list(set(all_equal_highs))
        unique_equal_lows = list(set(all_equal_lows))

        if unique_equal_highs or unique_equal_lows:
            logger.info(
                "💧 Liquidity pools: %d equal highs, %d equal lows",
                len(unique_equal_highs),
                len(unique_equal_lows),
            )

        # Log final summary with filter statistics
        total_obs = len(all_order_blocks)
        total_fvgs = len(all_fvgs)
        total_structs = len(all_structure_breaks)
        total_sweeps = len(all_liquidity_sweeps)

        logger.info("=" * 60)
        logger.info("📊 SMC DETECTION SUMMARY (ALL TIMEFRAMES)")
        logger.info("=" * 60)
        logger.info(
            "📦 Order Blocks: %d total (A=%d B=%d C=%d)",
            total_obs,
            sum(1 for ob in all_order_blocks if ob.grade == "A"),
            sum(1 for ob in all_order_blocks if ob.grade == "B"),
            sum(1 for ob in all_order_blocks if ob.grade == "C"),
        )
        logger.info(
            "🔲 FVGs: %d total (A=%d B=%d C=%d)",
            total_fvgs,
            sum(1 for fvg in all_fvgs if fvg.grade == "A"),
            sum(1 for fvg in all_fvgs if fvg.grade == "B"),
            sum(1 for fvg in all_fvgs if fvg.grade == "C"),
        )
        logger.info(
            "📐 Structure Breaks: %d total (BOS=%d CHoCH=%d)",
            total_structs,
            sum(1 for s in all_structure_breaks if s.break_type == "BOS"),
            sum(1 for s in all_structure_breaks if s.break_type == "CHoCH"),
        )
        logger.info("💧 Liquidity Sweeps: %d total", total_sweeps)
        logger.info("💧 Liquidity Pools: %d total", len(all_liquidity_pools))

        # Log filter statistics if any filtering occurred
        if self._filter_stats:
            logger.info("🔍 FILTER STATS:")
            for key, value in self._filter_stats.items():
                logger.info("  - %s: %d", key, value)
        logger.info("=" * 60)

        # Log liquidity pools summary
        self._log_liquidity_pools_summary(all_liquidity_pools)

        # Log HTF swing structure summary
        self._log_swing_structure_summary(swing_structure_by_tf)

        # Detect key levels (PDH/PDL/PWH/PWL)
        key_levels_data = self._detect_key_levels(multi_tf_data, current_price)

        # Update OB mitigation
        all_order_blocks = self._update_mitigation(multi_tf_data, all_order_blocks)

        # --- Phase 2: Mode-specific sweep TF filtering ---
        sweep_tfs = MODE_SWEEP_TIMEFRAMES.get(self._mode, ("4h", "1h"))
        unfiltered_count = len(all_liquidity_sweeps)
        all_liquidity_sweeps = [
            s
            for s in all_liquidity_sweeps
            if getattr(s, "timeframe", "1h").lower() in [tf.lower() for tf in sweep_tfs]
        ]
        if unfiltered_count > 0 and len(all_liquidity_sweeps) < unfiltered_count:
            logger.debug(
                "💧 Sweep TF filter (%s): %d → %d sweeps",
                self._mode,
                unfiltered_count,
                len(all_liquidity_sweeps),
            )

        # --- Phase 5: Build HTF sweep context for LTF entries ---
        htf_sweep_context = self._build_htf_sweep_context(all_liquidity_sweeps)

        return SMCSnapshot(
            order_blocks=all_order_blocks,
            fvgs=all_fvgs,
            structural_breaks=all_structure_breaks,
            liquidity_sweeps=all_liquidity_sweeps,
            equal_highs=unique_equal_highs,
            equal_lows=unique_equal_lows,
            liquidity_pools=all_liquidity_pools,
            consolidations=all_consolidations,  # NEW
            swing_structure=swing_structure_by_tf,
            premium_discount=premium_discount_by_tf,
            key_levels=key_levels_data,
            htf_sweep_context=htf_sweep_context,  # NEW: for LTF synergy bonus
        )

    def _detect_timeframe_patterns(
        self, timeframe: str, df, current_price: float
    ) -> Dict[str, Any]:
        """Detect all SMC patterns for a single timeframe."""
        result = {
            "order_blocks": [],
            "fvgs": [],
            "structure_breaks": [],
            "liquidity_sweeps": [],
            "equal_highs": [],
            "equal_lows": [],
            "liquidity_pools": [],
            "consolidations": [],  # NEW
            "swing_structure": None,
            "premium_discount": None,
        }

        # Get TF-aware config with mode overrides
        tf_config = get_tf_smc_config(timeframe, self._mode)

        # Create a TF-specific SMC config by merging base config with TF overrides
        # This ensures thresholds like ob_min_wick_ratio from tf_config actually get used
        tf_smc_config = self._create_tf_smc_config(tf_config)

        # Calculate ATR for FVG merge
        try:
            atr = compute_atr(df, period=14)
            atr_val = atr.iloc[-1] if len(atr) > 0 and pd.notna(atr.iloc[-1]) else 0

            # Log market state for diagnostics
            if atr_val > 0:
                atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0
                logger.info(
                    "📊 %s Market: ATR=%.4f | ATR%%=%.3f%% | Price=%.2f",
                    timeframe,
                    atr_val,
                    atr_pct,
                    current_price,
                )
            else:
                logger.warning(
                    "⚠️ %s Market: ATR=0 (insufficient data for volatility calc)", timeframe
                )
        except Exception as e:
            logger.warning("⚠️ %s ATR calculation failed: %s", timeframe, e)
            atr_val = 0

        # Swing detection for structural OBs
        swing_lookback = tf_config.get(
            "structure_swing_lookback", getattr(self._smc_config, "structure_swing_lookback", 10)
        )
        swing_highs = _detect_swing_highs(df, swing_lookback)
        swing_lows = _detect_swing_lows(df, swing_lookback)

        # Order blocks (skip if detect_ob=False for this TF)
        if tf_config.get("detect_ob", True):
            try:
                # Use TF-specific config with adjusted thresholds
                result["order_blocks"] = detect_order_blocks(df, tf_smc_config)
                logger.debug(
                    "📦 %s: Traditional OB detected %d", timeframe, len(result["order_blocks"])
                )
            except Exception as e:
                logger.warning("📦 %s: Traditional OB detection FAILED: %s", timeframe, e)
                result["order_blocks"] = []

            try:
                structural_obs = detect_order_blocks_structural(
                    df, swing_highs, swing_lows, tf_smc_config
                )
                result["order_blocks"].extend(structural_obs)
                logger.debug("📦 %s: Structural OB detected %d", timeframe, len(structural_obs))
            except Exception as e:
                logger.warning("📦 %s: Structural OB detection FAILED: %s", timeframe, e)

            # NEW: Detect OBs from BOS events (Grade A - structure-confirmed)
            try:
                bos_obs = detect_obs_from_bos(df, result["structure_breaks"], tf_smc_config)
                result["order_blocks"].extend(bos_obs)
                logger.debug("📦 %s: BOS-linked OB detected %d", timeframe, len(bos_obs))
            except Exception as e:
                logger.warning("📦 %s: BOS-linked OB detection FAILED: %s", timeframe, e)

            # Deduplicate overlapping OBs (prefer stronger ones)
            if result["order_blocks"]:
                result["order_blocks"] = filter_overlapping_order_blocks(
                    result["order_blocks"], max_overlap=0.7
                )

                # NEW: Mode-specific filtering (Gap #1 - SMC Enhancements)
                # Filter OBs by mode requirements (TF, mitigation, freshness)
                from datetime import datetime

                pre_filter_count = len(result["order_blocks"])

                # Track for UI stats
                self._filter_stats["ob_detected"] = (
                    self._filter_stats.get("ob_detected", 0) + pre_filter_count
                )

                result["order_blocks"] = filter_obs_by_mode(
                    result["order_blocks"],
                    mode_profile=self._mode_profile,
                    current_time=datetime.now(),
                )
                filtered_count = pre_filter_count - len(result["order_blocks"])
                if filtered_count > 0:
                    logger.debug(
                        "📦 %s: Mode filter (%s) removed %d OBs",
                        timeframe,
                        self._mode_profile,
                        filtered_count,
                    )
        else:
            logger.debug("📦 %s: OB detection SKIPPED (TF filter)", timeframe)

        # Fair value gaps (use TF-specific config for gap thresholds)
        if tf_config.get("detect_fvg", True):
            # NEW: Pass mode_profile for size filtering (Gap #2)
            fvgs_raw = detect_fvgs(df, tf_smc_config, mode_profile=None)  # Get unfiltered count
            fvgs = detect_fvgs(df, tf_smc_config, mode_profile=self._mode_profile)

            # Track for UI stats
            self._filter_stats["fvg_detected"] = self._filter_stats.get("fvg_detected", 0) + len(
                fvgs_raw
            )

            if atr_val > 0:
                fvgs = merge_consecutive_fvgs(fvgs, max_gap_atr=0.5, atr_value=atr_val)
            result["fvgs"] = fvgs

        # Structure breaks (use TF-specific config for break distance thresholds)
        if tf_config.get("detect_bos", True):
            # NEW: Pass mode_profile for volume filtering (Gap #4)
            result["structure_breaks"] = detect_structural_breaks(
                df, tf_smc_config, mode_profile=self._mode_profile
            )
        else:
            logger.debug("📐 %s: BOS detection SKIPPED (TF filter)", timeframe)

        # Liquidity sweeps (use TF-specific config for sweep thresholds)
        if tf_config.get("detect_sweep", True):
            try:
                sweeps_raw = detect_liquidity_sweeps(df, tf_smc_config, mode_profile=None)
                sweeps = detect_liquidity_sweeps(df, tf_smc_config, mode_profile=self._mode_profile)

                # Track for UI stats
                self._filter_stats["sweep_detected"] = self._filter_stats.get(
                    "sweep_detected", 0
                ) + len(sweeps_raw)

                # Set timeframe on each sweep for TF filtering and HTF context
                from dataclasses import replace

                result["liquidity_sweeps"] = [
                    replace(s, timeframe=timeframe.lower()) for s in sweeps
                ]
            except Exception as e:
                logger.warning("💧 %s: Sweep detection FAILED: %s", timeframe, e)
                result["liquidity_sweeps"] = []
        else:
            logger.debug("💧 %s: Sweep detection SKIPPED (TF filter)", timeframe)

        # --- LuxAlgo-style OB filtering (MODE-AWARE) ---
        # Keep raw OBs for liquidity analysis, filter to active for trading signals
        if result["order_blocks"]:
            raw_count = len(result["order_blocks"])
            result["raw_order_blocks"] = result["order_blocks"].copy()

            # MODE-AWARE filtering rules:
            # OBs persist until MITIGATED (price closes beyond range)
            # Structure confirmation is used for SCORING (confluence), not visibility
            # This ensures bearish OBs are visible for resistance detection
            tf_lower = timeframe.lower()
            is_htf = tf_lower in ("1w", "1d", "4h")
            is_ltf = tf_lower in ("15m", "5m")

            # Mitigation thresholds - HTF OBs are more sacred
            if is_htf:
                max_mit = 0.7  # HTF OBs can take more damage before invalidation
            elif is_ltf:
                max_mit = 0.8  # LTF OBs are quicker to invalidate
            else:
                max_mit = 0.75  # MTF (1H)

            # Apply filter - NO structure confirmation required for visibility
            # OBs live until mitigated, structure confirmation affects scoring only
            result["order_blocks"] = filter_to_active_obs(
                result["order_blocks"],
                df,
                structure_breaks=result["structure_breaks"],
                max_mitigation=max_mit,
                require_structure_confirmation=False,  # FIXED: OBs persist until mitigated
                confirmation_window_candles=10,
            )

            logger.debug(
                "🎯 %s: OB filtered %d → %d (active, mitig_threshold=%.2f, mode=%s)",
                timeframe,
                raw_count,
                len(result["order_blocks"]),
                max_mit,
                self._mode,
            )

        # Equal highs/lows (liquidity pools)
        self._detect_equal_highs_lows(timeframe, df, result)

        # Swing structure (for HTF bias)
        if timeframe.lower() in ("1w", "1d", "4h"):
            self._detect_swing_structure(timeframe, df, result)

        # Premium/Discount zones
        self._detect_premium_discount(timeframe, df, current_price, result)

        # Consolidations (NEW - for trend continuation entries)
        self._detect_consolidations(timeframe, df, atr_val, result, tf_smc_config)

        return result

    def _detect_equal_highs_lows(self, timeframe: str, df, result: Dict):
        """Detect equal highs/lows with structured liquidity pools."""
        try:
            ehl = detect_equal_highs_lows(df, config=self._smc_config, timeframe=timeframe)
            result["equal_highs"] = ehl.get("equal_highs", [])
            result["equal_lows"] = ehl.get("equal_lows", [])
            pools = ehl.get("pools", [])
            # Track pool sweeps (Phase 2.3)
            pools = track_pool_sweeps(df, pools)
            result["liquidity_pools"] = pools

            if pools:
                logger.debug(
                    "💧 %s: %d liquidity pools (tol=%.4f%%, min_touches=%d)",
                    timeframe,
                    len(pools),
                    ehl.get("metadata", {}).get("tolerance_used", 0) * 100,
                    ehl.get("metadata", {}).get("min_touches", 2),
                )
        except Exception:
            pass  # Non-critical, continue without

    def _detect_swing_structure(self, timeframe: str, df, result: Dict):
        """Detect swing structure (HH/HL/LH/LL) for HTF bias."""
        try:
            from backend.shared.config.smc_config import scale_lookback

            # Scale lookback by timeframe - HTF candles are more significant
            base_lookback = getattr(self._smc_config, "structure_swing_lookback", 15)

            # For HTF (1W, 1D), use higher min_lookback to catch true macro trend
            # Weekly needs at least 12-15 candles to see HH/HL pattern
            tf_lower = timeframe.lower()
            if tf_lower in ("1w",):
                min_lb = 12  # 12 weeks = ~3 months of structure
            elif tf_lower in ("1d",):
                min_lb = 10  # 10 days = 2 weeks of structure
            else:
                min_lb = 5

            scaled_lookback = scale_lookback(
                base_lookback, timeframe, min_lookback=min_lb, max_lookback=30
            )

            swing_struct = detect_swing_structure(df, lookback=scaled_lookback)
            result["swing_structure"] = swing_struct.to_dict()
            logger.debug(
                "📊 %s Swing structure: trend=%s (lookback=%d), last_HH=%s, last_HL=%s",
                timeframe,
                swing_struct.trend,
                scaled_lookback,
                f"{swing_struct.last_hh.price:.4f}" if swing_struct.last_hh else "N/A",
                f"{swing_struct.last_hl.price:.4f}" if swing_struct.last_hl else "N/A",
            )
        except Exception as e:
            logger.debug("Swing structure detection failed for %s: %s", timeframe, e)

    def _detect_premium_discount(self, timeframe: str, df, current_price: float, result: Dict):
        """Detect premium/discount zones."""
        try:
            pd_zone = detect_premium_discount(df, lookback=50, current_price=current_price)
            result["premium_discount"] = pd_zone.to_dict()
            logger.debug(
                "📊 %s P/D Zone: %s (%.1f%%)",
                timeframe,
                pd_zone.current_zone,
                pd_zone.zone_percentage or 50,
            )
        except Exception as e:
            logger.debug("Premium/Discount detection failed for %s: %s", timeframe, e)

    def _detect_key_levels(
        self, multi_tf_data: MultiTimeframeData, current_price: float
    ) -> Optional[Dict]:
        """Detect key levels (PDH/PDL/PWH/PWL)."""
        try:
            df_daily = multi_tf_data.timeframes.get("1D") or multi_tf_data.timeframes.get("1d")
            df_weekly = multi_tf_data.timeframes.get("1W") or multi_tf_data.timeframes.get("1w")
            if df_daily is not None and len(df_daily) >= 2:
                key_levels = detect_key_levels(df_daily, df_weekly, current_price)
                logger.info(
                    "🔑 Key Levels: PDH=%.4f PDL=%.4f PWH=%s PWL=%s",
                    key_levels.pdh.price if key_levels.pdh else 0,
                    key_levels.pdl.price if key_levels.pdl else 0,
                    f"{key_levels.pwh.price:.4f}" if key_levels.pwh else "N/A",
                    f"{key_levels.pwl.price:.4f}" if key_levels.pwl else "N/A",
                )
                return key_levels.to_dict()
        except Exception as e:
            logger.debug("Key levels detection failed: %s", e)
        return None

    def _update_mitigation(self, multi_tf_data: MultiTimeframeData, order_blocks: List) -> List:
        """Update order block mitigation status AND freshness scores."""
        if not order_blocks:
            return order_blocks

        try:
            ltf_df = (
                multi_tf_data.timeframes.get("15m")
                or multi_tf_data.timeframes.get("1H")
                or multi_tf_data.timeframes.get("1h")
            )
            if ltf_df is not None and len(ltf_df) > 0:
                order_blocks, mitigation_status = update_ob_mitigation(
                    order_blocks, ltf_df, max_mitigation=0.5
                )
                # Phase 2.1: Update OB lifecycle (breaker/invalidated)
                order_blocks = update_ob_lifecycle(ltf_df, order_blocks, preset="defaults")
                if mitigation_status.fully_mitigated_count > 0:
                    logger.info(
                        "🔄 OB Mitigation: %d fully mitigated, %d partial, %d fresh",
                        mitigation_status.fully_mitigated_count,
                        mitigation_status.partially_mitigated_count,
                        mitigation_status.fresh_count,
                    )
        except Exception as e:
            logger.debug("Mitigation tracking failed: %s", e)

        # FIXED: Recalculate freshness for ALL OBs after aggregation
        # This ensures structural OBs don't retain stale 100% freshness
        try:
            from datetime import datetime
            from dataclasses import replace
            from backend.strategy.smc.order_blocks import calculate_freshness

            current_time = datetime.now()
            updated_obs = []
            for ob in order_blocks:
                new_freshness = calculate_freshness(ob, current_time)
                updated_ob = replace(ob, freshness_score=new_freshness)
                updated_obs.append(updated_ob)

            # Filter out stale OBs (freshness below min threshold)
            min_freshness = self._smc_config.ob_min_freshness
            before_count = len(updated_obs)
            order_blocks = [ob for ob in updated_obs if ob.freshness_score >= min_freshness]
            filtered_count = before_count - len(order_blocks)

            if filtered_count > 0:
                logger.debug(
                    "🔄 Filtered %d stale OBs (freshness < %.1f%%)", filtered_count, min_freshness
                )
            logger.debug(
                "🔄 Recalculated freshness for %d OBs, kept %d", before_count, len(order_blocks)
            )
        except Exception as e:
            logger.debug("Freshness recalc failed: %s", e)

        return order_blocks

    def _log_liquidity_pools_summary(self, pools: List):
        """Log summary of graded liquidity pools."""
        if not pools:
            return
        grade_a = sum(1 for p in pools if p.grade == "A")
        grade_b = sum(1 for p in pools if p.grade == "B")
        grade_c = sum(1 for p in pools if p.grade == "C")
        logger.info(
            "🎯 Liquidity pools graded: A=%d B=%d C=%d (total=%d)",
            grade_a,
            grade_b,
            grade_c,
            len(pools),
        )

    def _count_by_grade(self, patterns: List) -> Dict[str, int]:
        """Count patterns by grade (A/B/C)."""
        counts = {"A": 0, "B": 0, "C": 0}
        for pattern in patterns:
            grade = getattr(pattern, "grade", "C")
            if grade in counts:
                counts[grade] += 1
        return counts

    def _log_swing_structure_summary(self, swing_structure_by_tf: Dict):
        """Log HTF swing structure summary."""
        for tf, ss in swing_structure_by_tf.items():
            logger.info("📈 %s Structure: %s trend", tf, ss.get("trend", "unknown"))

    def _build_htf_sweep_context(self, sweeps: List) -> dict:
        """
        Build HTF sweep context for LTF entry synergy.

        When a 4H/1D sweep is detected, it signals 'smart money grabbed liquidity'
        → Good time for LTF counter-trade entries in the expected direction.

        Returns:
            dict: HTF sweep context for synergy bonus calculation
        """
        from backend.shared.models.smc import LiquiditySweep  # Avoid circular import

        if not sweeps:
            return {"has_recent_htf_sweep": False}

        # Filter to HTF sweeps only (1d, 4h)
        htf_sweeps = [s for s in sweeps if getattr(s, "timeframe", "1h").lower() in ("1d", "4h")]

        if not htf_sweeps:
            return {"has_recent_htf_sweep": False}

        # Get most recent HTF sweep
        latest = max(htf_sweeps, key=lambda s: s.timestamp)

        # Determine expected LTF direction from sweep type:
        # - Low swept → liquidity grabbed below → expect bullish reversal
        # - High swept → liquidity grabbed above → expect bearish reversal
        expected_direction = "bullish" if latest.sweep_type == "low" else "bearish"

        context = {
            "has_recent_htf_sweep": True,
            "sweep_timeframe": getattr(latest, "timeframe", "4h"),
            "sweep_type": latest.sweep_type,
            "sweep_level": latest.level,
            "sweep_timestamp": (
                latest.timestamp.isoformat()
                if hasattr(latest.timestamp, "isoformat")
                else str(latest.timestamp)
            ),
            "expected_ltf_direction": expected_direction,
            "sweep_confirmed": latest.confirmation,
            "sweep_grade": getattr(latest, "grade", "B"),
        }

        logger.debug(
            "📊 HTF Sweep Context: %s sweep @ %.2f (%s) → expect %s",
            context["sweep_timeframe"],
            context["sweep_level"],
            context["sweep_type"],
            expected_direction,
        )

        return context

    def _detect_consolidations(
        self, timeframe: str, df, atr_val: float, result: Dict, tf_smc_config: SMCConfig
    ):
        """
        Detect consolidation ranges for trend continuation entries.

        Consolidations are horizontal trading ranges that break out and retest,
        providing entry opportunities in trending markets when no fresh OB/FVG exists.
        """
        try:
            # Skip HTF for consolidations (focus on LTF/MTF ranges)
            if timeframe.lower() in ("1w", "1d"):
                return

            consolidations = detect_consolidations(
                df=df,
                timeframe=timeframe,
                min_touches=5,
                max_height_pct=0.02,  # 2% range max
                min_duration_candles=10,
                atr=max(atr_val, 0.001),  # Fallback ATR
            )

            if consolidations:
                result["consolidations"] = consolidations
                logger.debug(
                    "🔄 %s: Detected %d consolidations (breakout confirmed: %d)",
                    timeframe,
                    len(consolidations),
                    sum(1 for c in consolidations if c.breakout_confirmed),
                )
        except Exception as e:
            logger.debug("Consolidation detection failed for %s: %s", timeframe, e)


# Singleton
_smc_service: Optional[SMCDetectionService] = None


def get_smc_service() -> Optional[SMCDetectionService]:
    """Get the singleton SMCDetectionService instance."""
    return _smc_service


def configure_smc_service(
    smc_config: Optional[SMCConfig] = None, mode: str = "strike"
) -> SMCDetectionService:
    """Configure and return the singleton SMCDetectionService."""
    global _smc_service
    _smc_service = SMCDetectionService(smc_config=smc_config, mode=mode)
    return _smc_service
