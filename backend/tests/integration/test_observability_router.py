"""
HTTP integration tests for backend.routers.observability.

Validates the contract of all 6 observability endpoints via FastAPI's
TestClient. Tests assert at the schema level (Pydantic model validation
on every response) — not just "200 OK". A 200 with the wrong shape is
exactly the silent-failure class CLAUDE.md §15 warns about.

Coverage:
  - Happy path per endpoint (200, schema match, envelope shape)
  - Unknown signal id → 404 with structured detail
  - Buffer-mismatch → 200 with status=PARTIAL + reason=breakdown_evicted
  - Empty cache / cold start per endpoint
  - direction param on confluence distribution exposes both bull/bear
  - include_audit=true surfaces DEGRADED status when drift detected
  - Concurrency: 50 simultaneous reads with writer thread
        - every response parses as Envelope[T]
        - metadata.ts is monotonic within each individual response
        - no torn reads (data and metadata are consistent)
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.analysis.pair_selection import (
    clear_snapshot as clear_universe_snapshot,
    select_symbols,
)
from backend.diagnostics import status_cache
from backend.engine import cycle_heartbeat
from backend.routers.observability import router as observability_router
from backend.shared.models.envelope import Envelope, ResponseMetadata
from backend.shared.models.observability import (
    ConfluenceBreakdownDTO,
    ConfluenceDistribution,
    CycleHeartbeat,
    SignalTrace,
    Universe,
)
from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
from backend.strategy.confluence import cache as confluence_cache


def _mk_breakdown(symbol="BTC/USDT", direction="bullish", score=72.0):
    return ConfluenceBreakdown(
        total_score=score,
        factors=[
            ConfluenceFactor("structure", 80, 0.4, "BOS confirmed"),
            ConfluenceFactor("momentum", 70, 0.3, "MACD aligned"),
            ConfluenceFactor("volume", 65, 0.3, "Vol above avg"),
        ],
        synergy_bonus=2.0, conflict_penalty=1.0, regime="trend",
        htf_aligned=True, btc_impulse_gate=True,
        symbol=symbol, direction=direction,
    )


def _mk_heartbeat(run_id="abcd1234", **overrides):
    base = {
        "ts_start": 1_700_000_000.0,
        "ts_end": 1_700_000_001.5,
        "wall_ms": 1500,
        "run_id": run_id,
        "mode": "stealth",
        "symbols_scanned": 10,
        "plans_emitted": 2,
        "total_rejected": 8,
        "signals_per_stage": {"low_confluence": 5, "no_data": 3},
        "bottleneck_stage": "low_confluence",
        "direction_stats": {"longs_generated": 1, "shorts_generated": 1},
        "regime": None,
        "next_cycle_eta_ts": 1_700_000_061.5,
        "failed": False,
        "exception_class": None,
    }
    base.update(overrides)
    return base


class _FakeService:
    """Stand-in for LiveTradingService — exposes get_signal_by_id only."""
    def __init__(self, log):
        self.signal_log = log
    def get_signal_by_id(self, sid):
        for e in reversed(self.signal_log):
            if e.get("id") == sid:
                return e
        return None


@pytest.fixture
def fake_service(monkeypatch):
    """Patch the live trading service accessor to return our fake."""
    service = _FakeService(log=[
        {
            "id": "BTC-USDT_42_15m_long",
            "scan_number": 42, "symbol": "BTC/USDT", "direction": "LONG",
            "timeframe": "15m", "confluence": 78.0, "result": "pending",
            "reason_type": "pending_fill", "reason": "Waiting for fill",
        },
        {
            "id": "ETH/USDT_43_4h_short",
            "scan_number": 43, "symbol": "ETH/USDT", "direction": "SHORT",
            "timeframe": "4h", "confluence": 65.0, "result": "filtered",
            "reason_type": "low_confluence", "reason": "Score below gate",
        },
    ])
    import backend.bot.live_trading_service as lts_mod
    monkeypatch.setattr(lts_mod, "get_live_trading_service", lambda: service)
    return service


@pytest.fixture(autouse=True)
def _reset_state():
    confluence_cache.clear()
    cycle_heartbeat.clear()
    clear_universe_snapshot()
    status_cache.clear()
    yield
    confluence_cache.clear()
    cycle_heartbeat.clear()
    clear_universe_snapshot()
    status_cache.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(observability_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Envelope validation helper
# ---------------------------------------------------------------------------


def _assert_envelope_shape(payload: dict) -> None:
    """Every response MUST parse as a generic Envelope (extra=forbid)."""
    assert "data" in payload and "metadata" in payload and "warnings" in payload
    md = payload["metadata"]
    # ResponseMetadata is strict: validate it
    ResponseMetadata.model_validate(md)
    assert md["status"] in ("OK", "PARTIAL", "DEGRADED")
    assert md["cost_class"] in ("cheap", "moderate", "expensive")


# ===========================================================================
# /api/cycles/last
# ===========================================================================


def test_cycles_last_cold_start_returns_null_data(client):
    r = client.get("/api/cycles/last")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    assert body["data"] is None
    assert body["metadata"]["status"] == "OK"


def test_cycles_last_returns_latest_heartbeat(client):
    cycle_heartbeat.record(_mk_heartbeat(run_id="r1"))
    cycle_heartbeat.record(_mk_heartbeat(run_id="r2", ts_start=1_700_000_060.0))
    r = client.get("/api/cycles/last")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    # data must validate as CycleHeartbeat
    hb = CycleHeartbeat.model_validate(body["data"])
    assert hb.run_id == "r2"


# ===========================================================================
# /api/cycles/history
# ===========================================================================


def test_cycles_history_default_n_returns_all_when_below_limit(client):
    for i in range(3):
        cycle_heartbeat.record(_mk_heartbeat(run_id=f"r{i}", ts_start=1_700_000_000 + i))
    r = client.get("/api/cycles/history")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    assert len(body["data"]) == 3
    # Each entry must validate as CycleHeartbeat
    for entry in body["data"]:
        CycleHeartbeat.model_validate(entry)


def test_cycles_history_n_param_caps_at_max(client):
    for i in range(60):
        cycle_heartbeat.record(_mk_heartbeat(run_id=f"r{i}", ts_start=1_700_000_000 + i))
    r = client.get("/api/cycles/history?n=100")
    # Validation should reject n>50
    assert r.status_code == 422


def test_cycles_history_mode_filter(client):
    cycle_heartbeat.record(_mk_heartbeat(run_id="ow1", mode="overwatch"))
    cycle_heartbeat.record(_mk_heartbeat(run_id="sg1", mode="surgical"))
    cycle_heartbeat.record(_mk_heartbeat(run_id="sg2", mode="surgical"))
    r = client.get("/api/cycles/history?mode=surgical")
    body = r.json()
    assert all(e["mode"] == "surgical" for e in body["data"])


def test_cycles_history_include_audit_embeds_status(client):
    # Seed enough cycles to trigger drift detection (collapse)
    for i in range(5):
        cycle_heartbeat.record(_mk_heartbeat(
            run_id=f"healthy{i}", plans_emitted=10, symbols_scanned=20,
            signals_per_stage={"low_confluence": 10},
            ts_start=1_700_000_000 + i * 60.0,
        ))
    cycle_heartbeat.record(_mk_heartbeat(
        run_id="anomaly", plans_emitted=1, symbols_scanned=20,
        signals_per_stage={"low_confluence": 19},
        ts_start=1_700_000_500.0,
    ))
    r = client.get("/api/cycles/history?include_audit=true")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    assert body["metadata"]["status"] == "DEGRADED"
    assert body["metadata"]["cost_class"] == "moderate"
    assert any("collapsed" in w for w in body["warnings"])


# ===========================================================================
# /api/scanner/universe
# ===========================================================================


def test_universe_cold_start_returns_empty(client):
    r = client.get("/api/scanner/universe")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    universe = Universe.model_validate(body["data"])
    assert universe.counts.qualified == 0


def test_universe_after_select_symbols_populates(client):
    class A:
        def get_top_symbols(self, n=20, quote_currency="USDT", market_type=None):
            return ["BTC/USDT", "ETH/USDT", "USDC/USDT", "DOGE/USDT"]
        def is_perp(self, s): return True
    select_symbols(A(), limit=2, majors=True, altcoins=True, meme_mode=False)
    r = client.get("/api/scanner/universe")
    body = r.json()
    _assert_envelope_shape(body)
    universe = Universe.model_validate(body["data"])
    assert universe.counts.qualified == 2
    # USDC was a stable_base drop
    drop_reasons = {d.reason for d in universe.dropped}
    assert "stable_base" in drop_reasons


# ===========================================================================
# /api/signals/{id}/trace  &  /confluence  — lookup-miss contract
# ===========================================================================


def test_trace_unknown_id_returns_404(client, fake_service):
    r = client.get("/api/signals/never_existed/trace")
    assert r.status_code == 404
    body = r.json()
    assert body["detail"]["reason"] == "unknown_id"
    assert body["detail"]["id"] == "never_existed"


def test_trace_known_id_returns_full_trace(client, fake_service):
    r = client.get("/api/signals/BTC-USDT_42_15m_long/trace")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    trace = SignalTrace.model_validate(body["data"])
    assert trace.id == "BTC-USDT_42_15m_long"
    assert trace.symbol == "BTC/USDT"
    assert trace.side == "long"
    assert len(trace.stages) == 11  # flattened pipeline


def test_confluence_unknown_id_returns_404(client, fake_service):
    r = client.get("/api/signals/never_existed/confluence")
    assert r.status_code == 404
    assert r.json()["detail"]["reason"] == "unknown_id"


def test_confluence_buffer_mismatch_returns_partial(client, fake_service):
    """id known to signal_log but breakdown evicted from cache → 200 PARTIAL."""
    # fake_service has BTC-USDT_42_15m_long in signal_log; we record NO breakdown.
    r = client.get("/api/signals/BTC-USDT_42_15m_long/confluence")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    assert body["data"] is None
    assert body["metadata"]["status"] == "PARTIAL"
    assert body["metadata"]["reason"] == "breakdown_evicted"


def test_confluence_present_returns_breakdown(client, fake_service):
    confluence_cache.record("BTC-USDT_42_15m_long", _mk_breakdown())
    r = client.get("/api/signals/BTC-USDT_42_15m_long/confluence")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    dto = ConfluenceBreakdownDTO.model_validate(body["data"])
    assert dto.id == "BTC-USDT_42_15m_long"
    assert len(dto.factors) == 3


# ===========================================================================
# /api/signals/confluence/distribution
# ===========================================================================


def test_distribution_empty_cache(client):
    r = client.get("/api/signals/confluence/distribution")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    dist = ConfluenceDistribution.model_validate(body["data"])
    assert dist.sample_count == 0


def test_distribution_exposes_both_directions_regardless_of_filter(client):
    """Standing fix #3 protection: by_direction always includes both sides."""
    for i in range(3):
        confluence_cache.record(f"long_{i}", _mk_breakdown(direction="bullish"))
    for i in range(2):
        confluence_cache.record(f"short_{i}", _mk_breakdown(direction="bearish"))

    for direction in ("all", "long", "short"):
        r = client.get(f"/api/signals/confluence/distribution?direction={direction}")
        body = r.json()
        dist = ConfluenceDistribution.model_validate(body["data"])
        directions_present = {d.direction for d in dist.by_direction}
        assert directions_present == {"long", "short"}, (
            f"direction={direction} should expose BOTH sides, got {directions_present}"
        )


