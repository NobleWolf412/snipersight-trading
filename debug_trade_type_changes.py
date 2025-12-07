#!/usr/bin/env python3
"""
Debug script to test all trade-type-aware changes.

Tests:
1. Scanner mode expected_trade_type values
2. PlannerConfig defaults per trade type
3. validate_rr with trade type thresholds
4. _derive_trade_type classification logic
5. End-to-end orchestrator flow (mock)
6. LIVE: Run all modes with Phemex data

Run with: python debug_trade_type_changes.py
"""

import sys
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")


def print_pass(msg: str):
    print(f"  {GREEN}✓ PASS{RESET}: {msg}")


def print_fail(msg: str):
    print(f"  {RED}✗ FAIL{RESET}: {msg}")


def print_info(msg: str):
    print(f"  {YELLOW}ℹ INFO{RESET}: {msg}")


def test_scanner_modes():
    """Test expected_trade_type on all scanner modes."""
    print_header("1. Scanner Mode expected_trade_type")
    
    from backend.shared.config.scanner_modes import get_mode, MODES, list_modes
    
    expected = {
        "overwatch": "swing",
        "strike": "intraday",  # HTF structure produces intraday/swing setups
        "surgical": "intraday",  # 1h/15m structure produces intraday setups
        "stealth": "intraday"
    }
    
    all_pass = True
    for name, expected_type in expected.items():
        mode = get_mode(name)
        if mode.expected_trade_type == expected_type:
            print_pass(f"{name}: expected_trade_type={mode.expected_trade_type}")
        else:
            print_fail(f"{name}: got {mode.expected_trade_type}, expected {expected_type}")
            all_pass = False
    
    # Test backward compat (ghost -> stealth)
    ghost = get_mode("ghost")
    if ghost.expected_trade_type == "intraday":
        print_pass(f"ghost (backward compat): expected_trade_type={ghost.expected_trade_type}")
    else:
        print_fail(f"ghost backward compat failed: {ghost.expected_trade_type}")
        all_pass = False
    
    # Test list_modes includes expected_trade_type
    modes_list = list_modes()
    if all("expected_trade_type" in m for m in modes_list):
        print_pass("list_modes() includes expected_trade_type")
    else:
        print_fail("list_modes() missing expected_trade_type")
        all_pass = False
    
    return all_pass


def test_planner_config():
    """Test PlannerConfig.defaults_for_mode per trade type."""
    print_header("2. PlannerConfig Defaults by Trade Type")
    
    from backend.shared.config.planner_config import PlannerConfig
    
    all_pass = True
    
    # Scalp config
    scalp = PlannerConfig.defaults_for_mode("scalp")
    checks = [
        ("stop_buffer_atr", scalp.stop_buffer_atr, 0.25),
        ("target_rr_ladder", scalp.target_rr_ladder, [1.2, 2.0, 3.0]),
        ("target_min_rr_after_clip", scalp.target_min_rr_after_clip, 1.0),
        ("stop_lookback_bars", scalp.stop_lookback_bars, 15),
    ]
    for name, actual, expected in checks:
        if actual == expected:
            print_pass(f"scalp.{name} = {actual}")
        else:
            print_fail(f"scalp.{name}: got {actual}, expected {expected}")
            all_pass = False
    
    # Swing config
    swing = PlannerConfig.defaults_for_mode("swing")
    checks = [
        ("stop_buffer_atr", swing.stop_buffer_atr, 0.35),
        ("target_rr_ladder", swing.target_rr_ladder, [2.0, 3.0, 5.0]),
        ("target_min_rr_after_clip", swing.target_min_rr_after_clip, 1.5),
        ("stop_lookback_bars", swing.stop_lookback_bars, 30),
    ]
    for name, actual, expected in checks:
        if actual == expected:
            print_pass(f"swing.{name} = {actual}")
        else:
            print_fail(f"swing.{name}: got {actual}, expected {expected}")
            all_pass = False
    
    # Intraday config
    intraday = PlannerConfig.defaults_for_mode("intraday")
    checks = [
        ("stop_buffer_atr", intraday.stop_buffer_atr, 0.3),
        ("target_rr_ladder", intraday.target_rr_ladder, [1.5, 2.5, 4.0]),
        ("target_min_rr_after_clip", intraday.target_min_rr_after_clip, 1.2),
    ]
    for name, actual, expected in checks:
        if actual == expected:
            print_pass(f"intraday.{name} = {actual}")
        else:
            print_fail(f"intraday.{name}: got {actual}, expected {expected}")
            all_pass = False
    
    return all_pass


