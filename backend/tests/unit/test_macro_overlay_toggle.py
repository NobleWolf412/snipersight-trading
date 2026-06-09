"""Regression: macro_overlay_enabled surfaced as an operator-controllable bot config field.

Surfacing task 2026-06-08 (ledger T19): the macro/dominance overlay (scorer.py:3114 reads
config.macro_overlay_enabled) is now exposed on the PAPER bot config + UI so the operator can
run pure-technicals. Default True = back-compat (no behavior change). This pins the plumbing:
the field exists, defaults True, round-trips, and rides the API request model. The scorer gate
itself (scorer.py:3114) is unchanged and covered by existing scorer tests — this surfacing task
only adds the config field + UI, so the regression target is the plumbing, not the overlay logic.
"""
from backend.bot.paper_trading_service import PaperTradingConfig


def test_macro_overlay_default_true_backcompat():
    # Surfacing must NOT change behavior: default stays True (matches orchestrator defaults.py:40).
    assert PaperTradingConfig().macro_overlay_enabled is True


def test_macro_overlay_round_trips_off():
    c = PaperTradingConfig(macro_overlay_enabled=False)
    d = c.to_dict()
    assert d["macro_overlay_enabled"] is False
    assert PaperTradingConfig.from_dict(d).macro_overlay_enabled is False


def test_api_request_model_carries_macro_overlay():
    from backend.api_server import PaperTradingConfigRequest
    assert PaperTradingConfigRequest().macro_overlay_enabled is True
    assert PaperTradingConfigRequest(macro_overlay_enabled=False).macro_overlay_enabled is False


def test_execution_mode_still_present():
    # Guard the sibling field the same UI panel surfaces (T14) wasn't disturbed.
    assert PaperTradingConfig().execution_mode == "snap_taker"
    from backend.api_server import PaperTradingConfigRequest
    assert PaperTradingConfigRequest().execution_mode == "snap_taker"
