"""
Phase-1 regression for the maker-execution toggle (T14, design
decisions/2026-06-06__maker-execution-experiment-design.md).

Guards the two load-bearing invariants that backend-integrity + §16 flagged:
  1. DEFAULT is snap_taker and BYTE-INERT — `rest_maker_active` is False, so the snap +
     immediate-fill paths in _process_signal are unchanged (`and not False` / `else` branch).
  2. §15 LIVE-PATH GUARD — rest_maker is force-disabled under use_testnet (the executor is a
     LiveExecutor then; the maker experiment is paper-only).

Pure config-level invariants (the property is the single source of truth the entry path reads),
so no heavyweight service/executor setup needed.
"""
from __future__ import annotations

from backend.bot.paper_trading_service import PaperTradingConfig, CompletedTrade


def test_default_is_snap_taker_and_inert():
    """INVARIANT 1: default config = snap_taker, rest_maker NOT active → entry path untouched."""
    c = PaperTradingConfig()
    assert c.execution_mode == "snap_taker"
    assert c.rest_maker_active is False


def test_rest_maker_active_on_paper():
    """Positive: rest_maker on a paper (non-testnet) config activates the maker path."""
    c = PaperTradingConfig(execution_mode="rest_maker")
    assert c.use_testnet is False
    assert c.rest_maker_active is True


def test_rest_maker_forced_off_under_testnet():
    """INVARIANT 2 (§15): rest_maker + use_testnet → force-disabled (LiveExecutor path is paper-only-guarded)."""
    c = PaperTradingConfig(execution_mode="rest_maker", use_testnet=True)
    assert c.rest_maker_active is False


def test_snap_taker_under_testnet_still_off():
    """Negative pair: snap_taker (default) under testnet is also not maker — never accidentally on."""
    c = PaperTradingConfig(execution_mode="snap_taker", use_testnet=True)
    assert c.rest_maker_active is False


def test_from_dict_accepts_execution_mode_and_ignores_unknown():
    """The API/botConfig path builds config via from_dict; the toggle must round-trip, unknown keys ignored."""
    c = PaperTradingConfig.from_dict({"execution_mode": "rest_maker", "not_a_field": 123})
    assert c.execution_mode == "rest_maker"
    # absent key falls to the default (forward/backward compatible)
    assert PaperTradingConfig.from_dict({}).execution_mode == "snap_taker"


def test_completed_trade_tags_execution_mode():
    """The journal row must carry execution_mode (default snap_taker) for cohort-filtering in edge_significance."""
    ct = CompletedTrade(
        trade_id="t", symbol="X", direction="SHORT", entry_price=1.0, exit_price=1.0,
        quantity=1.0, entry_time=None, exit_time=None, pnl=0.0, pnl_pct=0.0,
        exit_reason="x", targets_hit=[],
    )
    d = ct.to_dict()
    assert "execution_mode" in d and d["execution_mode"] == "snap_taker"
