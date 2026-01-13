#!/usr/bin/env python3
"""Quick script to check recent scan scores."""
import json
from collections import defaultdict

LOG_FILE = "logs/scoring_analysis.jsonl"

def main():
    scores_by_symbol = defaultdict(list)
    
    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()
    
    # Parse last 50 records
    for line in lines[-50:]:
        try:
            data = json.loads(line.strip())
            if 'symbol' in data and 'total_score' in data:
                symbol = data['symbol']
                direction = data.get('direction', 'unknown')
                score = data['total_score']
                scores_by_symbol[symbol].append({
                    'direction': direction,
                    'score': score,
                    'factors': len(data.get('factors', []))
                })
        except:
            pass
    
    # Show unique symbols with their best scores
    print("\n" + "="*70)
    print("RECENT SCAN RESULTS - Score Summary")
    print("="*70)
    print(f"{'Symbol':<15} {'Direction':<10} {'Score':<8} {'Factors':<8} {'Status'}")
    print("-"*70)
    
    min_threshold = 60.0  # Strike mode threshold
    
    passing = []
    for symbol in sorted(scores_by_symbol.keys()):
        directions = scores_by_symbol[symbol]
        # Get the winner (highest score)
        winner = max(directions, key=lambda x: x['score'])
        score = winner['score']
        status = "✓ PASS" if score >= min_threshold else "✗ FAIL"
        
        if score >= min_threshold:
            passing.append(symbol)
        
        print(f"{symbol:<15} {winner['direction']:<10} {score:<8.1f} {winner['factors']:<8} {status}")
    
    print("-"*70)
    print(f"\n{len(passing)} / {len(scores_by_symbol)} symbols passed (threshold: {min_threshold})")
    
    # Score distribution
    all_scores = [d['score'] for dirs in scores_by_symbol.values() for d in dirs]
    if all_scores:
        avg = sum(all_scores) / len(all_scores)
        min_score = min(all_scores)
        max_score = max(all_scores)
        print(f"\nScore Range: {min_score:.1f} - {max_score:.1f} (avg: {avg:.1f})")
    
    # Show score histogram
    print("\nScore Distribution:")
    buckets = defaultdict(int)
    for score in all_scores:
        bucket = int(score // 10) * 10
        buckets[bucket] += 1
    
    for bucket in sorted(buckets.keys()):
        bar = "█" * buckets[bucket]
        print(f"  {bucket:3d}-{bucket+9:3d}: {bar}")

if __name__ == "__main__":
    main()
