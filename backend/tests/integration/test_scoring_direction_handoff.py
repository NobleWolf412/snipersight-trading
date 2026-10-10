"""Real symbol pipeline/controller/service; input and planner ports are fixtures."""
from types import SimpleNamespace as S
from unittest.mock import Mock

import pytest

from backend.engine import orchestrator as module
from backend.engine.replay_engine import ReplayEngine
from backend.shared.config.scanner_modes import get_mode
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import SMCSnapshot, StructuralBreak
from backend.services.confluence_service import ConfluenceService
from backend.tests.unit.test_replay_analysis_inputs import AS_OF, candles, ob
from backend.tests.unit.test_confluence_htf_proximity import make_indicators
from backend.tests.unit.test_scoring_confidence_contract import breakdown
from backend.tests.integration.test_paper_workflow import workflow


@pytest.fixture
def handoff(monkeypatch):
    def build(direction='LONG', policy='thesis', flat=False, tie=False, score=75.):
        monkeypatch.setenv('SS_DECISION_POLICY', policy)
        engine = ReplayEngine(object())._build_orchestrator(get_mode('surgical'))
        engine._Orchestrator__replay_mode = False
        engine.config.macro_overlay_enabled = False
        engine._check_critical_timeframes = lambda data: []
        engine._check_cooldown = lambda *args: None
        engine.regime_detector = None
        engine.indicator_service = S(compute=lambda data: make_indicators(), diagnostics={})
        d = 'bullish' if direction == 'LONG' else 'bearish'
        breaks = [] if flat else [StructuralBreak('1h', 'CHoCH', 100., AS_OF, True, direction=d)]
        smc = SMCSnapshot([ob(d, AS_OF)], [], breaks, [])
        engine.smc_service = S(detect=Mock(return_value=smc), diagnostics={})
        chosen, other = breakdown(score, d), breakdown(score if tie else 80., 'bearish' if direction == 'LONG' else 'bullish')
        engine.confluence_service = ConfluenceService(config=engine.config, scanner_mode=engine.scanner_mode)
        score_direction = Mock(side_effect=lambda **kw: chosen if kw['is_bullish'] == (direction == 'LONG') else other)
        monkeypatch.setattr(engine.confluence_service, '_score_direction', score_direction)
        engine.telemetry = S(log_event=Mock())
        # The actual planner's input contract is observed; price geometry is covered
        # separately by the raw-candle workflow suite, not fabricated here.
        planner = Mock(return_value=None)
        monkeypatch.setattr(engine, '_generate_trade_plan', planner)
        gates = Mock(wraps=module.run_pre_scoring_gates)
        monkeypatch.setattr(module, 'run_pre_scoring_gates', gates)
        data = MultiTimeframeData('BTC/USDT', {'1h': candles()})
        return S(engine=engine, data=data, chosen=chosen, other=other, planner=planner, gates=gates,
                 score_direction=score_direction, run=lambda: engine._process_symbol('BTC/USDT', 'fixture', AS_OF, prefetched_data=data))
    return build


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('tie', [False, True])
def test_scoring_thesis_direction_survives_gates_score_and_planner_handoff(handoff, direction, tie):
    h = handoff(direction, tie=tie)
    h.run()
    assert h.gates.call_args.kwargs['direction'] == direction
    h.planner.assert_called_once()
    ctx = h.planner.call_args.args[0]
    assert ctx.metadata['decision'].legacy_str == ctx.metadata['chosen_direction'] == direction
    assert ctx.confluence_breakdown is h.chosen
    assert ctx.confluence_breakdown.total_score == 75.
    assert ctx.metadata['pre_dir_tie_break'] == 'thesis_direction'


def test_scoring_flat_is_owned_before_gates_or_legacy_ties(handoff):
    h = handoff(flat=True, tie=True)
    plan, rejection = h.run()
    assert plan is None and rejection['reason_type'] == 'no_thesis'
    assert rejection['direction'] == 'FLAT'
    assert not h.gates.called and not h.score_direction.called and not h.planner.called
    rejected = [call.args[0] for call in h.engine.telemetry.log_event.call_args_list
                if getattr(call.args[0], 'event_type', '') == 'signal_rejected']
    assert len(rejected) == 1


