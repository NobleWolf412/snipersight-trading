"""
Regression tests for the Phemex → SniperSight data layer.

These tests cover the three failure modes identified in the data-layer debug
report:

1. Trade journal must dedupe so the periodic Phemex backfill cannot create
   duplicate rows after a restart.
2. PhemexAdapter.fetch_my_trades must increment the metrics counters and
   propagate auth/rate-limit/exchange errors so /healthz reflects reality.
3. PhemexWebSocketClient must count parse errors instead of silently
   discarding malformed frames, so a protocol drift is visible immediately.
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Trade journal: append + upsert dedupe
# ---------------------------------------------------------------------------

def test_trade_journal_upsert_skips_existing_trade_id(tmp_path):
    """Re-running the backfill must not create duplicate journal rows."""
    from backend.bot.trade_journal import TradeJournalService

    journal = TradeJournalService(path=tmp_path / "journal.jsonl")

    trade = {
        "trade_id": "abc-1",
        "symbol": "BTC/USDT:USDT",
        "pnl": 12.34,
        "exit_time": "2026-05-06T10:00:00Z",
    }
    assert journal.upsert(trade, session_id="s1") is True
    assert journal.upsert(trade, session_id="s1") is False, (
        "second upsert with same trade_id must be a no-op"
    )

    rows = journal.query(limit=10)
    assert len(rows) == 1
    assert rows[0]["trade_id"] == "abc-1"


def test_trade_journal_upsert_without_id_falls_back_to_append(tmp_path):
    """No trade_id → behave like append; better to risk a dup than drop a fill."""
    from backend.bot.trade_journal import TradeJournalService

    journal = TradeJournalService(path=tmp_path / "journal.jsonl")

    payload: Dict[str, Any] = {"symbol": "ETH/USDT:USDT", "pnl": 1.0}
    journal.upsert(payload, session_id="s1")
    journal.upsert(payload, session_id="s1")

    rows = journal.query(limit=10)
    assert len(rows) == 2, "without a trade_id, dedupe is impossible — both rows persist"


# ---------------------------------------------------------------------------
# PhemexAdapter.fetch_my_trades: counters + error propagation
# ---------------------------------------------------------------------------

def _make_adapter_with_mocked_exchange(monkeypatch) -> Any:
    """Construct a PhemexAdapter without touching the network."""
    import ccxt
    from backend.data.adapters.phemex import PhemexAdapter

    # Stub ccxt.phemex so __init__ doesn't try to load_markets()
    fake_exchange = MagicMock()
    fake_exchange.load_markets.return_value = {}
    fake_exchange.markets = {}
    fake_exchange.apiKey = "k"
    fake_exchange.secret = "s"
    monkeypatch.setattr(ccxt, "phemex", lambda *a, **kw: fake_exchange)

    adapter = PhemexAdapter(api_key="k", api_secret="s")
    return adapter, fake_exchange


def test_fetch_my_trades_increments_counters(monkeypatch):
    """A successful call must bump call+row counters and stamp last_rest_call_ts."""
    adapter, fake_exchange = _make_adapter_with_mocked_exchange(monkeypatch)
    fake_trades: List[Dict[str, Any]] = [
        {"id": "t1", "order": "o1", "amount": 0.1, "price": 60000.0, "timestamp": 1, "symbol": "BTC/USDT:USDT"},
        {"id": "t2", "order": "o2", "amount": 0.2, "price": 60100.0, "timestamp": 2, "symbol": "BTC/USDT:USDT"},
    ]
    fake_exchange.fetch_my_trades.return_value = fake_trades

    rows = adapter.fetch_my_trades(symbol="BTC/USDT:USDT", since=0, limit=10)

    assert rows == fake_trades
    assert adapter.metrics["fetch_my_trades_calls_total"] == 1
    assert adapter.metrics["fetch_my_trades_rows_total"] == 2
    assert adapter.metrics["rest_calls_total"] == 1
    assert adapter.metrics["last_rest_call_ts"] is not None


def test_fetch_my_trades_propagates_auth_error(monkeypatch):
    """Auth failure must bump rest_auth_errors_total and re-raise."""
    import ccxt

    adapter, fake_exchange = _make_adapter_with_mocked_exchange(monkeypatch)
    fake_exchange.fetch_my_trades.side_effect = ccxt.AuthenticationError("bad key")

    with pytest.raises(ccxt.AuthenticationError):
        adapter.fetch_my_trades()

    assert adapter.metrics["rest_auth_errors_total"] == 1
    assert adapter.metrics["last_rest_error_ts"] is not None
    assert "auth" in (adapter.metrics["last_rest_error_msg"] or "")


def test_fetch_my_trades_propagates_rate_limit(monkeypatch):
    """RateLimitExceeded must bump rest_429_total."""
    import ccxt

    adapter, fake_exchange = _make_adapter_with_mocked_exchange(monkeypatch)
    fake_exchange.fetch_my_trades.side_effect = ccxt.RateLimitExceeded("slow down")

    # The retry decorator will retry; eventually it must surface the error.
    with pytest.raises(ccxt.RateLimitExceeded):
        adapter.fetch_my_trades()

    # Counter is bumped on every attempt — should be at least 1.
    assert adapter.metrics["rest_429_total"] >= 1


# ---------------------------------------------------------------------------
# PhemexWebSocketClient: parse-error counter + heartbeat counter
# ---------------------------------------------------------------------------

def test_ws_dispatch_counts_parse_errors_without_crashing():
    """A malformed frame must not crash; counter must increment."""
    from backend.data.adapters.phemex_ws import PhemexWebSocketClient

    client = PhemexWebSocketClient(api_key="k", api_secret="s", testnet=True)
    assert client.metrics["parse_errors_total"] == 0

    # _dispatch is sync — call it directly with an unparseable string.
    client._dispatch("{not json")

    assert client.metrics["parse_errors_total"] == 1
    assert client.metrics["frames_in_total"] == 1
    assert client.metrics["last_frame_ts"] is not None


def test_ws_dispatch_routes_aop_orders_to_callback():
    """A well-formed aop_p frame must invoke the order callback per order."""
    from backend.data.adapters.phemex_ws import PhemexWebSocketClient

    received: List[tuple] = []

    def on_update(exchange_id, client_id, status, filled_qty, avg_price):
        received.append((exchange_id, client_id, status, filled_qty, avg_price))

    client = PhemexWebSocketClient(
        api_key="k", api_secret="s", testnet=True, on_order_update=on_update,
    )

    payload = {
        "type": "aop_p",
        "orders": [
            {
                "orderID": "X1",
                "clOrdID": "LIVE_00000001",
                "ordStatus": "Filled",
                "cumQtyRq": "0.1",
                "avgPriceRp": "60000.5",
            }
        ],
    }
    client._dispatch(json.dumps(payload))

    assert client.metrics["frames_aop_total"] == 1
    assert client.metrics["order_events_total"] == 1
    assert len(received) == 1
    exchange_id, client_id, status, filled_qty, avg_price = received[0]
    assert exchange_id == "X1"
    assert client_id == "LIVE_00000001"
    assert status == "Filled"
    assert filled_qty == pytest.approx(0.1)
    assert avg_price == pytest.approx(60000.5)


# ---------------------------------------------------------------------------
# LiveTradingService.get_trade_history: merge restores trades after restart
# ---------------------------------------------------------------------------

def test_get_trade_history_merges_journal_after_restart(tmp_path, monkeypatch):
    """
    Simulate a restart: completed_trades is empty (as it would be in a fresh
    process) but the journal on disk has rows. The merged source must surface
    those rows so the UI doesn't go blank.
    """
    from backend.bot import trade_journal as tj_module
    from backend.bot.live_trading_service import LiveTradingService

    # Point the singleton at a tmp journal file
    tmp_journal_path = tmp_path / "journal.jsonl"
    fresh_journal = tj_module.TradeJournalService(path=tmp_journal_path)
    monkeypatch.setattr(tj_module, "_journal_instance", fresh_journal)

    # Pre-populate the journal as if a prior session had closed two trades
    fresh_journal.append(
        {
            "trade_id": "T1",
            "symbol": "BTC/USDT:USDT",
            "pnl": 5.0,
            "entry_time": "2026-05-06T09:00:00Z",
            "exit_time": "2026-05-06T09:30:00Z",
        },
        session_id="restart-session",
    )
    fresh_journal.append(
        {
            "trade_id": "T2",
            "symbol": "ETH/USDT:USDT",
            "pnl": -2.5,
            "entry_time": "2026-05-06T09:45:00Z",
            "exit_time": "2026-05-06T10:00:00Z",
        },
        session_id="restart-session",
    )

    service = LiveTradingService()
    service.session_id = "restart-session"
    service.completed_trades = []   # restart wiped in-memory state

    merged = service.get_trade_history(limit=10, source="merged")
    assert len(merged) == 2
    assert {t["trade_id"] for t in merged} == {"T1", "T2"}

    journal_only = service.get_trade_history(limit=10, source="journal")
    assert len(journal_only) == 2

    session_only = service.get_trade_history(limit=10, source="session")
    assert session_only == [], "session-only must reflect empty in-memory list"
