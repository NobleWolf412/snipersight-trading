"""Form-B fix: the limit snap is now bounded by the RR floor so it can't manufacture a
sub-floor geometry the entry gate then rejects. Pins _rr_bounded_snap (pure, symmetric).
See decisions/2026-06-25__DESIGN-fresh-entry-price-geometry.md (Form B note) +
2026-06-13__fill-geometry-distortion.md (the RR floor it preserves)."""
from backend.bot.paper_trading_service import _entry_realized_rr, _rr_bounded_snap

FLOOR = 1.0


# ---- SELL (short): stop ABOVE entry, TP1 BELOW; snap moves entry DOWN toward market ----

def test_sell_preserving_snap_unchanged():
    # desired snap already keeps RR >= floor -> returned unchanged
    # stop=70, tp1=66 -> rr_bound=(70+66)/2=68 ; desired 68.17 >= bound -> unchanged
    out = _rr_bounded_snap("SELL", desired_limit=68.17, raw_limit=69.0, stop=70.0, nearest_tp=66.0, rr_floor=FLOOR)
    assert abs(out - 68.17) < 1e-9
    assert _entry_realized_rr(out, 70.0, [66.0]) >= FLOOR


def test_sell_overaggressive_snap_clamped_to_floor():
    # desired 66.77 would collapse RR to ~0.24; clamp UP to the rr_bound (68.0) where RR==floor
    out = _rr_bounded_snap("SELL", desired_limit=66.77, raw_limit=69.0, stop=70.0, nearest_tp=66.0, rr_floor=FLOOR)
    assert abs(out - 68.0) < 1e-9
    assert _entry_realized_rr(out, 70.0, [66.0]) >= FLOOR - 1e-9  # at the floor exactly


# ---- BUY (long): mirror — stop BELOW entry, TP1 ABOVE; snap moves entry UP toward market ----

def test_buy_preserving_snap_unchanged():
    out = _rr_bounded_snap("BUY", desired_limit=65.8, raw_limit=65.0, stop=64.0, nearest_tp=68.0, rr_floor=FLOOR)
    assert abs(out - 65.8) < 1e-9
    assert _entry_realized_rr(out, 64.0, [68.0]) >= FLOOR


def test_buy_overaggressive_snap_clamped_to_floor():
    # stop=64, tp1=68 -> rr_bound=(64+68)/2=66 ; desired 66.23 -> clamp DOWN to 66.0
    out = _rr_bounded_snap("BUY", desired_limit=66.23, raw_limit=65.0, stop=64.0, nearest_tp=68.0, rr_floor=FLOOR)
    assert abs(out - 66.0) < 1e-9
    assert _entry_realized_rr(out, 64.0, [68.0]) >= FLOOR - 1e-9


# ---- symmetry: BUY and SELL are exact mirrors ----

def test_buy_sell_symmetry():
    # mirror geometry around a center; the clamp distance from raw_limit should match
    sell = _rr_bounded_snap("SELL", desired_limit=66.77, raw_limit=69.0, stop=70.0, nearest_tp=66.0, rr_floor=FLOOR)
    buy = _rr_bounded_snap("BUY", desired_limit=66.23, raw_limit=65.0, stop=64.0, nearest_tp=68.0, rr_floor=FLOOR)
    assert abs(sell - 68.0) < 1e-9 and abs(buy - 66.0) < 1e-9  # both clamp to their RR=floor bound


# ---- OB itself sub-floor -> no snap (returns raw_limit); the RR gate then rejects ----

def test_ob_subfloor_returns_raw_limit_no_snap_sell():
    # raw_limit (OB) 66.5 is already sub-floor vs stop=70/tp=66 (rr_bound=68 > raw_limit)
    out = _rr_bounded_snap("SELL", desired_limit=66.7, raw_limit=66.5, stop=70.0, nearest_tp=66.0, rr_floor=FLOOR)
    assert abs(out - 66.5) < 1e-9                       # unchanged -> no snap
    assert _entry_realized_rr(66.5, 70.0, [66.0]) < FLOOR  # gate will (correctly) reject


def test_ob_subfloor_returns_raw_limit_no_snap_buy():
    out = _rr_bounded_snap("BUY", desired_limit=66.3, raw_limit=66.5, stop=64.0, nearest_tp=66.0, rr_floor=FLOOR)
    assert abs(out - 66.5) < 1e-9
    assert _entry_realized_rr(66.5, 64.0, [66.0]) < FLOOR


# ---- unusable geometry -> returns desired unchanged (never crashes) ----

def test_unusable_geometry_passthrough():
    assert _rr_bounded_snap("SELL", 68.0, 69.0, 0.0, 66.0, FLOOR) == 68.0   # stop 0
    assert _rr_bounded_snap("BUY", 66.0, 65.0, 64.0, 0.0, FLOOR) == 66.0    # tp 0
    assert _rr_bounded_snap("SELL", 68.0, 69.0, 70.0, 66.0, 0.0) == 68.0    # floor 0 (disabled)
