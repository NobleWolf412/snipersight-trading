"""Raw candles through actual scanner/worker/strategy and paper settlement.

Synthetic OHLCV, dominance, quotes and precision are input fixtures. Worker calls
pickle both inputs and results but execute serially, so process spawning and
parallel isolation are not certified. The existing dormant cycle branch remains
visible; these tests do not claim historical performance or automatic restart.
"""
import asyncio
import json
import concurrent.futures
from datetime import datetime, timezone
from functools import lru_cache
import pickle
import sys
import time
from types import SimpleNamespace as S

import numpy as np
import pandas as pd
import pytest

from backend.engine import orchestrator as module
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.analysis import dominance_service
from backend.tests.integration.test_paper_workflow import workflow, tick, assert_published


class InlineWorkerPool:
    """Same worker and serialized arguments, without spawning unguarded children."""
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def submit(self, function, *args):
        future = concurrent.futures.Future()
        try:
            result = function(*pickle.loads(pickle.dumps(args)))
            future.set_result(pickle.loads(pickle.dumps(result)))
        except BaseException as error:
            future.set_exception(error)
        return future


@lru_cache(maxsize=8)
def synthetic_frames(seed, as_of, impulse):
    """One seeded five-minute price tape, consistently aggregated to all TFs."""
    rng = np.random.default_rng(seed)
    n = 500*288
    change = rng.normal(.000012, .001, n)
    if impulse:
        change[-24:-20] += impulse/4
    change[-20:] = .00015
    close = 100*np.exp(np.cumsum(change))
    close *= 100/close[-1]
    open_ = np.r_[close[0], close[:-1]]
    wick = rng.uniform(.0001, .0008, n)
    wick[-20:] = .00003
    index = pd.date_range(end=as_of-pd.Timedelta(minutes=5), periods=n, freq='5min')
    tape = pd.DataFrame({'open': open_, 'close': close,
        'high': np.maximum(open_, close)*(1+wick),
        'low': np.minimum(open_, close)*(1-wick),
        'volume': rng.lognormal(12., .8, n)}, index=index)
    tape.loc[tape.index[-24:], 'volume'] *= 8.
    frames = {}
    for tf, rule in [('5m','5min'), ('15m','15min'), ('1h','1h'), ('4h','4h'), ('1d','1D')]:
        rows = tape.resample(rule).agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
        rows.index.name = 'timestamp'
        for symbol, scale in [('BTC/USDT',1),('ETH/USDT',.5),('SOL/USDT',.1)]:
            frame = rows.reset_index()
            frame[['open','high','low','close']] *= scale
            frames[(symbol,tf)] = frame
    return frames


class SyntheticMarket:
    """Generated candle fixture, cut at the test clock; no external fetches."""
    def __init__(self, as_of, mirror=False, seed=2, impulse=0.):
        self.as_of = as_of
        self.frames = synthetic_frames(seed, as_of, impulse)
        self.omitted = set()
        self.flat = False
        self.mirror = mirror
        self.calls = []

    def reflection_reference(self, symbol):
        source = self.frames[(symbol, '1h')]
        source = source.loc[source.timestamp < self.as_of]
        return float(source.close.iloc[-1])

    def fetch_ohlcv(self, symbol, timeframe, limit=500):
        self.calls.append((symbol, timeframe, limit))
        frame = self.frames.get((symbol, timeframe))
        if frame is None or (symbol, timeframe) in self.omitted:
            return pd.DataFrame()
        frame = frame.loc[frame.timestamp < self.as_of].tail(limit).copy()
        if self.flat:
            frame[['open', 'close']] = 100.
            frame['high'], frame['low'], frame['volume'] = 100.1, 99.9, 1000.
        if self.mirror:
            center = self.reflection_reference(symbol)
            frame[['open', 'close']] = 2*center-frame[['open', 'close']]
            high, low = frame.high.copy(), frame.low.copy()
            frame['high'], frame['low'] = 2*center-low, 2*center-high
        return frame

    def get_market_info(self, symbol):
        return {'tick_size': .01, 'lot_size': .001}

    def get_symbol_volumes(self, symbols):
        return {s: 100_000_000. for s in symbols}


