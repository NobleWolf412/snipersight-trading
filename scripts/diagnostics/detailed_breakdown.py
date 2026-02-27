"""Extract detailed confluence breakdowns for Strike scan signals"""
import re

with open('logs/confluence_breakdown.log', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Split into individual breakdowns
breakdowns = content.split('=' * 40)

# Get the last 10 breakdowns (most recent)
recent = breakdowns[-15:]

print("=" * 80)
print("DETAILED CONFLUENCE BREAKDOWNS - STRIKE SCAN")
print("=" * 80)

for section in recent:
    # Extract header
    header_match = re.search(r'CONFLUENCE BREAKDOWN \| (\S+) (BULLISH|BEARISH)', section)
    if not header_match:
        continue
    
    symbol = header_match.group(1)
    direction = header_match.group(2)
    
    # Extract final score
    score_match = re.search(r'Final Score: ([\d.]+)', section)
    if not score_match:
        continue
    
    final_score = float(score_match.group(1))
    
    # Only show signals that passed (70%+ for Strike)
    if final_score < 70.0:
        continue
    
    print(f"\n{'=' * 80}")
    print(f"{symbol} - {direction}")
    print(f"{'=' * 80}")
    
    # Extract components
    weighted_base = re.search(r'Weighted Base: ([\d.]+)', section)
    synergy = re.search(r'Synergy Bonus: \+([\d.]+)', section)
    conflict = re.search(r'Conflict Penalty: -([\d.]+)', section)
    macro = re.search(r'Macro Score: ([\d.]+)', section)
    
    print(f"\nFINAL SCORE: {final_score:.2f}%")
    print(f"\nCOMPONENTS:")
    if weighted_base:
        print(f"  Weighted Base:     {float(weighted_base.group(1)):>6.2f}")
    if synergy:
        print(f"  Synergy Bonus:     +{float(synergy.group(1)):>5.2f}")
    if conflict:
        print(f"  Conflict Penalty:  -{float(conflict.group(1)):>5.2f}")
    if macro:
        print(f"  Macro Score:       {float(macro.group(1)):>6.2f}")
    
    # Extract top factors
    print(f"\nTOP FACTORS:")
    factor_pattern = r'(\d+)\.\s+([^:]+):\s+([\d.]+)\s+×\s+([\d.]+)\s+=\s+([\d.]+)pts'
    factors = re.findall(factor_pattern, section)
    
    if factors:
        print(f"  {'Rank':<5} {'Factor':<30} {'Score':<8} {'Weight':<8} {'Contrib':<8}")
        print(f"  {'-'*5} {'-'*30} {'-'*8} {'-'*8} {'-'*8}")
        for rank, name, score, weight, contrib in factors[:10]:
            print(f"  {rank:<5} {name:<30} {score:>6}% × {weight:>6} = {contrib:>6}pts")
    
    print()

print("=" * 80)
