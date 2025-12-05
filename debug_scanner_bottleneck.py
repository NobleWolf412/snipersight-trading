"""
SniperSight Scanner Diagnostic Script - Enhanced Version

This script helps identify where signals are getting filtered out.
Run this to see detailed rejection reasons for your scans.

Usage:
    # Single mode scan
    python debug_scanner_bottleneck.py --mode strike --count 10

    # All modes comparison
    python debug_scanner_bottleneck.py --all-modes --count 10

    # Specific symbols
    python debug_scanner_bottleneck.py --symbols BTC/USDT ETH/USDT SOL/USDT --mode strike

    # Verbose output
    python debug_scanner_bottleneck.py --mode strike --count 5 --verbose
"""

import sys
import argparse
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
import json
from datetime import datetime
import time

# Add backend to path
sys.path.insert(0, 'backend')

from engine.orchestrator import Orchestrator
from shared.config.defaults import ScanConfig
from shared.config.scanner_modes import get_mode, MODES
from data.adapters.phemex import PhemexAdapter  # Use Phemex (no geo-blocking)


# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def print_header(title: str, char: str = "=", width: int = 90):
    """Print a formatted header."""
    print(f"\n{Colors.CYAN}{char * width}{Colors.RESET}")
    print(f"{Colors.BOLD}{title.center(width)}{Colors.RESET}")
    print(f"{Colors.CYAN}{char * width}{Colors.RESET}")


def print_section(title: str, char: str = "-", width: int = 90):
    """Print a section header."""
    print(f"\n{Colors.YELLOW}{title}{Colors.RESET}")
    print(f"{Colors.DIM}{char * len(title)}{Colors.RESET}")


def analyze_rejection_breakdown(rejection_stats: Dict[str, List[Dict[str, Any]]], verbose: bool = False) -> Dict[str, Any]:
    """Print detailed breakdown of rejections and return stats."""
    
    total_rejected = sum(len(v) for v in rejection_stats.values())
    
    print_header(f"REJECTION BREAKDOWN ({total_rejected} total)", "─")
    
    # Sort by count
    sorted_reasons = sorted(
        rejection_stats.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )
    
    stats = {}
    
    for reason_type, rejections in sorted_reasons:
        if not rejections:
            continue
        
        count = len(rejections)
        pct = (count / total_rejected * 100) if total_rejected > 0 else 0
        stats[reason_type] = {'count': count, 'pct': pct}
        
        # Color code by severity
        if pct > 50:
            color = Colors.RED
        elif pct > 25:
            color = Colors.YELLOW
        else:
            color = Colors.GREEN
        
        print(f"\n{color}{Colors.BOLD}{reason_type.upper()}: {count} ({pct:.1f}%){Colors.RESET}")
        print("-" * 80)
        
        if reason_type == "low_confluence":
            # Detailed confluence analysis
            scores = [r.get('score', 0) for r in rejections]
            thresholds = [r.get('threshold', 0) for r in rejections]
            avg_score = sum(scores) / len(scores) if scores else 0
            avg_threshold = sum(thresholds) / len(thresholds) if thresholds else 0
            
            print(f"  {Colors.CYAN}Average Score:{Colors.RESET} {avg_score:.1f}")
            print(f"  {Colors.CYAN}Average Threshold:{Colors.RESET} {avg_threshold:.1f}")
            print(f"  {Colors.CYAN}Gap:{Colors.RESET} {avg_threshold - avg_score:.1f} points")
            
            # Show worst performers
            print(f"\n  {Colors.BOLD}Worst 5 Performers:{Colors.RESET}")
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
                
                print(f"    {Colors.YELLOW}{symbol}{Colors.RESET}: {score:.1f}/{threshold:.1f} (gap={gap:.1f})")
                if top_factors and verbose:
                    print(f"      {Colors.DIM}Top factors: {', '.join(top_factors[:3])}{Colors.RESET}")
        
        elif reason_type == "missing_critical_tf":
            # Which timeframes are missing?
            missing_tfs = defaultdict(int)
            for r in rejections:
                for tf in r.get('missing_timeframes', []):
                    missing_tfs[tf] += 1
            
            print(f"  {Colors.BOLD}Missing Timeframes:{Colors.RESET}")
            for tf, count in sorted(missing_tfs.items(), key=lambda x: x[1], reverse=True):
                print(f"    {Colors.YELLOW}{tf}{Colors.RESET}: {count} symbols")
            
            if verbose:
                print(f"\n  {Colors.BOLD}Affected Symbols:{Colors.RESET}")
                for r in rejections[:5]:  # Show first 5
                    symbol = r.get('symbol', 'UNKNOWN')
                    missing = r.get('missing_timeframes', [])
                    print(f"    {symbol}: missing {', '.join(missing)}")
        
        elif reason_type == "no_data":
            print(f"  {Colors.BOLD}Symbols with data fetch failures:{Colors.RESET}")
            for r in rejections[:10]:  # Show first 10
                symbol = r.get('symbol', 'UNKNOWN')
                error = r.get('error', '')
                print(f"    {Colors.RED}{symbol}{Colors.RESET}")
                if verbose and error:
                    print(f"      {Colors.DIM}{error[:80]}{Colors.RESET}")
        
        elif reason_type == "no_trade_plan":
            print(f"  {Colors.BOLD}Symbols where planner couldn't generate a plan:{Colors.RESET}")
            for r in rejections[:10]:
                symbol = r.get('symbol', 'UNKNOWN')
                reason = r.get('reason', 'Unknown reason')
                print(f"    {Colors.YELLOW}{symbol}{Colors.RESET}: {reason}")
        
        elif reason_type == "risk_validation":
            print(f"  {Colors.BOLD}Risk validation failures:{Colors.RESET}")
            for r in rejections[:10]:
                symbol = r.get('symbol', 'UNKNOWN')
                reason = r.get('reason', 'Unknown reason')
                print(f"    {Colors.YELLOW}{symbol}{Colors.RESET}: {reason}")
        
        elif reason_type == "errors":
            print(f"  {Colors.BOLD}Pipeline errors:{Colors.RESET}")
            for r in rejections[:10]:
                symbol = r.get('symbol', 'UNKNOWN')
                error = r.get('error', r.get('reason', 'Unknown error'))
                print(f"    {Colors.RED}{symbol}{Colors.RESET}: {error[:80] if error else 'Unknown'}")
    
    return stats


