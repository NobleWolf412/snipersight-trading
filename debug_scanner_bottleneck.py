"""
SniperSight Scanner Diagnostic Script

This script helps identify where signals are getting filtered out.
Run this to see detailed rejection reasons for your scans.

Usage:
    python backend/debug_scanner_bottleneck.py --symbols BTC/USDT ETH/USDT SOL/USDT --mode strike

Or scan your full watchlist:
    python backend/debug_scanner_bottleneck.py --mode strike --count 20
"""

import sys
import argparse
from collections import defaultdict
from typing import Dict, List, Any
import json

# Add backend to path
sys.path.insert(0, 'backend')

from engine.orchestrator import Orchestrator
from shared.config.defaults import ScanConfig
from shared.config.scanner_modes import get_mode
from data.adapters.bybit import BybitAdapter


def analyze_rejection_breakdown(rejection_stats: Dict[str, List[Dict[str, Any]]]) -> None:
    """Print detailed breakdown of rejections."""
    
    total_rejected = sum(len(v) for v in rejection_stats.values())
    
    print("\n" + "="*80)
    print(f"REJECTION BREAKDOWN ({total_rejected} total)")
    print("="*80)
    
    # Sort by count
    sorted_reasons = sorted(
        rejection_stats.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )
    
    for reason_type, rejections in sorted_reasons:
        if not rejections:
            continue
        
        count = len(rejections)
        pct = (count / total_rejected * 100) if total_rejected > 0 else 0
        
        print(f"\n{reason_type.upper()}: {count} ({pct:.1f}%)")
        print("-" * 80)
        
        if reason_type == "low_confluence":
            # Detailed confluence analysis
            scores = [r.get('score', 0) for r in rejections]
            thresholds = [r.get('threshold', 0) for r in rejections]
            avg_score = sum(scores) / len(scores) if scores else 0
            avg_threshold = sum(thresholds) / len(thresholds) if thresholds else 0
            
            print(f"  Average Score: {avg_score:.1f}")
            print(f"  Average Threshold: {avg_threshold:.1f}")
            print(f"  Gap: {avg_threshold - avg_score:.1f} points")
            
            # Show worst performers
            print("\n  Worst 5 Performers:")
            sorted_by_gap = sorted(
                rejections,
                key=lambda r: r.get('threshold', 0) - r.get('score', 0),
                reverse=True
            )[:5]
            
            for r in sorted_by_gap:
                symbol = r.get('symbol', 'UNKNOWN')
                score = r.get('score', 0)
                threshold = r.get('threshold', 0)
                gap = threshold - score
                top_factors = r.get('top_factors', [])
                
                print(f"    {symbol}: {score:.1f}/{threshold:.1f} (gap={gap:.1f})")
                print(f"      Top factors: {', '.join(top_factors[:3])}")
        
        elif reason_type == "missing_critical_tf":
            # Which timeframes are missing?
            missing_tfs = defaultdict(int)
            for r in rejections:
                for tf in r.get('missing_timeframes', []):
                    missing_tfs[tf] += 1
            
            print("  Missing Timeframes:")
            for tf, count in sorted(missing_tfs.items(), key=lambda x: x[1], reverse=True):
                print(f"    {tf}: {count} symbols")
            
            print("\n  Affected Symbols:")
            for r in rejections[:5]:  # Show first 5
                symbol = r.get('symbol', 'UNKNOWN')
                missing = r.get('missing_timeframes', [])
                print(f"    {symbol}: missing {', '.join(missing)}")
        
        elif reason_type == "no_data":
            print("  Symbols with data fetch failures:")
            for r in rejections[:10]:  # Show first 10
                symbol = r.get('symbol', 'UNKNOWN')
                print(f"    {symbol}")
        
        elif reason_type == "no_trade_plan":
            print("  Symbols where planner couldn't generate a plan:")
            for r in rejections[:10]:
                symbol = r.get('symbol', 'UNKNOWN')
                reason = r.get('reason', 'Unknown reason')
                print(f"    {symbol}: {reason}")
        
        elif reason_type == "risk_validation":
            print("  Risk validation failures:")
            for r in rejections[:10]:
                symbol = r.get('symbol', 'UNKNOWN')
                reason = r.get('reason', 'Unknown reason')
                print(f"    {symbol}: {reason}")


