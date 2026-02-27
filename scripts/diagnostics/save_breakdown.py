"""Extract detailed confluence breakdowns for Strike scan signals - save to file"""
import re

with open('logs/confluence_breakdown.log', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Split into individual breakdowns
breakdowns = content.split('=' * 40)

# Get the last 15 breakdowns (most recent)
recent = breakdowns[-15:]

output = []
output.append("=" * 80)
output.append("DETAILED CONFLUENCE BREAKDOWNS - STRIKE SCAN")
output.append("=" * 80)

signal_count = 0

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
    
    signal_count += 1
    
    output.append(f"\n{'=' * 80}")
    output.append(f"SIGNAL #{signal_count}: {symbol} - {direction}")
    output.append(f"{'=' * 80}")
    
    # Extract components
    weighted_base = re.search(r'Weighted Base: ([\d.]+)', section)
    synergy = re.search(r'Synergy Bonus: \+([\d.]+)', section)
    conflict = re.search(r'Conflict Penalty: -([\d.]+)', section)
    macro = re.search(r'Macro Score: ([\d.]+)', section)
    
    output.append(f"\nFINAL SCORE: {final_score:.2f}%")
    output.append(f"\nCOMPONENTS:")
    if weighted_base:
        output.append(f"  Weighted Base:     {float(weighted_base.group(1)):>6.2f}")
    if synergy:
        output.append(f"  Synergy Bonus:     +{float(synergy.group(1)):>5.2f}")
    if conflict:
        output.append(f"  Conflict Penalty:  -{float(conflict.group(1)):>5.2f}")
    if macro:
        output.append(f"  Macro Score:       {float(macro.group(1)):>6.2f}")
    
    # Extract top factors
    output.append(f"\nTOP FACTORS:")
    factor_pattern = r'(\d+)\.\s+([^:]+):\s+([\d.]+)\s+[×x]\s+([\d.]+)\s+=\s+([\d.]+)pts'
    factors = re.findall(factor_pattern, section)
    
    if factors:
        output.append(f"  {'Rank':<5} {'Factor':<35} {'Score':<8} {'Weight':<8} {'Contrib'}")
        output.append(f"  {'-'*5} {'-'*35} {'-'*8} {'-'*8} {'-'*8}")
        for rank, name, score, weight, contrib in factors[:10]:
            output.append(f"  {rank:<5} {name:<35} {score:>6}% × {weight:>6} = {contrib:>6}pts")

output.append("\n" + "=" * 80)
output.append(f"TOTAL SIGNALS ANALYZED: {signal_count}")
output.append("=" * 80)

# Write to file
with open('strike_detailed_breakdown.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print(f"✅ Detailed breakdown saved to: strike_detailed_breakdown.txt")
print(f"📊 Analyzed {signal_count} signals that passed 70% threshold")
print(f"\nShowing first signal preview:\n")

# Print first 40 lines as preview
for line in output[:40]:
    print(line)
