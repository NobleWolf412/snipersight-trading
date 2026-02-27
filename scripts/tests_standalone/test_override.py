"""Test the confluence override system."""
from backend.strategy.confluence.scorer import calculate_confluence_override, MODE_PENALTY_MULTIPLIERS, MODE_SYNERGY_CAPS
from backend.shared.models.smc import SMCSnapshot, LiquiditySweep, StructuralBreak
from backend.shared.models.scoring import ConfluenceFactor
from datetime import datetime
from unittest.mock import Mock

# Create mock mode config for Strike
mode_config = Mock()
mode_config.profile = 'strike'

# Create mock SMC with Institutional Sequence
smc = SMCSnapshot(
    order_blocks=[],
    fvgs=[],
    structural_breaks=[
        StructuralBreak(
            break_type='CHoCH',
            direction='bullish',
            timestamp=datetime.now(),
            level=100.0,
            timeframe='15m',
            htf_aligned=True,
            grade='A'
        )
    ],
    liquidity_sweeps=[
        LiquiditySweep(
            sweep_type='low',
            level=99.0,
            timestamp=datetime.now(),
            confirmation=True,
            confirmation_level=3,
            timeframe='15m'
        )
    ],
)

# Create mock factors with strong scores
factors = [
    ConfluenceFactor(name='Order Block', score=75.0, weight=0.18, rationale='Strong OB'),
    ConfluenceFactor(name='Market Structure', score=85.0, weight=0.28, rationale='CHoCH detected'),
    ConfluenceFactor(name='Momentum', score=60.0, weight=0.15, rationale='RSI aligned'),
    ConfluenceFactor(name='Volume', score=50.0, weight=0.10, rationale='Volume spike'),
]

# Test override calculation
print("=== OVERRIDE TEST RESULTS ===")
result = calculate_confluence_override(factors, smc, mode_config, 'long')
print(f"Reduction: {result['reduction'] * 100:.0f}%")
print(f"Triggered By: {result['triggered_by']}")
print(f"Matches: {result['matches']}")
print(f"Rationale: {result['rationale']}")
print()
print(f"MODE_PENALTY_MULTIPLIERS: {MODE_PENALTY_MULTIPLIERS}")
print(f"MODE_SYNERGY_CAPS: {MODE_SYNERGY_CAPS}")
