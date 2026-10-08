"""Only candles strictly after formation may consume or break a zone."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from backend.shared.models.smc import FVG, OrderBlock
from backend.shared.models.data import MultiTimeframeData
from backend.services.smc_service import SMCDetectionService
from backend.strategy.smc.mitigation_tracker import _calculate_ob_mitigation, _calculate_fvg_fill
from backend.strategy.smc.order_blocks import update_ob_lifecycle


def pattern(kind, direction, timestamp):
    if kind == 'ob':
        return OrderBlock('1h', direction, 101., 99., timestamp, 80., 0., 100.)
    return FVG('1h', direction, 101., 99., timestamp, 2., 0.)


def candles(direction, tz=None):
    # The first two candles crossed the whole zone, but neither was AFTER formation.
    frame = pd.DataFrame({'open': [100., 100., 105.], 'high': [120., 120., 106.],
                          'low': [80., 80., 104.], 'close': [80., 120., 105.],
                          'volume': [10., 10., 10.]},
                         index=pd.date_range('2001-02-03', periods=3, freq='h', tz=tz))
    if direction == 'bearish':
        frame.loc[:, ['open', 'high', 'low', 'close']] = [[100.,120.,80.,120.],
                                                        [100.,120.,80.,80.], [95.,96.,94.,95.]]
    frame['timestamp'] = frame.index
    return frame


@pytest.mark.parametrize('kind', ['ob', 'fvg'])
@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('frame_tz,formation', [
    (None, datetime(2001,2,3,1,tzinfo=timezone.utc)),
    ('UTC', datetime(2001,2,3,1)),
    ('UTC', pd.Timestamp('2001-02-02T20:00:00-05:00')),
    (None, datetime(2001,2,3,1)),
])
def test_only_later_candles_count(kind, direction, frame_tz, formation):
    zone = pattern(kind, direction, formation)
    frame = candles(direction, frame_tz)
    calculate = _calculate_ob_mitigation if kind == 'ob' else _calculate_fvg_fill
    assert calculate(zone, frame) == 0.
    # A genuine subsequent sweep must still consume the zone in either direction.
    frame.loc[frame.index[-1], ['low', 'high']] = [80., 120.]
    assert calculate(zone, frame) == 1.


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('frame_tz', [None, 'UTC'])
def test_lifecycle_uses_the_same_utc_boundary(direction, frame_tz):
    formation = datetime(2001,2,3,1,tzinfo=timezone.utc) if frame_tz is None else datetime(2001,2,3,1)
    zone = pattern('ob', direction, formation)
    result = update_ob_lifecycle(candles(direction, frame_tz), [zone])
    assert len(result) == 1 and not result[0].breaker and not result[0].invalidated


@pytest.mark.parametrize('kind', ['ob', 'fvg'])
@pytest.mark.parametrize('bad_time', [None, pd.NaT, 'not-a-time', 12345])
def test_invalid_formation_is_not_treated_as_whole_history(kind, bad_time):
    zone = pattern(kind, 'bullish', datetime(2001,2,3,1))
    zone.timestamp = bad_time
    calculate = _calculate_ob_mitigation if kind == 'ob' else _calculate_fvg_fill
    with pytest.raises(ValueError, match='SMC_FORMATION_TIME_INVALID'):
        calculate(zone, candles('bullish'))


@pytest.mark.parametrize('kind', ['ob', 'fvg'])
@pytest.mark.parametrize('bad_index', ['numeric', 'nat', 'unordered'])
def test_invalid_candle_clock_does_not_reuse_unverified_zone(kind, bad_index):
    frame = candles('bullish')
    if bad_index == 'numeric':
        frame.index = range(len(frame))
    elif bad_index == 'nat':
        frame.index = pd.DatetimeIndex([frame.index[0], pd.NaT, frame.index[2]])
    else:
        frame = frame.iloc[::-1]
    data = MultiTimeframeData('BTC/USDT', {'15m': frame})
    service = SMCDetectionService()
    zone = pattern(kind, 'bullish', datetime(2001,2,3,1))
    method = service._update_mitigation if kind == 'ob' else service._update_fvg_fill
    with pytest.raises(ValueError, match='SMC_FORMATION_TIME_INVALID'):
        method(data, [zone])
