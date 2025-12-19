#!/usr/bin/env python3
"""
Comprehensive Feature Test - Phemex Live Data

Tests the following recently implemented features:
1. Universal Momentum Gate (ADX + RSI climax detection)
2. Auto-Leverage Derating (wide stops → lower leverage recommendation)
3. Overwatch Volatility Exception (explosive regime → ATR fallback allowed)
4. ADX Indicator Integration
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Dict, List, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Reduce noise from other loggers
logging.getLogger('ccxt').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


async def run_comprehensive_test():
    """Run comprehensive test of new features."""
    
    print("\n" + "="*80)
    print("🔬 COMPREHENSIVE FEATURE TEST - PHEMEX LIVE DATA")
    print("="*80)
    
    # Import after path setup
    from backend.engine.orchestrator import Orchestrator
    from backend.shared.config.scanner_modes import get_mode
    from backend.shared.config.defaults import ScanConfig
    from backend.data.adapters.phemex import PhemexAdapter
    
    # Test symbols - mix of volatile and stable
    test_symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT',  # Major
        'DOGE/USDT', 'XRP/USDT',  # High volatility
        'BNB/USDT', 'ADA/USDT', 'AVAX/USDT'  # Mid-cap
    ]
    
    results = {
        'momentum_gate_tests': [],
        'leverage_derating_tests': [],
        'overwatch_exception_tests': [],
        'adx_detection_tests': [],
        'signals_generated': [],
        'rejections': []
    }
    
    # Test each mode
    modes_to_test = ['surgical', 'stealth', 'overwatch']
    
    for mode_name in modes_to_test:
        print(f"\n{'─'*80}")
        print(f"📡 TESTING MODE: {mode_name.upper()}")
        print(f"{'─'*80}")
        
        try:
            mode = get_mode(mode_name)
        except Exception as e:
            print(f"  ❌ Mode '{mode_name}' not found: {e}")
            continue
        
        try:
            # Create config with test leverage (10x to trigger derating)
            config = ScanConfig(
                profile=mode.profile,
                min_confluence_score=55.0,  # Lower threshold to see more signals
                min_rr_ratio=1.2,
                leverage=10,
            )
            
            # Create exchange adapter
            exchange = PhemexAdapter()
            
            # Create orchestrator
            orchestrator = Orchestrator(
                config=config,
                exchange_adapter=exchange
            )
            
            print(f"  ⏳ Scanning {len(test_symbols)} symbols...")
            
            # Run scan
            scan_results = await orchestrator.scan(test_symbols)
            
            # Analyze results
            signals = scan_results.get('signals', [])
            rejections = scan_results.get('rejections', [])
            metadata = scan_results.get('metadata', {})
            
            print(f"\n  📊 RESULTS FOR {mode_name.upper()}:")
            print(f"     Signals: {len(signals)}")
            print(f"     Rejections: {len(rejections)}")
            
            # Check signals for new features
            for signal in signals:
                symbol = signal.get('symbol', 'Unknown')
                plan_meta = signal.get('metadata', {})
                
                # Check 1: Leverage Derating
                lev_adj = plan_meta.get('leverage_adjustments', {})
                if lev_adj and lev_adj.get('leverage_derated'):
                    result = {
                        'mode': mode_name,
                        'symbol': symbol,
                        'original_lev': lev_adj.get('original_leverage'),
                        'suggested_lev': lev_adj.get('suggested_leverage'),
                        'reason': lev_adj.get('reason')
                    }
                    results['leverage_derating_tests'].append(result)
                    print(f"     ⚠️ LEVERAGE DERATING: {symbol}")
                    print(f"        {lev_adj.get('original_leverage')}x → {lev_adj.get('suggested_leverage')}x")
                    print(f"        Reason: {lev_adj.get('reason')}")
                
                # Check 2: ATR Regime
                atr_regime = plan_meta.get('atr_regime', {})
                if atr_regime:
                    regime_label = atr_regime.get('label', 'unknown')
                    if regime_label in ('elevated', 'explosive'):
                        results['overwatch_exception_tests'].append({
                            'mode': mode_name,
                            'symbol': symbol,
                            'regime': regime_label,
                            'allowed_fallback': mode_name == 'overwatch'
                        })
                        print(f"     🌊 HIGH VOLATILITY: {symbol} ({regime_label})")
                
                # Store signal
                results['signals_generated'].append({
                    'mode': mode_name,
                    'symbol': symbol,
                    'direction': signal.get('direction'),
                    'confidence': signal.get('confidence_score'),
                    'plan_type': signal.get('plan_type'),
                    'conviction': signal.get('conviction_class')
                })
            
            # Check rejections for momentum gate blocks
            for rejection in rejections:
                symbol = rejection.get('symbol', 'Unknown')
                reason = rejection.get('reason', '')
                
                if 'momentum' in reason.lower() or 'blocked' in reason.lower():
                    results['momentum_gate_tests'].append({
                        'mode': mode_name,
                        'symbol': symbol,
                        'reason': reason,
                        'blocked': True
                    })
                    print(f"     🛑 MOMENTUM GATE BLOCK: {symbol}")
                    print(f"        Reason: {reason[:80]}...")
                
                results['rejections'].append({
                    'mode': mode_name,
                    'symbol': symbol,
                    'reason': reason
                })
            
        except Exception as e:
            print(f"  ❌ Error testing {mode_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary Report
    print("\n" + "="*80)
    print("📋 FEATURE TEST SUMMARY")
    print("="*80)
    
    print(f"\n1️⃣ UNIVERSAL MOMENTUM GATE:")
    if results['momentum_gate_tests']:
        for test in results['momentum_gate_tests']:
            print(f"   • {test['mode']}/{test['symbol']}: {'BLOCKED' if test['blocked'] else 'ALLOWED'}")
            print(f"     Reason: {test['reason'][:60]}...")
    else:
        print("   No momentum gate blocks detected (trades either passed or were rejected for other reasons)")
    
    print(f"\n2️⃣ AUTO-LEVERAGE DERATING:")
    if results['leverage_derating_tests']:
        for test in results['leverage_derating_tests']:
            print(f"   • {test['mode']}/{test['symbol']}: {test['original_lev']}x → {test['suggested_lev']}x")
            print(f"     {test['reason']}")
    else:
        print("   No leverage derating triggered (all stops within safe range for 10x)")
    
    print(f"\n3️⃣ OVERWATCH VOLATILITY EXCEPTION:")
    if results['overwatch_exception_tests']:
        for test in results['overwatch_exception_tests']:
            status = "✅ ALLOWED FALLBACK" if test['allowed_fallback'] else "Would allow in Overwatch"
            print(f"   • {test['mode']}/{test['symbol']}: {test['regime']} regime - {status}")
    else:
        print("   No elevated/explosive regimes detected")
    
    print(f"\n4️⃣ SIGNALS GENERATED:")
    print(f"   Total: {len(results['signals_generated'])}")
    for signal in results['signals_generated'][:10]:  # Show first 10
        conf = signal.get('confidence') or 0
        print(f"   • {signal['mode']}/{signal['symbol']}: {signal['direction']} | "
              f"Conf: {conf:.1f} | Type: {signal['plan_type']} | Conv: {signal['conviction']}")
    
    print(f"\n5️⃣ REJECTIONS:")
    print(f"   Total: {len(results['rejections'])}")
    
    # Group by reason category
    reason_counts = {}
    for rej in results['rejections']:
        reason = rej['reason']
        # Categorize
        if 'momentum' in reason.lower() or 'blocked' in reason.lower():
            cat = 'Momentum Gate'
        elif 'confluence' in reason.lower():
            cat = 'Low Confluence'
        elif 'stop' in reason.lower():
            cat = 'Stop Issues'
        elif 'structure' in reason.lower():
            cat = 'No Structure'
        elif 'r:r' in reason.lower() or 'risk' in reason.lower():
            cat = 'Risk/Reward'
        else:
            cat = 'Other'
        reason_counts[cat] = reason_counts.get(cat, 0) + 1
    
    for cat, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        print(f"   • {cat}: {count}")
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80)
    
    return results


if __name__ == "__main__":
    try:
        results = asyncio.run(run_comprehensive_test())
    except KeyboardInterrupt:
        print("\n⛔ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