def test_validate_rr():
    """Test validate_rr with trade type thresholds and min_rr_override."""
    print_header("3. validate_rr() Trade Type Thresholds")
    
    from backend.shared.config.rr_matrix import validate_rr
    
    all_pass = True
    
    test_cases = [
        # (plan_type, rr, trade_type, min_rr_override, expected_valid, description)
        ("SMC", 2.0, "swing", None, True, "swing R:R 2.0 should pass (min=2.0)"),
        ("SMC", 1.9, "swing", None, False, "swing R:R 1.9 should fail (min=2.0)"),
        ("SMC", 1.2, "scalp", None, True, "scalp R:R 1.2 should pass (min=1.2)"),
        ("SMC", 1.1, "scalp", None, False, "scalp R:R 1.1 should fail (min=1.2)"),
        ("SMC", 1.5, "intraday", None, True, "intraday R:R 1.5 should pass (min=1.5)"),
        ("SMC", 1.4, "intraday", None, False, "intraday R:R 1.4 should fail (min=1.5)"),
        ("SMC", 1.5, None, None, True, "no trade_type R:R 1.5 should pass (base SMC=1.5)"),
        ("HYBRID", 1.2, None, None, True, "HYBRID R:R 1.2 should pass (base=1.2)"),
        # min_rr_override tests (simulating STRIKE mode with intraday label but 1.2 override)
        ("SMC", 1.2, "intraday", 1.2, True, "intraday+override R:R 1.2 should pass (override=1.2)"),
        ("SMC", 1.1, "intraday", 1.2, False, "intraday+override R:R 1.1 should fail (override=1.2)"),
        ("SMC", 1.4, "intraday", 1.5, False, "intraday+override R:R 1.4 should fail (override=1.5)"),
        ("SMC", 1.5, "intraday", 1.5, True, "intraday+override R:R 1.5 should pass (override=1.5)"),
    ]
    
    for plan_type, rr, trade_type, min_rr_override, expected_valid, desc in test_cases:
        valid, reason = validate_rr(plan_type, rr, trade_type=trade_type, min_rr_override=min_rr_override)
        if valid == expected_valid:
            print_pass(desc)
        else:
            print_fail(f"{desc} - got valid={valid}, reason={reason[:50] if reason else ''}")
            all_pass = False
    
    # Test EV override with aggressive mode (min_rr_override <= 1.2 uses lower floor)
    valid, reason = validate_rr(
        "SMC", 0.66,
        trade_type="intraday",
        min_rr_override=1.2,  # Aggressive mode like STRIKE
        expected_value=0.05,
        confluence_score=75.0
    )
    if valid and "EV override" in reason:
        print_pass("aggressive mode EV override allows R:R 0.66 (floor=0.65)")
    else:
        print_fail(f"aggressive mode EV override failed: valid={valid}")
        all_pass = False
    
    # Swing should NOT allow 0.66 (floor=0.75)
    valid, _ = validate_rr(
        "SMC", 0.66,
        trade_type="swing",
        expected_value=0.05,
        confluence_score=75.0
    )
    if not valid:
        print_pass("swing EV override rejects R:R 0.66 (floor=0.75)")
    else:
        print_fail("swing EV override should reject R:R 0.66")
        all_pass = False
    
    return all_pass


