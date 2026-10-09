"""Evidence ownership regressions; run through diagnostics/offline_verify.py."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace as S

import pandas as pd
import pytest

from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.models.scoring import ConfluenceFactor
from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG, StructuralBreak, LiquiditySweep
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.score_policy import FAMILY_NAMES, SCORE_MODEL_VERSION
from backend.strategy.confluence import scorer
from backend.strategy.confluence.liquidity_map_scorer import score_liquidity_draw
from backend.tests.unit.test_live_entry_risk import state, plan as live_plan, run as live_run, assert_budget
from backend.tests.integration.test_paper_workflow import workflow
from backend.tests.integration.test_rejection_consumers import live_rejection_service


NOW = datetime(2025, 12, 3, 15, tzinfo=timezone.utc)


def volume(**overrides):
    values = dict(volume_spike=False, volume_ratio=1.)
    values.update(overrides)
    return S(**values)


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('ratio', [2.5, 3.5])
def test_evidence_volume_magnitude_has_one_budget(direction, ratio):
    # Both representations come from the same current / rolling20 volume ratio.
    assert scorer._score_volume(volume(volume_spike=True, volume_ratio=ratio), direction) == 75.


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_evidence_volume_persistence_not_paid_again(direction):
    ind = volume(volume_acceleration=.25, volume_accel_direction=direction,
                 volume_is_accelerating=True, volume_consecutive_increases=4)
    assert scorer._score_volume(ind, direction) == 60.
    opposite = 'bearish' if direction == 'bullish' else 'bullish'
    assert scorer._score_volume(ind, opposite) == 25.


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_evidence_swing_bias_does_not_create_a_structural_break(direction):
    smc = SMCSnapshot([], [], [], [])
    smc.swing_structure = {tf: {'trend': direction} for tf in ('1w', '1d', '4h')}
    assert scorer._score_htf_structure_bias(smc.swing_structure, direction)['bonus'] == 15.
    assert scorer._score_market_structure_incremental(smc, direction)['score'] == 0.


@pytest.mark.parametrize('direction,sign', [('bullish', 1), ('bearish', -1)])
def test_evidence_mtf_sign_is_not_histogram_slope(direction, sign):
    def score(history):
        ind = S(rsi=50., macd_line=sign, macd_signal=0., macd_histogram=sign,
                macd_histogram_series=history)
        return scorer._score_mtf_indicator_confluence(S(by_timeframe={tf: ind for tf in ('4h','1h','15m')}), direction)
    assert score(None)[0] == 15.
    assert score([sign, sign])[0] == 15.
    assert score([2*sign, sign])[0] == 15.
    assert score([0., sign])[0] == 23.
    assert 'slope' not in score(None)[1].lower()


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_evidence_liquidity_target_does_not_reuse_origin_sweep(direction):
    smc = SMCSnapshot([], [], [], [LiquiditySweep(100., 'low' if direction == 'bullish' else 'high', True, NOW, confirmation_level=2)])
    assert score_liquidity_draw(direction, 100., smc, 2.)['score'] == 0.


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_evidence_duplicate_divergence_reports_do_not_multiply(direction):
    def event(indicator, p1=10, p2=30, side=direction):
        return S(indicator=indicator, divergence_type='regular_'+side, strength=100.,
                 price_pivot_1=p1, price_pivot_2=p2)
    single = scorer._score_divergences_incremental({'rsi':[event('rsi')]}, direction)
    repeated = scorer._score_divergences_incremental({'rsi':[event('rsi'),event('rsi')], 'macd':[event('macd')]}, direction)
    assert repeated['score'] == single['score'] == 100.
    opposite = 'bearish' if direction == 'bullish' else 'bullish'
    mixed = scorer._score_divergences_incremental({'rsi':[event('rsi')], 'macd':[event('macd', side=opposite)]}, direction)
    assert mixed['score'] == single['score']
    distinct = scorer._score_divergences_incremental({'rsi':[event('rsi'),event('rsi', 35,55)]}, direction)
    assert distinct['distinct_price_events'] == 2
    assert distinct['score'] == 100.


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('delay,expected', [(0,False),(1,True)])
def test_evidence_override_requires_confirmed_temporal_sequence(direction, delay, expected):
    sweep = LiquiditySweep(99., 'low' if direction == 'bullish' else 'high', True,
                           NOW-timedelta(hours=2), confirmation_level=2, confirmed_at=NOW)
    shift = StructuralBreak('4h','BOS',100.,NOW+timedelta(minutes=delay),True,direction=direction)
    ob = OrderBlock('4h',direction,101.,99.,NOW,90.,0.,90.)
    smc = SMCSnapshot([ob], [], [shift], [sweep])
    factors = [ConfluenceFactor('Order Block',80.,1.,'fixture')]
    result = scorer.calculate_confluence_override(factors, smc, S(profile='stealth'), direction)
    assert (result['triggered_by'] == 'institutional_sequence') is expected


def evidence_case(mode, direction, strong):
    """Controlled source inputs for before/after score comparisons, not a backtest."""
    sign = 1 if direction == 'bullish' else -1
    config = ScanConfig(profile=get_mode(mode).profile)
    config.min_confluence_score = get_mode(mode).min_confluence_score
    config.primary_planning_timeframe = '4h'
    frame = pd.DataFrame({'open':[99.8,99.9,100.], 'close':[99.9,100.,100.1],
                          'high':[100.,100.1,100.2], 'low':[99.7,99.8,99.9], 'volume':[100.,200.,400.]})
    if sign < 0:
        frame[['open','close']] = 200-frame[['open','close']]
        high,low=frame.high.copy(),frame.low.copy()
        frame['high'],frame['low']=200-low,200-high
    snapshots = {}
    for tf in ('1d','4h','1h','15m','5m'):
        snap = IndicatorSnapshot(rsi=25. if sign>0 else 75., stoch_rsi=10. if sign>0 else 90.,
            bb_upper=102.,bb_middle=100.,bb_lower=98.,atr=2.,atr_percent=2.,volume_spike=strong,
            volume_ratio=2.5 if strong else 1.,mfi=20. if sign>0 else 80.,
            stoch_rsi_k=10. if sign>0 else 90.,stoch_rsi_d=5. if sign>0 else 95.,
            macd_line=2.*sign,macd_signal=sign,macd_histogram=sign,
            macd_histogram_series=[.5*sign,sign], macd_line_series=[2.*sign]*3,
            macd_signal_series=[sign]*3, adx=35.,adx_plus_di=30. if sign>0 else 10.,
            adx_minus_di=10. if sign>0 else 30.,ema_9=100.+sign,ema_21=100.,ema_50=100.-sign)
        snap.dataframe = frame
        snapshots[tf] = snap
    smc = SMCSnapshot([],[],[],[])
    if strong:
        smc.order_blocks=[OrderBlock('4h',direction,101.,99.,NOW-timedelta(hours=3),90.,0.,90.,grade='A')]
        smc.fvgs=[FVG('4h',direction,101.,99.,NOW-timedelta(hours=2),2.,0.,1.,grade='A',size_atr=1.2)]
        smc.structural_breaks=[StructuralBreak('4h','BOS',99.*sign+100.*(1-sign),NOW-timedelta(minutes=30),True,grade='A',direction=direction)]
        smc.liquidity_sweeps=[LiquiditySweep(98. if sign>0 else 102.,'low' if sign>0 else 'high',True,NOW-timedelta(hours=1),grade='A',timeframe='4h',confirmation_level=3)]
        smc.swing_structure={tf:{'trend':direction,'last_hh':104.,'last_ll':96.} for tf in ('1w','1d','4h')}
        smc.premium_discount={'4h':{'current_zone':'discount' if sign>0 else 'premium','zone_percentage':20 if sign>0 else 80}}
    return config, smc, IndicatorSet(snapshots)


@pytest.mark.parametrize('mode', ['overwatch','strike','surgical','stealth'])
@pytest.mark.parametrize('direction', ['bullish','bearish'])
@pytest.mark.parametrize('strong', [False,True])
def test_evidence_score_snapshot(mode, direction, strong, capsys):
    config, smc, indicators = evidence_case(mode,direction,strong)
    result = scorer.calculate_confluence_score(smc,indicators,config,direction,current_price=100.,
        regime=S(trend='up' if direction=='bullish' else 'down',score=80.,volatility='normal'),
        btc_impulse=direction,as_of=NOW)
    assert 0 <= result.total_score <= 100
    assert sum(f.weight for f in result.factors) == pytest.approx(1.)
    assert result.metadata['admission_passed'] is strong
    assert result.metadata['evidence_eligible'] is strong
    if strong:
        assert result.metadata['score_gate_passed'] is True
        assert result.metadata['evidence_missing'] == []
    else:
        assert result.metadata['evidence_missing']
    assert all(f.weight == 0. for f in result.factors if f.name not in FAMILY_NAMES)
    with capsys.disabled():
        print('EVIDENCE_SNAPSHOT '+json.dumps({'case':[mode,direction,strong], 'score':result.total_score,
            'gate':config.min_confluence_score,'tier':result.metadata['signal_tier'],
            'pass':result.metadata['score_gate_passed'],
            'factors':{f.name:[f.score,f.weight] for f in result.factors}}))


@pytest.mark.parametrize('veto', [False, True])
def test_evidence_macd_diagnostic_has_no_positive_score_budget(monkeypatch, veto):
    config, smc, indicators = evidence_case('stealth', 'bullish', True)
    monkeypatch.setattr(scorer, '_score_momentum', lambda *a, **kw:
                        (0., {'veto_active':veto, 'reasons':[], 'role':'fixture'}))
    result = scorer.calculate_confluence_score(smc, indicators, config, 'bullish',current_price=100.,as_of=NOW)
    factor = result.get_factor('MACD Veto')
    assert factor.score == (0. if veto else 100.)
    assert factor.weight == 0.
    assert result.metadata['veto_blocked'] is False  # Opposition is a risk deduction, not an admission veto.
    adjustments = result.metadata['score_components']['adjustments']
    assert next(a['delta'] for a in adjustments if a['name'] == 'macd_opposition') == (-10. if veto else 0.)
    assert result.total_score == pytest.approx(max(0., result.base_score-result.conflict_penalty-(10. if veto else 0.)))
    assert result.metadata['quality_factor_count'] == sum(f.score >= 50 and f.weight > 0 for f in result.factors)
    assert result.metadata['score_model_version'] == SCORE_MODEL_VERSION == 'family-evidence-v2'


def test_evidence_zero_weight_diagnostic_cannot_erase_conflicts():
    smc = SMCSnapshot([],[],[],[])
    factors = [ConfluenceFactor('Momentum',80.,.5,'fixture'), ConfluenceFactor('Volume',80.,.5,'fixture')]
    before = scorer.calculate_confluence_override(factors,smc,S(profile='stealth'),'bullish')
    after = scorer.calculate_confluence_override(factors+[ConfluenceFactor('MACD Veto',100.,0.,'diagnostic')],smc,S(profile='stealth'),'bullish')
    assert before == after
    assert after['reduction'] == 0.


@pytest.mark.parametrize('direction', ['LONG','SHORT'])
def test_evidence_cycle_views_share_positive_budget(direction):
    from backend.shared.models.smc import CyclePhase, CycleTranslation, CycleConfirmation
    cycle = S(phase=CyclePhase.ACCUMULATION if direction=='LONG' else CyclePhase.DISTRIBUTION,
              translation=CycleTranslation.RTR if direction=='LONG' else CycleTranslation.LTR,
              in_dcl_zone=True,in_wcl_zone=False,dcl_confirmation=CycleConfirmation.CONFIRMED,
              wcl_failed=False,dcl_failed=False)
    reversal = S(direction=direction,is_reversal_setup=True,choch_detected=True,
                 cycle_aligned=True,liquidity_swept=True,htf_bypass_active=False,conflict_detected=False)
    # Direct cycle=23 LONG /25 SHORT; reversal-cycle=27. One budget ->27,
    # then the existing diminishing-return function ->15.6 (not sum ->cap18).
    factors=[ConfluenceFactor('Market Structure',80.,1.,'fixture')]
    smc=SMCSnapshot([],[],[],[])
    assert scorer._calculate_synergy_bonus(factors,smc,cycle,reversal,direction,S(profile='overwatch')) == pytest.approx(15.6)
    opposite='SHORT' if direction=='LONG' else 'LONG'
    assert scorer._calculate_synergy_bonus(factors,smc,cycle,reversal,opposite,S(profile='overwatch')) == scorer._calculate_synergy_bonus(factors,smc,cycle,None,opposite,S(profile='overwatch'))


def test_evidence_empty_structure_name_does_not_confirm_cycle():
    from backend.shared.models.smc import CyclePhase, CycleTranslation, CycleConfirmation
    cycle=S(phase=CyclePhase.ACCUMULATION,translation=CycleTranslation.MTR,
            in_dcl_zone=False,in_wcl_zone=False,dcl_confirmation=CycleConfirmation.UNCONFIRMED,
            wcl_failed=False,dcl_failed=False)
    assert scorer._calculate_synergy_bonus([ConfluenceFactor('Market Structure',0.,1.,'absent')],
        SMCSnapshot([],[],[],[]),cycle,None,'LONG',S(profile='overwatch')) == 0.


@pytest.mark.parametrize('score,accepted', [(64.94,False),(64.96,True),(65.,True),(float('nan'),False),(float('inf'),False),(-1.,False),(101.,False)])
def test_evidence_actual_live_entry_gate_and_risk_budget(state, score, accepted):
    candidate=live_plan(state,score=score)
    orders=live_run(state,candidate)
    assert bool(orders) is accepted
    if accepted:
        assert_budget(state,candidate,orders[0])
    else:
        assert any(row[2].get('reason_type')=='confluence' for row in state.svc.signals)


@pytest.mark.parametrize('direction', ['bullish','bearish'])
@pytest.mark.parametrize('indicator,threshold', [('rsi',45.),('macd',70.)])
def test_evidence_divergence_confirmation_boundaries(direction, indicator, threshold):
    def score(strength):
        event=S(divergence_type='regular_'+direction,strength=strength,price_pivot_1=10,price_pivot_2=30)
        return scorer._score_divergences_incremental({indicator:[event]},direction)['score']
    assert score(threshold-.01) < 60.
    assert score(threshold) == pytest.approx(60.)
    assert score(threshold+.01) > 60.


@pytest.mark.parametrize('direction', ['bullish','bearish'])
@pytest.mark.parametrize('indicator', ['rsi','macd'])
@pytest.mark.parametrize('strong', [False,True])
def test_evidence_real_divergence_detector_to_counter_htf_service(monkeypatch,direction,indicator,strong):
    from backend.indicators import divergence
    from backend.services.confluence_service import ConfluenceService, ConflictingDirectionsException
    from backend.tests.unit.test_scoring_confidence_contract import breakdown
    # The actual pivot detector consumes controlled oscillator series. These
    # fixtures isolate detection/consumer units; raw oscillator math is exercised
    # separately in the raw-candle workflow.
    price=pd.Series([100.]*60)
    oscillator=pd.Series([50.]*60)
    price.iloc[20],price.iloc[40]=99.,98. if strong else 98.999
    oscillator.iloc[20],oscillator.iloc[40]=20.,30. if strong else 20.001
    if direction=='bearish':
        price,oscillator=200-price,100-oscillator
    frame=pd.DataFrame({'high':price+.1,'low':price-.1,'close':price})
    monkeypatch.setattr(divergence,'compute_rsi',lambda *a,**kw: oscillator)
    monkeypatch.setattr(divergence,'compute_macd',lambda *a,**kw: (oscillator,oscillator,oscillator))
    detected=divergence.detect_all_divergences(frame,direction)
    assert len(detected[indicator])==1
    result=scorer._score_divergences_incremental({indicator:detected[indicator]},direction)
    duplicate=scorer._score_divergences_incremental({indicator:detected[indicator]*2},direction)
    assert duplicate['score']==result['score']
    assert (result['score']>=60.) is strong
    chosen=breakdown(80.,direction,aligned=False)
    chosen.factors=[ConfluenceFactor('Price-Indicator Divergence',result['score'],1.,'detected pivot')]
    other=breakdown(20.)
    service=ConfluenceService(config=S(min_confluence_score=65.,profile='strike'))
    monkeypatch.setattr(service,'_score_direction',lambda **kw:chosen if kw['is_bullish']==(direction=='bullish') else other)
    ctx=S(symbol='FIXTURE',multi_tf_indicators=True,smc_snapshot=SMCSnapshot([],[],[],[]),metadata={})
    if strong:
        assert service.score(ctx,100.,selected_direction='LONG' if direction=='bullish' else 'SHORT') is chosen
        assert chosen.total_score==65.
        assert ctx.metadata['counter_htf_quality']=='soft'
    else:
        with pytest.raises(ConflictingDirectionsException,match='Counter-HTF blocked'):
            service.score(ctx,100.,selected_direction='LONG' if direction=='bullish' else 'SHORT')


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('anchor', ['ob', 'fvg'])
@pytest.mark.parametrize('scenario,expected_quality,expected_penalty', [
    ('same_time', 'partial', -10.),
    ('ordered', 'confirmed', -5.),
    ('disallowed_later_shift', 'partial', -10.),
    ('latest_unconfirmed_sweep', 'partial', -10.),
])
def test_evidence_counter_htf_service_uses_scoped_confirmed_sequence(
    monkeypatch, direction, anchor, scenario, expected_quality, expected_penalty,
):
    from backend.services.confluence_service import ConfluenceService
    from backend.tests.unit.test_scoring_confidence_contract import family_breakdown

    sweep_type = 'low' if direction == 'bullish' else 'high'
    sweeps = [LiquiditySweep(
        99. if direction == 'bullish' else 101., sweep_type, True,
        NOW-timedelta(hours=2), timeframe='4h', confirmation_level=2, confirmed_at=NOW,
    )]
    # Only the ordered case starts with a shift strictly after confirmation.
    shift_time = NOW+timedelta(minutes=1) if scenario == 'ordered' else NOW
    shifts = [StructuralBreak('4h', 'BOS', 100., shift_time, True, direction=direction)]
    if scenario == 'disallowed_later_shift':
        # An in-scope same-time shift cannot borrow ordering from a 1w event.
        shifts.append(StructuralBreak(
            '1w', 'BOS', 100., NOW+timedelta(minutes=1), True, direction=direction,
        ))
    elif scenario == 'latest_unconfirmed_sweep':
        # The older confirmed sweep cannot lend confirmation to the newer one.
        sweeps.append(LiquiditySweep(
            99. if direction == 'bullish' else 101., sweep_type, False,
            NOW+timedelta(minutes=1), timeframe='4h', confirmation_level=0,
        ))
        shifts[0] = StructuralBreak(
            '4h', 'BOS', 100., NOW+timedelta(minutes=2), True, direction=direction,
        )
    ob = OrderBlock('4h', direction, 101., 99., NOW-timedelta(hours=3), 90., 0., 90.)
    fvg = FVG('4h', direction, 101., 99., NOW-timedelta(hours=3), 2., 0., 1., grade='A', size_atr=1.2)
    smc = SMCSnapshot([ob] if anchor == 'ob' else [], [fvg] if anchor == 'fvg' else [], shifts, sweeps)
    chosen = family_breakdown(80., direction, htf_status='opposed')
    # Both entry routes expose their original factor quality, independent of
    # their zero diagnostic weight in the new family model.
    chosen.factors = [ConfluenceFactor('Order Block' if anchor == 'ob' else 'Fair Value Gap', 80., 0., 'fixture')]
    other = family_breakdown(20., 'bearish' if direction == 'bullish' else 'bullish')
    service = ConfluenceService(config=S(
        min_confluence_score=65., profile='strike',
        primary_planning_timeframe='4h', structure_timeframes=('4h',),
    ))
    monkeypatch.setattr(service, '_score_direction',
                        lambda **kw: chosen if kw['is_bullish'] == (direction == 'bullish') else other)
    context = S(symbol='FIXTURE', multi_tf_indicators=True, smc_snapshot=smc, metadata={})

    result = service.score(context, 100.,
                           selected_direction='LONG' if direction == 'bullish' else 'SHORT')

    assert result is chosen
    assert context.metadata['counter_htf_quality'] == expected_quality
    assert context.metadata['counter_htf_penalty'] == expected_penalty
    assert result.total_score == 80.+expected_penalty
    assert result.metadata['score_components']['adjustments'][-1]['delta'] == expected_penalty


@pytest.mark.parametrize('version,calibration', [
    (None, None), ('evidence-dedup-v1', 'heuristic_uncalibrated'),
    ('family-evidence-v2', 'reference_policy_uncalibrated'),
])
def test_evidence_signal_jsonl_preserves_source_version(workflow,live_rejection_service,tmp_path,version,calibration):
    from backend.tests.unit.test_scoring_confidence_contract import breakdown
    candidate=workflow.plan()
    candidate.confluence_breakdown=breakdown(90.)
    if version:
        candidate.confluence_breakdown.metadata.update(score_model_version=version,score_calibration=calibration)
    for label,svc in [('paper',workflow.svc),('live',live_rejection_service)]:
        svc._session_log_dir=tmp_path/label
        svc._session_log_dir.mkdir()
        svc._log_signal(candidate,'filtered','fixture',reason_type='confluence')
        row=json.loads((svc._session_log_dir/'signals.jsonl').read_text().splitlines()[-1])
        assert row.get('score_model_version')==version
        if version:
            assert row['score_calibration']==calibration
        else:
            assert 'score_model_version' not in row


def test_evidence_raw_score_log_preserves_version(monkeypatch):
    rows=[]
    monkeypatch.setattr(scorer,'BREAKDOWN_LOG_FILE',S(info=rows.append))
    config,smc,indicators=evidence_case('strike','bullish',True)
    score=scorer.calculate_confluence_score(smc,indicators,config,'bullish',current_price=100.,as_of=NOW)
    row=json.loads(rows[0])
    assert row['score_model_version']==score.metadata['score_model_version']==SCORE_MODEL_VERSION=='family-evidence-v2'
    assert row['score_calibration']=='reference_policy_uncalibrated'
