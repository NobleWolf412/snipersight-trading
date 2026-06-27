"""Outlier guard for SS_FRESH_ENTRY_PRICE (heart-change Form-A, adversarial-review hardening):
the fresh tick re-anchors plan geometry ONLY for modest drift; a big/painted move falls back to
the candle close so it can't swap the scored OB. Pins the pure guard predicate _fresh_within_guard.
See decisions/2026-06-25__DESIGN-fresh-entry-price-geometry.md."""
from backend.engine.orchestrator import Orchestrator

G = Orchestrator._fresh_within_guard  # staticmethod — no instance needed


def test_modest_drift_within_guard():
    # |fresh-close| = 1.0, atr=2.0, mult=1.0 -> 1.0 <= 2.0 -> use fresh
    assert G(101.0, 100.0, 2.0, 1.0) is True
    assert G(99.0, 100.0, 2.0, 1.0) is True   # symmetric (down)


def test_big_move_rejected_as_outlier():
    # |fresh-close| = 3.0 > 1.0*2.0 -> reject, fall back to close
    assert G(103.0, 100.0, 2.0, 1.0) is False
    assert G(97.0, 100.0, 2.0, 1.0) is False  # symmetric (down)


def test_boundary_inclusive():
    # exactly at the bound is allowed (<=)
    assert G(102.0, 100.0, 2.0, 1.0) is True


def test_mult_scales_the_window():
    # a 3.0 move passes when the window is 1.5*2.0=3.0
    assert G(103.0, 100.0, 2.0, 1.5) is True
    assert G(103.0, 100.0, 2.0, 0.5) is False  # tighter window rejects


def test_no_usable_atr_falls_back():
    # atr<=0 or mult<=0 or close<=0 -> distrust the fresh tick (False -> use candle close)
    assert G(101.0, 100.0, 0.0, 1.0) is False
    assert G(101.0, 100.0, 2.0, 0.0) is False
    assert G(101.0, 0.0, 2.0, 1.0) is False


def test_symmetry_up_down_identical_magnitude():
    # equal-magnitude up and down deviations get the same verdict
    assert G(100.0 + 1.5, 100.0, 2.0, 1.0) == G(100.0 - 1.5, 100.0, 2.0, 1.0)
    assert G(100.0 + 2.5, 100.0, 2.0, 1.0) == G(100.0 - 2.5, 100.0, 2.0, 1.0)