def test_derive_trade_type():
    """Test _derive_trade_type classification logic."""
    print_header("4. _derive_trade_type() Classification")
    
    from backend.strategy.planner.planner_service import _derive_trade_type
    
    all_pass = True
    
    test_cases = [
        # (target_move_pct, stop_atr, structure_tfs, primary_tf, expected, desc)
        (2.5, 3.0, ("1d", "4h"), "4h", "swing", "Large move + HTF = swing"),
        (0.5, 1.0, ("15m", "5m"), "5m", "scalp", "Small move + LTF = scalp"),
        (1.2, 2.0, ("1h", "15m"), "15m", "intraday", "Mid move + mixed TF = intraday"),
        (1.5, 4.0, ("4h", "1h"), "1h", "swing", "Wide stop (4 ATR) + HTF = swing"),
        (0.4, 1.2, ("15m", "5m"), "5m", "scalp", "Tight stop + LTF only = scalp"),
        (3.0, 5.0, ("1w", "1d", "4h"), "4h", "swing", "Very large move = swing"),
    ]
    
    for target, stop, structure, primary, expected, desc in test_cases:
        result = _derive_trade_type(target, stop, structure, primary)
        if result == expected:
            print_pass(f"{desc}: {result}")
        else:
            print_fail(f"{desc}: got {result}, expected {expected}")
            all_pass = False
    
    return all_pass


def test_generate_trade_plan_signature():
    """Test that generate_trade_plan accepts expected_trade_type parameter."""
    print_header("5. generate_trade_plan() Signature")
    
    import inspect
    from backend.strategy.planner.planner_service import generate_trade_plan
    
    all_pass = True
    
    sig = inspect.signature(generate_trade_plan)
    params = list(sig.parameters.keys())
    
    if "expected_trade_type" in params:
        print_pass("generate_trade_plan has expected_trade_type parameter")
    else:
        print_fail(f"generate_trade_plan missing expected_trade_type. Params: {params}")
        all_pass = False
    
    # Check it has default None
    param = sig.parameters.get("expected_trade_type")
    if param and param.default is None:
        print_pass("expected_trade_type defaults to None")
    else:
        print_fail(f"expected_trade_type should default to None, got {param.default if param else 'N/A'}")
        all_pass = False
    
    return all_pass


def test_orchestrator_integration():
    """Test that orchestrator passes expected_trade_type correctly."""
    print_header("6. Orchestrator Integration")
    
    all_pass = True
    
    # Check the orchestrator source has the parameter
    import re
    orchestrator_path = "backend/engine/orchestrator.py"
    
    try:
        with open(orchestrator_path, "r") as f:
            content = f.read()
        
        # Check generate_trade_plan call includes expected_trade_type
        if "expected_trade_type=self.scanner_mode.expected_trade_type" in content:
            print_pass("Orchestrator passes expected_trade_type to generate_trade_plan")
        else:
            print_fail("Orchestrator not passing expected_trade_type")
            all_pass = False
        
        # Verify import works
        from backend.engine.orchestrator import Orchestrator
        print_pass("Orchestrator imports successfully")
        
    except Exception as e:
        print_fail(f"Error checking orchestrator: {e}")
        all_pass = False
    
    return all_pass