class ReflectedSyntheticMarket(SyntheticMarket):
    """Reflect the established SHORT tape into LONG; no seed/time/volume search.

    The source is exactly SyntheticMarket(mirror=True, seed=2, impulse=.01).
    Reflection uses one fixed positive reference per symbol across all TFs.
    Timestamps and volume are retained; reflected high/low exchange places.
    """
    def fetch_ohlcv(self, symbol, timeframe, limit=500):
        frame = super().fetch_ohlcv(symbol, timeframe, limit)
        if frame.empty:
            return frame
        center = self.reflection_reference(symbol)
        frame[['open', 'close']] = 2*center-frame[['open', 'close']]
        high, low = frame.high.copy(), frame.low.copy()
        frame['high'], frame['low'] = 2*center-low, 2*center-high
        return frame


@pytest.fixture
def core_factory(monkeypatch, tmp_path):
    # CooldownManager and diagnostic bundles use cwd-relative stores.
    monkeypatch.chdir(tmp_path)
    clock = S(now=datetime(2025, 12, 3, 12, tzinfo=timezone.utc))
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.now.astimezone(tz) if tz is not None else clock.now.replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return clock.now.replace(tzinfo=None)

    for name, imported in list(sys.modules.items()):
        if name.startswith('backend.') and not name.startswith('backend.tests.') and getattr(imported, 'datetime', None) is datetime:
            monkeypatch.setattr(imported, 'datetime', FrozenDateTime)
    monkeypatch.setattr(time, 'time', lambda: clock.now.timestamp())
    from backend.services import confluence_service
    real_score = confluence_service.calculate_confluence_score
    def clocked_score(*args, **kwargs):
        kwargs['as_of'] = clock.now
        return real_score(*args, **kwargs)
    monkeypatch.setattr(confluence_service, 'calculate_confluence_score', clocked_score)
    monkeypatch.setattr(concurrent.futures, 'ProcessPoolExecutor', InlineWorkerPool)
    monkeypatch.setattr(module, '_WORKER_ORCHESTRATOR', None)
    monkeypatch.setattr(module, '_WORKER_CONFIG_ID', None)
    # Explicit input-port fixture, not a claimed historical dominance observation.
    monkeypatch.setattr(dominance_service, 'get_current_dominance', lambda:
        dominance_service.DominanceSnapshot(clock.now.timestamp(), 54., 8., 38.,
                                           1e12, 5.4e11, 8e10, 3.8e11))
    monkeypatch.setenv('SS_DECISION_POLICY', 'legacy')
    monkeypatch.setenv('SS_FRESH_ENTRY_PRICE', '0')
    contexts, risk_checks = [], []
    real_risk = Orchestrator._validate_risk
    def observed_risk(engine, plan):
        passed = real_risk(engine, plan)
        risk_checks.append((plan.direction, passed))
        return passed
    monkeypatch.setattr(Orchestrator, '_validate_risk', observed_risk)
    context_class = module.SniperContext
    def context(*args, **kwargs):
        result = context_class(*args, **kwargs)
        contexts.append(result)
        return result
    monkeypatch.setattr(module, 'SniperContext', context)

    def make(mode='stealth', mirror=False, as_of=None, seed=2, impulse=0., reflect_short=False):
        if as_of is not None:
            clock.now = as_of
        market_type = ReflectedSyntheticMarket if reflect_short else SyntheticMarket
        adapter = market_type(clock.now, True if reflect_short else mirror, seed, impulse)
        engine = Orchestrator(ScanConfig(profile=get_mode(mode).profile),
                              exchange_adapter=adapter, concurrency_workers=1)
        # Unknown adapter identity already disables shared caching; each fixture
        # also explicitly uses fresh ingestion to avoid cross-test input state.
        engine.ingestion_pipeline.use_cache = False
        return S(engine=engine, adapter=adapter, contexts=contexts, clock=clock, risk_checks=risk_checks)
    return make


def attach_core(core_factory, workflow, preset='balanced'):
    """Resolve a supported preset through the bot's actual scan wrapper."""
    core = core_factory(mirror=workflow.sign < 0, impulse=.012 if workflow.sign > 0 else .01,
                        as_of=datetime(2025, 12, 3, 15, tzinfo=timezone.utc))
    svc = workflow.svc
    svc.config.sensitivity_preset = preset
    svc.config.symbols = ['BTC/USDT']
    svc.mode = get_mode('stealth')
    svc.orchestrator = core.engine
    svc._price_cache['BTC/USDT'] = float(core.adapter.fetch_ohlcv('BTC/USDT','5m').close.iloc[-1])
    return core


