
import logging
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add backward compatibility for imports
sys.path.append(os.getcwd())

from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG
from backend.shared.models.data import MultiTimeframeData
from backend.shared.config.defaults import ScanConfig
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.services.smc_service import SMCDetectionService
from backend.strategy.confluence import scorer
from backend.strategy.planner import planner_service
from backend.shared.config.planner_config import PlannerConfig

# --- Helper Functions ---

def create_mock_ob(timeframe, direction, high, low, grade='B'):
    return OrderBlock(
        timeframe=timeframe,
        direction=direction,
        high=high,
        low=low,
        timestamp=datetime.now(),
        displacement_strength=0.8,
        mitigation_level=0.0,
        freshness_score=100.0,
        grade=grade,
        displacement_atr=1.5
    )

def create_mock_fvg(timeframe, direction, top, bottom):
    return FVG(
        timeframe=timeframe,
        direction=direction,
        top=top,
        bottom=bottom,
        timestamp=datetime.now(),
        grade='A',
        size=abs(top-bottom),
        overlap_with_price=0.0
    )

def mock_tf_data():
    """Create dummy MultiTimeframeData"""
    data = MultiTimeframeData(symbol="BTC/USDT", timeframes={})
    # We don't strictly need real DF content if we mock the detectors
    return data

def create_mock_indicators():
    mock_ind = MagicMock()
    # Set scalar values to avoid comparison errors
    mock_ind.rsi = 50.0
    mock_ind.stoch_rsi_k = 50.0
    mock_ind.stoch_rsi = 50.0 # Fallback
    mock_ind.stoch_rsi_d = 50.0
    mock_ind.macd_hist = 0.5
    mock_ind.macd_line = 1.0
    mock_ind.macd_signal = 0.5
    mock_ind.adx = 25.0
    mock_ind.volume_ma_ratio = 1.2
    mock_ind.atr = 10.0
    mock_ind.volatility_score = 50.0
    mock_ind.mfi = 50.0
    mock_ind.obv_slope = 0.0
    mock_ind.cci = 0.0
    mock_ind.volume_consecutive_up = 0
    mock_ind.volume_consecutive_down = 0
    mock_ind.bb_width_percentile = 50.0
    mock_ind.bb_upper = 105.0
    mock_ind.bb_lower = 95.0
    mock_ind.vwap_deviation = 0.0
    mock_ind.volume_spike = False
    mock_ind.volume_acceleration = 0.0
    mock_ind.volume_accel_direction = 'neutral'
    mock_ind.volume_is_accelerating = False
    mock_ind.volume_consecutive_increases = 0
    mock_ind.volume_exhaustion = False
    mock_ind.atr_percent = 0.5
    return mock_ind

# --- Test Cases ---

def test_1_scoring_weights():
    """Verify Mode-Aware OB Weights in Scorer"""
    logger.info("--- Test 1: Scoring Weights ---")
    
    modes = {
        'overwatch': 0.25,
        'strike': 0.18,
        'surgical': 0.15,
        'stealth': 0.20
    }
    
    for mode, expected_weight in modes.items():
        # Setup
        config = ScanConfig(profile=mode)
        # Create a snapshot with 1 OB so it triggers scoring
        ob = create_mock_ob('1h', 'bullish', 100, 90)
        snapshot = SMCSnapshot(order_blocks=[ob], fvgs=[], structural_breaks=[], liquidity_sweeps=[])
        
        # We assume _score_order_blocks returns > 0
        with patch('backend.strategy.confluence.scorer._score_order_blocks', return_value=80.0):
             # Mock config for scorer
             mock_tf_inds = {'1h': create_mock_indicators()}
             result = scorer.calculate_confluence_score(
                 smc_snapshot=snapshot,
                 indicators=MagicMock(by_timeframe=mock_tf_inds), # Mock indicators with 1 TF
                 current_price=100.0,
                 direction='bullish',
                 config=config,
                 volume_profile=None,
                 cycle_context=None,
                 reversal_context=None
             )
             
        # Find OB factor
        ob_factor = next((f for f in result.factors if f.name == "Order Block"), None)
        
        if ob_factor:
            # Note: weights are normalized if multiple factors exist, but here we only have OB? 
            # Wait, calculate_confluence_breakdown might add other factors (regime etc).
            # The weights constructed in the list BEFORE normalization are what we check.
            # But the result returned has normalized weights.
            # However, if ONLY OB is present (and maybe HTF/Regime defaults), normalization triggers.
            # We must inspect the code: `factors` list construction uses hardcoded weights.
            # We can't easily inspect the internal `factors` list inside the function without mocking the ConfluenceFactor init?
            # Or we can check if the output weight roughly matches implicit normalization.
            # Better: The user changed the code to use `ob_weight_map`. We can trust the code if we verify the logic path.
            # But let's try to infer from the normalized weight if possible, or just mock ConfluenceFactor to capture init args.
            
            # Since normalized weights depend on what else is there, this is tricky.
            # Let's trust the inspection for now, or just print the normalized weight to see relative sizing if we add a reference factor.
            pass
        else:
            logger.error(f"FAIL: No OB factor found for mode {mode}")
            continue

        # Actually, let's just inspect the raw weight by mocking ConfluenceFactor? 
        # Easier: The weight is passed to ConfluenceFactor constructor.
        # We can mock ConfluenceFactor in the scorer module.
        pass

    # Re-run with mocking ConfluenceFactor to verify initialization
    with patch('backend.strategy.confluence.scorer.ConfluenceFactor') as MockFactor:
        MockFactor.side_effect = lambda name, score, weight, rationale: MagicMock(name=name, score=score, weight=weight, rationale=rationale)
        
        for mode, expected_weight in modes.items():
            config = ScanConfig(profile=mode)
            ob = create_mock_ob('1h', 'bullish', 100, 90)
            snapshot = SMCSnapshot(order_blocks=[ob], fvgs=[], structural_breaks=[], liquidity_sweeps=[])
            
            with patch('backend.strategy.confluence.scorer._score_order_blocks', return_value=80.0):
                # We need to supply basic indicators to avoid crashes
                mock_tf_inds = {'1h': create_mock_indicators()}
                scorer.calculate_confluence_score(
                     smc_snapshot=snapshot,
                     indicators=MagicMock(by_timeframe=mock_tf_inds),
                     current_price=100.0,
                     direction='bullish',
                     config=config
                )
            
            # Check calls
            found = False
            for call_args in MockFactor.call_args_list:
                args, kwargs = call_args
                name = kwargs.get('name')
                weight = kwargs.get('weight')
                if name == "Order Block":
                    if abs(weight - expected_weight) < 0.01:
                         logger.info(f"✅ Mode {mode}: OB Weight = {weight} (Expected {expected_weight})")
                         found = True
                    else:
                         logger.error(f"❌ Mode {mode}: OB Weight = {weight} (Expected {expected_weight})")
            
            if not found:
                logger.error(f"❌ Mode {mode}: Order Block factor not created")
            
            MockFactor.reset_mock()


