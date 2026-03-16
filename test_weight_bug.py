
import dataclasses
from typing import List

@dataclasses.dataclass
class ConfluenceFactor:
    name: str
    score: float
    weight: float

factors = []
# Factor A: Score 100, Weight 0.5
# Factor B: Score 0, Weight 0.5

# Existing logic:
score_a = 100
if score_a > 0:
    factors.append(ConfluenceFactor("A", score_a, 0.5))

score_b = 0
if score_b > 0:
    factors.append(ConfluenceFactor("B", score_b, 0.5))

print(f"Factors appended: {[f.name for f in factors]}")

total_weight = sum(f.weight for f in factors)
print(f"Total weight: {total_weight}")

if total_weight > 0 and abs(total_weight - 1.0) > 0.01:
    for i, f in enumerate(factors):
        factors[i] = ConfluenceFactor(f.name, f.score, f.weight / total_weight)

final_score = sum(f.score * f.weight for f in factors)
print(f"Final Score: {final_score}")