def test_core_workflow_reflection_detector_symmetry(core_factory, capsys):
    """A fixed price reflection must preserve ATR-based structural events."""
    from backend.shared.config.smc_config import get_tf_smc_config
    from backend.strategy.smc import bos_choch as detector
    cores = [core_factory(mirror=True, reflect_short=reflected, impulse=.01,
                         as_of=datetime(2025, 12, 3, 15, tzinfo=timezone.utc))
             for reflected in (False, True)]
    for timeframe in cores[0].engine.config.timeframes:
        source, reflected = [core.adapter.fetch_ohlcv('BTC/USDT', timeframe) for core in cores]
        center = cores[0].adapter.reflection_reference('BTC/USDT')
        pd.testing.assert_frame_equal(reflected[['timestamp','volume']], source[['timestamp','volume']])
        for output, original in [('open','open'), ('close','close'), ('high','low'), ('low','high')]:
            np.testing.assert_allclose(reflected[output], 2*center-source[original])
        assert (reflected[['open','high','low','close']] > 0).all().all()
    data = [core.engine._ingest_data('BTC/USDT') for core in cores]
    results = []
    for timeframe in cores[0].engine.config.timeframes:
        service = cores[0].engine.smc_service
        tf_config = get_tf_smc_config(timeframe, service._mode)
        if not tf_config.get('detect_bos', True):
            continue
        config = service._create_tf_smc_config(tf_config)
        frames = [d.timeframes[timeframe] for d in data]
        lookback = detector.scale_lookback(config.structure_swing_lookback, timeframe)
        swings = [(detector._detect_swing_highs(frame, lookback),
                   detector._detect_swing_lows(frame, lookback)) for frame in frames]
        breaks = [detector.detect_structural_breaks(frame, config, mode_profile=service._mode_profile)
                  for frame in frames]
        summaries = [[(b.timestamp.isoformat(), b.break_type, b.direction, b.grade) for b in rows]
                     for rows in breaks]
        expected = [(ts, kind, 'bullish' if direction == 'bearish' else 'bearish', grade)
                    for ts, kind, direction, grade in summaries[0]]
        result = {'timeframe':timeframe,
                  'initial_trends':[detector._determine_initial_trend(*s) for s in swings],
                  'first_swings':[[list(s[0].head(2)), list(s[1].head(2))] for s in swings],
                  'short_events':summaries[0], 'reflected_events':summaries[1]}
        with capsys.disabled():
            print('STRUCTURAL_REFLECTION_SNAPSHOT '+json.dumps(result))
        if len(breaks[0]) == len(breaks[1]):
            center = cores[0].adapter.reflection_reference('BTC/USDT')
            np.testing.assert_allclose([b.level for b in breaks[1]],
                                       [2*center-b.level for b in breaks[0]])
        results.append((timeframe, expected, summaries[1]))
    assert any(expected for _, expected, _ in results), 'Fixture must exercise real structural breaks'
    assert all(expected == actual for _, expected, actual in results), results


@pytest.mark.parametrize('preset,gate,floor', [('balanced',65.,65.), ('aggressive',65.,65.)])
def test_core_workflow_score_preset_admission(core_factory, workflow, preset, gate, floor, capsys):
    """Compare policy admission on the unchanged original candle tapes."""
    core = attach_core(core_factory, workflow, preset)
    svc = workflow.svc
    asyncio.run(svc._run_scan())
    assert not core.engine.diagnostics['indicator_failures']
    assert not core.engine.diagnostics['smc_rejections']
    assert not module._WORKER_ORCHESTRATOR.diagnostics['indicator_failures']
    ctx = core.contexts[-1]
    direction = 'LONG' if workflow.sign > 0 else 'SHORT'
    score = (ctx.confluence_breakdown.total_score if ctx.confluence_breakdown is not None
             else ctx.metadata['raw_directional_scores'][direction.lower()])
    assert core.engine.config.min_confluence_score == gate
    assert core.engine.config.confluence_soft_floor == floor
    assert module._WORKER_ORCHESTRATOR.config.min_confluence_score == gate
    with capsys.disabled():
        print('CORE_SCORE_SNAPSHOT '+json.dumps({'direction':direction,'fixture':'original',
            'seed':2,'impulse':.012 if workflow.sign>0 else .01,'hour':15,
            'preset':preset,'gate':gate,'floor':floor,'score':score,'accepted':svc.stats.signals_generated,
            'detected_shifts':sorted({(b.direction,b.timeframe,b.break_type,b.grade)
                                      for b in ctx.smc_snapshot.structural_breaks}),
            'allowed_structure_timeframes':core.engine.config.structure_timeframes,
            'reasons':[r.get('reason_type') for r in svc.signal_log]}))
    # Both original tapes qualify after the mirrored initial-trend defect was
    # repaired. The prior missing-shift and crossed-wall failures remain in the
    # review evidence; neither candle tape nor preset is tuned around them.
    assert svc.stats.signals_generated == 1, svc.signal_log
    assert ctx.plan is not None
    assert ctx.plan.direction == direction
    assert ctx.plan.confidence_score >= gate
    assert ctx.confluence_breakdown.metadata['score_model_version'] == 'family-evidence-v2'
    assert ctx.confluence_breakdown.metadata['evidence_eligible'] is True
    assert ctx.confluence_breakdown.metadata['evidence_missing'] == []
    if workflow.sign < 0:
        assert ctx.plan.risk_reward > {'scalp': 4., 'intraday': 7., 'swing': 15.}[ctx.plan.trade_type]
        assert svc.signal_log[-1]['reason_type'] == 'rr_too_wide'
        assert not svc.executor.orders
    else:
        assert svc.executor.orders


