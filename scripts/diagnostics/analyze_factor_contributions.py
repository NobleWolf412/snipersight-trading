#!/usr/bin/env python3
"""
Analyze scoring factor contributions from recent scan.
Identifies which factors are driving high scores and why.
"""
import json
import re
from collections import defaultdict
from typing import Dict, List

def extract_score_traces(log_file: str = "logs/backend.log") -> List[Dict]:
    """Extract SCORE_TRACE entries from backend log."""
    traces = []
    
    with open(log_file, 'r') as f:
        for line in f:
            if "SCORE_TRACE:" in line:
                # Extract JSON after SCORE_TRACE:
                json_str = line.split("SCORE_TRACE:", 1)[1].strip()
                try:
                    data = json.loads(json_str)
                    traces.append(data)
                except json.JSONDecodeError:
                    continue
    
    return traces

def analyze_factors(traces: List[Dict]):
    """Analyze factor contributions across all traces."""
    
    # Statistics per factor
    factor_stats = defaultdict(lambda: {
        'count': 0,
        'total_contribution': 0,
        'contributions': [],
        'raw_scores': [],
        'weights': [],
        'rationales': []
    })
    
    print("\n" + "="*80)
    print("SCORING FACTOR ANALYSIS")
    print("="*80)
    
    # Collect all factor data
    for trace in traces:
        symbol = trace.get('symbol', 'unknown')
        direction = trace.get('direction', 'unknown')
        final_score = trace.get('final_score', 0)
        
        for factor in trace.get('factors', []):
            name = factor['name']
            contribution = factor['contribution']
            raw_score = factor.get('raw_score', factor.get('score', 0))
            weight = factor['weight']
            rationale = factor.get('rationale', '')
            
            stats = factor_stats[name]
            stats['count'] += 1
            stats['total_contribution'] += contribution
            stats['contributions'].append(contribution)
            stats['raw_scores'].append(raw_score)
            stats['weights'].append(weight)
            stats['rationales'].append(rationale)
    
    # Calculate averages and print
    print(f"\n{'FACTOR NAME':<30} {'AVG CONTRIB':<12} {'AVG RAW':<10} {'AVG WEIGHT':<12} {'FREQ':<6}")
    print("-"*80)
    
    sorted_factors = sorted(
        factor_stats.items(),
        key=lambda x: sum(x[1]['contributions']) / len(x[1]['contributions']),
        reverse=True
    )
    
    for name, stats in sorted_factors:
        avg_contrib = sum(stats['contributions']) / len(stats['contributions'])
        avg_raw = sum(stats['raw_scores']) / len(stats['raw_scores'])
        avg_weight = sum(stats['weights']) / len(stats['weights'])
        freq = stats['count']
        
        print(f"{name:<30} {avg_contrib:<12.2f} {avg_raw:<10.1f} {avg_weight:<12.4f} {freq:<6}")
    
    # Identify high contributors (driving scores up)
    print("\n" + "="*80)
    print("TOP 5 CONTRIBUTING FACTORS (Driving High Scores)")
    print("="*80)
    
    for name, stats in sorted_factors[:5]:
        avg_contrib = sum(stats['contributions']) / len(stats['contributions'])
        avg_raw = sum(stats['raw_scores']) / len(stats['raw_scores'])
        
        print(f"\n{name}: {avg_contrib:.2f} avg points")
        print(f"  Raw Score: {avg_raw:.1f}/100")
        print(f"  Sample rationale:")
        print(f"    {stats['rationales'][0][:120]}...")
    
    # Check for synergy/penalties
    print("\n" + "="*80)
    print("SYNERGY & PENALTY ANALYSIS")
    print("="*80)
    
    synergies = [t['components']['synergy'] for t in traces if 'components' in t]
    penalties = [t['components']['penalty'] for t in traces if 'components' in t]
    
    if synergies:
        avg_syn = sum(synergies) / len(synergies)
        max_syn = max(synergies)
        min_syn = min(synergies)
        print(f"Synergy Bonus: avg={avg_syn:.1f}, range={min_syn:.1f}-{max_syn:.1f}")
    
    if penalties:
        avg_pen = sum(penalties) / len(penalties)
        max_pen = max(penalties)
        min_pen = min(penalties)
        print(f"Penalties:     avg={avg_pen:.1f}, range={min_pen:.1f}-{max_pen:.1f}")
    
    # Score breakdown
    print("\n" + "="*80)
    print("SCORE COMPOSITION BREAKDOWN")
    print("="*80)
    
    for trace in traces[-5:]:  # Last 5
        symbol = trace['symbol']
        direction = trace['direction']
        final = trace['final_score']
        comp = trace.get('components', {})
        
        print(f"\n{symbol} ({direction}): {final:.1f}")
        print(f"  Base:    {comp.get('weighted_base', 0):.1f}")
        print(f"  Synergy: +{comp.get('synergy', 0):.1f}")
        print(f"  Penalty: -{comp.get('penalty', 0):.1f}")
        print(f"  Macro:   {comp.get('macro', 0):.1f}")

def main():
    traces = extract_score_traces("logs/backend.log")
    
    if not traces:
        print("No SCORE_TRACE entries found in logs/backend.log")
        return
    
    # Get recent traces (last 20)
    recent_traces = traces[-20:]
    
    print(f"\nAnalyzing {len(recent_traces)} recent score traces...")
    
    analyze_factors(recent_traces)
    
    # Overall score distribution
    print("\n" + "="*80)
    print("OVERALL SCORE DISTRIBUTION")
    print("="*80)
    
    scores = [t['final_score'] for t in recent_traces]
    avg = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)
    
    print(f"Range: {min_score:.1f} - {max_score:.1f}")
    print(f"Average: {avg:.1f}")
    print(f"Spread: {max_score - min_score:.1f} points")
    
    # Histogram
    print("\nScore Distribution:")
    buckets = defaultdict(int)
    for score in scores:
        bucket = int(score // 5) * 5
        buckets[bucket] += 1
    
    max_count = max(buckets.values()) if buckets else 1
    for bucket in sorted(buckets.keys()):
        bar_len = int((buckets[bucket] / max_count) * 40)
        bar = "█" * bar_len
        pct = (buckets[bucket] / len(scores)) * 100
        print(f"  {bucket:3d}-{bucket+4:3d}: {bar} ({buckets[bucket]:2d}, {pct:5.1f}%)")

if __name__ == "__main__":
    main()
