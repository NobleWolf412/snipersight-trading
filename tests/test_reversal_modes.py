import sys
import os
import logging
from unittest.mock import MagicMock

# Setup path
sys.path.append(os.getcwd())

from backend.strategy.confluence.scorer import calculate_confluence_score
from backend.shared.models.smc import SMCSnapshot, ReversalContext
from backend.shared.config.defaults import ScanConfig
# Indicators/Context mocks
from backend.shared.models.indicators import IndicatorSet

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Concrete Mock Class to avoid MagicMock issues
class MockIndicators:
    def __init__(self):
        self.by_timeframe = {'1h': MagicMock(), '4h': MagicMock()}
        self.by_timeframe['4h'].dataframe = [] 
        # Scalars must be real floats
        self.rsi = 50.0
        self.stoch_rsi = 50.0
        self.macd_line = 0.0
        self.macd_signal = 0.0
        self.volume_spike = False
        self.relative_volume = 1.0
        self.adx = 20.0
        self.mfi = 50.0
        self.cci = 0.0
        self.obv_slope = 0.0
        self.volume_acceleration = 0.0
        self.volume_is_accelerating = False
        self.volume_consecutive_up = 0
        self.volume_consecutive_down = 0

def test_reversal_mode_differentiation():
    logger.info("--- Verifying Reversal Logic Across Modes ---")

    # 1. Setup Common Reversal Context (Moderate Confidence)
    reversal = ReversalContext(
        is_reversal_setup=True,
        direction="LONG",
        cycle_aligned=True,
        choch_detected=True,
        volume_displacement=False, # Missing volume
        liquidity_swept=False,     # Missing sweep
        confidence=50.0,           # Moderate confidence
        rationale="Cycle aligned + CHoCH"
    )
    
    # 2. Setup Dummy Snapshot & Indicators (Neutral)
    snapshot = SMCSnapshot(
        order_blocks=[], fvgs=[], structural_breaks=[], liquidity_sweeps=[],
        swing_structure={}
    )
    indicators = MockIndicators()
    
    # 3. Test Modes
    modes = ['strike', 'surgical', 'overwatch', 'stealth']
    scores = {}
    
    for mode in modes:
        logger.info(f"\nTesting Mode: {mode.upper()}")
        config = MagicMock(spec=ScanConfig)
        config.profile = mode
        # Disable gates to allow scoring
        config.btc_impulse_gate_enabled = False
        config.weekly_stoch_rsi_gate_enabled = False
        config.htf_proximity_enabled = False
        
        # Scorer
        breakdown = calculate_confluence_score(
            smc_snapshot=snapshot,
            indicators=indicators,
            config=config,
            direction="LONG",
            reversal_context=reversal,
            current_price=100.0
        )
        
        total = breakdown.total_score
        logger.info(f"Total Score: {total}")
        scores[mode] = total

    # 4. Compare
    logger.info("\n--- Comparison ---")
    base_score = scores['strike']
    all_identical = all(s == base_score for s in scores.values())
    
    if all_identical:
        logger.warning(f"⚠️  ALL MODES PRODUCED IDENTICAL SCORE: {base_score}")
        logger.warning("Conclusion: Reversal logic is NOT mode-aware.")
    else:
        logger.info("✅ Modes produced different scores.")
        logger.info(scores)

if __name__ == "__main__":
    test_reversal_mode_differentiation()