@pytest.mark.parametrize('direction,impulse', [('LONG', 'strong_up'), ('SHORT', 'strong_down')])
@pytest.mark.parametrize('count,confirmed,proceeds', [(4, False, False), (4, True, True), (6, True, False)])
def test_scoring_thesis_no_opposite_retry_preserves_same_direction_btc_allowance(handoff, monkeypatch, direction, impulse, count, confirmed, proceeds):
    h = handoff(direction)
    monkeypatch.setattr(h.engine, '_derive_btc_impulse', lambda *a: impulse if confirmed else 'neutral')
    h.gates.side_effect = None
    h.gates.return_value = S(passed=False, gate_name='conflict_density', reason='fixture opposition', metadata={'conflict_count': count})
    _, rejection = h.run()
    h.gates.assert_called_once()
    assert h.gates.call_args.kwargs['direction'] == direction
    assert h.planner.called == proceeds
    if not proceeds:
        assert rejection['reason_type'] == 'conflict_density'
        assert rejection['direction'] == direction


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_scoring_legacy_still_selects_score_winner(handoff, direction):
    h = handoff(direction, policy='legacy')
    # Either score winner must have its own anchor when its gates are checked.
    other = 'bearish' if direction == 'LONG' else 'bullish'
    h.engine.smc_service.detect.return_value.order_blocks.append(ob(other, AS_OF))
    h.run()
    h.planner.assert_called_once()
    ctx = h.planner.call_args.args[0]
    assert ctx.confluence_breakdown is h.other
    assert ctx.metadata['chosen_direction'] == ('SHORT' if direction == 'LONG' else 'LONG')


def conflict_handoff(handoff, monkeypatch, direction, opposition, count=4, score=75., tie='bull_majority'):
    """Real gates+service; hold the preliminary heuristic steady to test handoff."""
    from dataclasses import replace
    h = handoff(direction, policy='legacy', score=score)
    monkeypatch.setattr(h.engine, '_derive_pre_direction', lambda *a: (direction, tie))
    snap = h.engine.smc_service.detect.return_value
    other = 'bearish' if direction == 'LONG' else 'bullish'
    snap.order_blocks.append(ob(other, AS_OF))
    snap.structural_breaks = [StructuralBreak(tf, 'BOS', 100., AS_OF, True, direction=opposition)
                              for tf in ['4h', '1h', '15m']]
    # Distinct zones keep count6 reachable after history/zone deduplication.
    snap.order_blocks.extend(replace(ob(opposition, AS_OF), low=120.+20*i, high=130.+20*i)
                             for i in range(count - 4))
    return h


@pytest.mark.parametrize('direction,aligned', [('LONG', 'bullish'), ('SHORT', 'bearish')])
def test_conflict_density_changed_score_winner_is_revalidated(handoff, monkeypatch, direction, aligned):
    h = conflict_handoff(handoff, monkeypatch, direction, aligned)
    _, rejection = h.run()
    winner = 'SHORT' if direction == 'LONG' else 'LONG'
    assert not h.planner.called
    assert [c.kwargs['direction'] for c in h.gates.call_args_list] == [direction, winner]
    assert rejection['direction'] == winner and rejection['score'] == 80.
    assert rejection['reason_type'] == 'conflict_density'
    assert rejection['conflict_count'] == 4  # 3 states plus its opposing entry zone
    assert len(rejection['conflict_conditions']) == 4


@pytest.mark.parametrize('direction,opposed', [('LONG', 'bearish'), ('SHORT', 'bullish')])
@pytest.mark.parametrize('score,expected_calls,blocked', [(75., 2, False), (90., 3, True)])
def test_conflict_density_final_check_tracks_admitted_flip_without_retry_loop(
        handoff, monkeypatch, direction, opposed, score, expected_calls, blocked):
    h = conflict_handoff(handoff, monkeypatch, direction, opposed, score=score)
    _, rejection = h.run()
    assert h.gates.call_count == expected_calls
    assert h.planner.called == (not blocked)
    if blocked:
        assert rejection['direction'] == direction and rejection['reason_type'] == 'conflict_density'
    else:
        assert h.planner.call_args.args[0].metadata['chosen_direction'] != direction


