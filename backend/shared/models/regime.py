"""
Market Regime Models - Multi-dimensional regime analysis

Provides structured regime tracking across multiple dimensions:
- Trend (HTF structure)
- Volatility (ATR-based)
- Liquidity (volume-based)
- Risk appetite (dominance-based)
- Derivatives (funding/OI-based)
"""
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime


@dataclass
class RegimeDimensions:
    """Individual regime dimensions"""
    trend: Literal["strong_up", "up", "sideways", "down", "strong_down"]
    volatility: Literal["compressed", "normal", "elevated", "chaotic"]
    liquidity: Literal["thin", "healthy", "heavy"]
    risk_appetite: Literal["risk_on", "risk_off", "rotation"]
    derivatives: Literal["short_crowded", "long_crowded", "balanced"]


@dataclass
class MarketRegime:
    """Complete market regime structure"""
    dimensions: RegimeDimensions
    composite: str  # e.g. "choppy_risk_off", "bullish_risk_on"
    score: float  # 0-100, higher = more trade-friendly
    timestamp: datetime
    
    # Per-dimension scores for visibility
    trend_score: float
    volatility_score: float
    liquidity_score: float
    risk_score: float
    derivatives_score: float
    
    # Context (optional)
    btc_dominance: Optional[float] = None
    usdt_dominance: Optional[float] = None
    alt_dominance: Optional[float] = None


@dataclass
class SymbolRegime:
    """Per-symbol local regime"""
    symbol: str
    trend: Literal["strong_up", "up", "sideways", "down", "strong_down"]
    volatility: Literal["compressed", "normal", "elevated", "chaotic"]
    score: float  # 0-100


@dataclass
class RegimePolicy:
    """Mode-specific regime handling"""
    mode_name: str
    min_regime_score: float
    allow_in_risk_off: bool
    position_size_adjustment: dict  # trend -> multiplier
    confluence_adjustment: dict  # composite_regime -> boost/penalty
    rr_adjustment: dict  # trend/regime -> R:R multiplier
