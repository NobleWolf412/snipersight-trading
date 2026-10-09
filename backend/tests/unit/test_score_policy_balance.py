"""Reference setup shapes and evidence-policy invariants, not a profit backtest."""
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace as S

import pytest

from backend.tests.unit.test_evidence_accounting import evidence_case, NOW
from backend.shared.models.smc import LiquidityPool
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.score_policy import FAMILY_BUDGETS, FAMILY_NAMES, SCORE_MODEL_VERSION
from backend.shared.models.scoring import ConfluenceFactor
from backend.strategy.confluence.evidence_policy import allocate_evidence
from backend.strategy.confluence import scorer


CASES = ('ob_continuation', 'fvg_continuation', 'ob_reversal', 'fvg_reversal',
         'local_continuation', 'no_anchor', 'unconfirmed', 'weak')


def reference_setup(mode, direction, case):
    """Independent expectations: anchor OR alternative, real shift, context/flow.

    These controlled detector outputs exercise the actual scorer. They do not
    pretend that manually supplied indicator snapshots came from these candles.
    """
    config, smc, indicators = evidence_case(mode, direction, True)
    config.primary_planning_timeframe = get_mode(mode).primary_planning_timeframe
    config.structure_timeframes = get_mode(mode).structure_timeframes
    sign = 1 if direction == 'bullish' else -1
    for ind in indicators.by_timeframe.values():
        # Directional continuation momentum, not the oversold reversal mixture
        # used by the older deliberately saturated evidence fixture.
        ind.rsi = 58. if sign > 0 else 42.
        ind.stoch_rsi = 60. if sign > 0 else 40.
        ind.stoch_rsi_k = 65. if sign > 0 else 35.
        ind.stoch_rsi_d = 55. if sign > 0 else 45.
        ind.mfi = 58. if sign > 0 else 42.
        ind.obv_trend = direction
    if case.startswith('fvg'):
        smc.order_blocks = []
    else:
        smc.fvgs = []
    if 'reversal' not in case:
        smc.liquidity_sweeps = []
    else:
        smc.structural_breaks[0].break_type = 'CHoCH'
    if case == 'local_continuation':
        smc.structural_breaks[0].timeframe = '15m'
    if case == 'no_anchor':
        smc.order_blocks = []
        smc.fvgs = []
    if case == 'unconfirmed':
        smc.structural_breaks = []
    if case == 'weak':
        smc.structural_breaks = []
        smc.swing_structure = {}
        smc.premium_discount = {}
        for ob in smc.order_blocks:
            ob.grade = 'C'
            ob.freshness_score = 25.
            ob.displacement_strength = .1
        for ind in indicators.by_timeframe.values():
            ind.rsi = ind.stoch_rsi = ind.mfi = 50.
            ind.macd_line = ind.macd_signal = ind.macd_histogram = 0.
            ind.macd_histogram_series = [0.,0.]
            ind.adx = 10.
            ind.adx_plus_di = ind.adx_minus_di = 10.
            ind.volume_spike = False
            ind.volume_ratio = 1.
            ind.obv_trend = None
    smc.liquidity_pools = [LiquidityPool(106. if sign > 0 else 94.,
        'equal_highs' if sign > 0 else 'equal_lows', touches=3, timeframe='4h', grade='A')]
    regime = S(trend='up' if sign > 0 else 'down',score=80.,volatility='normal')
    if case == 'weak':
        regime = S(trend='sideways',score=0.,volatility='normal')
    return config, smc, indicators, regime