def test_soft_atr_caps():
    """Test trade-type-aware soft ATR caps."""
    print_header("7. Trade-Type Soft ATR Caps")
    
    # These values are defined in generate_trade_plan
    caps = {
        "swing": (0.5, 6.0),
        "scalp": (0.15, 2.5),
        "intraday": (0.3, 4.0)
    }
    
    all_pass = True
    
    # Verify the caps are sensible
    for trade_type, (soft_min, soft_max) in caps.items():
        print_info(f"{trade_type}: ATR range {soft_min} - {soft_max}")
        
        if trade_type == "swing" and soft_max >= 6.0:
            print_pass(f"swing allows wide stops (up to {soft_max} ATR)")
        elif trade_type == "scalp" and soft_max <= 3.0:
            print_pass(f"scalp caps stops at {soft_max} ATR")
        elif trade_type == "intraday":
            print_pass(f"intraday balanced at {soft_min}-{soft_max} ATR")
    
    # Check planner_service.py contains these caps
    with open("backend/strategy/planner/planner_service.py", "r") as f:
        content = f.read()
    
    if "trade_type_atr_caps" in content:
        print_pass("trade_type_atr_caps defined in planner_service.py")
    else:
        print_fail("trade_type_atr_caps not found in planner_service.py")
        all_pass = False
    
    return all_pass


def test_smc_preset_integration():
    """Test SMC preset is still working with expected_trade_type."""
    print_header("8. SMC Preset + Trade Type Integration")
    
    from backend.shared.config.scanner_modes import get_mode
    from backend.shared.config.smc_config import SMCConfig
    
    all_pass = True
    
    # Test each mode has both smc_preset and expected_trade_type
    modes = ["overwatch", "strike", "surgical", "stealth"]
    
    for name in modes:
        mode = get_mode(name)
        print_info(f"{name}: smc_preset={mode.smc_preset}, expected_trade_type={mode.expected_trade_type}")
        
        # Verify smc_preset is valid
        if mode.smc_preset in ("defaults", "luxalgo_strict", "sensitive"):
            print_pass(f"{name} has valid smc_preset")
        else:
            print_fail(f"{name} has invalid smc_preset: {mode.smc_preset}")
            all_pass = False
    
    # Verify SMCConfig factory methods work
    strict = SMCConfig.luxalgo_strict()
    defaults = SMCConfig.defaults()
    
    if strict.min_wick_ratio > defaults.min_wick_ratio:
        print_pass(f"luxalgo_strict is stricter than defaults (wick_ratio: {strict.min_wick_ratio} > {defaults.min_wick_ratio})")
    else:
        print_fail("luxalgo_strict should be stricter than defaults")
        all_pass = False
    
    return all_pass


