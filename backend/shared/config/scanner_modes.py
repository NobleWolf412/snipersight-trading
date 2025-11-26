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
from typing import Tuple, Dict, List


@dataclass(frozen=True)
class ScannerMode:
    name: str
    description: str
    timeframes: Tuple[str, ...]
    min_confluence_score: float
    profile: str
    critical_timeframes: Tuple[str, ...] = ()  # Must be present or symbol rejected


# Mode definitions (ordered roughly by strategic altitude)
# Timeframes use ccxt-compatible lowercase strings.
# Synced with UI expectations as of 2025-11-26
MODES: Dict[str, ScannerMode] = {
    "overwatch": ScannerMode(
        name="overwatch",
        description="High-altitude regime & trend surveillance (macro + swing alignment).",
        timeframes=("1w", "1d", "4h", "1h", "15m", "5m"),  # Extended to match UI
        min_confluence_score=75.0,
        profile="macro_surveillance",
        critical_timeframes=("1w", "1d"),  # Weekly and daily are essential for macro view
    ),
    "recon": ScannerMode(
        name="recon",
        description="Broad multi-timeframe scouting for emerging momentum pivots.",
        timeframes=("1d", "4h", "1h", "15m", "5m"),  # Added 1D to match UI
        min_confluence_score=65.0,
        profile="balanced",
        critical_timeframes=("4h", "1h"),  # 4H and 1H essential for swing context
    ),
    "strike": ScannerMode(
        name="strike",
        description="Intraday execution focus (momentum + local liquidity).",
        timeframes=("4h", "1h", "15m", "5m"),  # Changed from 1m to 4h start
        min_confluence_score=60.0,
        profile="intraday_aggressive",
        critical_timeframes=("15m",),  # 15m is essential for intraday entries
    ),
    "surgical": ScannerMode(
        name="surgical",
        description="Tight precision setups only (higher quality threshold).",
        timeframes=("1h", "15m", "5m"),  # Simplified for precision
        min_confluence_score=70.0,
        profile="precision",
        critical_timeframes=("15m",),  # 15m essential for precision scalping
    ),
    "ghost": ScannerMode(
        name="ghost",
        description="Stealth monitoring across mixed horizons (reduced surface area).",
        timeframes=("1d", "4h", "1h", "15m", "5m"),
        min_confluence_score=70.0,
        profile="stealth_balanced",
        critical_timeframes=("1h",),  # 1H essential for multi-horizon context
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
        }
        for m in MODES.values()
    ]


def get_mode(name: str) -> ScannerMode:
    """Lookup a scanner mode by name (case-insensitive)."""
    key = name.lower()
    if key not in MODES:
        raise ValueError(f"Unknown scanner mode: {name}")
    return MODES[key]

