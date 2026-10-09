"""A universe is a filtered set, not a priority list with excluded backfill."""
import itertools
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.analysis import pair_selection as pairs
from backend.analysis.symbol_classifier import SymbolClassifier, SymbolCategory


class Adapter:
    def __init__(self, symbols, perps=(), error=None):
        self.symbols = symbols
        self.perps = set(perps)
        self.error = error
        self.calls = []

    def get_top_symbols(self, n=20, quote_currency="USDT", market_type=None):
        self.calls.append((n, quote_currency, market_type))
        if self.error:
            raise self.error
        return self.symbols[:n]

    def is_perp(self, symbol):
        return symbol in self.perps


@pytest.fixture(autouse=True)
def isolated_selection(monkeypatch):
    monkeypatch.setattr(pairs, "_classifier", SymbolClassifier(auto_fetch=False))
    pairs.clear_snapshot()
    pairs.clear_stale_counters()
    yield
    pairs.clear_snapshot()
    pairs.clear_stale_counters()


def assert_partition(selected, dropped, candidates):
    unique = set(candidates)
    rejected = [row["symbol"] for row in dropped]
    assert len(selected) == len(set(selected))
    assert len(rejected) == len(set(rejected))
    assert not set(selected).intersection(rejected)
    assert set(selected).union(rejected) == unique
    assert len(selected) + len(dropped) == len(unique)
    snapshot = pairs.get_latest_snapshot()
    assert snapshot["fetched"] == len(unique)
    assert snapshot["selected"] == selected
    assert snapshot["dropped"] == dropped


@pytest.mark.parametrize("toggles", itertools.product([False, True], repeat=3))
@pytest.mark.parametrize("limit", [2, 20])
def test_universe_contract_every_toggle_combination_is_strict(toggles, limit):
    symbols = ["DOGE/USDT", "FOO/USDT", "BTC/USDT", "ETH/USDT", "SHIB/USDT", "BAR/USDT"]
    majors, alts, memes = toggles
    selected, dropped = pairs.select_symbols_with_drops(
        Adapter(symbols), limit, majors, alts, memes
    )
    # All-off retains the explicit legacy meaning: all eligible categories.
    groups = [
        ["BTC/USDT", "ETH/USDT"] if majors else [],
        ["DOGE/USDT", "SHIB/USDT"] if memes else [],
        ["FOO/USDT", "BAR/USDT"] if alts else [],
    ]
    eligible = [s for group in groups for s in group] if any(toggles) else symbols
    assert selected == eligible[:limit]
    reasons = {row["symbol"]: row["reason"] for row in dropped}
    for symbol in symbols:
        if symbol not in eligible:
            assert reasons[symbol] == "bucket_excluded"
        elif symbol not in selected:
            assert reasons[symbol] == "limit_exhausted"
    assert_partition(selected, dropped, symbols)


def test_universe_contract_deduplicates_input_before_counting():
    symbols = ["BTC/USDT", "DOGE/USDT", "BTC/USDT", "DOGE/USDT", "USDC/USDT", "USDC/USDT"]
    selected, dropped = pairs.select_symbols_with_drops(Adapter(symbols), 20, True, False, False)
    assert selected == ["BTC/USDT"]
    assert_partition(selected, dropped, symbols)


def test_universe_contract_no_majors_does_not_promote_arbitrary_top_ranked_symbols():
    symbols = ["DOGE/USDT", "FOO/USDT", "SHIB/USDT"]
    selected, dropped = pairs.select_symbols_with_drops(Adapter(symbols), 20, True, False, False)
    assert selected == []
    assert all(row["reason"] == "bucket_excluded" for row in dropped)
    assert_partition(selected, dropped, symbols)


def test_universe_contract_classification_handles_standard_swap_and_compact_names():
    symbols = ["DOGE/USDT:USDT", "FOO/USDT", "ETHUSDT", "BTC/USDT:USDT"]
    selected, dropped = pairs.select_symbols_with_drops(Adapter(symbols), 20, True, False, False)
    assert selected == ["ETHUSDT", "BTC/USDT:USDT"]
    assert_partition(selected, dropped, symbols)