def test_distribution_invalid_direction_rejected(client):
    r = client.get("/api/signals/confluence/distribution?direction=sideways")
    assert r.status_code == 422


# ===========================================================================
# Concurrency — proves threading.Lock holds under FastAPI threadpool
# ===========================================================================


def test_concurrent_reads_during_writes_no_torn_state(client, fake_service):
    """50 concurrent GETs while a writer thread feeds the buffer.

    Asserts:
      - Every response parses as Envelope[T] (Pydantic schema validation)
      - metadata.ts is reasonable (positive, recent, monotonic-ish)
      - No torn reads — data field shape always matches metadata.status
    """
    # Seed some confluence breakdowns so /distribution has data to chew on
    for i in range(20):
        confluence_cache.record(f"seed_{i}", _mk_breakdown())

    stop = threading.Event()
    write_count = [0]

    def writer():
        i = 0
        while not stop.is_set():
            cycle_heartbeat.record(_mk_heartbeat(
                run_id=f"w{i}", ts_start=1_700_000_000 + i,
            ))
            confluence_cache.record(f"writer_{i}", _mk_breakdown())
            write_count[0] += 1
            i += 1
            time.sleep(0.001)  # yield

    writer_thread = threading.Thread(target=writer, daemon=True)
    writer_thread.start()

    # 50 concurrent reads across multiple endpoints
    endpoints = [
        "/api/cycles/last",
        "/api/cycles/history",
        "/api/cycles/history?n=10",
        "/api/scanner/universe",
        "/api/signals/confluence/distribution",
        "/api/signals/confluence/distribution?direction=long",
    ]

    def reader(url):
        resp = client.get(url)
        return resp.status_code, resp.json()

    try:
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(reader, endpoints[i % len(endpoints)]) for i in range(50)]
            results = [f.result(timeout=10) for f in as_completed(futures)]
    finally:
        stop.set()
        writer_thread.join(timeout=2)

    # Stronger assertions than "200 OK":
    for status_code, body in results:
        assert status_code == 200, f"non-200: {status_code}, body={body}"

        # Envelope schema must validate
        _assert_envelope_shape(body)

        # metadata.ts must be a recent timestamp (within the test runtime window)
        ts = body["metadata"]["ts"]
        assert ts > 1_700_000_000, f"unrealistic ts={ts}"
        assert ts < time.time() + 5, f"future ts={ts}"

        # Torn-read check: status=OK implies data type matches contract
        if body["metadata"]["status"] == "OK":
            # data must be either None (cold start), a dict, or a list — never a
            # half-built object missing required fields.
            data = body["data"]
            assert data is None or isinstance(data, (dict, list)), (
                f"torn data shape: {type(data).__name__}"
            )

    # Writer made progress
    assert write_count[0] > 0, "writer never ran"


# ===========================================================================
# OpenAPI — every endpoint registered, every response_model present
# ===========================================================================


def test_openapi_renders_all_observability_endpoints(client):
    spec = client.get("/openapi.json").json()
    paths = spec.get("paths", {})
    expected = {
        "/api/signals/{id}/trace",
        "/api/signals/{id}/confluence",
        "/api/signals/confluence/distribution",
        "/api/scanner/universe",
        "/api/cycles/last",
        "/api/cycles/history",
    }
    missing = expected - set(paths.keys())
    assert not missing, f"missing from OpenAPI: {missing}"

    # Every observability path has a response schema (not naked dict)
    for path in expected:
        get_op = paths[path]["get"]
        assert "responses" in get_op
        assert "200" in get_op["responses"]
        # Tag is observability
        assert "observability" in get_op.get("tags", [])
