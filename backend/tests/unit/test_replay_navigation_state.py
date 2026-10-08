"""Replay navigation must not reuse analysis state from a later displayed bar."""
from collections import deque
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest

from backend.engine.replay_engine import ReplayEngine,ReplaySession,StepResult
from backend.engine.orchestrator import Orchestrator


def fixture_engine():
    engine=ReplayEngine(object())
    start=datetime(2026,9,1,tzinfo=timezone.utc)
    session=ReplaySession('session','BTC/USDT','stealth',start,start+timedelta(hours=4),{}, {},'1h',
                          [start+timedelta(hours=i) for i in range(4)],SimpleNamespace(seen=[]))
    session.ring_buffer=deque(maxlen=2)
    engine._sessions[session.session_id]=session
    engine._build_orchestrator=lambda mode:SimpleNamespace(seen=[])
    def compute(session,index):
        prior=list(session.orchestrator.seen)
        session.orchestrator.seen.append(index)
        return StepResult(index,session.bar_timestamps[index],session.bar_timestamps[index]+timedelta(hours=1),
                          {},plan={'prior':prior})
    engine._compute_step=compute
    return engine,session


def test_repeat_index_and_step_at_end_return_the_existing_result():
    engine,session=fixture_engine()
    result=engine.goto('session',3)
    assert engine.goto('session',3) is result
    assert engine.step('session',1) is result
    assert session.orchestrator.seen==[0,1,2,3]


@pytest.mark.parametrize('back_to',[0,2])
def test_backtracking_then_forward_does_not_inherit_future_state(back_to):
    engine,session=fixture_engine()
    engine.goto('session',3)
    engine.goto('session',back_to)
    result=engine.step('session',1)
    assert result.plan['prior']==list(range(back_to+1))
    assert session.orchestrator.seen==list(range(back_to+2))


def test_failed_compute_does_not_advance_cursor_and_retry_rebuilds():
    engine,session=fixture_engine()
    compute=engine._compute_step
    def fail(session,index):
        session.orchestrator.seen.append(999)
        raise ValueError('scripted computation failure')
    engine._compute_step=fail
    with pytest.raises(ValueError,match='scripted'):
        engine.step('session',1)
    assert session.step_index==-1
    engine._compute_step=compute
    assert engine.step('session',1).plan['prior']==[]


def test_concurrent_steps_are_serialized_per_session():
    engine,session=fixture_engine()
    compute=engine._compute_step;entered=threading.Event();release=threading.Event()
    def controlled(session,index):
        if index==0:
            entered.set();assert release.wait(3)
        return compute(session,index)
    engine._compute_step=controlled
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(engine.step,'session',1)
        try:
            assert entered.wait(2)
            second=pool.submit(engine.step,'session',1)
        finally:
            release.set()
        results=[first.result(),second.result()]
    assert [r.index for r in results]==[0,1]
    assert session.orchestrator.seen==[0,1]


@pytest.mark.parametrize('btc',['missing','failed','none'])
def test_replay_missing_context_cannot_retain_a_later_steps_regime_or_macro(btc):
    engine=object.__new__(Orchestrator)
    engine._Orchestrator__replay_mode=True
    engine.current_regime=SimpleNamespace(composite='future')
    engine.macro_context=object()
    observed=[]
    def detector(**kwargs):
        if btc=='failed':raise ValueError('scripted historical detector failure')
        return None
    engine._detect_global_regime=detector
    engine._process_symbol=lambda **kwargs:(observed.append((engine.current_regime,engine.macro_context)),None)
    engine.process_symbol_for_replay('BTC/USDT',None,datetime(2026,9,1,tzinfo=timezone.utc),'r',0,'session',
                                     prefetched_btc_data=None if btc=='missing' else object())
    assert observed==[(None,None)]


def test_replay_engines_own_services_and_regime_state_without_reconfiguring_live_globals(monkeypatch):
    from backend.services import indicator_service,smc_service,confluence_service
    from backend.engine import orchestrator as module
    from backend.shared.config.scanner_modes import get_mode
    sentinel=object()
    monkeypatch.setattr(indicator_service,'_indicator_service',sentinel)
    monkeypatch.setattr(smc_service,'_smc_service',sentinel)
    monkeypatch.setattr(confluence_service,'_confluence_service',sentinel)
    def global_detector_forbidden():
        raise AssertionError('Replay attempted to borrow the global detector')
    monkeypatch.setattr(module,'get_regime_detector',global_detector_forbidden)
    engine=ReplayEngine(object())
    first=engine._build_orchestrator(get_mode('strike'))
    second=engine._build_orchestrator(get_mode('overwatch'))
    assert first.regime_detector is not second.regime_detector
    assert first.regime_detector.mode_profile=='intraday_aggressive'
    assert second.regime_detector.mode_profile=='macro_surveillance'
    assert first.regime_detector._global_regime_ttl==first.regime_detector._symbol_regime_ttl==0
    assert first.indicator_service is not second.indicator_service
    assert first.smc_service is not second.smc_service
    assert first.confluence_service is not second.confluence_service
    assert indicator_service.get_indicator_service() is sentinel
    assert smc_service.get_smc_service() is sentinel
    assert confluence_service.get_confluence_service() is sentinel


def test_jump_after_backtracking_rebuilds_prefix_and_preserves_advance_count():
    engine,session=fixture_engine();compute=engine._compute_step
    def signals(session,index):
        result=compute(session,index);result.signal_fired=index==2
        return result
    engine._compute_step=signals
    engine.goto('session',3)
    engine.goto('session',0)
    result,advanced=engine.jump_to_next_signal('session',max_lookahead=3)
    assert advanced==2 and result.index==2 and result.plan['prior']==[0,1]
    assert session.orchestrator.seen==[0,1,2]
