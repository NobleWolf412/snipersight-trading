"""
Pre-built SMC pattern fixtures for testing.
"""

from backend.shared.models.smc import (
    OrderBlock, FairValueGap, StructuralBreak, LiquiditySweep, SMCSnapshot
)


def create_bullish_order_block(
    timeframe: str = "1H",
    low: float = 99.0,
    high: float = 100.0
) -> OrderBlock:
    """Create a bullish order block for testing."""
    return OrderBlock(
        timeframe=timeframe,
        direction="bullish",
        high=high,
        low=low,
        open=99.5,
        close=99.2,
        volume=1500000,
        timestamp=1700000000,
        candle_index=50,
        displacement_atr=2.5,
        freshness_score=0.85,
        touched=False,
        volume_confirmation=True
    )


def create_bearish_order_block(
    timeframe: str = "1H",
    low: float = 99.0,
    high: float = 100.0
) -> OrderBlock:
    """Create a bearish order block for testing."""
    return OrderBlock(
        timeframe=timeframe,
        direction="bearish",
        high=high,
        low=low,
        open=99.2,
        close=99.8,
        volume=1500000,
        timestamp=1700000000,
        candle_index=50,
        displacement_atr=2.5,
        freshness_score=0.85,
        touched=False,
        volume_confirmation=True
    )


def create_bullish_fvg(
    timeframe: str = "15m",
    upper: float = 102.0,
    lower: float = 101.0
) -> FairValueGap:
    """Create a bullish FVG for testing."""
    return FairValueGap(
        timeframe=timeframe,
        direction="bullish",
        upper_bound=upper,
        lower_bound=lower,
        midpoint=(upper + lower) / 2,
        size_atr=0.8,
        timestamp=1700000000,
        start_candle=48,
        end_candle=50,
        filled=False,
        fill_percentage=0.0,
        displacement_strength=1.5
    )


def create_bearish_fvg(
    timeframe: str = "15m",
    upper: float = 100.0,
    lower: float = 99.0
) -> FairValueGap:
    """Create a bearish FVG for testing."""
    return FairValueGap(
        timeframe=timeframe,
        direction="bearish",
        upper_bound=upper,
        lower_bound=lower,
        midpoint=(upper + lower) / 2,
        size_atr=0.8,
        timestamp=1700000000,
        start_candle=48,
        end_candle=50,
        filled=False,
        fill_percentage=0.0,
        displacement_strength=1.5
    )


def create_bos(
    timeframe: str = "4H",
    direction: str = "bullish",
    break_level: float = 105.0
) -> StructuralBreak:
    """Create a Break of Structure (BOS) for testing."""
    return StructuralBreak(
        timeframe=timeframe,
        type="BOS",
        direction=direction,
        break_level=break_level,
        previous_extreme=103.0 if direction == "bullish" else 107.0,
        candle_index=75,
        timestamp=1700010000,
        strength=0.9,
        volume_confirmation=True,
        retest_count=0
    )


def create_choch(
    timeframe: str = "4H",
    direction: str = "bullish",
    break_level: float = 102.0
) -> StructuralBreak:
    """Create a Change of Character (CHoCH) for testing."""
    return StructuralBreak(
        timeframe=timeframe,
        type="CHoCH",
        direction=direction,
        break_level=break_level,
        previous_extreme=104.0 if direction == "bullish" else 100.0,
        candle_index=60,
        timestamp=1700005000,
        strength=0.75,
        volume_confirmation=True,
        retest_count=0
    )


def create_liquidity_sweep(
    timeframe: str = "1H",
    direction: str = "bullish",
    swept_level: float = 98.5
) -> LiquiditySweep:
    """Create a liquidity sweep for testing."""
    return LiquiditySweep(
        timeframe=timeframe,
        direction=direction,
        swept_level=swept_level,
        wick_high=99.0 if direction == "bullish" else 102.0,
        wick_low=98.0 if direction == "bullish" else 101.0,
        body_close=98.8 if direction == "bullish" else 101.5,
        candle_index=85,
        timestamp=1700015000,
        sweep_strength=0.8,
        liquidity_type="equal_lows" if direction == "bullish" else "equal_highs",
        follow_through=True
    )


def create_complete_smc_snapshot(
    direction: str = "bullish"
) -> SMCSnapshot:
    """
    Create a complete SMC snapshot with all pattern types.
    
    Useful for testing confluence scoring and trade planning.
    """
    if direction == "bullish":
        return SMCSnapshot(
            order_blocks=[
                create_bullish_order_block(timeframe="4H", low=98.0, high=99.0),
                create_bullish_order_block(timeframe="1H", low=99.5, high=100.0)
            ],
            fvgs=[
                create_bullish_fvg(timeframe="1H", upper=100.5, lower=99.8),
                create_bullish_fvg(timeframe="15m", upper=101.0, lower=100.5)
            ],
            structural_breaks=[
                create_bos(timeframe="4H", direction="bullish", break_level=102.0),
                create_choch(timeframe="1H", direction="bullish", break_level=100.5)
            ],
            liquidity_sweeps=[
                create_liquidity_sweep(timeframe="1H", direction="bullish", swept_level=98.5)
            ]
        )
    else:
        return SMCSnapshot(
            order_blocks=[
                create_bearish_order_block(timeframe="4H", low=101.0, high=102.0),
                create_bearish_order_block(timeframe="1H", low=100.0, high=100.5)
            ],
            fvgs=[
                create_bearish_fvg(timeframe="1H", upper=100.2, lower=99.5),
                create_bearish_fvg(timeframe="15m", upper=99.5, lower=99.0)
            ],
            structural_breaks=[
                create_bos(timeframe="4H", direction="bearish", break_level=98.0),
                create_choch(timeframe="1H", direction="bearish", break_level=99.5)
            ],
            liquidity_sweeps=[
                create_liquidity_sweep(timeframe="1H", direction="bearish", swept_level=101.5)
            ]
        )


def create_minimal_smc_snapshot() -> SMCSnapshot:
    """Create minimal SMC snapshot with only one OB (for testing edge cases)."""
    return SMCSnapshot(
        order_blocks=[create_bullish_order_block()],
        fvgs=[],
        structural_breaks=[],
        liquidity_sweeps=[]
    )


def create_empty_smc_snapshot() -> SMCSnapshot:
    """Create empty SMC snapshot (no patterns detected)."""
    return SMCSnapshot(
        order_blocks=[],
        fvgs=[],
        structural_breaks=[],
        liquidity_sweeps=[]
    )