@pytest.mark.parametrize('mode', ['overwatch','strike','surgical','stealth'])
@pytest.mark.parametrize('direction', ['bullish','bearish'])
@pytest.mark.parametrize('case', CASES)
def test_score_policy_reference_setups(mode, direction, case, capsys):
    config, smc, indicators, regime = reference_setup(mode,direction,case)
    result = scorer.calculate_confluence_score(smc,indicators,config,direction,
        current_price=100.,regime=regime,btc_impulse=direction,as_of=NOW)
    assert 0 <= result.total_score <= 100
    eligible = case not in ('no_anchor','unconfirmed','weak') and (
        case != 'local_continuation' or '15m' in get_mode(mode).structure_timeframes)
    assert result.metadata['evidence_eligible'] is eligible
    assert result.metadata['admission_passed'] is eligible
    assert bool(result.metadata['evidence_missing']) is not eligible
    if eligible:
        assert result.total_score >= config.min_confluence_score
    if case == 'weak':
        assert result.total_score < config.min_confluence_score
    assert sum(row['budget'] for row in result.metadata['evidence_families']) == 100.
    assert sum(row['contribution'] for row in result.metadata['evidence_families']) == pytest.approx(result.base_score)
    assert all(f.weight == 0. for f in result.factors if f.name not in FAMILY_NAMES)
    with capsys.disabled():
        print('SCORE_POLICY_REFERENCE '+json.dumps({'mode':mode,'direction':direction,'case':case,
            'score':result.total_score,'gate':config.min_confluence_score,
            'passed':result.metadata['score_gate_passed'],
            'eligible':result.metadata['evidence_eligible'],'admitted':result.metadata['admission_passed'],
            'missing':result.metadata['evidence_missing'],'families':result.metadata['evidence_families'],
            'base':result.base_score,'synergy':result.synergy_bonus,'conflict':result.conflict_penalty,
            'factors':{f.name:[f.score,f.weight] for f in result.factors}}))


def score_setup(mode='stealth', direction='bullish', case='ob_continuation', mutate=None):
    config, smc, indicators, regime = reference_setup(mode,direction,case)
    if mutate:
        mutate(config,smc,indicators,regime)
    return scorer.calculate_confluence_score(smc,indicators,config,direction,
        current_price=100.,regime=regime,btc_impulse=direction,as_of=NOW)


@pytest.mark.parametrize('mode',FAMILY_BUDGETS)
@pytest.mark.parametrize('case',CASES)
def test_score_policy_mirrored_evidence_has_symmetric_score_and_admission(mode,case):
    long = score_setup(mode,'bullish',case)
    short = score_setup(mode,'bearish',case)
    assert long.total_score == pytest.approx(short.total_score)
    assert long.metadata['admission_passed'] == short.metadata['admission_passed']


@pytest.mark.parametrize('direction',['bullish','bearish'])
@pytest.mark.parametrize('invalid',['invalidated','breaker','consumed_ob','consumed_fvg','wrong_tf'])
def test_score_policy_unusable_anchor_cannot_qualify_even_with_zero_cutoff(direction,invalid):
    case = 'fvg_continuation' if invalid == 'consumed_fvg' else 'ob_continuation'
    def mutate(config,smc,*unused):
        config.min_confluence_score = 0.
        if invalid == 'consumed_fvg':
            smc.fvgs[0].overlap_with_price = scorer._FVG_FILL_THRESHOLD
            smc.fvgs.append(deepcopy(smc.fvgs[0]))
        elif invalid == 'consumed_ob':
            smc.order_blocks[0].mitigation_level = 1.
        elif invalid == 'wrong_tf':
            smc.order_blocks[0].timeframe = '1m'
        else:
            setattr(smc.order_blocks[0],invalid,True)
    result = score_setup(direction=direction,case=case,mutate=mutate)
    assert result.get_factor('Entry anchor').score == 0.
    assert result.metadata['score_gate_passed'] is True
    assert result.metadata['evidence_eligible'] is False
    assert result.metadata['admission_passed'] is False


