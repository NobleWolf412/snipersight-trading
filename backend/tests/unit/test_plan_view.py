from types import SimpleNamespace as S

import pytest

from backend.bot.plan_view import pending_plan_view


@pytest.mark.parametrize('direction,near,far,stop,targets', [
    ('LONG', 100., 98., 95., [104., 108.]),
    ('SHORT', 100., 102., 105., [96., 92.]),
])
def test_pending_plan_view_publishes_saved_levels_for_both_directions(direction, near, far, stop, targets):
    plan = S(direction=direction, entry_zone=S(near_entry=near, far_entry=far), stop_loss=S(level=stop),
             targets=[S(level=level) for level in targets], timeframe='1h', trade_type='intraday',
             confidence_score=81.5, rationale='OB retest', metadata={'strategy': {'mode': 'strike', 'strategy_gate': 65}})
    view = pending_plan_view(plan)
    assert view == {'entry_near': near, 'entry_far': far, 'stop_loss': stop, 'targets': targets,
                    'timeframe': '1h', 'trade_type': 'intraday', 'confluence': 81.5, 'rationale': 'OB retest',
                    'strategy': {'mode': 'strike', 'strategy_gate': 65}}
    view['strategy']['mode'] = 'mutated'
    assert plan.metadata['strategy']['mode'] == 'strike'


def test_pending_plan_view_keeps_missing_or_invalid_prices_unknown():
    plan = S(entry_zone=S(near_entry=0, far_entry=float('nan')), stop_loss=None,
             targets=[S(level=0), S(level=None), S(level=3.5)], confidence_score=float('inf'))
    view = pending_plan_view(plan)
    assert view['entry_near'] is None and view['entry_far'] is None and view['stop_loss'] is None
    assert view['targets'] == [3.5] and view['confluence'] is None and view['strategy'] == {}
    assert pending_plan_view(S(symbol='A', direction='LONG'))['targets'] == []
