"""Directional score regressions; execute through the guarded offline runner."""
from types import SimpleNamespace as S

import pandas as pd
import pytest

from backend.shared.config.scanner_modes import MACDModeConfig
from backend.strategy.confluence import scorer


def snapshot(**kwargs):
    values = dict(rsi=50., stoch_rsi=50., mfi=50., macd_line=0.,
                  macd_signal=0., macd_histogram=0.)
    values.update(kwargs)
    return S(**values)


@pytest.mark.parametrize("hist", [0., pd.Series([1., 1.])])
def test_scoring_neutral_macd_does_not_favor_short(hist):
    indicators = S(by_timeframe={tf: snapshot(macd_histogram=hist) for tf in ['4h', '1h', '15m']})
    assert scorer._score_mtf_indicator_confluence(indicators, 'bullish')[0] == 0
    assert scorer._score_mtf_indicator_confluence(indicators, 'bearish')[0] == 0


def test_scoring_equal_di_is_neutral():
    indicators = snapshot(adx=30., adx_plus_di=20., adx_minus_di=20.)
    assert scorer._score_momentum(indicators, 'bullish')[0] == 0
    assert scorer._score_momentum(indicators, 'bearish')[0] == 0


def test_scoring_strict_macd_strengthening_is_mirrored():
    config = MACDModeConfig(use_htf_bias=False, treat_as_primary=True,
                            weight=1., min_persistence_bars=2, use_histogram_strict=True)
    def score(sign, hist):
        return scorer.evaluate_macd_for_mode(snapshot(
            macd_line=4*sign, macd_signal=2*sign, macd_histogram=hist[-1],
            macd_line_series=[3*sign, 4*sign], macd_signal_series=[2*sign, 2*sign],
            macd_histogram_series=hist), 'bullish' if sign == 1 else 'bearish', config)['score']
    assert score(1, [1., 2.]) == score(-1, [-1., -2.]) == 43.
    assert score(1, [2., 1.]) == score(-1, [-2., -1.]) == 35.


def test_scoring_htf_zero_histogram_is_neutral():
    config = MACDModeConfig(use_htf_bias=True)
    for direction in ['bullish', 'bearish']:
        assert scorer.evaluate_macd_for_mode(snapshot(), direction, config, snapshot())['score'] == 0.


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('score', [float('nan'), float('inf'), -float('inf'), -1., 101.])
def test_scoring_invalid_regime_score_is_rejected(direction, score):
    with pytest.raises(ValueError, match='regime score'):
        scorer._score_regime_alignment(S(trend='strong_up', score=score, volatility='normal'), direction)


@pytest.mark.parametrize('alias,profile', [('strike', 'intraday_aggressive'), ('overwatch', 'macro_surveillance'),
                                        ('surgical', 'precision'), ('stealth', 'stealth_balanced')])
@pytest.mark.parametrize('volatility', ['compressed', 'normal', 'high'])
def test_scoring_regime_alias_keeps_canonical_baseline(alias, profile, volatility):
    regime = S(trend='sideways', score=50., volatility=volatility)
    actual = scorer._score_regime_alignment(regime, 'bullish', scanner_profile=alias)
    canonical = scorer._score_regime_alignment(regime, 'bullish', scanner_profile=profile)
    assert actual['factor_score'] == canonical['factor_score']
    assert actual['adjustment'] == canonical['adjustment']


@pytest.mark.parametrize('sign,direction', [(1, 'bullish'), (-1, 'bearish')])
@pytest.mark.parametrize('offsets,expected', [([-1, 1, 2], 70.), ([1, 2, -1], 0.), ([1, 2, 3], 100.)])
def test_scoring_confirmation_counts_latest_streak(sign, direction, offsets, expected):
    frame = pd.DataFrame({'close': [100+sign*x for x in offsets]})
    indicators = S(by_timeframe={'4h': S(dataframe=frame)}, has_timeframe=lambda tf: tf == '4h')
    smc = S(structural_breaks=[S(direction=direction, level=100., break_type='BOS')], liquidity_sweeps=[])
    assert scorer._score_multi_close_confirmation(indicators, smc, direction, 100+2*sign)[0] == expected


