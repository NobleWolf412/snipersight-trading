"""Check recent confluence scores from all symbols"""
import re

with open('logs/confluence_breakdown.log', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all confluence breakdowns
pattern = r'CONFLUENCE BREAKDOWN \| (\S+) (BULLISH|BEARISH)\s+Final Score: ([\d.]+)'
matches = re.findall(pattern, content)

# Get last 15 unique symbols
seen = {}
results = []
for match in reversed(matches):
    symbol, direction, score = match
    key = f"{symbol}_{direction}"
    if key not in seen:
        seen[key] = True
        results.append((symbol, direction, float(score)))
    if len(results) >= 15:
        break

results.reverse()

print("=== RECENT CONFLUENCE SCORES ===\n")
print(f"{'Symbol':<20} {'Direction':<10} {'Score':<10} {'vs 78%'}")
print("-" * 55)
for symbol, direction, score in results:
    passed = "PASS" if score >= 78.0 else "FAIL"
    diff = score - 78.0
    print(f"{symbol:<20} {direction:<10} {score:>6.2f}%    {passed} ({diff:+.2f})")
