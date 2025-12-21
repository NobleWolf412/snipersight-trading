import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.getcwd())

from backend.strategy.smc.cycle_detector import _calculate_temporal_bias

def test_temporal_bias():
    print("Testing Temporal Bias Logic...")
    
    # Grid of test cases
    tests = [
        # (Name, Timestamp, Expected Active, Expected Score > 0)
        ("Monday Open (00:00 UTC)", datetime(2023, 10, 2, 0, 30), True, True), # Oct 2 2023 is Monday
        ("Monday Mid (10:00 UTC)", datetime(2023, 10, 2, 10, 0), True, True),
        ("Friday Open (00:00 UTC)", datetime(2023, 10, 6, 0, 30), True, True), # Oct 6 2023 is Friday
        ("Wed Mid (12:00 UTC)", datetime(2023, 10, 4, 12, 0), False, False), # Oct 4 is Wed
        ("Wed NY Mid (15:00 UTC)", datetime(2023, 10, 4, 15, 0), True, True), # Intraday window only
    ]
    
    passed = 0
    for name, ts, exp_active, exp_score in tests:
        score, active = _calculate_temporal_bias(ts)
        print(f"[{name}] Score: {score}, Active: {active}")
        
        if active == exp_active and (score > 0) == exp_score:
            print("  -> PASS")
            passed += 1
        else:
            print(f"  -> FAIL (Expected active={exp_active}, score>0={exp_score})")

    if passed == len(tests):
        print("\nALL TESTS PASSED ✅")
    else:
        print(f"\n{len(tests) - passed} TESTS FAILED ❌")

if __name__ == "__main__":
    test_temporal_bias()
