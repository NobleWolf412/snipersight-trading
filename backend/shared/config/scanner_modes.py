"""Scanner mode configuration mappings.

Defines tactical scanner modes (sniper-themed) that adjust
multi-timeframe coverage and baseline confluence expectations.

Each mode supplies:
- name: canonical lowercase key
- description: human readable summary
- timeframes: ordered tuple (highest -> lower frequency)
- min_confluence_score: baseline threshold (frontend may override upward)
- profile: semantic profile tag reused by scoring/planner heuristics
"""

from dataclasses import dataclass
from typing import Tuple, Dict, List, Optional, Any


# Multi-Timeframe Alignment Map
# exec: Entry Trigger | plan: Market Structure | context: Macro Trend
RELATIVITY_MAP = {
    "scalp": {
        "exec": "1m",
        "plan": "5m", 
        "context": "15m",
        "vol_profile_lookback": 24, # hours
        "label": "High Frequency"
    },
    "intraday": {
        "exec": "5m",
        "plan": "15m",
        "context": "1h",
        "vol_profile_lookback": 72, # hours
        "label": "Day Trading"
    },
    "swing": {
        "exec": "1h",
        "plan": "4h",
        "context": "1d",
        "vol_profile_lookback": 240, # hours
        "label": "Structural Swing"
    }
}


@dataclass(frozen=True)
class MACDModeConfig:
    """
    Mode-aware MACD scoring configuration.

    Controls how MACD is interpreted per scanner mode:
    - HTF/Swing modes: MACD as primary directional bias (heavy weight)
    - Balanced modes: MACD as weighted confluence factor
    - Scalp/Surgical modes: MACD as HTF context + LTF veto only

    Attributes:
        use_htf_bias: Whether to pull HTF MACD for directional context
        treat_as_primary: If True, MACD drives scoring; if False, it filters
        min_persistence_bars: Consecutive bars MACD must align before counting
        weight: Multiplier for MACD contribution to confluence score (0.5-1.5)
        use_histogram_strict: If True, histogram expansion/contraction affects score
        allow_ltf_veto: If True, LTF MACD opposition can block/downgrade trades
        htf_timeframe: Which timeframe to use for HTF MACD bias (e.g., '1h', '4h')
        macd_settings: Tuple of (fast, slow, signal) periods for this mode
        min_amplitude: Minimum |MACD - Signal| to count (filters chop)
    """

    use_htf_bias: bool = True
    treat_as_primary: bool = False
    min_persistence_bars: int = 2
    weight: float = 1.0
    use_histogram_strict: bool = False
    allow_ltf_veto: bool = True
    htf_timeframe: str = "1h"
    macd_settings: Tuple[int, int, int] = (12, 26, 9)  # (fast, slow, signal)
    min_amplitude: float = 0.0  # Minimum separation to avoid chop


# Default MACD configs per mode profile
MACD_MODE_CONFIGS: Dict[str, MACDModeConfig] = {
    "macro_surveillance": MACDModeConfig(
        use_htf_bias=True,
        treat_as_primary=True,
        min_persistence_bars=3,
        weight=1.5,
        use_histogram_strict=True,
        allow_ltf_veto=False,
        htf_timeframe="4h",
        macd_settings=(12, 26, 9),
        min_amplitude=0.0,
    ),
    "balanced": MACDModeConfig(
        use_htf_bias=True,
        treat_as_primary=False,
        min_persistence_bars=2,
        weight=1.0,
        use_histogram_strict=False,
        allow_ltf_veto=True,
        htf_timeframe="1h",
        macd_settings=(12, 26, 9),
        min_amplitude=0.0,
    ),
    "intraday_aggressive": MACDModeConfig(
        use_htf_bias=True,
        treat_as_primary=False,
        min_persistence_bars=2,
        weight=0.7,
        use_histogram_strict=False,
        allow_ltf_veto=True,
        htf_timeframe="1h",
        macd_settings=(12, 26, 9),
        min_amplitude=0.0,
    ),
    "precision": MACDModeConfig(
        use_htf_bias=True,
        treat_as_primary=False,
        min_persistence_bars=3,
        weight=0.6,
        use_histogram_strict=True,
        allow_ltf_veto=True,
        htf_timeframe="1h",
        macd_settings=(24, 52, 9),  # Longer settings for LTF noise reduction
        min_amplitude=0.0001,
    ),
    "stealth_balanced": MACDModeConfig(
        use_htf_bias=True,
        treat_as_primary=False,
        min_persistence_bars=2,
        weight=0.8,
        use_histogram_strict=False,
        allow_ltf_veto=True,
        htf_timeframe="1h",
        macd_settings=(12, 26, 9),
        min_amplitude=0.0,
    ),
}


