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
    # Per-mode overrides (min_rr_ratio, atr_floor, gating thresholds, etc.)
    overrides: Optional[Dict[str, Any]] = None
    
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
        description="High-altitude overwatch: macro recon and regime alignment; fewer shots, higher conviction.",
        timeframes=("1w", "1d", "4h", "1h", "15m", "5m"),  # Extended to match UI
        min_confluence_score=75.0,
        profile="macro_surveillance",
        critical_timeframes=("1w", "1d"),  # Weekly and daily are essential for macro view
        primary_planning_timeframe="4h",
        max_pullback_atr=4.0,
        min_stop_atr=0.4,
        max_stop_atr=6.5,  # TUNED: was 8.0 - cap via max_stop_atr validation
        entry_timeframes=("4h", "1h"),  # Swing position entries, not scalping
        structure_timeframes=("1w", "1d", "4h"),  # RESTORED: HTF structure for target clipping
        stop_timeframes=("4h", "1h"),
        target_timeframes=("1d", "4h"),
        min_target_move_pct=1.5,  # Macro moves require >= 1.5% TP1
        overrides={"min_rr_ratio": 2.0, "atr_floor": 0.0025, "bias_gate": 0.7, "htf_swing_allowed": ("1d", "4h")},
    ),
    "recon": ScannerMode(
        name="recon",
        description="Balanced recon: multi-timeframe scouting for momentum pivots; adaptable and mission-ready.",
        timeframes=("1d", "4h", "1h", "15m", "5m"),  # Added 1D to match UI
        min_confluence_score=65.0,
        profile="balanced",
        critical_timeframes=("4h", "1h"),  # 4H and 1H essential for swing context
        primary_planning_timeframe="1h",
        max_pullback_atr=3.0,
        min_stop_atr=0.25,  # TUNED: was 0.3 - allow slightly tighter precision stops
        max_stop_atr=5.0,   # TUNED: was 6.0 - cap via max_stop_atr validation
        entry_timeframes=("1h", "15m", "5m"),  # TUNED: added 5m for flexible entries
        structure_timeframes=("1d", "4h", "1h"),  # RESTORED: HTF structure for target clipping
        stop_timeframes=("1h", "15m"),
        target_timeframes=("4h", "1h"),
        min_target_move_pct=0.8,  # Balanced swing requires >= 0.8% TP1
        overrides={"min_rr_ratio": 1.8, "atr_floor": 0.0015, "bias_gate": 0.65, "htf_swing_allowed": ("4h", "1h")},
    ),
    "strike": ScannerMode(
        name="strike",
        description="Strike ops: intraday assault on momentum with local liquidity reads; fast entry, fast exfil.",
        timeframes=("4h", "1h", "15m", "5m"),  # Changed from 1m to 4h start
        min_confluence_score=60.0,
        profile="intraday_aggressive",
        critical_timeframes=("15m",),  # 15m is essential for intraday entries
        primary_planning_timeframe="15m",
        max_pullback_atr=2.5,
        min_stop_atr=0.2,   # TUNED: was 0.25 - allow tighter scalp stops
        max_stop_atr=3.5,   # TUNED: was 5.0 - cap via max_stop_atr validation
        entry_timeframes=("15m", "5m"),  # Fast aggressive scalp entries (5m NOW ALLOWED)
        structure_timeframes=("4h", "1h", "15m"),  # RESTORED: 4h structure for target clipping
        stop_timeframes=("15m", "5m"),  # TUNED: added 5m for tighter scalp stops
        target_timeframes=("1h", "15m"),  # TUNED: added 15m for faster targets
        min_target_move_pct=0.4,  # TUNED: was 0.5 - allow tighter scalp targets
        overrides={"min_rr_ratio": 1.5, "atr_floor": 0.0010, "bias_gate": 0.6, "htf_swing_allowed": ("1h", "15m"), "emergency_atr_fallback": True},
    ),
    "surgical": ScannerMode(
        name="surgical",
        description="Surgical precision: tight, high-quality entries only; minimal exposure, maximum control.",
        timeframes=("1h", "15m", "5m"),  # Simplified for precision
        min_confluence_score=70.0,
        profile="precision",
        critical_timeframes=("15m",),  # 15m essential for precision scalping
        primary_planning_timeframe="15m",
        max_pullback_atr=2.0,
        min_stop_atr=0.15,  # TUNED: was 0.25 - surgical needs tightest stops
        max_stop_atr=3.0,   # TUNED: was 4.0 - surgical can't afford wide stops
        entry_timeframes=("15m", "5m"),  # TUNED: added 15m - 5m-only was too restrictive
        structure_timeframes=("1h", "15m"),  # Precision structure from 1h/15m ONLY (no 5m)
        stop_timeframes=("15m", "5m"),  # TUNED: added 5m for tightest stops
        target_timeframes=("1h", "15m"),  # TUNED: added 15m for faster exits
        min_target_move_pct=0.4,  # TUNED: was 0.6 - allow tighter surgical precision
        overrides={"min_rr_ratio": 1.5, "atr_floor": 0.0008, "bias_gate": 0.7, "htf_swing_allowed": ("1h", "15m"), "emergency_atr_fallback": True},
    ),
    "ghost": ScannerMode(
        name="ghost",
        description="Ghost mode: stealth surveillance across mixed horizons; nimble, low profile, reduced macro drag.",
        timeframes=("1d", "4h", "1h", "15m", "5m"),
        min_confluence_score=70.0,
        profile="stealth_balanced",
        critical_timeframes=("1h",),  # 1H essential for multi-horizon context
        primary_planning_timeframe="1h",
        max_pullback_atr=3.0,
        min_stop_atr=0.2,   # TUNED: was 0.3 - ghost needs flexibility
        max_stop_atr=4.5,   # TUNED: was 6.0 - cap via max_stop_atr validation
        entry_timeframes=("1h", "15m", "5m"),  # TUNED: added 1h - more entry flexibility
        structure_timeframes=("1d", "4h", "1h", "15m"),  # RESTORED: HTF structure for target clipping
        stop_timeframes=("15m", "5m"),  # TUNED: added 5m for tighter stops
        target_timeframes=("1h", "15m"),  # TUNED: added 15m for nimble exits
        min_target_move_pct=0.5,  # TUNED: was 0.7 - allow tighter stealth scalps
        overrides={"min_rr_ratio": 1.5, "atr_floor": 0.0010, "bias_gate": 0.7, "htf_swing_allowed": ("4h", "1h")},
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
            "overrides": m.overrides or {},
        }
        for m in MODES.values()
    ]


def get_mode(name: str) -> ScannerMode:
    """Lookup a scanner mode by name (case-insensitive)."""
    key = name.lower()
    if key not in MODES:
        raise ValueError(f"Unknown scanner mode: {name}")
    return MODES[key]

