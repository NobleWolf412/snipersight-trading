from types import SimpleNamespace

import pandas as pd
import pytest

from backend.analysis.regime_detector import RegimeDetector
from backend.strategy.planner.regime_engine import get_atr_regime


def indicators(atr=3.,price=100.,series=None):
    snapshot=SimpleNamespace(atr=atr,bb_middle=None,atr_series=series,
                             dataframe=None if price is None else pd.DataFrame({'close':[price]}))
    return SimpleNamespace(by_timeframe={'1d':snapshot})


@pytest.mark.parametrize('bad', [None, SimpleNamespace(by_timeframe={}),
    indicators(atr=None), indicators(price=None), indicators(atr=-1),
    indicators(atr=float('nan')), indicators(atr=float('inf')), indicators(atr=True),
    indicators(price=float('nan')), indicators(price=float('inf')), indicators(price=0),
    indicators(price=True)])
def test_missing_or_invalid_volatility_evidence_cannot_create_a_regime(bad):
    with pytest.raises(ValueError,match='VOLATILITY_INPUT_UNAVAILABLE'):
        RegimeDetector()._detect_volatility(bad)


@pytest.mark.parametrize('scale',[.000001,1.,10000.])
def test_valid_percentage_classification_is_scale_invariant(scale):
    assert RegimeDetector()._detect_volatility(indicators(3.*scale,100.*scale))==('normal',75.)


def test_atr_series_is_evaluated_without_ambiguous_truthiness():
    series=pd.Series([4.]*5+[6.]*5)
    assert RegimeDetector()._detect_volatility(indicators(6.,100.,series))==('elevated',55.)


def test_planner_uses_explicit_price_when_snapshot_has_no_close():
    assert get_atr_regime(indicators(3.,None),current_price=100.)=='normal'


def test_planner_rejects_unknown_indicator_shape():
    with pytest.raises(ValueError,match='VOLATILITY_INPUT_UNAVAILABLE'):
        get_atr_regime(object(),current_price=100.)