def test_universe_contract_classifies_once_per_candidate(monkeypatch):
    classify = Mock(return_value=SymbolCategory.MEME)
    monkeypatch.setattr(pairs, "_classifier", SimpleNamespace(classify=classify))
    selected, dropped = pairs.select_symbols_with_drops(Adapter(["FOO/USDT"]), 10, False, False, True)
    assert selected == ["FOO/USDT"]
    classify.assert_called_once_with("FOO/USDT")


@pytest.mark.parametrize("source_error", [None, RuntimeError("rank source unavailable")])
def test_universe_contract_initial_fallback_passes_all_filters(monkeypatch, source_error):
    symbols = ["USDC/USDT", "BTC/USDT", "ETH/USDT", "DOGE/USDT", "FOO/USDT"]
    monkeypatch.setattr(pairs, "DEFAULT_FALLBACK", symbols)
    for _ in range(pairs._NO_DATA_DROP_THRESHOLD):
        pairs.record_no_data_failure("ETH/USDT")
    adapter = Adapter([], perps={"BTC/USDT", "DOGE/USDT"}, error=source_error)
    selected, dropped = pairs.select_symbols_with_drops(adapter, 20, False, False, True, 3, "swap")
    assert selected == ["DOGE/USDT"]
    assert {d["symbol"]: d["reason"] for d in dropped} == {
        "USDC/USDT": "stable_base", "ETH/USDT": "stale_no_data",
        "FOO/USDT": "non_perp", "BTC/USDT": "bucket_excluded",
    }
    assert_partition(selected, dropped, symbols)


def test_universe_contract_no_perps_never_substitutes_unchecked_pool(monkeypatch):
    symbols = ["BTC/USDT", "DOGE/USDT"]
    monkeypatch.setattr(pairs, "DEFAULT_FALLBACK", ["BTC/USDT", "DOGE/USDT", "USDC/USDT"])
    selected, dropped = pairs.select_symbols_with_drops(Adapter(symbols), 20, False, False, True, 5, "swap")
    assert selected == []
    assert all(row["reason"] == "non_perp" for row in dropped)
    assert_partition(selected, dropped, symbols)


@pytest.mark.parametrize("perp_result", [False, RuntimeError("market lookup unavailable")])
def test_universe_contract_explicit_nonperp_does_not_turn_true_via_symbol_spelling(perp_result):
    adapter = Adapter(["BTC/USDT:USDT"])
    if isinstance(perp_result, Exception):
        adapter.is_perp = Mock(side_effect=perp_result)
        # An unavailable metadata lookup can use the documented notation fallback.
        assert pairs._is_perp_with_fallback(adapter, "BTC/USDT:USDT")
    else:
        assert pairs._is_perp_with_fallback(adapter, "BTC/USDT:USDT") is False


def test_universe_contract_zero_limit_is_empty_without_fetch():
    adapter = Adapter(["BTC/USDT"])
    selected, dropped = pairs.select_symbols_with_drops(adapter, 0, True, True, True)
    assert selected == dropped == []
    assert not adapter.calls
    assert_partition(selected, dropped, [])


def test_universe_contract_negative_limit_is_rejected_before_fetch():
    adapter = Adapter(["BTC/USDT"])
    with pytest.raises(ValueError, match="limit"):
        pairs.select_symbols_with_drops(adapter, -1, True, True, True)
    assert not adapter.calls


def test_universe_contract_snapshot_is_detached_from_returned_evidence():
    selected, dropped = pairs.select_symbols_with_drops(
        Adapter(["BTC/USDT", "DOGE/USDT"]), 20, True, False, False
    )
    dropped[0]["reason"] = "corrupted"
    selected.append("INJECTED/USDT")
    snapshot = pairs.get_latest_snapshot()
    assert snapshot["selected"] == ["BTC/USDT"]
    assert snapshot["dropped"] == [{"symbol": "DOGE/USDT", "reason": "bucket_excluded"}]
    snapshot["selected"].append("OTHER/USDT")
    snapshot["toggles"]["majors"] = False
    history = pairs.get_snapshot_history()
    history[-1]["dropped"][0]["reason"] = "other_corruption"
    assert pairs.get_latest_snapshot()["selected"] == ["BTC/USDT"]
    assert pairs.get_latest_snapshot()["toggles"]["majors"] is True
    assert pairs.get_latest_snapshot()["dropped"][0]["reason"] == "bucket_excluded"