@pytest.mark.parametrize('exit_kind', ['stop', 'target'])
@pytest.mark.parametrize('selection', ['fixed', 'adaptive'])
def test_core_workflow_candles_to_bot_outcome(core_factory, workflow, monkeypatch, exit_kind, selection):
    w = workflow
    # Original raw tapes and actual preset; detector, score and planner are real.
    core = attach_core(core_factory, w, preset='aggressive')
    svc = w.svc
    if selection == 'adaptive':
        from unittest.mock import AsyncMock
        from backend.analysis.mode_recommendation import AdaptiveModeSelector
        from backend.tests.unit.test_mode_regime_policy import snapshot
        svc.config.selection_mode = 'adaptive'
        svc._adaptive_selector = AdaptiveModeSelector()
        svc._regime_reader = S(get_global=AsyncMock(return_value=snapshot(volatility='compressed', now=core.clock.now)))
    asyncio.run(svc._run_scan())
    assert svc.stats.signals_generated == 1, svc.signal_log
    assert len(core.contexts) == 1
    ctx = core.contexts[0]
    assert set(ctx.multi_tf_indicators.by_timeframe) == {'5m', '15m', '1h', '4h', '1d'}
    assert ctx.macro_context is not None
    assert ctx.metadata['symbol_regime'] is not None
    assert ctx.metadata['global_regime'] is not None
    assert ctx.smc_snapshot.fvgs and ctx.smc_snapshot.liquidity_pools
    assert ctx.smc_snapshot.htf_levels
    assert any(f.name == 'Fair Value Gap' and f.score > 0 for f in ctx.confluence_breakdown.factors)
    assert ctx.plan is not None
    assert ctx.plan.metadata['strategy']['selection_mode'] == selection
    assert ctx.plan.metadata['strategy']['mode'] == 'stealth'
    direction = 'LONG' if w.sign > 0 else 'SHORT'
    assert ctx.plan.direction == direction
    assert ctx.plan.confidence_score >= core.engine.config.min_confluence_score
    assert core.risk_checks and all(d == direction and passed for d, passed in core.risk_checks)
    # The wrapper clamps the preset to the STEALTH baseline; workers preserve it.
    assert core.engine.config.min_confluence_score == 65.
    assert core.engine.config.confluence_soft_floor == 65.
    assert module._WORKER_ORCHESTRATOR.config.min_confluence_score == 65.
    assert module._WORKER_ORCHESTRATOR.config.min_rr_ratio == core.engine.config.min_rr_ratio
    assert not module._WORKER_ORCHESTRATOR.diagnostics['indicator_failures']
    assert not module._WORKER_ORCHESTRATOR.diagnostics['smc_rejections']

    if w.sign < 0:
        # The fixed VAP horizon changes this original tape's target geometry.
        # Preserve the tape and bot's risk cap; this is a negative admission case.
        assert ctx.plan.risk_reward > {'scalp': 4., 'intraday': 7., 'swing': 15.}[ctx.plan.trade_type]
        assert svc.signal_log[-1]['reason_type'] == 'rr_too_wide'
        assert not svc.executor.orders and not w.journal.query()
        return
    assert svc.executor.orders, svc.signal_log
    if not svc.position_manager.get_open_positions():
        order = svc.executor.get_open_orders()[0]
        svc._price_cache['BTC/USDT'] = order.price
        tick(w, monkeypatch)
    positions = svc.position_manager.get_open_positions()
    assert len(positions) == 1, svc.signal_log
    pos = positions[0]
    assert pos.direction == direction
    assert pos.strategy == ctx.plan.metadata['strategy']
    assert svc._get_active_positions()[0]['strategy'] == pos.strategy
    assert pos.confidence_score == pytest.approx(ctx.plan.confidence_score)
    assert pos.quantity > 0
    assert pos.quantity*abs(pos.entry_price-pos.stop_loss) <= 10.01
    if exit_kind == 'stop':
        svc._price_cache['BTC/USDT'] = pos.stop_loss*(1-.02*w.sign)
    else:
        last_target = max(t.level for t in pos.targets) if w.sign > 0 else min(t.level for t in pos.targets)
        svc._price_cache['BTC/USDT'] = last_target*(1+.001*w.sign)
    # The fixed planner can produce several partial targets; each monitor tick
    # consumes one confirmed receipt before advancing to the next target.
    for _ in range(len(pos.targets) + 1 if exit_kind == 'target' else 1):
        tick(w, monkeypatch)
        if not svc.position_manager.get_open_positions():
            break
    row = assert_published(w)
    assert row['strategy'] == json.loads(json.dumps(ctx.plan.metadata['strategy']))
    assert row['direction'] == direction
    assert (row['pnl'] < 0) if exit_kind == 'stop' else (row['pnl'] > 0)
    # Publication retries cannot duplicate the completed trade.
    asyncio.run(svc._sync_closed_positions())
    assert len(w.journal.query()) == 1


