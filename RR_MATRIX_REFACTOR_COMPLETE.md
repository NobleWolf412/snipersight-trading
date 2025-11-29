# RR Matrix Refactor - Complete ✅

**Status**: Production-ready quality gate implementation complete

## Executive Summary

Refactored `backend/shared/config/rr_matrix.py` to address all 7 identified issues and establish production-ready R:R validation as the single source of truth for plan quality assessment.

---

## Issues Addressed

### ✅ 1. ATR_FALLBACK Conviction Fix
**Problem**: ATR_FALLBACK plans permanently locked to class C
**Solution**: Band-based logic allows ATR_FALLBACK to reach class B
- ATR_FALLBACK capped at B (can be good, never A-tier without structure)
- B requires: R:R ≥ min_rr (1.0) AND confluence ≥ 60%
- Distinguishes "good ATR plan" from "barely acceptable"

### ✅ 2. A/B/C Band Logic
**Problem**: All-or-nothing thresholds (below ideal_rr = instant C)
**Solution**: Graduated quality bands with smooth transitions
- **Class A**: SMC + ideal R:R (≥2.5) + high confluence (≥80) + complete data
- **Class B**: R:R near ideal (≥80% of ideal) + decent confluence (≥65)
  - OR: SMC/HYBRID with decent R:R + decent confluence
  - OR: ATR_FALLBACK with min R:R + 60% confluence
- **Class C**: Meets minimum thresholds but nothing special

### ✅ 3. Production Min R:R Values
**Problem**: Demo-mode thresholds (0.8 everywhere)
**Solution**: Plan-type-specific production values
```python
SMC:          min_rr=1.5, ideal_rr=2.5  # Structure-based
ATR_FALLBACK: min_rr=1.0, ideal_rr=1.8  # Fallback when no structure
HYBRID:       min_rr=1.2, ideal_rr=2.0  # Mixed approach
```

### ✅ 4. EV Integration
**Problem**: No EV thinking in RR validation
**Solution**: Added `calculate_implied_pwin()` helper
```python
def calculate_implied_pwin(risk_reward: float, target_ev: float = 0.0) -> float:
    """
    EV = p_win * R - (1 - p_win) * 1
    Solving for p_win: p_win = (EV + 1) / (R + 1)
    """
```
- Utility function for EV-aware analysis
- Maps R:R → required win probability for target EV
- Enables downstream EV-based filtering/ranking

### ✅ 5. Mode-Aware Thresholds
**Problem**: Same thresholds for surgical scalps and swing setups
**Solution**: Profile-based multipliers via `MODE_RR_MULTIPLIERS`
```python
MODE_RR_MULTIPLIERS = {
    "precision": (1.0, 1.0),           # surgical: strict default
    "intraday_aggressive": (0.85, 0.9),  # strike: looser for scalps
    "balanced": (1.0, 1.0),            # recon: default
    "macro_surveillance": (1.1, 1.15),  # overwatch: tighter for swings
    "stealth_balanced": (1.0, 1.0),    # ghost: default
}
```
- `get_rr_threshold(plan_type, mode_profile)` applies multipliers
- Strike mode: 15% looser min R:R for fast scalps (1.5 → 1.28)
- Overwatch mode: 10-15% tighter for swing setups (1.5 → 1.65)

### ✅ 6. Conviction-Driven Behavior Documentation
**Problem**: Conviction class unused after classification
**Solution**: Added `get_conviction_behavior_guide()` mapping conviction → behavior
```python
Conviction A → Aggressive targets, full position size, tight entry patience
Conviction B → Balanced ladders, 75% size, moderate patience
Conviction C → Conservative single target, 50% size, wider zones
```
Dimensions specified:
- Target spacing (ladder aggressiveness)
- Position sizing (% of mode allocation)
- Entry patience (zone precision requirements)
- Gate strictness (borderline tolerance)
- Hold behavior (exit discipline)

### ✅ 7. Single Source of Truth
**Problem**: Duplicated R:R validation logic across modules
**Solution**: Centralized validation with clear delegation pattern
- `validate_rr()` is the **only** R:R validation function
- All components delegate to this function (no local thresholds)
- Mode-aware via `mode_profile` parameter
- Returns (bool, reason) tuple for actionable rejection messages

---

## Integration Points

### Planner Service
**Updated**: `backend/strategy/planner/planner_service.py`
```python
# Mode-aware validation
is_valid_rr, rr_reason = validate_rr(plan_type, risk_reward, mode_profile=config.profile)

# Mode-aware conviction classification
conviction_class = classify_conviction(
    plan_type=plan_type,
    risk_reward=risk_reward,
    confluence_score=confluence_breakdown.total_score,
    has_all_critical_tfs=has_all_critical_tfs,
    mode_profile=config.profile
)
```

