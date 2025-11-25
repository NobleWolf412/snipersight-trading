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


# Mode definitions (ordered roughly by strategic altitude)
# Timeframes use ccxt-compatible lowercase strings.
MODES: Dict[str, ScannerMode] = {
    "overwatch": ScannerMode(
        name="overwatch",
        description="High-altitude regime & trend surveillance (macro + swing alignment).",
        timeframes=("1w", "1d", "4h", "1h"),
        min_confluence_score=75.0,
        profile="macro_surveillance",
    ),
    "recon": ScannerMode(
        name="recon",
        description="Broad multi-timeframe scouting for emerging momentum pivots.",
        timeframes=("4h", "1h", "15m", "5m"),
        min_confluence_score=65.0,
        profile="balanced",
    ),
    "strike": ScannerMode(
        name="strike",
        description="Intraday execution focus (momentum + local liquidity).",
        timeframes=("1h", "15m", "5m", "1m"),
        min_confluence_score=60.0,
        profile="intraday_aggressive",
    ),
    "surgical": ScannerMode(
        name="surgical",
        description="Tight precision setups only (higher quality threshold).",
        timeframes=("4h", "1h", "15m"),
        min_confluence_score=70.0,
        profile="precision",
    ),
    "ghost": ScannerMode(
        name="ghost",
        description="Stealth monitoring across mixed horizons (reduced surface area).",
        timeframes=("1d", "4h", "1h", "15m", "5m"),
        min_confluence_score=70.0,
        profile="stealth_balanced",
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