@pytest.mark.parametrize('direction',['bullish','bearish'])
@pytest.mark.parametrize('kind',['ob','fvg'])
def test_score_policy_immediate_opposing_wall_blocks_admission(direction,kind):
    from backend.shared.models.smc import OrderBlock, FVG
    def mutate(config,smc,*unused):
        opposite = 'bearish' if direction == 'bullish' else 'bullish'
        if kind == 'ob':
            smc.order_blocks.append(OrderBlock('4h',opposite,101.,99.,NOW,90.,0.,90.,grade='A'))
        else:
            smc.fvgs.append(FVG('4h',opposite,101.,99.,NOW,2.,0.,1.,grade='A',size_atr=1.2))
    result = score_setup(direction=direction,mutate=mutate)
    assert result.metadata['evidence_eligible'] is False
    assert result.metadata['admission_passed'] is False
    assert any('opposing structure' in why for why in result.metadata['evidence_missing'])


@pytest.mark.parametrize('direction',['bullish','bearish'])
def test_score_policy_invalid_zone_does_not_hide_valid_alternative(direction):
    def mutate(config,smc,*unused):
        invalid = deepcopy(smc.order_blocks[0])
        invalid.invalidated = True
        invalid.freshness_score = 100.
        smc.order_blocks.insert(0,invalid)
    before = score_setup(direction=direction)
    after = score_setup(direction=direction,mutate=mutate)
    assert after.get_factor('Entry anchor').score == before.get_factor('Entry anchor').score
    assert after.metadata['admission_passed'] is True


def test_score_policy_default_flat_volume_is_unknown_without_measurements():
    def mutate(config,smc,indicators,regime):
        for ind in indicators.by_timeframe.values():
            ind.volume_ratio = ind.volume_acceleration = ind.obv = None
            ind.obv_trend = 'flat'
    result = score_setup(mutate=mutate)
    assert result.get_factor('Participation').score == 0.
    assert result.metadata['factor_availability']['Volume'] is False


def allocate(raw, *, available=None, macro=0., context=50., proximity=None):
    factors = [ConfluenceFactor(name,score,1.,'fixture') for name,score in raw.items()]
    return allocate_evidence(factors,'overwatch',available=available or {key:True for key in raw},
        structural_quality=100.,ordered_sequence=False,context_direction_score=context,
        required_data=True,macro_context_adjustment=macro,proximity=proximity)


def test_score_policy_removing_context_cannot_erase_known_negative_macro():
    raw = {'Regime Alignment':35.,'Order Block':100.}
    full = allocate(raw,macro=-20.)[1]
    missing = allocate(raw,available={'Regime Alignment':False},macro=-20.)[1]
    assert missing['evidence_families'][2]['quality'] <= full['evidence_families'][2]['quality']
    assert missing['context_macro_contribution'] < 0.


def test_score_policy_correlated_alternatives_cannot_enlarge_budget():
    raw = {'Order Block':100.,'Momentum':100.,'OB Precision':100.,'Regime Alignment':83.3}
    first = allocate(raw)[1]
    raw.update({'Fair Value Gap':95.,'Price-Indicator Divergence':100.,
                'MTF Indicator Alignment':100.,'Weekly StochRSI Bonus':100.,
                'Premium/Discount Zone':100.,'FVG Precision':100.,'Close Momentum':100.})
    extra = allocate(raw)[1]
    assert [r['contribution'] for r in first['evidence_families']] == [r['contribution'] for r in extra['evidence_families']]


def test_score_policy_positive_macro_is_bounded_and_requires_context():
    raw = {'Order Block':100.,'Regime Alignment':83.3}
    full = allocate(raw,macro=20.,context=100.)[1]
    unknown = allocate(raw,macro=20.,context=None)[1]
    assert full['evidence_families'][2]['quality'] == 100.
    assert full['context_macro_contribution'] == 0.
    assert unknown['context_macro_contribution'] == 0.


def test_score_policy_proximity_caution_caps_location_without_extra_budget():
    result = allocate({'Order Block':100.,'OB Precision':100.},proximity={
        'valid':False,'score_adjustment':-10.,'proximity_atr':1.,'structure_type':'OrderBlock_OPPOSING'})[1]
    assert result['evidence_families'][4]['quality'] == 90.
    assert result['evidence_eligible'] is True


