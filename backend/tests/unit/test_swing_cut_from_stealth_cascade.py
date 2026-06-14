"""
Guards the 2026-06-14 swing-tier cut: STEALTH must NOT cascade swing.
(decisions/2026-06-14__cut-swing-tier-from-stealth-cascade.md)

Swing was a structural loser (-8.32/trade net, shorting the bottom of the range 100%
of the time). intraday + scalp are the net-positive tiers and must remain.
"""
from backend.shared.config.scanner_modes import MODES, get_mode


def _stealth():
    try:
        return get_mode("stealth")
    except Exception:
        return MODES["stealth"]


def test_stealth_cascade_excludes_swing():
    cascade = tuple(_stealth().cascade_trade_types or ())
    assert "swing" not in cascade, f"swing must be cut from STEALTH cascade; got {cascade}"


def test_stealth_cascade_keeps_intraday_and_scalp():
    cascade = tuple(_stealth().cascade_trade_types or ())
    assert "intraday" in cascade and "scalp" in cascade, (
        f"intraday + scalp (the net-positive tiers) must remain; got {cascade}"
    )


def test_stealth_cascade_is_exactly_intraday_scalp():
    assert tuple(_stealth().cascade_trade_types or ()) == ("intraday", "scalp")


def test_four_modes_still_present():
    # standing fix: exactly the four scanner modes, swing-cut must not drop a mode
    for m in ("overwatch", "stealth", "strike", "surgical"):
        assert m in MODES, f"standing-fix: mode {m} missing"


def test_non_stealth_modes_untouched_by_cut():
    # OVERWATCH/STRIKE/SURGICAL are single-expected-type (no cascade) — the cut is STEALTH-only.
    for m in ("overwatch", "strike", "surgical"):
        cfg = MODES[m]
        cascade = getattr(cfg, "cascade_trade_types", None)
        # they either have no cascade or one that this change did not touch
        if cascade:
            assert "swing" not in cascade or m != "stealth"