def get_macd_config(profile: str) -> MACDModeConfig:
    """Get MACD configuration for a scanner mode profile."""
    return MACD_MODE_CONFIGS.get(profile, MACD_MODE_CONFIGS["balanced"])


@dataclass(frozen=True)
class ScannerMode:
    name: str
    description: str
    timeframes: Tuple[str, ...]  # Backward compat: bias + indicator TFs
    min_confluence_score: float
    profile: str
    critical_timeframes: Tuple[str, ...] = ()  # Must be present or symbol rejected
    # Planner-related knobs
    primary_planning_timeframe: str = "1h"
    max_pullback_atr: float = 3.0
    min_stop_atr: float = 0.3
    max_stop_atr: float = 6.0
    # Timeframe responsibility enforcement (3-tier)
    entry_timeframes: Tuple[str, ...] = ()  # TFs allowed for precise entry (LTF)
    structure_timeframes: Tuple[str, ...] = ()  # TFs allowed for SL/TP structure (HTF)
    stop_timeframes: Tuple[str, ...] = ()  # TFs allowed for stop-loss placement
    target_timeframes: Tuple[str, ...] = ()  # TFs allowed for target placement
    min_target_move_pct: float = 0.0  # Minimum TP1 move % threshold (0 = no minimum)
    # SMC detection strictness preset (defaults, luxalgo_strict, sensitive)
    smc_preset: str = "defaults"
    # Expected trade type hint (swing, scalp, intraday) - guides stop/target calculation
    expected_trade_type: str = "intraday"
    # Volume acceleration lookback (candles) - mode-aware for sensitivity
    volume_accel_lookback: int = 5  # Default: 5 candles (SURGICAL=3, OVERWATCH=8)
    # Allowed trade types for validation (enforces mode purpose)
    allowed_trade_types: Tuple[str, ...] = ("swing", "intraday", "scalp")  # Default all allowed
    # Per-mode overrides (min_rr_ratio, atr_floor, gating thresholds, etc.)
    overrides: Optional[Dict[str, Any]] = None

    # NEW: Top-down nested entry timeframe hierarchy
    # bias_timeframes: For direction bias (HH/HL/LH/LL analysis)
    # zone_timeframes: For entry zone OBs (where we want to trade from)
    # entry_trigger_timeframes: For refined entry OBs inside zones
    zone_timeframes: Tuple[str, ...] = ()  # TFs for entry zone (4H, 1H)
    entry_trigger_timeframes: Tuple[str, ...] = ()  # TFs for refined entry (15m, 5m)
    # Regime reference for HTF bias: "global" = daily-based, "intermediate" = 4H-based
    # Scalp/intraday modes use "intermediate" so 4H structure drives alignment, not the daily
    regime_reference: str = "global"

    # Cascade trade-type preference ordering (None = disabled, single-scale planning)
    # When set, the orchestrator attempts plan generation at each scale in order and
    # selects the highest-quality plan (confluence score + type-preference bonus).
    # Swing is preferred when quality is comparable; a clearly superior scalp can still win.
    cascade_trade_types: Optional[Tuple[str, ...]] = None

    @property
    def bias_timeframes(self) -> Tuple[str, ...]:
        """Alias for timeframes (bias + indicator TFs). For clarity in code."""
        return self.timeframes


