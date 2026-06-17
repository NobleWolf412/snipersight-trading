"""
Regression for the entry-regime snapshot bug (decisions/2026-06-16 §11.6 bug #1).

PositionState.regime_trend / regime_volatility are intentionally OVERWRITTEN every scan
by PaperTradingService._update_position_regimes so adaptive stagnation reacts to CURRENT
conditions. But the journal previously composed CompletedTrade.regime and
regime_trend_at_entry from those same mutable fields AT CLOSE — so every trade was
bucketed by the regime present when it CLOSED, not at entry. The down_normal vs
down_compressed split that the edge_by_regime cohort tables depend on is exactly a
normal<->compressed volatility-band flip — precisely what this bug scrambled, which is
why the +6.42 down_normal-scalp "edge" is a likely measurement artifact.

Fix: immutable entry_regime_trend / entry_regime_volatility captured at open_position;
the journal reads THOSE. The mutable pair stays for stagnation. A regime_labeled_at
marker tags post-fix rows so edge_by_regime can exclude dirty pre-fix history.

Per CLAUDE.md §11 (silent-bug surfacing), §14 rubric 4 (negative + positive pair,
bull/bear symmetry).
"""
from __future__ import annotations

from pathlib import Path

from backend.bot.executor.position_manager import PositionState


def _position(entry_trend: str, entry_vol: str) -> PositionState:
    """A PositionState whose entry snapshot is set as open_position sets it."""
    return PositionState(
        position_id="T1",
        symbol="BTC/USDT:USDT",
        direction="SHORT",
        entry_price=100.0,
        quantity=1.0,
        remaining_quantity=1.0,
        stop_loss=103.0,
        targets=[],
        regime_trend=entry_trend,
        regime_volatility=entry_vol,
        entry_regime_trend=entry_trend,
        entry_regime_volatility=entry_vol,
    )


def test_entry_regime_survives_scan_clobber():
    """After the stagnation updater overwrites the live regime to a DIFFERENT value, the
    journal must still bucket the trade by its ENTRY regime, not the close-time value."""
    pos = _position("down", "normal")  # entered in down_normal (the "+6.42" cohort)

    # Simulate _update_position_regimes: volatility band flips normal -> compressed
    # (the exact flip that would have leaked this trade into the -1.06 cohort).
    pos.regime_trend = "down"
    pos.regime_volatility = "compressed"

    # Stagnation still reads the CURRENT (clobbered) value — behavior unchanged.
    assert pos.regime_volatility == "compressed"

    # The journal composes from the immutable entry snapshot.
    journal_regime = f"{pos.entry_regime_trend}_{pos.entry_regime_volatility}"
    assert journal_regime == "down_normal", (
        "journal regime must reflect ENTRY (down_normal), not the clobbered close-time "
        f"value (down_compressed); got {journal_regime!r}"
    )
    assert pos.entry_regime_trend == "down"  # source for regime_trend_at_entry


def test_bullish_mirror_symmetric():
    """Bull path symmetry: entry up_elevated survives a clobber to up_normal."""
    pos = _position("up", "elevated")
    pos.regime_trend, pos.regime_volatility = "up", "normal"  # clobbered post-entry
    assert f"{pos.entry_regime_trend}_{pos.entry_regime_volatility}" == "up_elevated"
    assert pos.entry_regime_trend == "up"


def test_journal_writes_read_entry_snapshot_not_mutable_field():
    """Source-string pin: the paper AND live journal writes must read entry_regime_* and
    must NOT compose `regime` from the mutable (clobbered) regime_trend/regime_volatility.
    If a future refactor repoints these back to the bare fields, the close-vs-entry bug
    silently returns and every regime cohort is mis-bucketed again."""
    root = Path(__file__).resolve().parents[2]
    bug_signature = "'regime_trend', 'unknown')}_{getattr(pos, 'regime_volatility'"
    for rel in ("bot/paper_trading_service.py", "bot/live_trading_service.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "entry_regime_trend" in src, (
            f"{rel} journal write must read entry_regime_trend (the immutable entry "
            "snapshot), not the stagnation-clobbered regime_trend."
        )
        assert bug_signature not in src, (
            f"{rel} must NOT compose the journal `regime` from the mutable "
            "regime_trend/regime_volatility (clobbered every scan) — use entry_regime_* "
            "(decisions/2026-06-16 §11.6 bug #1)."
        )
