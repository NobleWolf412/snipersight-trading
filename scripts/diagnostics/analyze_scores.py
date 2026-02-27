import json
import statistics
from collections import defaultdict
import re

LOG_FILE = "logs/scoring_analysis.jsonl"

def parse_logs():
    data = []
    try:
        with open(LOG_FILE, 'r') as f:
            for line in f:
                try:
                    if "SCORE_TRACE:" in line:
                        json_str = line.split("SCORE_TRACE:", 1)[1].strip()
                        record = json.loads(json_str)
                        data.append(record)
                    elif line.strip().startswith("{"):
                         record = json.loads(line.strip())
                         data.append(record)
                except Exception:
                    pass
    except FileNotFoundError:
        print(f"File not found: {LOG_FILE}")
    return data

def analyze(data):
    if not data:
        print("No scoring data found.")
        return

    print(f"\n=== INDICATOR DEEP DIVE ({len(data)} Records) ===\n")
    
    # 1. Full Factor List
    print("ALL FACTORS FOUND:")
    factor_counts = defaultdict(int)
    factor_scores = defaultdict(list)
    
    # regex for common indicators
    indicator_patterns = {
        'RSI': r'RSI',
        'Stoch RSI': r'Stoch\s*RSI',
        'MACD': r'MACD',
        'Bollinger': r'Bollinger',
        'MFI': r'MFI',
        'EMA': r'EMA',
        'ADX': r'ADX',
        'VWAP': r'VWAP'
    }
    
    indicator_hits = defaultdict(int)
    indicator_rationales = defaultdict(list)

    for record in data:
        for factor in record.get('factors', []):
            name = factor['name']
            raw = factor.get('raw_score', factor.get('score', 0))
            w = factor['weight']
            contrib = factor.get('contribution', raw * w)
            rat = factor.get('rationale', '')
            
            factor_counts[name] += 1
            factor_scores[name].append(contrib)
            
            # Check rationales for specific indicators
            for ind_name, pat in indicator_patterns.items():
                if re.search(pat, rat, re.IGNORECASE) or re.search(pat, name, re.IGNORECASE):
                    indicator_hits[ind_name] += 1
                    indicator_rationales[ind_name].append(f"{name}: {rat} (+{contrib:.1f}pts)")

    # Print All Factors sorted by avg points
    sorted_factors = []
    for name, scores in factor_scores.items():
        avg = sum(scores) / len(scores)
        sorted_factors.append((name, avg, factor_counts[name]))
    
    sorted_factors.sort(key=lambda x: x[1], reverse=True)
    
    print(f"{'FACTOR NAME':<30} | {'AVG PTS':<8} | {'FREQ':<5}")
    print("-" * 50)
    for name, avg, freq in sorted_factors:
        print(f"{name:<30} | {avg:<8.2f} | {freq:<5}")

    print("\n=== SPECIFIC INDICATOR PRESENCE ===")
    print("(Count of times mentioned in Factor Rationales)")
    sorted_inds = sorted(indicator_hits.items(), key=lambda x: x[1], reverse=True)
    for ind, count in sorted_inds:
        print(f"{ind:<15}: {count} / {len(data)} trades ({count/len(data)*100:.0f}%)")
        # Show sample rationale
        if indicator_rationales[ind]:
            print(f"  Sample: {indicator_rationales[ind][0]}")

if __name__ == "__main__":
    data = parse_logs()
    analyze(data)