def analyze_confluence_factors(rejection_stats: Dict[str, List[Dict[str, Any]]], verbose: bool = False) -> None:
    """Analyze which confluence factors are contributing most to rejections."""
    
    low_conf_rejections = rejection_stats.get('low_confluence', [])
    if not low_conf_rejections:
        print(f"\n{Colors.DIM}No low_confluence rejections to analyze{Colors.RESET}")
        return
    
    print_header("CONFLUENCE FACTOR ANALYSIS", "─")
    
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
    
    print(f"\n{Colors.RED}{Colors.BOLD}WEAKEST FACTORS (dragging down scores):{Colors.RESET}")
    print("-" * 80)
    for factor in factor_summary[:10]:  # Show worst 10
        color = Colors.RED if factor['avg_score'] < 30 else Colors.YELLOW if factor['avg_score'] < 50 else Colors.GREEN
        print(f"  {factor['name']:<32} | {color}Avg: {factor['avg_score']:>6.1f}{Colors.RESET} | "
              f"Range: [{factor['min_score']:>5.1f}, {factor['max_score']:>5.1f}] | "
              f"Count: {factor['count']}")
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}STRONGEST FACTORS (helping scores):{Colors.RESET}")
    print("-" * 80)
    for factor in factor_summary[-10:][::-1]:  # Show best 10, reversed
        color = Colors.GREEN if factor['avg_score'] > 70 else Colors.YELLOW if factor['avg_score'] > 50 else Colors.RED
        print(f"  {factor['name']:<32} | {color}Avg: {factor['avg_score']:>6.1f}{Colors.RESET} | "
              f"Range: [{factor['min_score']:>5.1f}, {factor['max_score']:>5.1f}] | "
              f"Count: {factor['count']}")