### ScanConfig
**Updated**: `backend/shared/config/defaults.py`
```python
@dataclass
class ScanConfig:
    profile: str = "balanced"  # Mode profile for RR multipliers
    # ... planner knobs added
    primary_planning_timeframe: str = "4H"
    max_pullback_atr: float = 3.0
    min_stop_atr: float = 1.0
    max_stop_atr: float = 6.0
```

---

## API Changes

### Function Signatures (Backward Compatible)
All changes are **additive** via optional `mode_profile` parameter:

**Before**:
```python
get_rr_threshold(plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"]) -> RRThreshold
classify_conviction(plan_type, risk_reward, confluence_score, has_all_critical_tfs) -> Literal["A", "B", "C"]
validate_rr(plan_type, risk_reward) -> tuple[bool, str]
```

**After**:
```python
get_rr_threshold(plan_type, mode_profile: Optional[str] = None) -> RRThreshold
classify_conviction(plan_type, risk_reward, confluence_score, has_all_critical_tfs, mode_profile: Optional[str] = None) -> Literal["A", "B", "C"]
validate_rr(plan_type, risk_reward, mode_profile: Optional[str] = None) -> tuple[bool, str]
```

### New Functions
```python
calculate_implied_pwin(risk_reward: float, target_ev: float = 0.0) -> float
get_conviction_behavior_guide() -> Dict[str, Dict[str, str]]
```

---

## Testing Recommendations

### Unit Tests Needed
```python
# Test mode multipliers
assert get_rr_threshold("SMC", "intraday_aggressive").min_rr == 1.5 * 0.85
assert get_rr_threshold("SMC", "macro_surveillance").min_rr == 1.5 * 1.1

# Test ATR_FALLBACK conviction cap
assert classify_conviction("ATR_FALLBACK", 2.0, 70.0, True) == "B"  # Can be B
assert classify_conviction("ATR_FALLBACK", 3.0, 90.0, True) != "A"  # Never A

# Test band logic (80% of ideal threshold)
assert classify_conviction("SMC", 2.0, 70.0, True) == "B"  # 2.0 ≥ 2.5*0.8

# Test implied p_win
assert calculate_implied_pwin(2.0, 0.0) == pytest.approx(0.33, 0.01)  # Breakeven
assert calculate_implied_pwin(1.0, 0.2) == pytest.approx(0.6, 0.01)   # +20% EV
```

### Integration Tests
- Scan with surgical mode → verify strike uses looser thresholds (0.85x)
- Scan with overwatch mode → verify swing uses tighter thresholds (1.1x)
- Generate ATR_FALLBACK plan → verify class B achievable, A unreachable
- Compare conviction A/B/C signals → verify behavior guide influences downstream

---

## Migration Notes

### No Breaking Changes
- All existing callsites work unchanged (default `mode_profile=None`)
- New optional parameter preserves backward compatibility
- Planner updated to pass `config.profile` for mode-awareness

### Downstream Opportunities
**Conviction behavior guide** ready for integration:
- **Target planner**: Use conviction class to modulate ladder spacing
- **Position sizer**: Apply conviction-based allocation multipliers (A: 1.0x, B: 0.75x, C: 0.5x)
- **Entry logic**: A-class signals require tighter entry zones
- **Exit manager**: C-class signals exit on first adverse signal

---

## Next Steps

### Immediate
1. ✅ RR matrix refactor complete
2. 🔄 **Next**: Swing-based stop fallback in planner (user requested)
   - Use swing highs/lows from primary timeframe when SMC structures unavailable
   - Hierarchy: SMC structure → swing levels → HTF structure → reject

### Future Enhancements
- Wire conviction behavior guide into target planner (ladder spacing)
- Implement conviction-based position sizing multipliers
- Add conviction-aware entry zone tightness
- Create conviction-driven exit discipline rules

---

## Impact Summary

**Quality Gates**: Production-ready thresholds replace demo values
**Flexibility**: Mode-aware thresholds adapt to trading style (scalp vs swing)
**Intelligence**: Band-based logic allows nuanced quality assessment
**Architecture**: Single source of truth eliminates validation drift
**EV Integration**: Utility functions enable EV-based ranking/filtering
**Behavior Mapping**: Clear guide for how conviction should influence downstream systems

🎯 **Result**: Robust, production-ready R:R validation that adapts to mode, plan type, and quality signals while serving as the canonical quality gate for all trade plans.
