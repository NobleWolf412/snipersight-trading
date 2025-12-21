import sys
import os
import logging
from unittest.mock import MagicMock
from dataclasses import replace

# Setup path
sys.path.append(os.getcwd())

from backend.strategy.smc.reversal_detector import validate_reversal_profile
from backend.shared.models.smc import ReversalContext

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def verify_mode_gates():
    logger.info("--- Verifying Mode-Specific Reversal Gates ---")

    # 1. Setup Weak Reversal Context (50% conf, Not Cycle Aligned, No sweep/vol)
    weak_reversal = ReversalContext(
        is_reversal_setup=True,
        direction="LONG",
        cycle_aligned=False,
        choch_detected=True,
        volume_displacement=False, 
        liquidity_swept=False,     
        confidence=50.0,
        rationale="Cycle aligned + CHoCH",
        htf_bypass_active=False
    )
    
    # Modes to test
    scenarios = [
        ("strike", True),      # Should Pass (Conf >= 50)
        ("surgical", False),   # Should Fail (Conf < 75 & < 3 comps)
        ("overwatch", False),  # Should Fail (Not Cycle Aligned)
        ("stealth", False),    # Should Fail (No Sweep/Vol)
    ]
    
    # 2. Test Execution
    passed_all = True
    
    for mode, should_pass in scenarios:
        logger.info(f"\nTesting Mode: {mode.upper()}")
        
        result = validate_reversal_profile(weak_reversal, mode)
        
        is_setup = result.is_reversal_setup
        logger.info(f"Result: is_setup={is_setup} | Rationale: {result.rationale}")
        
        if is_setup != should_pass:
            logger.error(f"❌ Mismatch! Expected {should_pass}, Got {is_setup}")
            passed_all = False
        else:
            logger.info("✅ Pass")

    # 3. Test High Quality Reversal (Should Pass All)
    logger.info("\n--- Testing Perfect Reversal (Should Pass All) ---")
    perfect_reversal = ReversalContext(
        is_reversal_setup=True,
        direction="LONG",
        cycle_aligned=True,
        choch_detected=True,
        volume_displacement=True, 
        liquidity_swept=True,     
        confidence=90.0,
        rationale="Perfect Setup",
        htf_bypass_active=True
    )
    
    for mode in ["strike", "surgical", "overwatch", "stealth"]:
        res = validate_reversal_profile(perfect_reversal, mode)
        if not res.is_reversal_setup:
            logger.error(f"❌ Perfect setup failed in {mode}")
            passed_all = False
        else:
            logger.info(f"✅ Perfect setup passed {mode}")

    if passed_all:
        logger.info("\n🎉 All Gates Verified Successfully!")
    else:
        logger.error("\n⛔ Gates Verification Failed")

if __name__ == "__main__":
    verify_mode_gates()