@pytest.mark.parametrize('direction,opposed,impulse', [('SHORT', 'bearish', 'strong_up'), ('LONG', 'bullish', 'strong_down')])
@pytest.mark.parametrize('count,tie,proceeds', [(4, 'bull_majority', True), (6, 'bull_majority', False),
                                               (4, 'quality_override', False)])
def test_conflict_density_final_check_preserves_btc_boundary_and_quality_guard(
        handoff, monkeypatch, direction, opposed, impulse, count, tie, proceeds):
    h = conflict_handoff(handoff, monkeypatch, direction, opposed, count=count, tie=tie)
    monkeypatch.setattr(h.engine, '_derive_btc_impulse', lambda *a: impulse)
    _, rejection = h.run()
    assert h.gates.call_count == 2
    assert h.planner.called == proceeds
    if not proceeds:
        assert rejection['reason_type'] == 'conflict_density'
        assert rejection['conflict_count'] == count


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_conflict_density_final_direction_cannot_bypass_its_other_gates(handoff, direction):
    h = handoff(direction, policy='legacy')  # The score winner lacks an anchor.
    _, rejection = h.run()
    assert not h.planner.called
    assert rejection['reason_type'] == 'structural_anchor'
    assert rejection['direction'] != direction


@pytest.mark.parametrize('direction,opposed', [('LONG', 'bearish'), ('SHORT', 'bullish')])
def test_conflict_density_initial_rejection_records_known_direction_and_quality_guard(handoff, monkeypatch, direction, opposed):
    h = conflict_handoff(handoff, monkeypatch, direction, opposed, tie='quality_override')
    _, rejection = h.run()
    h.gates.assert_called_once()
    assert not h.score_direction.called and not h.planner.called
    assert rejection['direction'] == direction
    assert 'quality_override stands' in rejection['reason']


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_scoring_rejected_thesis_keeps_its_direction_score_and_gate(handoff, direction):
    h = handoff(direction, score=40.)
    h.chosen.htf_aligned = False
    # Thesis observes structure, but it is outside the HTF confirmation set.
    # Neither direction has the service's required counter-HTF evidence.
    h.engine.smc_service.detect.return_value.structural_breaks[0].timeframe = '1w'
    _, rejection = h.run()
    assert not h.planner.called
    assert rejection['direction'] == direction
    assert rejection['reason_type'] == 'low_confluence'
    assert rejection['score'] == 40.
    assert 'Counter-HTF blocked' in rejection['detail']
    events = [c.args[0] for c in h.engine.telemetry.log_event.call_args_list
              if getattr(c.args[0], 'event_type', '') == 'signal_rejected']
    assert len(events) == 1
    assert events[0].data['gate_name'] == 'counter_htf'
    assert events[0].data['score'] == 40.


@pytest.mark.parametrize('score,modifier', [(65., 1.), (64.96,1.),(64.94,None),(55., None), (54.96,None),(54.94,None),(54., None)])
def test_scoring_paper_entry_uses_resolved_balanced_thresholds(workflow, monkeypatch, score, modifier):
    import asyncio
    from backend.bot import paper_trading_service as paper
    svc = workflow.svc
    svc.mode = get_mode('stealth')
    monkeypatch.setenv('SS_DECISION_POLICY', 'legacy')
    monkeypatch.setattr(paper, 'get_current_kill_zone', lambda now: None)
    monkeypatch.setattr(svc, '_get_current_drawdown_pct', lambda: 0.)
    sizing = Mock(wraps=svc._calculate_position_size)
    monkeypatch.setattr(svc, '_calculate_position_size', sizing)
    plan = workflow.plan()
    plan.confidence_score = score
    asyncio.run(svc._process_signal(plan))
    assert sizing.called == (modifier is not None), svc.signal_log
    if modifier is not None:
        assert sizing.call_args_list[0].kwargs['size_modifier'] == modifier


def test_scoring_legacy_exception_without_breakdowns_preserves_rejection(handoff,monkeypatch):
    h=handoff(policy='legacy')
    h.score_direction.side_effect=ValueError('No directional edge')
    plan,rejection=h.run()
    assert plan is None and rejection['reason_type']=='low_confluence'
    assert 'No directional edge' in rejection['reason']
    assert rejection.get('score_model_version') is None
    assert rejection.get('score_calibration') is None