def breakdown(score, direction='bullish', aligned=True):
    from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
    names = ['Order Block', 'Market Structure', 'HTF Composite', 'Institutional Sequence', 'Liquidity Sweep']
    result = ConfluenceBreakdown(score, [ConfluenceFactor(n, 80., .2, 'fixture') for n in names],
        0., 0., 'trend', aligned, True, direction=direction, profile='stealth_balanced')
    scorer.refresh_score_classification(result, S(min_confluence_score=70.))
    return result


def family_breakdown(score, direction='bullish', *, eligible=True, htf_status='aligned'):
    """Scorer-output fixture for service boundaries, not a candle-derived score."""
    from dataclasses import replace
    from backend.shared.models.scoring import ConfluenceFactor
    from backend.shared.config.score_policy import FAMILY_NAMES, FAMILY_BUDGETS

    result = breakdown(score, direction, aligned=htf_status == 'aligned')
    result.factors = [replace(factor, weight=0.) for factor in result.factors]
    families = []
    for name, budget in zip(FAMILY_NAMES, FAMILY_BUDGETS['stealth']):
        result.factors.append(ConfluenceFactor(name, score, budget/100., 'controlled service input'))
        families.append({'family':name, 'budget':budget, 'quality':score})
    result.metadata.update(
        score_model_version='family-evidence-v2', score_policy_version='family-policy-v2',
        score_calibration='reference_policy_uncalibrated', evidence_families=families,
        evidence_eligible=eligible,
        evidence_missing=[] if eligible else ['Qualified order block or fair value gap'],
        htf_direction_status=htf_status,
    )
    scorer.refresh_score_classification(result, S(min_confluence_score=65.))
    return result


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_scoring_family_eligible_direction_beats_ineligible_higher_score(monkeypatch, direction):
    from backend.services.confluence_service import ConfluenceService
    side = 'bullish' if direction == 'LONG' else 'bearish'
    chosen = family_breakdown(70., side)
    invalid = family_breakdown(95., 'bearish' if direction == 'LONG' else 'bullish', eligible=False)
    service = ConfluenceService(config=S(min_confluence_score=65.))
    monkeypatch.setattr(service, '_score_direction',
        lambda **kw: chosen if kw['is_bullish'] == (direction == 'LONG') else invalid)
    context = S(symbol='FIXTURE/USDT', multi_tf_indicators=True,
                smc_snapshot=S(structural_breaks=[], liquidity_sweeps=[]), metadata={})

    assert service.score(context, 100.) is chosen
    assert context.metadata['chosen_direction'] == direction
    assert context.metadata['alt_confluence']['tie_break_used'] == 'evidence_eligibility'
    assert context.metadata['raw_directional_scores'][direction.lower()] == 70.
    assert invalid.total_score == 95. and invalid.metadata['evidence_eligible'] is False


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_scoring_family_ineligible_thesis_rejects_without_direction_flip(monkeypatch, direction):
    from backend.services.confluence_service import ConfluenceService, ConflictingDirectionsException
    chosen = family_breakdown(95., 'bullish' if direction == 'LONG' else 'bearish', eligible=False)
    other = family_breakdown(70., 'bearish' if direction == 'LONG' else 'bullish')
    service = ConfluenceService(config=S(min_confluence_score=65.))
    monkeypatch.setattr(service, '_score_direction',
        lambda **kw: chosen if kw['is_bullish'] == (direction == 'LONG') else other)
    context = S(symbol='FIXTURE/USDT', multi_tf_indicators=True,
                smc_snapshot=S(structural_breaks=[], liquidity_sweeps=[]), metadata={})

    with pytest.raises(ConflictingDirectionsException, match='Qualified order block or fair value gap') as caught:
        service.score(context, 100., selected_direction=direction)
    error = caught.value
    assert error.gate_name == 'evidence_requirements'
    assert error.selected_direction == context.metadata['chosen_direction'] == direction
    assert error.bullish_breakdown is (chosen if direction == 'LONG' else other)
    assert error.bearish_breakdown is (chosen if direction == 'SHORT' else other)
    assert chosen.total_score == 95. and other.total_score == 70.
    assert 'counter_htf_penalty' not in context.metadata


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('htf_status', ['neutral', 'unknown'])
def test_scoring_family_non_opposing_context_has_no_counter_htf_penalty(monkeypatch, direction, htf_status):
    from backend.services.confluence_service import ConfluenceService
    chosen = family_breakdown(80., 'bullish' if direction == 'LONG' else 'bearish', htf_status=htf_status)
    other = family_breakdown(40.)
    service = ConfluenceService(config=S(min_confluence_score=65.))
    monkeypatch.setattr(service, '_score_direction',
        lambda **kw: chosen if kw['is_bullish'] == (direction == 'LONG') else other)
    context = S(symbol='FIXTURE/USDT', multi_tf_indicators=True,
                smc_snapshot=S(structural_breaks=[], liquidity_sweeps=[], order_blocks=[]), metadata={})

    assert chosen.htf_aligned is False
    assert service.score(context, 100., selected_direction=direction) is chosen
    assert chosen.total_score == 80.
    assert chosen.metadata['htf_direction_status'] == htf_status
    assert chosen.metadata['admission_passed'] is True
    assert not any(key.startswith('counter_htf') for key in context.metadata)


