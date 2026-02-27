import sys
import os
import logging
from unittest.mock import MagicMock, patch
from datetime import datetime

# Setup path
sys.path.append(os.getcwd())

# Import strict types
from backend.engine.context import SniperContext
from backend.services.confluence_service import ConfluenceService
from backend.strategy.confluence.scorer import ConfluenceBreakdown
from backend.shared.models.scoring import ConfluenceFactor
from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG
# from backend.shared.config.scanner_modes import ScanConfig # Removed incorrect import

class ScanConfig: # Mock it simply
    def __init__(self, profile):
        self.profile = profile
        self.btc_impulse_gate_enabled = True
        self.htf_proximity_enabled = True
        self.enable_htf_momentum_gate = True
        self.primary_planning_timeframe = '1h'
        self.structure_timeframes = ('4h', '1d')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def create_mock_context(profile='surgical'):
    context = MagicMock(spec=SniperContext)
    context.symbol = "BTC/USD"
    context.metadata = {'symbol_regime': MagicMock(trend='bearish')} # Default regime
    
    # Config
    context.config = ScanConfig(profile=profile)
    
    # SMC Snapshot (Generic)
    context.smc_snapshot = SMCSnapshot(
        order_blocks=[], 
        fvgs=[], 
        structural_breaks=[], 
        liquidity_sweeps=[]
    )
    
    # Indicators Mock (Robust)
    mock_ind = MagicMock()
    mock_ind.atr = 10.0
    mock_ind.atr_percent = 0.5
    mock_ind.rsi = 75.0 # Overbought (good for short)
    mock_ind.stoch_rsi_k = 85.0
    mock_ind.stoch_rsi = 50.0  # fallback
    mock_ind.stoch_rsi_d = 50.0
    mock_ind.macd_hist = -0.5 # Bearish momentum
    mock_ind.volume_spike = False
    mock_ind.volume_acceleration = 0.2
    mock_ind.volume_accel_direction = 'bearish' 
    mock_ind.volume_consecutive_increases = 0
    mock_ind.volume_exhaustion = True
    
    # Missing fields
    mock_ind.mfi = 50.0
    mock_ind.obv_slope = 0.0
    mock_ind.cci = 0.0
    mock_ind.volume_consecutive_up = 0
    mock_ind.volume_consecutive_down = 0
    mock_ind.bb_width_percentile = 50.0
    mock_ind.bb_upper = 105.0
    mock_ind.bb_lower = 95.0
    mock_ind.vwap_deviation = 0.0
    
    # HTF Indicator (Bullish Momentum to trigger gate)
    htf_ind = MagicMock()
    htf_ind.atr = 50.0
    htf_ind.atr_series = [40, 41, 42, 43, 44, 45, 46, 47, 48, 50] # Expanding ATR = Strong Momentum
    htf_ind.relative_volume = 1.5
    htf_ind.macd_line = 100.0
    htf_ind.macd_signal = 50.0 # Bullish MACD
    
    # Helper for ANY attribute access
    htf_ind.stoch_rsi = 50.0 # prevent crash if checked
    htf_ind.rsi = 50.0
    htf_ind.stoch_rsi_k = 50.0
    
    context.multi_tf_indicators = MagicMock()
    context.multi_tf_indicators.by_timeframe = {
        '5m': mock_ind,   # Primary for Surgical
        '1h': htf_ind,    # HTF for Momentum Gate
        '4h': htf_ind
    }
    
    return context

