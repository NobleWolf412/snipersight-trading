"""Versioned evidence-scale policy. Design bands, not fitted win probabilities."""

SCORE_MODEL_VERSION = 'family-evidence-v2'
SCORE_POLICY_VERSION = 'family-policy-v2'
WATCH_SCORE = 60.0
STANDARD_SCORE = 65.0
STRONG_SCORE = 75.0
EXCEPTIONAL_SCORE = 85.0
DIRECTION_MARGIN = 5.0

MODE_SCORE_GATES = {'overwatch':75.0, 'strike':65.0, 'surgical':70.0, 'stealth':65.0}
BOT_SCORE_PRESETS = {
    'conservative': {'gate':75.0, 'floor':65.0},
    'balanced': {'gate':65.0, 'floor':55.0},
    'aggressive': {'gate':60.0, 'floor':50.0},
}
PROFILE_MODES = {'macro_surveillance':'overwatch', 'intraday_aggressive':'strike',
                 'precision':'surgical', 'stealth_balanced':'stealth', 'balanced':'stealth'}

FAMILY_NAMES = ('Entry anchor', 'Structural confirmation', 'Directional context',
                'Momentum evidence', 'Entry location', 'Participation', 'Destination', 'Session timing')
# Each number is an actual maximum contribution out of 100. Missing evidence
# keeps its budget; another family cannot inherit it. Related alternatives share
# one slot. These allocations express mode intent, not historical optimization.
FAMILY_BUDGETS = {
    'overwatch': (20.,15.,25.,10.,15.,10.,5.,0.),
    'strike': (20.,15.,15.,20.,10.,10.,5.,5.),
    'surgical': (20.,15.,10.,15.,15.,10.,5.,10.),
    'stealth': (20.,15.,20.,15.,15.,10.,5.,0.),
}


def scoring_mode(profile: str) -> str:
    name = str(profile).lower()
    return PROFILE_MODES.get(name, name if name in FAMILY_BUDGETS else 'stealth')


def evidence_allows_entry(plan) -> bool:
    """Versioned plans must satisfy structural/data requirements even at gate0."""
    metadata = getattr(getattr(plan,'confluence_breakdown',None),'metadata',{}) or {}
    if metadata.get('score_model_version') == SCORE_MODEL_VERSION:
        return metadata.get('evidence_eligible') is True
    return metadata.get('evidence_eligible') is not False
