"""Allocate raw observations to fixed, explainable evidence budgets.

Raw factors stay available to factor-specific consumers at weight zero. Only
family contributions enter the weighted score; adding a second name/alternative
cannot enlarge its family's budget. Correlated market data is not claimed to be
statistically independent.
"""
from dataclasses import replace
from typing import Optional

from backend.shared.config.score_policy import (
    FAMILY_BUDGETS, FAMILY_NAMES, SCORE_MODEL_VERSION, SCORE_POLICY_VERSION, scoring_mode,
)
from backend.shared.models.scoring import ConfluenceFactor


def upper_scale(value: float, attainable: float) -> float:
    """Keep neutral50 fixed for centered scores; scale point budgets from zero."""
    if attainable > 50 and value <= 50:
        return value
    if attainable > 50:
        return min(100., 50. + (value-50.) * 50. / (attainable-50.))
    return min(100., value * 100. / attainable)


def allocate_evidence(factors, profile, *, available, structural_quality,
                      ordered_sequence, context_direction_score: Optional[float],
                      required_data, macro_context_adjustment=0., proximity=None,
                      structural_detail: Optional[str] = None):
    """Return contribution factors and auditable eligibility/scale metadata."""
    raw = {f.name: f.score for f in factors}
    def value(name, ceiling=100.):
        if not available.get(name, name in raw):
            return 0.
        return upper_scale(raw.get(name, 0.), ceiling)
    def best(*candidates):
        return max(candidates, key=lambda item:item[1])

    anchor = best(('Order Block',value('Order Block')),
                  ('Fair Value Gap',value('Fair Value Gap',85.)))
    # One high-quality entry is enough. FVG's single ideal event supplies85 raw
    # points; its additional-gap bonus is not required to complete this slot.
    sequence_quality = 100. if ordered_sequence and structural_quality >= 50. else 0.
    confirmation = best(('Mode-scoped structural shift',structural_quality),
                        ('Confirmed sweep then shift',sequence_quality),
                        ('Multi-Candle Confirmation',value('Multi-Candle Confirmation')))
    context_before = ((context_direction_score or 0.) + value('Regime Alignment',83.3))/2.
    # Macro is contextual evidence, bounded inside its family rather than an
    # unbounded extra reward. Missing context cannot receive an overlay bonus.
    overlay = macro_context_adjustment if (macro_context_adjustment < 0. or (
        context_direction_score is not None and available.get('Regime Alignment',False))) else 0.
    context = max(0.,min(100.,context_before + overlay))
    momentum = best(*[(name,value(name)) for name in (
        'Momentum','Price-Indicator Divergence','MTF Indicator Alignment','Weekly StochRSI Bonus')])
    location = best(('OB Precision',value('OB Precision')),
                    ('FVG Precision',value('FVG Precision')),
                    ('Premium/Discount Zone',value('Premium/Discount Zone')),
                    ('Fibonacci Proximity',value('Fibonacci Proximity')),
                    ('Volume Profile',value('Volume Profile',80.)))
    # Keep proximity cautions in the location budget. Immediate opposing walls
    # also fail eligibility; another strong family cannot pay to enter a wall.
    proximity = proximity or {}
    location_ceiling = max(0.,100. + min(0.,proximity.get('score_adjustment',0.)))
    location = (location[0],min(location[1],location_ceiling))
    slots = (anchor,confirmation,('HTF direction and regime',context),momentum,location,
             ('Volume',value('Volume')),('Liquidity Draw',value('Liquidity Draw',40.)),
             ('Kill Zone Timing',value('Kill Zone Timing',35.)))
    mode = scoring_mode(profile)
    scored = [replace(f,weight=0.) for f in factors]
    ledger = []
    for family,budget,(source,quality) in zip(FAMILY_NAMES,FAMILY_BUDGETS[mode],slots):
        quality = max(0.,min(100.,quality))
        scored.append(ConfluenceFactor(family,quality,budget/100.,
            f'{source}: {quality:.1f}/100; fixed budget {budget:g} points'))
        ledger.append({'family':family,'budget':budget,'quality':quality,
                       'contribution':quality*budget/100.,'selected_evidence':source})
    missing = []
    if anchor[1] < 50.:
        missing.append('Qualified order block or fair value gap')
    # A strong candle or closes beyond an old level cannot invent a real shift.
    if structural_quality < 50.:
        reason = 'Confirmed direction-aligned structural shift on an allowed timeframe'
        missing.append(reason + (f' — {structural_detail}' if structural_detail else ''))
    if not required_data:
        missing.append('Required price, ATR and indicator data')
    distance = proximity.get('proximity_atr')
    wall_blocked = ('OPPOSING' in proximity.get('structure_type','')
                    and distance is not None and distance <= .5)
    if wall_blocked:
        missing.append('Entry blocked by immediate opposing structure: '+proximity.get('nearest_structure','unknown'))
    return scored, {
        'score_model_version':SCORE_MODEL_VERSION,'score_policy_version':SCORE_POLICY_VERSION,
        'score_calibration':'reference_policy_uncalibrated','scoring_mode':mode,
        'evidence_families':ledger,'evidence_eligible':not missing,'evidence_missing':missing,
        'raw_factor_scores':raw,'factor_availability':available,
        'structural_proximity':proximity,'location_quality_ceiling':location_ceiling,
        'context_macro_input':macro_context_adjustment,
        'context_macro_contribution':(context-context_before)*FAMILY_BUDGETS[mode][2]/100.,
        'quality_family_count':sum(row['budget']>0 and row['quality']>=50. for row in ledger),
    }
