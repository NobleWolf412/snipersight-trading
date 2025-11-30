"""
Technical indicators data models.

This module defines data structures for all technical indicators used in
the SniperSight analysis pipeline across multiple timeframes.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class IndicatorSnapshot:
    """
    Complete set of technical indicators for a single timeframe.
    
    Contains all computed indicators at a specific point in time.
    All values represent the most recent reading.
    
    Momentum Indicators:
        rsi: Relative Strength Index (0-100)
        stoch_rsi: Stochastic RSI (0-100)
        stoch_rsi_k: Stochastic RSI %K line
        stoch_rsi_d: Stochastic RSI %D line
        mfi: Money Flow Index (0-100)
    
    Mean Reversion Indicators:
        bb_upper: Bollinger Band upper boundary
        bb_middle: Bollinger Band middle line (SMA)
        bb_lower: Bollinger Band lower boundary
        bb_width: Bollinger Band width (upper - lower)
    
    Volatility Indicators:
        atr: Average True Range
        atr_percent: ATR as percentage of price
        realized_volatility: Historical volatility
    
    Volume Indicators:
        volume_spike: Boolean indicating abnormal volume
        volume_ratio: Current volume / average volume
        obv: On-Balance Volume
    
    Trend Indicators:
        ema_9: 9-period Exponential Moving Average
        ema_21: 21-period EMA
        ema_50: 50-period EMA
        ema_200: 200-period EMA
        macd_line: MACD line value
        macd_signal: MACD signal line value
    """
    # Momentum (required fields)
    rsi: float
    stoch_rsi: float
    
    # Mean Reversion (required fields)
    bb_upper: float
    bb_middle: float
    bb_lower: float
    
    # Volatility (required fields)
    atr: float
    
    # Volume (required fields)
    volume_spike: bool
    
    # Momentum (optional fields)
    stoch_rsi_k: Optional[float] = None
    stoch_rsi_d: Optional[float] = None
    mfi: Optional[float] = None
    
    # Mean Reversion (optional fields)
    bb_width: Optional[float] = None
    
    # Volatility (optional fields)
    atr_percent: Optional[float] = None
    realized_volatility: Optional[float] = None
    
    # Volume (optional fields)
    volume_ratio: Optional[float] = None
    obv: Optional[float] = None
    
    # Trend (all optional)
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    
    def __post_init__(self):
        """Validate indicator ranges."""
        # RSI should be 0-100
        if not 0 <= self.rsi <= 100:
            raise ValueError(f"RSI must be 0-100, got {self.rsi}")
        if not 0 <= self.stoch_rsi <= 100:
            raise ValueError(f"Stochastic RSI must be 0-100, got {self.stoch_rsi}")
        
        # MFI if present should be 0-100
        if self.mfi is not None and not 0 <= self.mfi <= 100:
            raise ValueError(f"MFI must be 0-100, got {self.mfi}")
        
        # BB upper must be > middle > lower
        if not (self.bb_upper > self.bb_middle > self.bb_lower):
            raise ValueError(
                f"Bollinger Bands must satisfy: upper ({self.bb_upper}) > "
                f"middle ({self.bb_middle}) > lower ({self.bb_lower})"
            )
        
        # ATR must be positive
        if self.atr <= 0:
            raise ValueError(f"ATR must be positive, got {self.atr}")
        
        # Calculate BB width if not provided
        if self.bb_width is None:
            self.bb_width = self.bb_upper - self.bb_lower
    
    @property
    def rsi_oversold(self) -> bool:
        """Check if RSI indicates oversold condition (< 30)."""
        return self.rsi < 30
    
    @property
    def rsi_overbought(self) -> bool:
        """Check if RSI indicates overbought condition (> 70)."""
        return self.rsi > 70
    
    @property
    def bb_squeeze(self) -> bool:
        """Check if Bollinger Bands are in squeeze (width < avg)."""
        # Simple heuristic: width < 2% of middle
        return self.bb_width < (self.bb_middle * 0.02) if self.bb_width else False


@dataclass
class IndicatorSet:
    """
    Complete indicator set across all timeframes.
    
    Maps timeframe strings to their respective IndicatorSnapshot objects.
    This is the output of the indicator computation stage.
    
    Attributes:
        by_timeframe: Dictionary mapping timeframe to IndicatorSnapshot
                     Keys: '1W', '1D', '4H', '1H', '15m', '5m'
                     Values: IndicatorSnapshot objects
    """
    by_timeframe: Dict[str, IndicatorSnapshot] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate timeframe indicator data."""
        if not self.by_timeframe:
            raise ValueError("IndicatorSet must contain at least one timeframe")
        
        # Validate all values are IndicatorSnapshot
        for tf, snapshot in self.by_timeframe.items():
            if not isinstance(snapshot, IndicatorSnapshot):
                raise TypeError(
                    f"Timeframe '{tf}' must contain IndicatorSnapshot, "
                    f"got {type(snapshot)}"
                )
    
    def get_indicator(self, timeframe: str) -> IndicatorSnapshot:
        """Get indicators for a specific timeframe."""
        if timeframe not in self.by_timeframe:
            raise KeyError(f"Timeframe '{timeframe}' not found in IndicatorSet")
        return self.by_timeframe[timeframe]
    
    def has_timeframe(self, timeframe: str) -> bool:
        """Check if indicators exist for a timeframe."""
        return timeframe in self.by_timeframe
    
    def get_timeframes(self) -> list:
        """Get list of available timeframes."""
        return list(self.by_timeframe.keys())
    
    def get_htf_rsi(self, htf: str = "1D") -> float:
        """Get higher timeframe RSI (default: 1D)."""
        return self.get_indicator(htf).rsi
    
    def get_ltf_rsi(self, ltf: str = "15m") -> float:
        """Get lower timeframe RSI (default: 15m)."""
        return self.get_indicator(ltf).rsi