@pytest.mark.parametrize('gate,ready', [(60., True), (75., True), (80., False)])
def test_scoring_family_quality_band_is_independent_of_custom_admission_gate(gate, ready):
    result = family_breakdown(75.)
    scorer.refresh_score_classification(result, S(min_confluence_score=gate))
    assert result.metadata['signal_tier'] == 'A'
    assert result.metadata['score_gate'] == gate
    assert result.metadata['score_gate_passed'] is ready
    assert result.metadata['admission_passed'] is ready
    assert (result.metadata['setup_state'] == 'READY') is ready


@pytest.mark.parametrize('score', [0., 95.])
def test_scoring_family_ineligible_evidence_cannot_be_ready_even_with_zero_gate(score):
    result = family_breakdown(score, eligible=False)
    scorer.refresh_score_classification(result, S(min_confluence_score=0.))
    assert result.metadata['score_gate_passed'] is True
    assert result.metadata['admission_passed'] is False
    assert result.metadata['setup_state'] != 'READY'


@pytest.mark.parametrize('score,expected', [(74.94, 'B'), (74.96, 'A'), (75., 'A')])
def test_scoring_planner_strong_band_uses_shared_boundary_without_dropping_geometry(score, expected):
    from backend.shared.config.rr_matrix import classify_conviction
    assert classify_conviction('SMC', 2.5, score, True) == expected
    assert classify_conviction('SMC', 2., score, True) == 'B'  # Below ideal RR.
    assert classify_conviction('SMC', 2.5, score, False) == 'B'  # Incomplete critical TFs.
    assert classify_conviction('ATR_FALLBACK', 2.5, score, True) == 'B'


@pytest.mark.parametrize('plan_type,rr,score,expected', [
    ('SMC', 1.5, 64.94, 'C'), ('SMC', 1.5, 64.96, 'B'), ('SMC', 1.5, 65., 'B'),
    ('ATR_FALLBACK', 1.5, 59.94, 'C'), ('ATR_FALLBACK', 1.5, 59.96, 'B'),
    ('ATR_FALLBACK', 1.5, 60., 'B'),
])
def test_scoring_planner_standard_and_watch_band_boundaries(plan_type, rr, score, expected):
    from backend.shared.config.rr_matrix import classify_conviction
    assert classify_conviction(plan_type, rr, score, True) == expected