def test_2_htf_backing():
    """Verify HTF Backing Validation (Filtering isolated LTF OBs)"""
    logger.info("\n--- Test 2: HTF Backing Validation ---")
    
    # Setup Service
    service = SMCDetectionService(mode='strike') # Strike allows LTF OBs
    
    # Mock Detect: We want to control the `_detect_timeframe_patterns` output
    # to return specific raw OBs.
    
    # Scenario: 
    # 1. 5m OB (Bullish) at 100-101 (Isolated) -> Should be REJECTED
    # 2. 5m OB (Bullish) at 200-201 (Backed by 1H OB at 199-202) -> Should be KEPT
    
    ob_isolated = create_mock_ob('5m', 'bullish', 101, 100)
    ob_backed = create_mock_ob('5m', 'bullish', 201, 200)
    ob_backer = create_mock_ob('1h', 'bullish', 202, 199)
    
    # Mock data frames (empty is fine as we assume _detect_timeframe_patterns is mocked)
    # BUT wait, the `detect` method loops over `multi_tf_data.timeframes`. 
    # We need keys in multi_tf_data.
    # Create valid DF with all columns
    dates_5m = pd.date_range(start='2024-01-01', periods=25, freq='5min')
    df_5m = pd.DataFrame({
        'open': [100.0]*25, 'high': [105.0]*25, 'low': [95.0]*25, 'close': [100.0]*25, 'volume': [1000.0]*25,
        'timestamp': dates_5m
    }, index=dates_5m)
    
    dates_1h = pd.date_range(start='2024-01-01', periods=25, freq='1h')
    df_1h = pd.DataFrame({
        'open': [200.0]*25, 'high': [205.0]*25, 'low': [195.0]*25, 'close': [200.0]*25, 'volume': [1000.0]*25,
        'timestamp': dates_1h
    }, index=dates_1h)

    tf_data = MultiTimeframeData(symbol="TEST", timeframes={
        '5m': df_5m,
        '1h': df_1h,
    })

    # We patch `_detect_timeframe_patterns` to return our predefined lists
    def side_effect_detect(timeframe, df, current_price):
        if timeframe == '5m':
             return {'order_blocks': [ob_isolated, ob_backed], 'fvgs': [], 'structure_breaks': [], 'liquidity_sweeps': [], 'equal_highs': [], 'equal_lows': [], 'liquidity_pools': [], 'swing_structure': None, 'premium_discount': None}
        if timeframe == '1h':
             return {'order_blocks': [ob_backer], 'fvgs': [], 'structure_breaks': [], 'liquidity_sweeps': [], 'equal_highs': [], 'equal_lows': [], 'liquidity_pools': [], 'swing_structure': None, 'premium_discount': None}
        return {'order_blocks': [], 'fvgs': [], 'structure_breaks': [], 'liquidity_sweeps': [], 'equal_highs': [], 'equal_lows': [], 'liquidity_pools': [], 'swing_structure': None, 'premium_discount': None}

    with patch.object(service, '_detect_timeframe_patterns', side_effect=side_effect_detect):
        # Also need to mock _detect_key_levels and other helpers to avoid errors
        with patch.object(service, '_detect_key_levels', return_value=None):
            with patch.object(service, '_update_mitigation', side_effect=lambda a, b: b): # returns obs passed as 2nd arg? No, first arg is data, second is obs. Return obs.
                 snapshot = service.detect(tf_data, current_price=205.0)

    # Check results
    obs = snapshot.order_blocks
    
    # Verify Isolated Removed
    if ob_isolated in obs:
        logger.error("❌ Isolated 5m OB was NOT removed")
    else:
        logger.info("✅ Isolated 5m OB removed")
        
    # Verify Backed Kept
    if ob_backed in obs:
        logger.info("✅ Backed 5m OB kept")
    else:
        logger.error("❌ Backed 5m OB was removed incorrectly")
        
    # Verify Backer Kept
    if ob_backer in obs:
        logger.info("✅ HTF Backer OB kept")