def test_short_reversal_override():
    logger.info("\n--- Test 1: Short Reversal Override (Surgical) ---")
    
    service = ConfluenceService(scanner_mode='surgical', config=ScanConfig(profile='surgical'))
    context = create_mock_context('surgical')
    
    # Setup SCENARIO:
    # 1. HTF Trend is BULLISH (should block shorts)
    # 2. We want a SHORT trade.
    # 3. We provide a Reversal Context.
    
    # Mock Swing Structure to say HTF is BULLISH
    context.smc_snapshot.swing_structure = {
        '1h': {'trend': 'bullish'},
        '4h': {'trend': 'bullish'}
    }
    
    # Reversal Context (The Key!)
    reversal_ctx_short = MagicMock()
    reversal_ctx_short.is_reversal_setup = True
    reversal_ctx_short.direction = 'SHORT'
    reversal_ctx_short.rationale = "Bearish Divergence + RSI Overbought"
    
    try:
        # Score it
        result = service.score(
            context=context,
            current_price=100000.0,
            reversal_context_short=reversal_ctx_short,
            reversal_context_long=None
        )
        
        # Validation
        chosen = context.metadata.get('chosen_direction')
        logger.info(f"Chosen Direction: {chosen}")
        logger.info(f"Total Score: {result.total_score}")
        
        # Check if Momentum Gate Blocked it
        # We need to peek into the factors to see if "HTF Momentum Gate" is present and what it says
        gate_factor = next((f for f in result.factors if f.name == 'HTF_Momentum_Gate'), None)
        
        if chosen == 'SHORT':
            logger.info("✅ SUCCESS: Short trade selected despite Bullish HTF.")
            if result.total_score > 0:
                 logger.info(f"   Score: {result.total_score}")
        else:
            logger.error(f"❌ FAILED: Chosen direction was {chosen}")
            
        if gate_factor:
             logger.info(f"   Gate Rationale: {gate_factor.rationale}")
             if "overridden by Reversal" in gate_factor.rationale:
                 logger.info("✅ SUCCESS: Gate Logic confirmed override.")
             else:
                 logger.error("❌ FAILED: Gate did not report override.")
        else:
             # It might not generate a factor if neutral, but we expect a factor if gate logic ran
             logger.info("ℹ️ No Momentum Gate factor found (maybe score was 0 adjustment?)")

    except Exception as e:
        logger.error(f"Test crashed: {e}")
        import traceback
        traceback.print_exc()

def test_confluence_tie_break():
    logger.info("\n--- Test 2: Confluence Tie Breaking (Regime) ---")
    service = ConfluenceService(scanner_mode='surgical', config=ScanConfig(profile='surgical'))
    context = create_mock_context('surgical')
    
    # Force scores to be identical by mocking _score_direction
    # We want valid breakdowns to return
    # Needs valid ConfluenceFactor to pass validation
    dummy_factor = ConfluenceFactor(name="Dummy", score=75.0, weight=1.0, rationale="Test")
    
    bd_long = ConfluenceBreakdown(
        total_score=75.0, 
        factors=[dummy_factor], 
        synergy_bonus=0, 
        conflict_penalty=0, 
        regime='unknown', 
        htf_aligned=False, 
        btc_impulse_gate=True
    )
    bd_short = ConfluenceBreakdown(
        total_score=75.0, 
        factors=[dummy_factor], 
        synergy_bonus=0, 
        conflict_penalty=0, 
        regime='unknown', 
        htf_aligned=False, 
        btc_impulse_gate=True
    )
    
    service._score_direction = MagicMock(side_effect=[bd_long, bd_short])
    
    # Set Regime to BEARISH
    context.metadata['symbol_regime'].trend = 'bearish'
    
    res = service.score(context, 100.0)
    
    chosen = context.metadata.get('chosen_direction')
    tie_break = context.metadata.get('alt_confluence', {}).get('tie_break_used')
    
    logger.info(f"Scores: Long=75.0, Short=75.0")
    logger.info(f"Regime: Bearish")
    logger.info(f"Chosen: {chosen}")
    logger.info(f"Tie Break Method: {tie_break}")
    
    if chosen == 'SHORT' and tie_break == 'regime_bearish':
        logger.info("✅ SUCCESS: Tie broken by regime correctly.")
    else:
        logger.error(f"❌ FAILED: Wrong tie break result: {chosen} via {tie_break}")

if __name__ == "__main__":
    test_short_reversal_override()
    test_confluence_tie_break()