def test_score_policy_cutoff_does_not_relabel_the_quality_band():
    strict = score_setup(mutate=lambda config,*unused:setattr(config,'min_confluence_score',95.))
    permissive = score_setup(mutate=lambda config,*unused:setattr(config,'min_confluence_score',0.))
    assert strict.total_score == permissive.total_score
    assert strict.metadata['signal_tier'] == permissive.metadata['signal_tier']
    assert strict.metadata['admission_passed'] is False
    assert permissive.metadata['admission_passed'] is True


@pytest.mark.parametrize('direction',['bullish','bearish'])
def test_score_policy_duplicate_oscillators_and_mfi_cannot_stack(direction):
    from backend.tests.unit.test_scoring_confidence_contract import snapshot
    low = direction == 'bullish'
    single = snapshot(rsi=20. if low else 80.,stoch_rsi=None,mfi=None)
    duplicate = snapshot(rsi=single.rsi,stoch_rsi=0. if low else 100.,
                         mfi=0. if low else 100.,stoch_rsi_k=10. if low else 90.,
                         stoch_rsi_d=5. if low else 95.)
    assert scorer._score_momentum(single,direction)[0] == scorer.MOMENTUM_CATEGORY_CAP
    assert scorer._score_momentum(duplicate,direction)[0] == scorer._score_momentum(single,direction)[0]
    neutral = snapshot(mfi=0. if low else 100.)
    assert scorer._score_momentum(neutral,direction)[0] == 0.


@pytest.mark.parametrize('direction',['bullish','bearish'])
def test_score_policy_partial_oscillator_agreement_is_not_additive(direction):
    from backend.tests.unit.test_scoring_confidence_contract import snapshot
    low = direction == 'bullish'
    rsi = 40. if low else 60.
    stoch = 35. if low else 65.
    a = scorer._score_momentum(snapshot(rsi=rsi,stoch_rsi=None),direction)[0]
    b = scorer._score_momentum(snapshot(rsi=None,stoch_rsi=stoch),direction)[0]
    combined = scorer._score_momentum(snapshot(rsi=rsi,stoch_rsi=stoch,mfi=0. if low else 100.),direction)[0]
    assert 0 < combined < scorer.MOMENTUM_CATEGORY_CAP
    assert combined == max(a,b)
    # The legacy MACD branch must actually contribute its selected alternative.
    macd = scorer._score_momentum(snapshot(rsi=rsi,stoch_rsi=stoch,
        macd_line=1. if low else -1.,macd_signal=0.),direction)[0]
    assert macd == max(combined,20.)


@pytest.mark.parametrize('direction',['bullish','bearish'])
@pytest.mark.parametrize('available',[True,False])
def test_score_policy_ob_fvg_precision_uses_same_observed_candle_evidence(direction,available):
    def mutate(config,smc,indicators,*unused):
        smc.swing_structure = {}
        smc.premium_discount = {}
        if not available:
            for ind in indicators.by_timeframe.values():
                ind.dataframe = None
    ob = score_setup(direction=direction,case='ob_continuation',mutate=mutate)
    gap = score_setup(direction=direction,case='fvg_continuation',mutate=mutate)
    assert ob.get_factor('Entry location').score == gap.get_factor('Entry location').score
    if not available:
        assert ob.get_factor('Entry location').score == 0.


@pytest.mark.parametrize('direction',['bullish','bearish'])
def test_score_policy_bad_premium_discount_cannot_mask_opposing_wall(direction,monkeypatch):
    from backend.shared.models.smc import OrderBlock
    config, smc, indicators, _ = reference_setup('stealth',direction,'ob_reversal')
    # Move all aligned levels away; wrong P/D previously returned before the wall.
    smc.swing_structure = {}
    smc.order_blocks[0].low,smc.order_blocks[0].high = 90.,92.
    smc.order_blocks.append(OrderBlock('4h','bearish' if direction == 'bullish' else 'bullish',
                                     101.,99.,NOW,90.,0.,90.,grade='A'))
    monkeypatch.setattr(scorer,'detect_premium_discount',lambda *args,**kwargs:S(
        equilibrium=95. if direction=='bullish' else 105.,
        current_zone='premium' if direction=='bullish' else 'discount'))
    result = scorer.evaluate_htf_structural_proximity(smc,indicators,100.,direction,config)
    assert result['valid'] is False
    assert 'OPPOSING' in result['structure_type']


