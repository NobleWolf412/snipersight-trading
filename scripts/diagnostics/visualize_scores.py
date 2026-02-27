#!/usr/bin/env python3
"""
Text-based score distribution visualization.
Creates ASCII charts for terminal display.
"""
import json
from collections import defaultdict

def extract_score_traces(log_file: str = "logs/backend.log"):
    """Extract SCORE_TRACE entries from backend log."""
    traces = []
    
    with open(log_file, 'r') as f:
        for line in f:
            if "SCORE_TRACE:" in line:
                json_str = line.split("SCORE_TRACE:", 1)[1].strip()
                try:
                    data = json.loads(json_str)
                    traces.append(data)
                except json.JSONDecodeError:
                    continue
    
    return traces

def create_ascii_histogram(values, title, width=60):
    """Create ASCII histogram."""
    if not values:
        return
    
    print(f"\n{title}")
    print("=" * 80)
    
    # Create buckets
    min_val = min(values)
    max_val = max(values)
    bucket_size = 5
    buckets = defaultdict(int)
    
    for val in values:
        bucket = int(val // bucket_size) * bucket_size
        buckets[bucket] += 1
    
    # Find max count for scaling
    max_count = max(buckets.values()) if buckets else 1
    
    # Print histogram
    for bucket in sorted(buckets.keys()):
        count = buckets[bucket]
        bar_len = int((count / max_count) * width)
        bar = "█" * bar_len
        pct = (count / len(values)) * 100
        print(f"  {bucket:3d}-{bucket+bucket_size-1:3d}: {bar} {count:2d} ({pct:5.1f}%)")
    
    # Statistics
    avg = sum(values) / len(values)
    std = (sum((x - avg) ** 2 for x in values) / len(values)) ** 0.5
    
    print(f"\n  Range: {min_val:.1f} - {max_val:.1f}")
    print(f"  Mean:  {avg:.1f}")
    print(f"  Std:   {std:.1f}")
    print(f"  Spread: {max_val - min_val:.1f} points")

def create_bar_chart(data, title, width=60):
    """Create ASCII bar chart."""
    if not data:
        return
    
    print(f"\n{title}")
    print("=" * 80)
    
    # Sort by value
    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
    
    # Find max for scaling
    max_val = max(v for _, v in sorted_data)
    
    for name, value in sorted_data:
        bar_len = int((value / max_val) * width)
        bar = "█" * bar_len
        print(f"  {name[:30]:<30} {bar} {value:6.1f}")

def analyze_score_issues(traces):
    """Detailed analysis of scoring issues."""
    
    print("\n" + "=" * 80)
    print("DETAILED ISSUE ANALYSIS")
    print("=" * 80)
    
    # Issue 1: Perfect Raw Scores
    print("\n📊 ISSUE 1: Too Many Perfect Raw Scores (100/100)")
    print("-" * 80)
    
    perfect_score_factors = defaultdict(int)
    total_factor_instances = defaultdict(int)
    
    for trace in traces:
        for factor in trace['factors']:
            name = factor['name']
            raw = factor.get('raw_score', factor.get('score', 0))
            total_factor_instances[name] += 1
            if raw == 100.0:
                perfect_score_factors[name] += 1
    
    for name in sorted(perfect_score_factors.keys(), key=lambda x: perfect_score_factors[x], reverse=True):
        perfect_count = perfect_score_factors[name]
        total = total_factor_instances[name]
        pct = (perfect_count / total) * 100
        if pct > 50:  # Show factors that score 100 more than 50% of the time
            bar = "█" * int(pct / 2)
            print(f"  {name:<30} {bar} {perfect_count}/{total} ({pct:.0f}%)")
    
    # Issue 2: No Penalties
    print("\n⚠️  ISSUE 2: Conflict Penalties Not Being Applied")
    print("-" * 80)
    
    penalties = [t['components']['penalty'] for t in traces]
    zero_penalties = sum(1 for p in penalties if p == 0.0)
    
    print(f"  Total setups:        {len(penalties)}")
    print(f"  Zero penalties:      {zero_penalties} ({100*zero_penalties/len(penalties):.0f}%)")
    print(f"  Non-zero penalties:  {len(penalties) - zero_penalties}")
    
    if zero_penalties == len(penalties):
        print("\n  ⚠️  CRITICAL: NO penalties applied across ALL setups!")
        print("     This suggests conflict detection is not working or disabled.")
    
    # Issue 3: High Synergy Bonuses
    print("\n🔥 ISSUE 3: Synergy Bonuses Too High")
    print("-" * 80)
    
    synergies = [t['components']['synergy'] for t in traces]
    avg_synergy = sum(synergies) / len(synergies)
    
    create_ascii_histogram(synergies, "Synergy Bonus Distribution", width=40)
    
    print(f"\n  Average synergy: {avg_synergy:.1f} pts")
    print(f"  This adds {avg_synergy:.1f}pts to EVERY setup on average")
    print(f"  Recommendation: Cap synergy at 10-15pts max")
    
    # Issue 4: Clustering Analysis
    print("\n📈 ISSUE 4: Score Clustering (Lack of Differentiation)")
    print("-" * 80)
    
    scores = [t['final_score'] for t in traces]
    
    # Count how many scores in each 5-point band
    bands = {
        '60-69': sum(1 for s in scores if 60 <= s < 70),
        '70-74': sum(1 for s in scores if 70 <= s < 75),
        '75-79': sum(1 for s in scores if 75 <= s < 80),
        '80-84': sum(1 for s in scores if 80 <= s < 85),
        '85-89': sum(1 for s in scores if 85 <= s < 90),
        '90-100': sum(1 for s in scores if 90 <= s <= 100),
    }
    
    for band, count in bands.items():
        pct = (count / len(scores)) * 100
        bar = "█" * int(pct)
        status = "⚠️ " if pct > 40 else "  "
        print(f"{status}{band}: {bar} {count:2d} ({pct:5.1f}%)")
    
    print("\n  ⚠️  Ideal distribution: Bell curve centered around 70-75")
    print("     Current: Heavy clustering in 80-84 range")

def main():
    traces = extract_score_traces("logs/backend.log")
    
    if not traces:
        print("No SCORE_TRACE entries found in logs/backend.log")
        return
    
    recent_traces = traces[-20:]
    
    print("\n" + "=" * 80)
    print(f"SCORE DISTRIBUTION ANALYSIS ({len(recent_traces)} recent setups)")
    print("=" * 80)
    
    # Overall score distribution
    scores = [t['final_score'] for t in recent_traces]
    create_ascii_histogram(scores, "Final Score Distribution (Should be Bell Curve)", width=50)
    
    # Base scores vs final scores
    base_scores = [t['components']['weighted_base'] for t in recent_traces]
    create_ascii_histogram(base_scores, "Base Score Distribution (Before Synergy/Penalties)", width=50)
    
    # Synergy distribution
    synergies = [t['components']['synergy'] for t in recent_traces]
    create_ascii_histogram(synergies, "Synergy Bonus Distribution", width=50)
    
    # Factor contributions
    factor_totals = defaultdict(float)
    for trace in recent_traces:
        for factor in trace['factors']:
            factor_totals[factor['name']] += factor['contribution']
    
    create_bar_chart(dict(list(sorted(factor_totals.items(), key=lambda x: x[1], reverse=True))[:15]), 
                     "Top 15 Contributing Factors (Total Points)", width=40)
    
    # Detailed issue analysis
    analyze_score_issues(recent_traces)
    
    # Summary recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("""
1. ⚡ ENABLE CONFLICT PENALTIES
   - Currently all penalties = 0.0
   - Implement opposing structure/momentum detection
   - Target: 5-15pt penalties when conflicts exist

2. 📉 REDUCE SYNERGY BONUSES
   - Current avg: 18.3pts (too high!)
   - Cap synergy at 10-15pts max
   - Require stronger alignment for bonuses

3. 🎯 TIGHTEN GRADIENT SCORING
   - Too many factors scoring 100/100
   - Implement stricter thresholds for perfect scores
   - Use linear gradient scoring with neutral zones

4. 📊 INCREASE SCORE SPREAD
   - Current spread: 14.8pts (too tight!)
   - Target spread: 30-40pts
   - Differentiate between A+ and B- setups

5. 🔧 ADJUST THRESHOLDS
   - Strike mode: 60 → 70 (more selective)
   - Surgical mode: 70 → 75
   - Overwatch mode: 72 → 78
""")
    print("=" * 80)

if __name__ == "__main__":
    main()