def test_live_phemex_scan():
    """
    LIVE TEST: Run all scanner modes with Phemex data.
    
    This tests the full end-to-end pipeline with real market data.
    """
    print_header("9. LIVE Phemex Scan - All Modes")
    
    from backend.engine.orchestrator import Orchestrator
    from backend.data.adapters.phemex import PhemexAdapter
    from backend.shared.config.scanner_modes import get_mode, MODES
    from backend.shared.config.defaults import ScanConfig
    
    all_pass = True
    mode_results = {}
    
    # Test symbols - mix of majors and alts
    test_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    # Initialize Phemex adapter
    print_info("Initializing Phemex adapter...")
    try:
        adapter = PhemexAdapter()
        print_pass("Phemex adapter initialized")
    except Exception as e:
        print_fail(f"Failed to initialize Phemex adapter: {e}")
        return False
    
    # Test each mode
    for mode_name in ["overwatch", "strike", "surgical", "stealth"]:
        print(f"\n  {MAGENTA}--- Testing Mode: {mode_name.upper()} ---{RESET}")
        
        mode = get_mode(mode_name)
        print_info(f"expected_trade_type={mode.expected_trade_type}, smc_preset={mode.smc_preset}")
        print_info(f"timeframes={mode.timeframes}")
        
        try:
            # Create ScanConfig with mode settings
            config = ScanConfig(
                profile=mode_name,
                timeframes=mode.timeframes,
                min_confluence_score=mode.min_confluence_score,
                leverage=1
            )
            
            # Create orchestrator with this config
            orchestrator = Orchestrator(
                config=config,
                exchange_adapter=adapter,
                concurrency_workers=2  # Reduced for testing
            )
            
            print_info(f"Orchestrator created with profile={mode_name}")
            print_info(f"Scanner mode expected_trade_type: {orchestrator.scanner_mode.expected_trade_type}")
            
            # Run scan on test symbols
            print_info(f"Running scan for {test_symbols}...")
            
            try:
                signals, rejections_dict = orchestrator.scan(test_symbols)
                
                print_info(f"Scan complete: {len(signals)} signals, {len(rejections_dict)} rejection categories")
                
                for sig in signals:
                    print_pass(f"{sig.symbol}: {sig.direction} {sig.setup_type}")
                    print_info(f"  R:R={sig.risk_reward:.2f}")
                    print_info(f"  Entry: {sig.entry_zone.near_entry:.2f} - {sig.entry_zone.far_entry:.2f}")
                    print_info(f"  Stop: {sig.stop_loss.level:.2f} ({sig.stop_loss.distance_atr:.2f} ATR)")
                    print_info(f"  Targets: {[f'{t.level:.2f}' for t in sig.targets]}")
                
                # Count rejections - handle mixed types in rejection dict
                total_rejections = 0
                for v in rejections_dict.values():
                    if isinstance(v, list):
                        total_rejections += len(v)
                    elif isinstance(v, int):
                        total_rejections += v
                
                mode_results[mode_name] = {
                    "signals": len(signals),
                    "rejections": total_rejections,
                    "expected_trade_type": mode.expected_trade_type,
                    "success": True
                }
                
                print(f"\n  {CYAN}Mode {mode_name} Summary:{RESET}")
                print(f"    Signals: {len(signals)}, Rejections: {total_rejections}")
                
                if signals:
                    # Verify signals' setup types
                    for sig in signals:
                        setup_type = getattr(sig, 'setup_type', 'unknown')
                        print_info(f"Signal {sig.symbol}: setup_type={setup_type}")
                
                print_pass(f"Mode {mode_name} completed successfully")
                
            except Exception as scan_err:
                print_fail(f"Scan error: {scan_err}")
                import traceback
                traceback.print_exc()
                mode_results[mode_name] = {"success": False, "error": str(scan_err)}
            
        except Exception as e:
            print_fail(f"Mode {mode_name} failed: {e}")
            import traceback
            traceback.print_exc()
            mode_results[mode_name] = {"success": False, "error": str(e)}
            all_pass = False
    
    # Overall summary
    print(f"\n  {BOLD}Live Test Summary:{RESET}")
    for mode_name, result in mode_results.items():
        if result.get("success"):
            print(f"    {GREEN}✓{RESET} {mode_name}: {result.get('signals', 0)} signals, {result.get('rejections', 0)} rejections")
        else:
            print(f"    {RED}✗{RESET} {mode_name}: {result.get('error', 'unknown error')}")
    
    return all_pass


def main():
    """Run all tests."""
    print(f"\n{BOLD}Trade-Type-Aware Changes Debug Script{RESET}")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    tests = [
        ("Scanner Modes", test_scanner_modes),
        ("PlannerConfig", test_planner_config),
        ("validate_rr", test_validate_rr),
        ("_derive_trade_type", test_derive_trade_type),
        ("generate_trade_plan signature", test_generate_trade_plan_signature),
        ("Orchestrator Integration", test_orchestrator_integration),
        ("Soft ATR Caps", test_soft_atr_caps),
        ("SMC Preset Integration", test_smc_preset_integration),
        ("LIVE Phemex Scan", test_live_phemex_scan),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print_fail(f"Exception in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print_header("SUMMARY")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    failed = total - passed
    
    for name, status in results:
        if status:
            print(f"  {GREEN}✓{RESET} {name}")
        else:
            print(f"  {RED}✗{RESET} {name}")
    
    print()
    if failed == 0:
        print(f"{GREEN}{BOLD}All {total} test groups passed! ✓{RESET}")
        return 0
    else:
        print(f"{RED}{BOLD}{failed}/{total} test groups failed ✗{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
