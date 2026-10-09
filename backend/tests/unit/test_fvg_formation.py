"""Raw continuous candles must form an FVG; displacement is not mitigation."""
import pandas as pd
import pytest

from backend.strategy.smc.fvg import detect_fvgs


def formation(bearish=False, wick_only=False, retest=False):
    rows = [[100., 100.3, 99.7, 100., 1000.]] * 20
    # Each open equals the prior close. The middle candle displaces through
    # the first/third wick gap [100.5, 102.5].
    rows += [[100., 100.5, 99.8, 100.2, 1000.],
             [100.2, 103.2, 100., 103., 5000.],
             [103., 103.5, 102.5, 103.2, 2000.]]
    if wick_only:
        rows[-2] = [100.2, 103.2, 100., 100.3, 5000.]
        # A discontinuous third open is necessary to make a wick-only gap.
    if retest:
        rows.append([103.2, 103.3, 99.5, 100., 1500.])
    frame = pd.DataFrame(rows, columns=['open', 'high', 'low', 'close', 'volume'],
                         index=pd.date_range('2025-12-01', periods=len(rows), freq='1h', tz='UTC'))
    if bearish:
        frame[['open', 'close']] = 200-frame[['open', 'close']]
        high, low = frame.high.copy(), frame.low.copy()
        frame['high'], frame['low'] = 200-low, 200-high
    return frame


@pytest.mark.parametrize('bearish', [False, True])
@pytest.mark.parametrize('mode', ['stealth_balanced', 'intraday_aggressive', 'precision', 'macro_surveillance'])
def test_fvg_formation_continuous_displacement(bearish, mode):
    frame = formation(bearish)
    fvgs, raw = detect_fvgs(frame, mode_profile=mode, _return_raw_count=True)
    found = [f for f in fvgs if pd.Timestamp(f.timestamp) == frame.index[-1]]
    assert len(found) == 1
    assert raw >= 1
    fvg = found[0]
    assert fvg.direction == ('bearish' if bearish else 'bullish')
    assert fvg.size == 2.
    assert (fvg.bottom, fvg.top) == ((97.5, 99.5) if bearish else (100.5, 102.5))
    assert fvg.overlap_with_price == 0.
    assert fvg.size_atr > 1.


@pytest.mark.parametrize('bearish', [False, True])
def test_fvg_formation_wick_overlap_still_rejected(bearish):
    frame = formation(bearish, wick_only=True)
    fvgs = detect_fvgs(frame, mode_profile='stealth_balanced')
    assert not [f for f in fvgs if pd.Timestamp(f.timestamp) == frame.index[-1]]


@pytest.mark.parametrize('bearish', [False, True])
def test_fvg_formation_later_retest_is_mitigation(bearish):
    frame = formation(bearish, retest=True)
    fvgs = detect_fvgs(frame, mode_profile='stealth_balanced')
    found = [f for f in fvgs if pd.Timestamp(f.timestamp) == frame.index[-2]]
    assert len(found) == 1
    assert found[0].overlap_with_price == 1.


@pytest.mark.parametrize('bearish', [False, True])
@pytest.mark.parametrize('limit,accepted', [(.25, True), (.249, False)])
def test_fvg_formation_fractional_wick_limit(bearish, limit, accepted):
    frame = formation()
    frame.iloc[-2, frame.columns.get_loc('open')] = 101.
    if bearish:
        frame[['open', 'close']] = 200-frame[['open', 'close']]
        high, low = frame.high.copy(), frame.low.copy()
        frame['high'], frame['low'] = 200-low, 200-high
    fvgs = detect_fvgs(frame, config={'max_overlap': limit}, mode_profile='stealth_balanced')
    found = [f for f in fvgs if pd.Timestamp(f.timestamp) == frame.index[-1]]
    assert bool(found) is accepted


@pytest.mark.parametrize('bearish', [False, True])
def test_fvg_formation_partial_retest(bearish):
    frame = formation(bearish, retest=True)
    if bearish:
        frame.iloc[-1] = [96.8, 98.5, 96.7, 98., 1500.]
    else:
        frame.iloc[-1] = [103.2, 103.3, 101.5, 102., 1500.]
    found = [f for f in detect_fvgs(frame, mode_profile='stealth_balanced')
             if pd.Timestamp(f.timestamp) == frame.index[-2]]
    assert len(found) == 1
    assert found[0].overlap_with_price == .5