@pytest.mark.parametrize('direction',['bullish','bearish'])
def test_score_policy_consumed_opposing_zone_cannot_block_entry(direction):
    from backend.shared.models.smc import OrderBlock
    def mutate(config,smc,*unused):
        smc.order_blocks.append(OrderBlock('4h','bearish' if direction=='bullish' else 'bullish',
                                          101.,99.,NOW,90.,1.,90.,grade='A'))
    result = score_setup(direction=direction,mutate=mutate)
    assert result.metadata['evidence_eligible'] is True


def test_score_policy_default_configuration_uses_standard_band():
    from backend.shared.config.defaults import ScanConfig
    from backend.shared.config.score_policy import STANDARD_SCORE, BOT_SCORE_PRESETS
    assert ScanConfig().min_confluence_score == STANDARD_SCORE == 65.
    assert ScanConfig().confluence_soft_floor == BOT_SCORE_PRESETS['balanced']['floor'] == 55.
    assert ScanConfig(min_confluence_score=70.).min_confluence_score == 70.


@pytest.mark.parametrize('score,tier',[(64.94,'C'),(64.96,'B'),(74.94,'B'),(74.96,'A'),(84.94,'A'),(84.96,'APEX')])
def test_score_policy_tiers_share_display_and_gate_precision(score,tier):
    result = score_setup()
    result.total_score = score
    config = reference_setup('stealth','bullish','ob_continuation')[0]
    scorer.refresh_score_classification(result,config)
    assert result.metadata['signal_tier'] == tier
    assert result.is_high_quality is (tier in ('A','APEX'))


@pytest.mark.parametrize('direction',['bullish','bearish'])
@pytest.mark.parametrize('kind',['ob','fvg','level','swing'])
def test_score_policy_crossed_wall_behind_entry_does_not_block(direction,kind):
    from backend.shared.models.smc import OrderBlock,FVG
    def mutate(config,smc,*unused):
        opposite = 'bearish' if direction=='bullish' else 'bullish'
        # Near enough to fail the old absolute-distance check, but behind price.
        price = 99.5 if direction=='bullish' else 100.5
        if kind=='ob':
            smc.order_blocks.append(OrderBlock('4h',opposite,price+.1,price-.1,NOW,90.,0.,90.,grade='A'))
        elif kind=='fvg':
            smc.fvgs.append(FVG('4h',opposite,price+.3,price-.3,NOW,.6,0.,1.,grade='A',size_atr=.3))
        elif kind=='level':
            smc.htf_levels=[S(price=price,timeframe='4h',level_type='resistance' if direction=='bullish' else 'support')]
        else:
            smc.swing_structure['4h']['last_hh' if direction=='bullish' else 'last_ll']=price
    assert score_setup(direction=direction,mutate=mutate).metadata['evidence_eligible'] is True


@pytest.mark.parametrize('highs,lows,expected',[
    ([110.,105.],[90.,95.],'ranging'),([105.,110.],[95.,90.],'ranging'),
    ([105.,110.],[90.,95.],'uptrend'),([110.,105.],[95.,90.],'downtrend')])
def test_score_policy_structure_seed_respects_both_sides_and_reflection(highs,lows,expected):
    import pandas as pd
    from backend.strategy.smc.bos_choch import _determine_initial_trend
    assert _determine_initial_trend(pd.Series(highs),pd.Series(lows)) == expected
    reflected = _determine_initial_trend(pd.Series([200.-p for p in lows]),pd.Series([200.-p for p in highs]))
    assert reflected == {'ranging':'ranging','uptrend':'downtrend','downtrend':'uptrend'}[expected]