# Mode definitions (ordered roughly by strategic altitude)
# Timeframes use ccxt-compatible lowercase strings.
# Synced with UI expectations as of 2025-11-26
MODES: Dict[str, ScannerMode] = {
    "overwatch": ScannerMode(
        name="overwatch",
        description="SWING TRADES (Days-Weeks) • High-conviction setups only • Weekly/Daily structure alignment • Best for: Patient traders wanting A+ quality with 2:1+ R:R minimum",
        timeframes=("1w", "1d", "4h", "1h", "15m", "5m"),  # Extended to match UI
        min_confluence_score=78.0,  # RAISED: 72→78 for A+ quality setups only
        profile="macro_surveillance",
        critical_timeframes=("1w", "1d"),  # Weekly and daily are essential for macro view
        primary_planning_timeframe="4h",
        max_pullback_atr=4.0,
        min_stop_atr=0.4,
        max_stop_atr=8.0,  # INCREASED: Allow wider stops for true swing invalidation
        entry_timeframes=(
            "1w",
            "1d",
            "4h",
            "1h",
            "15m",
        ),  # TUNED: Allow entries on HTF structure (Overwatch requirement)
        structure_timeframes=("1w", "1d", "4h"),  # RESTORED: HTF structure for target clipping
        stop_timeframes=("1d", "4h", "1h"),  # UPDATED: Include 1d for swing invalidation stops
        target_timeframes=("1d", "4h"),
        min_target_move_pct=1.5,  # Macro moves require >= 1.5% TP1
        smc_preset="luxalgo_strict",  # Institutional-grade strict detection for macro positions
        expected_trade_type="swing",  # HTF macro positions
        allowed_trade_types=("swing",),  # STRICT: Only swing trades allowed
        volume_accel_lookback=8,  # Longer lookback for swing - filters noise, catches institutional accumulation
        overrides={
            "min_rr_ratio": 2.0,
            "atr_floor": 0.0025,
            "bias_gate": 0.7,
            "htf_swing_allowed": ("1d", "4h", "1h"),
        },  # UPDATED: Include 1h
        # NEW: Nested OB entry hierarchy
        zone_timeframes=("4h", "1h"),  # Entry zone OBs
        entry_trigger_timeframes=("15m", "5m"),  # Refined entry OBs inside zone
    ),
    "strike": ScannerMode(
        name="strike",
        description="INTRADAY TRADES (Hours) • Aggressive momentum plays • More signals, faster entries • Best for: Active traders comfortable with quick decision-making and 1.2:1+ R:R",
        timeframes=("4h", "1h", "15m", "5m"),  # Changed from 1m to 4h start
        min_confluence_score=72.0,  # RAISED: 70→72 — structural anchor gate now required
        profile="intraday_aggressive",
        critical_timeframes=("15m",),  # 15m is essential for intraday entries
        primary_planning_timeframe="15m",
        max_pullback_atr=2.5,
        min_stop_atr=0.2,  # TUNED: was 0.25 - allow tighter scalp stops
        max_stop_atr=5.0,  # TUNED: was 3.5 - allow HTF structure stops
        entry_timeframes=("15m", "5m"),  # Fast aggressive entries with LTF precision
        structure_timeframes=("4h", "1h", "15m"),  # RESTORED: 4h structure for target clipping
        stop_timeframes=("1h", "15m", "5m"),  # TUNED: added 1h for HTF structure stops
        target_timeframes=("1h", "15m"),  # TUNED: added 15m for faster targets
        min_target_move_pct=0.4,  # TUNED: was 0.5 - allow tighter scalp targets
        smc_preset="luxalgo_aggressive",  # Loose detection for max signals
        expected_trade_type="strike",  # FIXED: Changed from "intraday" to "strike" to enable trend continuation
        allowed_trade_types=(
            "swing",
            "intraday",
            "scalp",
        ),  # Allow swing since 4h structure produces swing-sized targets
        volume_accel_lookback=4,  # Balanced - faster detection for intraday but not as reactive as scalp
        overrides={
            "min_rr_ratio": 1.2,
            "atr_floor": 0.0010,
            "bias_gate": 0.6,
            "htf_swing_allowed": ("1h", "15m"),
            "emergency_atr_fallback": True,
            "entry_zone_offset_atr": -0.05,
        },
        # NEW: Nested OB entry hierarchy
        zone_timeframes=("15m", "5m"),  # Entry zone OBs (faster for intraday)
        entry_trigger_timeframes=("5m",),  # Refined entry OBs
        regime_reference="intermediate",  # Use 4H regime so 4H bullish structure aligns scalp longs
    ),
    "surgical": ScannerMode(
        name="surgical",
        description="SCALP/INTRADAY (Minutes-Hours) • Precision entries with tight stops • Fewer but cleaner setups • Best for: Experienced traders wanting controlled risk with 1.5:1+ R:R",
        timeframes=("4h", "1h", "15m", "5m"),  # Simplified for precision
        min_confluence_score=74.0,  # RAISED: 72→74 — structural anchor gate now required
        profile="precision",
        critical_timeframes=("15m",),  # 15m essential for precision entries
        primary_planning_timeframe="15m",
        max_pullback_atr=2.0,
        min_stop_atr=0.25,  # TUNED: bumped from 0.15 to 0.25 for spread safety
        max_stop_atr=6.0,  # TUNED: was 5.0 - allow HTF structure stops (6 ATR cap with hard ceiling 2x)
        entry_timeframes=(
            "4h",
            "1h",
            "15m",
            "5m",
        ),  # TUNED: added 4h/1h - allows HTF OB entries when no LTF OBs exist
        structure_timeframes=(
            "4h",
            "1h",
            "15m",
        ),  # Precision structure from 4h/1h/15m (added 4h for HTF awareness)
        stop_timeframes=("4h", "1h", "15m", "5m"),  # TUNED: added 4h for HTF structure stops
        target_timeframes=("4h", "1h", "15m"),  # TUNED: added 4h for major targets
        min_target_move_pct=0.4,  # TUNED: was 0.6 - allow tighter surgical precision
        smc_preset="luxalgo_strict",  # Strict detection for precision - quality over quantity
        expected_trade_type="precision",  # FIXED: Changed from "intraday" to "precision" to enable trend continuation
        allowed_trade_types=("intraday", "scalp"),  # Precision focus
        volume_accel_lookback=3,  # Shortest lookback - scalp/surgical needs fastest reaction to volume changes
        overrides={
            "min_rr_ratio": 1.5,
            "atr_floor": 0.0008,
            "bias_gate": 0.7,
            "htf_swing_allowed": ("1h", "15m"),
            "emergency_atr_fallback": True,
            "entry_zone_offset_atr": 0.05,
        },
        # NEW: Nested OB entry hierarchy
        zone_timeframes=(
            "4h",
            "1h",
            "15m",
            "5m",
        ),  # Entry zone OBs - includes HTF for institutional context
        entry_trigger_timeframes=("5m",),  # Refined entry OBs
        regime_reference="intermediate",  # Use 4H regime so 4H bullish structure aligns scalp longs
    ),
    # STEALTH replaces both RECON and GHOST (merged per SMC_PIPELINE_REFACTOR.md)
    # Use stealth_strict=False for balanced (was RECON), stealth_strict=True for higher conviction (was GHOST)
    "stealth": ScannerMode(
        name="stealth",
        description="BALANCED (Hours-Days) • Mix of swing and intraday setups • Good signal volume with solid quality • Best for: All-around trading with 1.8:1+ R:R minimum",
        timeframes=("1d", "4h", "1h", "15m", "5m"),
        min_confluence_score=70.0,  # RAISED: 65→70 for better balanced quality
        profile="stealth_balanced",
        critical_timeframes=("4h", "1h"),  # Essential for swing context
        primary_planning_timeframe="1h",
        max_pullback_atr=3.0,
        min_stop_atr=0.2,
        max_stop_atr=4.5,
        entry_timeframes=(
            "4h",
            "1h",
            "15m",
            "5m",
        ),  # TUNED: added 4h for swing component (like Surgical)
        structure_timeframes=("1d", "4h", "1h", "15m"),  # Added 15m to support 5m entries
        stop_timeframes=("4h", "1h", "15m"),  # TUNED: added 4h/1h for swing structure stops
        target_timeframes=(
            "1d",
            "4h",
            "1h",
            "15m",
        ),  # FIXED: Added 4h and 1d (was missing, caused daily FVG targets to be ignored)
        min_target_move_pct=0.5,
        smc_preset="defaults",  # Balanced detection for swing trading
        expected_trade_type="stealth",  # FIXED: Changed from "intraday" to enable trend continuation (PlannerConfig.defaults_for_mode("stealth"))
        allowed_trade_types=("swing", "intraday", "scalp"),  # Balanced mix of all types
        volume_accel_lookback=5,  # Default balanced - good for mixed swing/intraday
        overrides={
            "min_rr_ratio": 1.5,  # was 1.8 — more achievable with 4h/1h structure stops
            "atr_floor": 0.0015,
            "bias_gate": 0.65,
            "htf_swing_allowed": ("4h", "1h"),
            "stealth_strict": False,  # Set True for higher conviction mode
        },
        # NEW: Nested OB entry hierarchy
        zone_timeframes=("4h", "1h", "15m"),  # Entry zone OBs (balanced)
        entry_trigger_timeframes=("5m",),  # Refined entry OBs
        # Cascade: try swing first (highest quality), then intraday, then scalp.
        # The orchestrator attempts plan generation at each scale and picks the best-scoring plan
        # (confluence + type-preference bonus so swing is preferred when quality is comparable).
        cascade_trade_types=("swing", "intraday", "scalp"),
    ),
}


