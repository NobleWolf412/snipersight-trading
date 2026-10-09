"""Universe failures/empty results must end the cycle before decision or execution."""
import asyncio
from types import SimpleNamespace as S
from unittest.mock import Mock

import pytest

from backend.analysis import pair_selection as pairs
from backend.bot.paper_trading_service import PaperTradingConfig, PaperTradingService
from backend.bot.live_trading_service import LiveTradingService
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.analysis.symbol_classifier import SymbolClassifier
from backend.services.scanner_service import ScannerService


@pytest.fixture
def ranked_adapter(monkeypatch):
    pairs.clear_stale_counters()
    pairs.clear_snapshot()
    monkeypatch.setattr(pairs, "_classifier", SymbolClassifier(auto_fetch=False))
    from backend.data.adapters.phemex import PhemexAdapter
    adapter = PhemexAdapter.__new__(PhemexAdapter)
    adapter.default_type = "swap"
    markets = {
        symbol: {"active": True, "quote": "USDT", "type": market_type}
        for symbol, market_type in [
            ("BTC/USDT", "spot"), ("BTC/USDT:USDT", "swap"),
            ("DOGE/USDT", "spot"), ("DOGE/USDT:USDT", "swap"),
            ("FOO/USDT:USDT", "swap"),
        ]
    }
    adapter.exchange = S(
        markets=markets, load_markets=lambda: markets,
        fetch_tickers=lambda: {symbol: {"quoteVolume": 100_000_000., "close": 100.}
                               for symbol in markets},
    )
    adapter.get_symbol_volumes = lambda symbols: {symbol: 100_000_000. for symbol in symbols}
    yield adapter
    pairs.clear_stale_counters()
    pairs.clear_snapshot()


@pytest.mark.parametrize("service_class", [PaperTradingService, LiveTradingService])
def test_universe_consumers_enabled_category_reaches_bot_engine(ranked_adapter, service_class):
    svc = service_class.__new__(service_class)
    svc.diagnostic_logger = None
    svc.config = PaperTradingConfig(sniper_mode="strike", symbols=[], majors=False,
                                    altcoins=False, meme_mode=True, leverage=3)
    svc.mode = get_mode("strike")
    svc.stats = S(scans_completed=0, signals_generated=0)
    svc._prev_regime_trend = None
    svc.position_manager = None
    svc._running = True
    svc._generation = 1
    svc._expired_symbols = set()
    svc.current_scan = None
    svc._log_activity = Mock()
    scan = Mock(return_value=([], {"details": {}, "by_reason": {}}))
    svc.orchestrator = S(exchange_adapter=ranked_adapter, config=ScanConfig(),
                         scan_with_heartbeat=scan, apply_mode=Mock())
    asyncio.run(svc._run_scan())
    scan.assert_called_once()
    assert scan.call_args.kwargs["symbols"] == ["DOGE/USDT:USDT"]
    assert svc.current_scan["status"] == ("completed" if service_class is PaperTradingService else "complete")
    assert pairs.get_latest_snapshot()["selected"] == ["DOGE/USDT:USDT"]
    assert all(call.args[0] != "scan_error" for call in svc._log_activity.call_args_list)


@pytest.mark.parametrize("empty", [False, True])
def test_universe_consumers_scanner_job_preserves_selection(ranked_adapter, empty):
    if empty:
        ranked_adapter.get_top_symbols = lambda **_: ["BTC/USDT"]
    scan = Mock(return_value=([], {"total_rejected": 0, "details": {}, "by_reason": {}}))
    ranked_adapter.exchange.options = {}
    engine = S(config=ScanConfig(), apply_mode=Mock(), scan=scan)
    svc = ScannerService(engine, {"fixture": lambda: ranked_adapter})
    svc._transform_signals = lambda *args: ([], [])

    async def run():
        job = await svc.create_scan(exchange="fixture", limit=20, majors=False,
                                    altcoins=False, meme_mode=True, leverage=3)
        await job.task
        return job

    job = asyncio.run(run())
    if empty:
        scan.assert_not_called()
        assert job.status == "failed" and "No symbols selected" in job.error
    else:
        scan.assert_called_once()
        assert scan.call_args.args[0] == ["DOGE/USDT:USDT"]
        assert job.status == "completed" and job.metadata["scanned"] == 1


@pytest.mark.parametrize("service_class", [PaperTradingService, LiveTradingService])
@pytest.mark.parametrize("outcome", ["error", "empty", "stale", "excluded", "illiquid"])
def test_universe_consumers_end_unscannable_cycle(monkeypatch, service_class, outcome):
    # Construct only the scan boundary; never start an executor, client or session.
    svc = service_class.__new__(service_class)
    svc.diagnostic_logger = None
    svc.config = PaperTradingConfig(sniper_mode="strike", symbols=[])
    svc.mode = get_mode("strike")
    svc.stats = S(scans_completed=0)
    svc._running = True
    svc._generation = 1
    svc._expired_symbols = set()
    svc._cvd_poll_symbols = ["OLD/USDT"]
    svc.current_scan = {"status": "complete", "total": 99}
    svc._log_activity = Mock()
    adapter = S(get_symbol_volumes=Mock(return_value={"BTC/USDT": 1.}))
    scan = Mock(return_value=([], {}))
    svc.orchestrator = S(exchange_adapter=adapter, config=ScanConfig(),
                         scan_with_heartbeat=scan, apply_mode=Mock())
    selection = Mock(return_value=[] if outcome == "empty" else ["BTC/USDT"])
    if outcome == "error":
        selection.side_effect = AssertionError("candidate accounting broken")
    if outcome in ("stale", "excluded", "illiquid"):
        svc.config.symbols = ["BTC/USDT"]
    if outcome == "excluded":
        svc.config.exclude_symbols = ["BTC/USDT"]
        adapter.get_symbol_volumes.return_value = {"BTC/USDT": 100_000_000.}
    monkeypatch.setattr(pairs, "select_symbols", selection)
    monkeypatch.setattr(pairs, "filter_stale_symbols", lambda symbols, **_: (
        ([], [{"symbol": "BTC/USDT", "reason": "stale_no_data"}])
        if outcome == "stale" else (symbols, [])
    ))
    asyncio.run(svc._run_scan())
    scan.assert_not_called()
    if outcome in ("error", "empty", "stale"):
        adapter.get_symbol_volumes.assert_not_called()
    assert svc.current_scan["total"] == 0
    terminal = "completed" if service_class is PaperTradingService else "complete"
    assert svc.current_scan["status"] == ("error" if outcome == "error" else terminal)
    event, details = svc._log_activity.call_args.args
    assert event == ("scan_error" if outcome == "error" else "scan_completed")
    assert details["reason"] == ("universe_selection_failed" if outcome == "error" else "universe_empty")
    assert details["symbols_scanned"] == details["signals_found"] == 0
    if outcome == "error":
        assert "candidate accounting broken" in details["error"]
    if service_class is PaperTradingService:
        assert svc._cvd_poll_symbols == []
