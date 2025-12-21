import sys
import os
import logging
from unittest.mock import MagicMock

# Setup path
sys.path.append(os.getcwd())

# Import planner
from backend.strategy.planner import planner_service
from backend.shared.models.smc import SMCSnapshot, OrderBlock
# from backend.shared.config.scanner_modes import ScanConfig

class ScanConfig:
    def __init__(self, profile):
        self.profile = profile
        self.entry_timeframes = ('1h', '4h')

from backend.shared.config.planner_config import PlannerConfig

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_overwatch_rejection():
    logger.info("--- Testing Overwatch Rejection Logic ---")
    
    # 1. Setup Mock Config
    config = ScanConfig(profile='overwatch')
    # Overwatch usually allows 1h, 4h entry
    config.entry_timeframes = ('1h', '4h')
    
    planner_cfg = PlannerConfig()
    planner_cfg.max_pullback_atr = 5.0 # Generous
    
    # 2. Setup Mock OBs
    # Case A: Price is ABOVE the OB (Classic Pullback) -> Should pass
    ob_valid = OrderBlock(
        timeframe='1h',
        direction='bullish',
        high=100.0,
        low=90.0,
        displacement_strength=80.0,
        mitigation_level=0.0,
        freshness_score=100.0,
        timestamp=None
    )
    # top/bottom properties usually derived or aliased, but let's set them if they are attrs
    # Actually if it's a dataclass, top/bottom might be properties or missing
    # I'll rely on high/low which are the core fields
    
    # Case B: Price is INSIDE the OB (Instant Entry) -> Currently suspected to FAIL
    ob_inside = OrderBlock(
        timeframe='1h',
        direction='bullish',
        high=110.0,
        low=100.0,
        displacement_strength=80.0,
        mitigation_level=0.0,
        freshness_score=100.0,
        timestamp=None
    )
    
    snapshot = SMCSnapshot(
        order_blocks=[ob_valid, ob_inside],
        fvgs=[], structural_breaks=[], liquidity_sweeps=[]
    )
    
    # 3. Test Function
    # Current Price = 105.0. 
    # ob_valid: 90-100. Price is 5 units ABOVE. Distance = 5. ATR=1.0. Distance=5 ATR.
    # ob_inside: 100-110. Price is INSIDE. 
    
    current_price = 105.0
    atr = 1.0
    
    logger.info(f"Current Price: {current_price}, ATR: {atr}")
    logger.info(f"OB Valid: {ob_valid.low}-{ob_valid.high}")
    logger.info(f"OB Inside: {ob_inside.low}-{ob_inside.high}")
    
    try:
        # We need to mock _get_allowed_entry_tfs if it's not picking up our config
        # But let's check basic logic first
        
        # We invoke _calculate_entry_zone directly
        entry_zone, used = planner_service._calculate_entry_zone(
            is_bullish=True,
            smc_snapshot=snapshot,
            current_price=current_price,
            atr=atr,
            primary_tf='1h',
            setup_archetype=MagicMock(),
            config=config,
            planner_cfg=planner_cfg,
            multi_tf_data=None # skip data validation for now
        )
        
        logger.info(f"✅ Success! Entry Zone: {entry_zone}")
        
    except ValueError as e:
        logger.error(f"❌ Planner Rejected: {e}")
    except Exception as e:
        logger.error(f"❌ Crash: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_overwatch_rejection()