def list_modes() -> List[Dict[str, object]]:
    """Return serializable summaries for all modes."""
    return [
        {
            "name": m.name,
            "description": m.description,
            "timeframes": m.timeframes,
            "min_confluence_score": m.min_confluence_score,
            "profile": m.profile,
            "primary_planning_timeframe": m.primary_planning_timeframe,
            "max_pullback_atr": m.max_pullback_atr,
            "min_stop_atr": m.min_stop_atr,
            "max_stop_atr": m.max_stop_atr,
            "entry_timeframes": m.entry_timeframes,
            "structure_timeframes": m.structure_timeframes,
            "stop_timeframes": m.stop_timeframes,
            "target_timeframes": m.target_timeframes,
            "min_target_move_pct": m.min_target_move_pct,
            "smc_preset": m.smc_preset,
            "expected_trade_type": m.expected_trade_type,
            "volume_accel_lookback": m.volume_accel_lookback,
            "overrides": m.overrides or {},
        }
        for m in MODES.values()
    ]


# Profile to mode mapping (reverse lookup)
PROFILE_TO_MODE: Dict[str, str] = {
    "macro_surveillance": "overwatch",
    "intraday_aggressive": "strike",
    "precision": "surgical",
    "stealth_balanced": "stealth",
    "balanced": "stealth",  # Fallback
}


def map_profile_to_relativity(profile: str) -> str:
    """Map a profile name to its relativity category (scalp, intraday, swing)."""
    p = (profile or "stealth").lower()
    if p in ("surgical", "precision"):
        return "scalp"
    if p in ("strike", "intraday_aggressive"):
        return "intraday"
    return "swing" # Overwatch, Stealth, Balanced all map to swing



def get_mode_by_profile(profile: str) -> ScannerMode:
    """
    Lookup a scanner mode by profile name.

    Args:
        profile: Profile name (e.g., 'intraday_aggressive', 'precision')

    Returns:
        ScannerMode corresponding to the profile
    """
    mode_name = PROFILE_TO_MODE.get(profile.lower(), "stealth")
    return get_mode(mode_name)


def get_mode(name: str) -> ScannerMode:
    """
    Lookup a scanner mode by name (case-insensitive).

    Valid modes: strike, surgical, stealth, overwatch
    """
    key = name.lower()

    if key not in MODES:
        raise ValueError(f"Unknown scanner mode: {name}")
    return MODES[key]