def analyze_confluence_factors(rejection_stats: Dict[str, List[Dict[str, Any]]]) -> None:
    """Analyze which confluence factors are contributing most to rejections."""
    
    low_conf_rejections = rejection_stats.get('low_confluence', [])
    if not low_conf_rejections:
        print("\nNo low_confluence rejections to analyze")
        return
    
    print("\n" + "="*80)
    print("CONFLUENCE FACTOR ANALYSIS")
    print("="*80)
    
    # Aggregate all factors across rejections
    factor_stats = defaultdict(lambda: {'count': 0, 'total_score': 0, 'scores': []})
    
    for rejection in low_conf_rejections:
        all_factors = rejection.get('all_factors', [])
        for factor in all_factors:
            name = factor.get('name', 'UNKNOWN')
            score = factor.get('score', 0)
            
            factor_stats[name]['count'] += 1
            factor_stats[name]['total_score'] += score
            factor_stats[name]['scores'].append(score)
    
    # Calculate averages
    factor_summary = []
    for name, stats in factor_stats.items():
        avg_score = stats['total_score'] / stats['count'] if stats['count'] > 0 else 0
        factor_summary.append({
            'name': name,
            'count': stats['count'],
            'avg_score': avg_score,
            'min_score': min(stats['scores']) if stats['scores'] else 0,
            'max_score': max(stats['scores']) if stats['scores'] else 0
        })
    
    # Sort by average score (ascending = worst performers)
    factor_summary.sort(key=lambda x: x['avg_score'])
    
    print("\nWEAKEST FACTORS (dragging down scores):")
    print("-" * 80)
    for factor in factor_summary[:10]:  # Show worst 10
        print(f"  {factor['name']:<30} | Avg: {factor['avg_score']:>6.1f} | "
              f"Range: [{factor['min_score']:>5.1f}, {factor['max_score']:>5.1f}] | "
              f"Count: {factor['count']}")
    
    print("\nSTRONGEST FACTORS (helping scores):")
    print("-" * 80)
    for factor in factor_summary[-10:][::-1]:  # Show best 10, reversed
        print(f"  {factor['name']:<30} | Avg: {factor['avg_score']:>6.1f} | "
              f"Range: [{factor['min_score']:>5.1f}, {factor['max_score']:>5.1f}] | "
              f"Count: {factor['count']}")


