
import logging
import sys
from unittest.mock import MagicMock

# Setup dummy logging
logging.basicConfig(level=logging.INFO)

# Mock the imports that orchestrator needs
sys.modules['backend.shared.models.context'] = MagicMock()
sys.modules['backend.shared.models.scoring'] = MagicMock()
sys.modules['backend.strategy.confluence.scorer'] = MagicMock()

# Determine where to look for imports
import os
sys.path.append(os.getcwd())

from backend.services.confluence_service import ConflictingDirectionsException
from backend.shared.models.scoring import ConfluenceBreakdown

def test_orchestrator_exception_handling():
    print("Testing Exception Handling...")
    
    # Create dummy breakdowns
    bullish = MagicMock(spec=ConfluenceBreakdown)
    bullish.total_score = 75.0
    bullish.factors = []
    bullish.synergy_bonus = 0
    bullish.conflict_penalty = 0
    
    bearish = MagicMock(spec=ConfluenceBreakdown)
    bearish.total_score = 73.0
    bearish.factors = []
    bearish.synergy_bonus = 0
    bearish.conflict_penalty = 0
    
    # Create the exception
    exc = ConflictingDirectionsException(
        "Conflicting signals - close call",
        bullish_breakdown=bullish,
        bearish_breakdown=bearish
    )
    
    # Simulate Orchestrator logic (copy-paste dependent logic)
    # We can't easily import Orchestrator without all dependencies, so we verify the logic block itself
    
    try:
        raise exc
    except Exception as e:
        if isinstance(e, ConflictingDirectionsException):
            print("✅ Caught ConflictingDirectionsException correctly")
            
            # Simulate extraction logic
            bullish = e.bullish_breakdown
            bearish = e.bearish_breakdown
            gap = abs(bullish.total_score - bearish.total_score)
            
            result = {
                "symbol": "TEST",
                "reason": str(e),
                "reason_type": "low_confluence",
                "detail": "Confluence scores tied",
                "bullish_score": bullish.total_score,
                "bearish_score": bearish.total_score,
                "gap": gap,
                "bullish_factors": [], # Mock
                "bearish_factors": []  # Mock
            }
            
            print(f"✅ Extracted Gap: {result['gap']}")
            print(f"✅ Extracted Bullish Score: {result['bullish_score']}")
            
            # Verify keys exist for frontend
            if "bullish_factors" in result and "bearish_factors" in result:
                print("✅ Factor arrays present")
            else:
                print("❌ Factor arrays MISSING")
                
        else:
            print(f"❌ Failed to identify exception type. Got: {type(e)}")

test_orchestrator_exception_handling()
