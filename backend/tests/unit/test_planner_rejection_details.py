"""Clean planner declines keep their cause without changing the plan-or-None API."""
import pytest

from backend.strategy.planner import planner_service as planner
from backend.shared.models.planner import EntryZone, StopLoss, Target
from backend.tests.unit.test_ev_none_plan_reason_mask import _ctx


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('decline', ['entry_depth', 'tp1_unreachable'])
@pytest.mark.parametrize('caller_owned', [False, True])
def test_planner_rejection_details_clean_declines(monkeypatch, direction, decline, caller_owned):
    context = _ctx()
    emitted = []
    monkeypatch.setattr(planner, 'get_telemetry_logger', lambda: type('Sink', (), {'log_event': lambda self, e: emitted.append(e)})())
    sign = 1 if direction == 'LONG' else -1
    entry = EntryZone(near_entry=100., far_entry=100.-sign, rationale='fixture')
    stop = StopLoss(level=100.-2*sign, distance_atr=1., rationale='fixture')
    monkeypatch.setattr(planner, '_calculate_entry_zone', lambda **kwargs: (None if decline == 'entry_depth' else entry, True))
    monkeypatch.setattr(planner, '_calculate_stop_loss', lambda **kwargs: (stop, True))
    def unreachable(**kwargs):
        raise planner.ReachabilityDecline('target exceeds reachability ceiling')
    monkeypatch.setattr(planner, '_calculate_targets', unreachable)
    details = {'reason': 'stale call'}
    from backend.shared.config.defaults import ScanConfig
    result = planner.generate_trade_plan(
        symbol='ETH/USDT', direction=direction, setup_type='OB_FVG_BOS',
        smc_snapshot=context.smc_snapshot, indicators=context.multi_tf_indicators,
        confluence_breakdown=context.confluence_breakdown, config=ScanConfig(), current_price=100.,
        rejection_details=details if caller_owned else None)
    assert result is None
    if caller_owned:
        assert details['reason_code'] == decline
        assert details['reason'] != 'stale call'
        if decline == 'tp1_unreachable':
            assert 'target exceeds reachability ceiling' in details['reason']
    rejects = [e for e in emitted if e.event_type.value == 'signal_rejected']
    assert len(rejects) == (1 if not caller_owned and decline == 'tp1_unreachable' else 0)


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('cause', ['atr_invalid', 'stop_loss_calc_failed', 'trade_type_mismatch', 'insufficient_rr'])
@pytest.mark.parametrize('caller_owned', [False, True])
def test_planner_rejection_details_error_sites_preserve_event_ownership(monkeypatch, direction, cause, caller_owned):
    from backend.shared.config.defaults import ScanConfig
    context = _ctx()
    emitted = []
    monkeypatch.setattr(planner, 'get_telemetry_logger', lambda: type('Sink', (), {'log_event': lambda self, e: emitted.append(e)})())
    sign = 1 if direction == 'LONG' else -1
    entry = EntryZone(near_entry=100., far_entry=100.-.1*sign, rationale='fixture')
    stop = StopLoss(level=100.-sign, distance_atr=1., rationale='fixture')
    monkeypatch.setattr(planner, '_calculate_entry_zone', lambda **kwargs: (entry, True))
    def calculate_stop(**kwargs):
        if cause == 'stop_loss_calc_failed':
            raise ValueError('injected stop calculation failure')
        return stop, True
    monkeypatch.setattr(planner, '_calculate_stop_loss', calculate_stop)
    monkeypatch.setattr(planner, '_calculate_targets', lambda **kwargs: [Target(level=100.+3*sign, percentage=100., rationale='fixture')])
    monkeypatch.setattr(planner, '_derive_trade_type', lambda *a, **k: 'swing' if cause == 'trade_type_mismatch' else 'scalp')
    monkeypatch.setattr(planner, 'validate_rr', lambda *a, **k: (False, 'injected R:R decline'))
    config = ScanConfig()
    config.allowed_trade_types = ('scalp',)
    if cause == 'atr_invalid':
        context.multi_tf_indicators.by_timeframe['4H'].atr = 0.
    details = {}
    with pytest.raises(ValueError):
        planner.generate_trade_plan(
            symbol='ETH/USDT', direction=direction, setup_type='OB_FVG_BOS',
            smc_snapshot=context.smc_snapshot, indicators=context.multi_tf_indicators,
            confluence_breakdown=context.confluence_breakdown, config=config, current_price=100.,
            rejection_details=details if caller_owned else None)
    rejects = [event for event in emitted if event.event_type.value == 'signal_rejected']
    if caller_owned:
        assert details['reason_code'] == cause
        assert details['reason'] and details['diagnostics']
        assert not rejects
    else:
        assert len(rejects) == 1 and rejects[0].data['reason'] == cause