def print_mode_config(mode, mode_name: str) -> None:
    """Print detailed mode configuration."""
    print_section(f"MODE CONFIGURATION: {mode_name.upper()}")
    
    print(f"  {Colors.CYAN}Profile:{Colors.RESET} {mode.profile}")
    print(f"  {Colors.CYAN}Timeframes:{Colors.RESET} {', '.join(mode.timeframes)}")
    print(f"  {Colors.CYAN}Min Confluence Score:{Colors.RESET} {mode.min_confluence_score:.1f}%")
    print(f"  {Colors.CYAN}Critical Timeframes:{Colors.RESET} {', '.join(mode.critical_timeframes) if mode.critical_timeframes else 'None'}")
    print(f"  {Colors.CYAN}Entry TFs:{Colors.RESET} {', '.join(mode.entry_timeframes) if mode.entry_timeframes else 'Any'}")
    print(f"  {Colors.CYAN}Structure TFs:{Colors.RESET} {', '.join(mode.structure_timeframes) if mode.structure_timeframes else 'Any'}")
    print(f"  {Colors.CYAN}Stop TFs:{Colors.RESET} {', '.join(mode.stop_timeframes) if mode.stop_timeframes else 'Any'}")
    print(f"  {Colors.CYAN}Min R:R:{Colors.RESET} {mode.overrides.get('min_rr_ratio', 'Not set') if mode.overrides else 'Not set'}")


def run_single_mode_scan(
    mode_name: str, 
    symbols: List[str], 
    verbose: bool = False
) -> Tuple[List[Any], Dict[str, Any], float]:
    """Run a scan for a single mode and return results."""
    
    print_header(f"SCANNING WITH MODE: {mode_name.upper()}", "═")
    
    mode = get_mode(mode_name)
    config = ScanConfig(
        profile=mode_name,
        timeframes=mode.timeframes,
        min_confluence_score=mode.min_confluence_score,
        primary_planning_timeframe=mode.primary_planning_timeframe,
    )
    
    # Store mode info for later reference
    config.structure_timeframes = mode.structure_timeframes
    config.entry_timeframes = mode.entry_timeframes
    config.stop_timeframes = mode.stop_timeframes
    config.target_timeframes = mode.target_timeframes
    
    adapter = PhemexAdapter()
    orchestrator = Orchestrator(config=config, exchange_adapter=adapter, debug_mode=True)
    
    # Run scan with timing
    print(f"\n{Colors.DIM}Running scan...{Colors.RESET}")
    start_time = time.time()
    signals, rejection_stats = orchestrator.scan(symbols)
    elapsed = time.time() - start_time
    
    print(f"{Colors.GREEN}✓ Scan completed in {elapsed:.1f}s{Colors.RESET}")
    
    return signals, rejection_stats, elapsed, mode


def print_signals_detail(signals: List[Any], verbose: bool = False) -> None:
    """Print detailed signal information."""
    if not signals:
        print(f"\n{Colors.RED}No signals generated{Colors.RESET}")
        return
    
    print_section(f"GENERATED SIGNALS ({len(signals)})")
    
    for i, signal in enumerate(signals, 1):
        direction_color = Colors.GREEN if signal.direction == 'LONG' else Colors.RED
        
        print(f"\n  {Colors.BOLD}[{i}] {signal.symbol}{Colors.RESET}")
        print(f"      Direction: {direction_color}{signal.direction}{Colors.RESET}")
        print(f"      Entry Zone: {signal.entry_zone.near_entry:.5f} - {signal.entry_zone.far_entry:.5f}")
        print(f"      Confidence: {Colors.CYAN}{signal.confidence_score:.1f}%{Colors.RESET}")
        
        if hasattr(signal, 'stop_loss') and signal.stop_loss:
            # StopLoss object has .price attribute
            stop_price = getattr(signal.stop_loss, 'price', None) or signal.stop_loss
            if isinstance(stop_price, (int, float)):
                print(f"      Stop Loss: {stop_price:.5f}")
            else:
                print(f"      Stop Loss: {stop_price}")
        
        if hasattr(signal, 'targets') and signal.targets:
            # Targets might be Target objects or floats
            try:
                targets_str = ", ".join([f"{getattr(t, 'price', t):.5f}" for t in signal.targets[:3]])
                print(f"      Targets: {targets_str}")
            except Exception:
                print(f"      Targets: {signal.targets[:3]}")
        
        if verbose and hasattr(signal, 'rationale') and signal.rationale:
            print(f"      {Colors.DIM}Rationale: {signal.rationale[:100]}...{Colors.RESET}")