@pytest.mark.parametrize('exit_kind', ['stop', 'target'])
def test_core_workflow_family_plan_to_paper_settlement(workflow, monkeypatch, exit_kind):
    """Controlled family-v2 plan boundary; this does not claim raw admission."""
    from backend.tests.unit.test_scoring_confidence_contract import family_breakdown
    from backend.shared.config.sensitivity import resolve_sensitivity

    w = workflow
    svc = w.svc
    svc.config.sensitivity_preset = 'conservative'
    svc.mode = get_mode('stealth')
    assert resolve_sensitivity(svc.config, svc.mode.min_confluence_score)[:2] == (75., 65.)
    plan = w.plan()
    direction = 'bullish' if w.sign > 0 else 'bearish'
    plan.confluence_breakdown = family_breakdown(75., direction)
    plan.confidence_score = plan.confluence_breakdown.total_score
    asyncio.run(svc._process_signal(plan))
    positions = svc.position_manager.get_open_positions()
    assert len(positions) == 1, svc.signal_log
    pos = positions[0]
    assert pos.direction == plan.direction
    assert pos.confidence_score == 75.
    assert 0 < pos.quantity*abs(pos.entry_price-pos.stop_loss) <= 10.01
    if exit_kind == 'stop':
        svc._price_cache[plan.symbol] = pos.stop_loss*(1-.02*w.sign)
    else:
        target = max(t.level for t in pos.targets) if w.sign > 0 else min(t.level for t in pos.targets)
        svc._price_cache[plan.symbol] = target*(1+.001*w.sign)
    tick(w, monkeypatch)
    row = assert_published(w)
    assert row['direction'] == plan.direction
    assert (row['pnl'] < 0) if exit_kind == 'stop' else (row['pnl'] > 0)
    asyncio.run(svc._sync_closed_positions())
    assert len(w.journal.query()) == 1


@pytest.mark.parametrize('missing', ['1h', '4h'])
def test_core_workflow_missing_critical_data_stops_before_scoring(core_factory, workflow, missing):
    core = attach_core(core_factory, workflow)
    core.adapter.omitted.add(('BTC/USDT', missing))
    asyncio.run(workflow.svc._run_scan())
    assert not workflow.svc.executor.orders
    assert not workflow.journal.query()
    assert workflow.svc.stats.signals_generated == 0
    assert any(r['reason_type'] == 'missing_critical_tf' for r in workflow.svc.signal_log)
    assert len(core.contexts) == 1
    assert all(ctx.confluence_breakdown is None and ctx.plan is None for ctx in core.contexts)
    assert not core.risk_checks


def test_core_workflow_no_anchor_stops_before_scoring(core_factory, workflow):
    core = attach_core(core_factory, workflow)
    core.adapter.flat = True
    asyncio.run(workflow.svc._run_scan())
    assert not workflow.svc.executor.orders
    assert not workflow.journal.query()
    assert workflow.svc.stats.signals_generated == 0
    assert any(r['reason_type'] == 'structural_anchor' for r in workflow.svc.signal_log)
    assert len(core.contexts) == 1
    assert all(ctx.confluence_breakdown is None and ctx.plan is None for ctx in core.contexts)
    assert not core.risk_checks