@pytest.mark.parametrize('direction,trend', [('LONG', 'up'), ('SHORT', 'down')])
@pytest.mark.parametrize('raw,state', [(69., 'WATCHING'), (99., 'READY')])
def test_scoring_service_does_not_reaward_regime_alignment(monkeypatch, direction, trend, raw, state):
    from backend.services.confluence_service import ConfluenceService
    chosen = breakdown(raw, 'bullish' if direction == 'LONG' else 'bearish')
    other = breakdown(40.)
    ctx = S(symbol='FIXTURE/USDT', multi_tf_indicators=True,
            smc_snapshot=S(structural_breaks=[], liquidity_sweeps=[]),
            metadata={'global_regime': S(dimensions=S(trend=trend)), 'symbol_regime': S(trend=trend)})
    service = ConfluenceService(config=S(min_confluence_score=70.))
    monkeypatch.setattr(service, '_score_direction', lambda **kw: chosen if kw['is_bullish'] == (direction == 'LONG') else other)
    result = service.score(ctx, 100.)
    assert result is chosen and ctx.metadata['chosen_direction'] == direction
    assert result.total_score == raw
    assert result.metadata['setup_state'] == state
    assert 'htf_alignment_bonus' not in ctx.metadata
    assert not any(a['name'] == 'htf_alignment'
                   for a in result.metadata.get('score_components', {}).get('adjustments', []))
    assert ctx.metadata['raw_directional_scores'][direction.lower()] == raw


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('raw,other', [(40., 80.), (80., 80.)])
def test_scoring_thesis_keeps_own_breakdown_even_against_winner_or_tie(monkeypatch, direction, raw, other):
    from backend.services.confluence_service import ConfluenceService
    chosen = breakdown(raw, 'bullish' if direction == 'LONG' else 'bearish')
    alternate = breakdown(other)
    ctx = S(symbol='FIXTURE/USDT', multi_tf_indicators=True, smc_snapshot=S(structural_breaks=[]), metadata={})
    service = ConfluenceService(config=S(min_confluence_score=70.))
    monkeypatch.setattr(service, '_score_direction', lambda **kw: chosen if kw['is_bullish'] == (direction == 'LONG') else alternate)
    assert service.score(ctx, 100., selected_direction=direction) is chosen
    assert chosen.total_score == raw
    assert ctx.metadata['chosen_direction'] == direction
    assert ctx.metadata['alt_confluence']['tie_break_used'] == 'thesis_direction'


@pytest.mark.parametrize('direction,break_dir', [('LONG', 'bullish'), ('SHORT', 'bearish')])
def test_scoring_service_reclassifies_after_counter_htf_penalty(monkeypatch, direction, break_dir):
    from backend.services.confluence_service import ConfluenceService
    chosen = breakdown(75., break_dir, aligned=False)
    ctx = S(symbol='FIXTURE/USDT', multi_tf_indicators=True,
            smc_snapshot=S(structural_breaks=[S(direction=break_dir, break_type='CHoCH', timeframe='1h')], liquidity_sweeps=[], order_blocks=[]), metadata={})
    service = ConfluenceService(config=S(min_confluence_score=70.))
    monkeypatch.setattr(service, '_score_direction', lambda **kw: chosen if kw['is_bullish'] == (direction == 'LONG') else breakdown(40.))
    result = service.score(ctx, 100.)
    assert result.total_score == 65.
    assert result.metadata['setup_state'] != 'READY'
    assert result.metadata['signal_tier'] == 'C'
    assert result.metadata['score_components']['adjustments'][-1]['delta'] == -10.


def test_scoring_classification_respects_explicit_zero():
    result = breakdown(0.)
    scorer.refresh_score_classification(result, S(min_confluence_score=0.))
    assert result.metadata['setup_state'] == 'READY'
    assert result.metadata['score_gate'] == 0.


@pytest.mark.parametrize('score,ready', [(69.94, False), (69.96, True), (70., True)])
def test_scoring_classification_uses_existing_rounded_admission_boundary(score, ready):
    result = breakdown(score)
    assert result.metadata['score_gate_passed'] == ready
    assert (result.metadata['setup_state'] == 'READY') == ready
    assert (result.metadata['signal_tier'] == 'B') == ready


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_scoring_real_calculation_trace_and_raw_stoch_bonus(monkeypatch, direction):
    from datetime import datetime, timezone
    from backend.tests.unit.test_confluence_htf_proximity import make_indicators
    from backend.shared.models.smc import SMCSnapshot
    from backend.shared.config.defaults import ScanConfig
    monkeypatch.setattr(scorer, 'evaluate_weekly_stoch_rsi_bonus', lambda **kw: {'bonus': 15., 'reason': 'fixture'})
    result = scorer.calculate_confluence_score(SMCSnapshot([], [], [], []), make_indicators(), ScanConfig(), direction,
        current_price=100., as_of=datetime(2025, 1, 1, tzinfo=timezone.utc))
    trace = result.metadata['score_components']
    assert trace['weighted_base'] == result.base_score
    assert trace['weighted_base'] + sum(a['delta'] for a in trace['adjustments']) == pytest.approx(result.total_score)
    assert trace['final_score'] == result.total_score
    assert result.weekly_stoch_rsi_bonus == 15.
    with pytest.raises(ValueError, match='regime score'):
        scorer.calculate_confluence_score(SMCSnapshot([], [], [], []), make_indicators(), ScanConfig(), direction,
            current_price=100., regime=S(trend='strong_up', score=float('nan')))