def run_all_modes_comparison(symbols: List[str], verbose: bool = False) -> None:
    """Run scans for all modes and compare results."""
    
    print_header("ALL MODES COMPARISON SCAN", "═", 90)
    print(f"\n{Colors.CYAN}Symbols:{Colors.RESET} {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}")
    print(f"{Colors.CYAN}Total Symbols:{Colors.RESET} {len(symbols)}")
    print(f"{Colors.CYAN}Timestamp:{Colors.RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_modes = ['overwatch', 'strike', 'surgical', 'stealth']
    results = {}
    
    for mode_name in all_modes:
        signals, rejection_stats, elapsed, mode = run_single_mode_scan(mode_name, symbols, verbose)
        
        # Quick summary for this mode
        total_rejected = sum(len(v) for v in rejection_stats['details'].values())
        signal_rate = len(signals) / len(symbols) * 100 if symbols else 0
        
        results[mode_name] = {
            'signals': len(signals),
            'rejected': total_rejected,
            'rate': signal_rate,
            'time': elapsed,
            'mode': mode,
            'rejection_details': rejection_stats['details']
        }
        
        # Print quick summary
        print(f"\n{Colors.BOLD}Quick Summary:{Colors.RESET}")
        print(f"  Signals: {Colors.GREEN if len(signals) > 0 else Colors.RED}{len(signals)}{Colors.RESET}")
        print(f"  Rejected: {total_rejected}")
        print(f"  Rate: {signal_rate:.1f}%")
        
        # Print signals
        print_signals_detail(signals, verbose)
        
        # Print rejection breakdown (condensed for multi-mode)
        if total_rejected > 0:
            analyze_rejection_breakdown(rejection_stats['details'], verbose)
    
    # Final comparison table
    print_header("MODE COMPARISON SUMMARY", "═")
    
    print(f"\n{'Mode':<12} {'Signals':>8} {'Rejected':>10} {'Rate':>8} {'Time':>8} {'Threshold':>10}")
    print("-" * 70)
    
    for mode_name in all_modes:
        r = results[mode_name]
        rate_color = Colors.GREEN if r['rate'] > 20 else Colors.YELLOW if r['rate'] > 5 else Colors.RED
        print(f"{mode_name:<12} {r['signals']:>8} {r['rejected']:>10} "
              f"{rate_color}{r['rate']:>7.1f}%{Colors.RESET} {r['time']:>7.1f}s "
              f"{r['mode'].min_confluence_score:>9.0f}%")
    
    # Best performing mode
    best_mode = max(results.keys(), key=lambda m: results[m]['rate'])
    print(f"\n{Colors.GREEN}{Colors.BOLD}Best Performing Mode: {best_mode.upper()} "
          f"({results[best_mode]['rate']:.1f}% signal rate){Colors.RESET}")
    
    # Recommendation
    print_section("RECOMMENDATIONS")
    
    # Analyze rejection patterns across modes
    for mode_name in all_modes:
        r = results[mode_name]
        if r['rate'] < 5:
            print(f"\n  {Colors.YELLOW}⚠ {mode_name.upper()}: Very low signal rate{Colors.RESET}")
            
            # Find main rejection reason
            if r['rejection_details']:
                main_reason = max(r['rejection_details'].items(), 
                                 key=lambda x: len(x[1]) if x[1] else 0)
                if main_reason[1]:
                    print(f"    Main rejection: {main_reason[0]} ({len(main_reason[1])} symbols)")


def main():
    parser = argparse.ArgumentParser(
        description='SniperSight Scanner Diagnostic Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single mode scan
  python debug_scanner_bottleneck.py --mode strike --count 10
  
  # All modes comparison
  python debug_scanner_bottleneck.py --all-modes --count 10
  
  # Specific symbols with verbose output
  python debug_scanner_bottleneck.py --symbols BTC/USDT ETH/USDT --mode surgical --verbose
  
  # Save results to JSON
  python debug_scanner_bottleneck.py --mode strike --count 5 --output results.json
        """
    )
    parser.add_argument('--symbols', nargs='+', help='Symbols to scan (e.g., BTC/USDT ETH/USDT)')
    parser.add_argument('--mode', default='strike', choices=['overwatch', 'strike', 'surgical', 'stealth'],
                       help='Scanner mode to use (default: strike)')
    parser.add_argument('--count', type=int, default=10, help='Number of top volume symbols to scan (default: 10)')
    parser.add_argument('--all-modes', action='store_true', help='Run comparison across all modes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    parser.add_argument('--output', help='Save detailed rejection data to JSON file')
    
    args = parser.parse_args()
    
    # Banner
    print(f"\n{Colors.CYAN}{'━' * 90}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("   ███████╗███╗   ██╗██╗██████╗ ███████╗██████╗ ███████╗██╗ ██████╗ ██╗  ██╗████████╗")
    print("   ██╔════╝████╗  ██║██║██╔══██╗██╔════╝██╔══██╗██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝")
    print("   ███████╗██╔██╗ ██║██║██████╔╝█████╗  ██████╔╝███████╗██║██║  ███╗███████║   ██║   ")
    print("   ╚════██║██║╚██╗██║██║██╔═══╝ ██╔══╝  ██╔══██╗╚════██║██║██║   ██║██╔══██║   ██║   ")
    print("   ███████║██║ ╚████║██║██║     ███████╗██║  ██║███████║██║╚██████╔╝██║  ██║   ██║   ")
    print("   ╚══════╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ")
    print(f"{Colors.RESET}")
    print(f"{Colors.YELLOW}                    SCANNER DIAGNOSTIC TOOL v2.0{Colors.RESET}")
    print(f"{Colors.CYAN}{'━' * 90}{Colors.RESET}")
    
    # Get symbols
    if args.symbols:
        symbols = args.symbols
    else:
        # Default symbol list
        symbols = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
            'ADA/USDT', 'DOGE/USDT', 'MATIC/USDT', 'DOT/USDT', 'AVAX/USDT',
            'LINK/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ETC/USDT',
            'BCH/USDT', 'FIL/USDT', 'NEAR/USDT', 'APT/USDT', 'ARB/USDT'
        ][:args.count]
    
    print(f"\n{Colors.CYAN}Timestamp:{Colors.RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Colors.CYAN}Symbols:{Colors.RESET} {len(symbols)} ({', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''})")
    print(f"{Colors.CYAN}Mode:{Colors.RESET} {args.mode if not args.all_modes else 'ALL MODES'}")
    print(f"{Colors.CYAN}Verbose:{Colors.RESET} {'Yes' if args.verbose else 'No'}")
    
    if args.all_modes:
        # Run all modes comparison
        run_all_modes_comparison(symbols, args.verbose)
    else:
        # Run single mode scan
        signals, rejection_stats, elapsed, mode = run_single_mode_scan(args.mode, symbols, args.verbose)
        
        # Print summary
        print_header("SCAN SUMMARY", "═")
        
        total_rejected = sum(len(v) for v in rejection_stats['details'].values())
        signal_rate = len(signals) / len(symbols) * 100 if symbols else 0
        
        print(f"\n  {Colors.CYAN}Symbols Scanned:{Colors.RESET} {len(symbols)}")
        print(f"  {Colors.GREEN if len(signals) > 0 else Colors.RED}Signals Generated:{Colors.RESET} {len(signals)}")
        print(f"  {Colors.YELLOW}Signals Rejected:{Colors.RESET} {total_rejected}")
        
        rate_color = Colors.GREEN if signal_rate > 20 else Colors.YELLOW if signal_rate > 5 else Colors.RED
        print(f"  {Colors.CYAN}Signal Rate:{Colors.RESET} {rate_color}{signal_rate:.1f}%{Colors.RESET}")
        print(f"  {Colors.CYAN}Scan Time:{Colors.RESET} {elapsed:.1f}s")
        
        # Print signals
        print_signals_detail(signals, args.verbose)
        
        # Analyze rejections
        if total_rejected > 0:
            analyze_rejection_breakdown(rejection_stats['details'], args.verbose)
            analyze_confluence_factors(rejection_stats['details'], args.verbose)
        
        # Print mode configuration
        print_mode_config(mode, args.mode)
        
        # Save to file if requested
        if args.output:
            output_data = {
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'mode': args.mode,
                    'symbols_scanned': len(symbols),
                    'signals_generated': len(signals),
                    'signals_rejected': total_rejected,
                    'signal_rate': signal_rate,
                    'scan_time_seconds': elapsed
                },
                'signals': [
                    {
                        'symbol': s.symbol,
                        'direction': s.direction,
                        'entry_near': s.entry_zone.near_entry,
                        'entry_far': s.entry_zone.far_entry,
                        'confidence': s.confidence_score,
                        'stop_loss': getattr(s, 'stop_loss', None),
                        'targets': getattr(s, 'targets', [])
                    }
                    for s in signals
                ],
                'rejection_stats': {
                    k: [dict(r) for r in v] 
                    for k, v in rejection_stats['details'].items()
                },
                'mode_config': {
                    'profile': mode.profile,
                    'timeframes': mode.timeframes,
                    'min_confluence_score': mode.min_confluence_score,
                    'critical_timeframes': mode.critical_timeframes,
                    'entry_timeframes': mode.entry_timeframes,
                    'structure_timeframes': mode.structure_timeframes
                }
            }
            
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)
            
            print(f"\n{Colors.GREEN}✓ Detailed data saved to: {args.output}{Colors.RESET}")
        
        # Recommendations
        print_section("RECOMMENDATIONS")
        
        low_conf_count = len(rejection_stats['details'].get('low_confluence', []))
        missing_tf_count = len(rejection_stats['details'].get('missing_critical_tf', []))
        no_data_count = len(rejection_stats['details'].get('no_data', []))
        no_plan_count = len(rejection_stats['details'].get('no_trade_plan', []))
        error_count = len(rejection_stats['details'].get('errors', []))
        
        if error_count > 0:
            print(f"\n  {Colors.RED}⚠️  PIPELINE ERRORS ({error_count}){Colors.RESET}")
            print(f"     Review error messages above for specific issues")
            print(f"     Common causes: Missing attributes, data type mismatches")
        
        if no_plan_count > len(symbols) * 0.3:
            print(f"\n  {Colors.YELLOW}⚠️  HIGH TRADE PLAN FAILURE RATE (>30%){Colors.RESET}")
            print(f"     Common causes:")
            print(f"     - Stop too wide/tight relative to ATR")
            print(f"     - Poor R:R ratio (below minimum threshold)")
            print(f"     - Entry zone conflicts with current price")
        
        if low_conf_count > len(symbols) * 0.5:
            print(f"\n  {Colors.YELLOW}⚠️  HIGH CONFLUENCE REJECTION RATE (>50%){Colors.RESET}")
            print(f"     Current threshold: {mode.min_confluence_score:.1f}%")
            print(f"     Consider:")
            print(f"     - Lowering min_confluence_score by 5-10 points")
            print(f"     - Check which factors are consistently weak")
        
        if no_data_count > len(symbols) * 0.2:
            print(f"\n  {Colors.YELLOW}⚠️  HIGH DATA FETCH FAILURE RATE (>20%){Colors.RESET}")
            print(f"     Consider:")
            print(f"     - Check API rate limits")
            print(f"     - Verify symbol names are correct for exchange")
        
        if signal_rate > 30:
            print(f"\n  {Colors.GREEN}✓ HEALTHY SIGNAL RATE ({signal_rate:.1f}%){Colors.RESET}")
            print(f"     Scanner is finding good opportunities")
        elif signal_rate < 5:
            print(f"\n  {Colors.RED}⚠️  VERY LOW SIGNAL RATE (<5%){Colors.RESET}")
            print(f"     This could be:")
            print(f"     - Working as intended (high selectivity)")
            print(f"     - Too restrictive (missing opportunities)")
            print(f"     - Market conditions unfavorable")


if __name__ == '__main__':
    main()