def test_3_planner_gates():
    """Verify Overwatch Gate and Surgical Filter"""
    logger.info("\n--- Test 3: Planner Gates ---")
    
    # --- Surgical Filter (Grade C Rejection) ---
    logger.info("Testing Surgical Grade Filter...")
    config_surgical = ScanConfig(profile='surgical')
    planner_cfg = PlannerConfig()
    
    ob_grade_a = create_mock_ob('15m', 'bullish', 100, 99, grade='A')
    ob_grade_c = create_mock_ob('15m', 'bullish', 98, 97, grade='C')
    
    snapshot = SMCSnapshot(order_blocks=[ob_grade_a, ob_grade_c], fvgs=[], structural_breaks=[], liquidity_sweeps=[])
    
    # We call _calculate_entry_zone directly
    # Need to mock _get_allowed_entry_tfs to include 15m
    with patch('backend.strategy.planner.planner_service._get_allowed_entry_tfs', return_value={'15m'}):
        # We also need to mock _classify_atr_regime to avoid dependency issues
        with patch('backend.strategy.planner.planner_service._classify_atr_regime', return_value='balanced'):
             entry_zone, used = planner_service._calculate_entry_zone(
                 is_bullish=True,
                 smc_snapshot=snapshot,
                 current_price=105.0,
                 atr=1.0,
                 primary_tf='15m',
                 setup_archetype=None,
                 config=config_surgical,
                 planner_cfg=planner_cfg
             )
    
    # We assume the mocked call uses OrderBlocks.
    # To verify which one was used, we check the rationale or entry price.
    # Grade A OB High is 100. Grade C High is 98.
    # If filtered correctly, Grade C should be ignored.
    # The function picks the "Best" OB from the remaining list.
    # Best score uses grade weight. A > C.
    # But if C is filtered, it's not even a candidate.
    # Let's verify by passing ONLY a Grade C OB. It should fallback (return used_structure=False) OR raise error?
    # Actually if NO obs remain, it falls back to ATR.
    
    snapshot_c_only = SMCSnapshot(order_blocks=[ob_grade_c], fvgs=[], structural_breaks=[], liquidity_sweeps=[])
    with patch('backend.strategy.planner.planner_service._get_allowed_entry_tfs', return_value={'15m'}):
        with patch('backend.strategy.planner.planner_service._classify_atr_regime', return_value='balanced'):
             entry_zone, used = planner_service._calculate_entry_zone(
                 is_bullish=True,
                 smc_snapshot=snapshot_c_only,
                 current_price=105.0,
                 atr=1.0,
                 primary_tf='15m',
                 setup_archetype=None,
                 config=config_surgical,
                 planner_cfg=planner_cfg
             )
    
    if used is False:
        logger.info("✅ Surgical Mode rejected Grade C OB (Fallback trigger)")
    else:
        logger.error(f"❌ Surgical Mode accepted Grade C OB (Used structure: {used})")

    # --- Overwatch Gate (HTF Requirement) ---
    logger.info("Testing Overwatch HTF Gate...")
    config_overwatch = ScanConfig(profile='overwatch')
    
    # Snapshot with NO OBs/FVGs
    snapshot_empty = SMCSnapshot(order_blocks=[], fvgs=[], structural_breaks=[], liquidity_sweeps=[])
    
    try:
        with patch('backend.strategy.planner.planner_service._get_allowed_entry_tfs', return_value={'1h'}):
             entry_zone, used = planner_service._calculate_entry_zone(
                 is_bullish=True,
                 smc_snapshot=snapshot_empty,
                 current_price=105.0,
                 atr=1.0,
                 primary_tf='1h',
                 setup_archetype=None,
                 config=config_overwatch,
                 planner_cfg=planner_cfg
             )
        logger.error("❌ Overwatch Mode DID NOT raise ValueError on empty structure")
    except ValueError as e:
        if "Overwatch mode requires valid HTF structure" in str(e):
            logger.info("✅ Overwatch Mode matched expected ValueError: " + str(e))
        else:
            logger.warning("⚠️ Overwatch Mode raised different ValueError: " + str(e))
    except Exception as e:
        logger.error(f"❌ Unexpected exception type: {type(e)} - {e}")


if __name__ == "__main__":
    test_1_scoring_weights()
    test_2_htf_backing()
    test_3_planner_gates()
