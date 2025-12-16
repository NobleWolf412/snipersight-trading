
import sys
import os
import asyncio
from unittest.mock import MagicMock
from decimal import Decimal

# Setup path
sys.path.append(os.getcwd())

from backend.strategy.planner.planner_service import generate_trade_plan
from backend.shared.models.smc import SMCSnapshot, OrderBlock
from backend.shared.config.planner_config import PlannerConfig
from backend.shared.config.defaults import ScanConfig

class FairValueGap:
    pass # Mock for now

async def debug_overwatch_gate():
    print("--- Debugging Overwatch Gate Logic ---")
    
    # 1. Mock Config (Profile = Overwatch)
    scan_config = MagicMock(spec=ScanConfig)
    scan_config.profile = "overwatch"
    scan_config.timeframes = ["1d", "4h", "1h", "15m"]
    scan_config.entry_timeframes = ["15m", "5m"]
    
    # 2. Mock HTF Structure
    # SHORT Scenario: Price rising into Bearish OB
    # Price = 94800. Bearish OB Low = 95000.
    # Front-Running: Entry should be < 95000 (e.g. 94997.5).

    htf_ob = OrderBlock(
        timeframe="4h",
        high=96000.0,
        low=95000.0, # Resistance Level
        direction="bearish",
        mitigation_level=0,
        displacement_strength=0.8,
        freshness_score=0.9,
        timestamp=1000000 
    )
    
    # 3. Mock Snapshot
    snapshot = SMCSnapshot(
        order_blocks=[htf_ob],
        fvgs=[],
        liquidity_sweeps=[], 
        structural_breaks=[]
    )
    
    # 4. Context Mock
    context = MagicMock()
    context.smc_snapshot = snapshot
    context.current_price = 94800.0 # Below resistance
    context.symbol = "BTC/USDT"
    
    # Cycles & Indicators
    context.cycle_context = MagicMock()
    context.cycle_context.is_aligned = MagicMock(return_value=True) 
    context.multi_tf_indicators = MagicMock()
    
    # Real Config
    scan_config = ScanConfig(
        profile="strike",
        timeframes=["4h", "1h", "15m", "5m"],
        primary_planning_timeframe="15m"
    )
    # Ensure planner config is set (will be updated by defaults_for_mode + override injection)
    scan_config.planner = None # Force re-creation inside generate_trade_plan
    # Strike overrides allow front-running (-0.05 ATR), so entry should be > OB High
    scan_config.overrides = {"entry_zone_offset_atr": -0.05} # Explicitly forcing it for test if not loaded from file
    
    # ...
    # Set Price inside 4H OB (95k-94k) AND near 15m OB (94.9k).
    context.current_price = 95000.0  
    print(f"HTF OB: {htf_ob.high}-{htf_ob.low} ({htf_ob.timeframe})")
    # Mock dictionary access for indicators['15m']
    indicators_15m = MagicMock()
    indicators_15m.atr = 50.0
    context.multi_tf_indicators.by_timeframe = {"15m": indicators_15m, "4h": indicators_15m}
    context.multi_tf_indicators.__getitem__ = lambda self, key: self.by_timeframe.get(key)
    # Mock Confluence
    confluence = MagicMock()
    confluence.score = 80.0
    confluence.breakdown = {}
    
    # Fix p_win calculation issue
    # p_win_raw = confluence.score / 100.0
    # Ensure this works by patching the attribute access
    
    print(f"Testing with Price: {context.current_price}")
    
    try:
        plan = await generate_trade_plan(
            symbol="BTC/USDT",
            direction="SHORT",
            setup_type="OB_PULLBACK",
            smc_snapshot=context.smc_snapshot,
            indicators=context.multi_tf_indicators,
            confluence_breakdown=confluence,
            config=scan_config,
            current_price=context.current_price
        )
        print("✅ Plan Generated Successfully!")
        print(f"Entry Zone: {plan.entry.entry_zone}")
        
    except ValueError as e:
        print(f"❌ Planner Rejected: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_overwatch_gate())