def main():
    parser = argparse.ArgumentParser(description='Diagnose SniperSight scanner bottlenecks')
    parser.add_argument('--symbols', nargs='+', help='Symbols to scan (e.g., BTC/USDT ETH/USDT)')
    parser.add_argument('--mode', default='strike', choices=['overwatch', 'strike', 'surgical', 'stealth'],
                       help='Scanner mode to use')
    parser.add_argument('--count', type=int, help='Number of top volume symbols to scan')
    parser.add_argument('--output', help='Save detailed rejection data to JSON file')
    
    args = parser.parse_args()
    
    # Get symbols
    if args.symbols:
        symbols = args.symbols
    elif args.count:
        # Fetch top volume symbols from Bybit
        adapter = BybitAdapter()
        print(f"Fetching top {args.count} volume symbols from Bybit...")
        # TODO: Implement top volume fetch
        symbols = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
            'ADA/USDT', 'DOGE/USDT', 'MATIC/USDT', 'DOT/USDT', 'AVAX/USDT',
            'LINK/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ETC/USDT',
            'BCH/USDT', 'FIL/USDT', 'NEAR/USDT', 'APT/USDT', 'ARB/USDT'
        ][:args.count]
    else:
        # Default: scan top 20
        symbols = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
            'ADA/USDT', 'DOGE/USDT', 'MATIC/USDT', 'DOT/USDT', 'AVAX/USDT',
            'LINK/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ETC/USDT',
            'BCH/USDT', 'FIL/USDT', 'NEAR/USDT', 'APT/USDT', 'ARB/USDT'
        ]
    
    print(f"\n{'='*80}")
    print(f"SNIPERSIGHT SCANNER DIAGNOSTIC")
    print(f"{'='*80}")
    print(f"Mode: {args.mode.upper()}")
    print(f"Symbols: {len(symbols)}")
    print(f"{'='*80}\n")
    
    # Setup scanner
    mode = get_mode(args.mode)
    config = ScanConfig(
        profile=mode.profile,
        timeframes=mode.timeframes,
        min_confluence_score=mode.min_confluence_score,
        primary_planning_timeframe=mode.primary_planning_timeframe,
        entry_timeframes=mode.entry_timeframes,
        structure_timeframes=mode.structure_timeframes,
        stop_timeframes=mode.stop_timeframes,
        target_timeframes=mode.target_timeframes
    )
    
    adapter = BybitAdapter()
    orchestrator = Orchestrator(config=config, exchange_adapter=adapter, debug_mode=True)
    
    # Run scan
    print("Running scan...")
    signals, rejection_stats = orchestrator.scan(symbols)
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"SCAN SUMMARY")
    print(f"{'='*80}")
    print(f"Symbols Scanned: {len(symbols)}")
    print(f"Signals Generated: {len(signals)}")
    print(f"Signals Rejected: {sum(len(v) for v in rejection_stats['details'].values())}")
    print(f"Signal Rate: {len(signals)}/{len(symbols)} ({len(signals)/len(symbols)*100:.1f}%)")
    
    # Print generated signals
    if signals:
        print(f"\n{'='*80}")
        print(f"GENERATED SIGNALS")
        print(f"{'='*80}")
        for signal in signals:
            print(f"{signal.symbol}: {signal.direction} @ {signal.entry_zone.near_entry:.5f} "
                  f"(confidence: {signal.confidence_score:.1f}%)")
    
    # Analyze rejections
    analyze_rejection_breakdown(rejection_stats['details'])
    analyze_confluence_factors(rejection_stats['details'])
    
    # Print mode configuration
    print(f"\n{'='*80}")
    print(f"MODE CONFIGURATION")
    print(f"{'='*80}")
    print(f"Profile: {mode.profile}")
    print(f"Timeframes: {', '.join(mode.timeframes)}")
    print(f"Min Confluence Score: {mode.min_confluence_score:.1f}%")
    print(f"Critical Timeframes: {', '.join(mode.critical_timeframes) if mode.critical_timeframes else 'None'}")
    print(f"Entry TFs: {', '.join(mode.entry_timeframes) if mode.entry_timeframes else 'Any'}")
    print(f"Structure TFs: {', '.join(mode.structure_timeframes) if mode.structure_timeframes else 'Any'}")
    print(f"Min R:R: {mode.overrides.get('min_rr_ratio', 'Not set') if mode.overrides else 'Not set'}")
    
    # Save to file if requested
    if args.output:
        output_data = {
            'summary': {
                'mode': args.mode,
                'symbols_scanned': len(symbols),
                'signals_generated': len(signals),
                'signals_rejected': sum(len(v) for v in rejection_stats['details'].values()),
                'signal_rate': len(signals) / len(symbols) if symbols else 0
            },
            'signals': [
                {
                    'symbol': s.symbol,
                    'direction': s.direction,
                    'entry': s.entry_zone.near_entry,
                    'confidence': s.confidence_score
                }
                for s in signals
            ],
            'rejection_stats': rejection_stats
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"\nDetailed data saved to: {args.output}")
    
    # Recommendations
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print("="*80)
    
    low_conf_count = len(rejection_stats['details'].get('low_confluence', []))
    missing_tf_count = len(rejection_stats['details'].get('missing_critical_tf', []))
    no_data_count = len(rejection_stats['details'].get('no_data', []))
    
    if low_conf_count > len(symbols) * 0.7:
        print("⚠️  HIGH CONFLUENCE REJECTION RATE (>70%)")
        print(f"   Current threshold: {mode.min_confluence_score:.1f}%")
        print(f"   Consider:")
        print(f"   - Lowering min_confluence_score by 5-10 points")
        print(f"   - Check which factors are consistently weak (see WEAKEST FACTORS above)")
        print(f"   - Verify HTF data is loading correctly")
    
    if missing_tf_count > len(symbols) * 0.3:
        print("\n⚠️  HIGH CRITICAL TIMEFRAME MISSING RATE (>30%)")
        print(f"   Missing: {', '.join(set(tf for r in rejection_stats['details'].get('missing_critical_tf', []) for tf in r.get('missing_timeframes', [])))}")
        print(f"   Consider:")
        print(f"   - Check exchange API connectivity")
        print(f"   - Verify these timeframes exist for your symbols")
        print(f"   - Remove timeframes from critical_timeframes if not essential")
    
    if no_data_count > len(symbols) * 0.2:
        print("\n⚠️  HIGH DATA FETCH FAILURE RATE (>20%)")
        print(f"   Consider:")
        print(f"   - Check API rate limits")
        print(f"   - Verify symbol names are correct")
        print(f"   - Check network connectivity")
    
    if len(signals) < len(symbols) * 0.05:  # <5% signal rate
        print("\n⚠️  VERY LOW SIGNAL RATE (<5%)")
        print(f"   This might be:")
        print(f"   - Working as intended (high quality filter)")
        print(f"   - Too restrictive (missing opportunities)")
        print(f"   Review the confluence factor analysis above to identify bottlenecks")


if __name__ == '__main__':
    main()
