"""Candle rows keep their supplied anchor and cannot close before open+duration."""
import pandas as pd
import pytest
from backend.data.ingestion_pipeline import IngestionPipeline


def candles(times):
    return pd.DataFrame(dict(timestamp=pd.to_datetime(times,utc=True),open=100.,high=101.,low=99.,close=100.5,volume=10.))


def test_monday_weekly_candles_survive_gap_normalization(monkeypatch):
    pipeline=IngestionPipeline(object(),use_cache=False)
    monkeypatch.setattr('backend.data.ingestion_pipeline.time.time',lambda:pd.Timestamp('2026-10-08T12:00:00Z').timestamp())
    frame=candles(['2026-09-21','2026-09-28','2026-10-05'])
    result=pipeline.normalize_and_validate(frame,'BTC/USDT','1w')
    assert list(result.timestamp)==list(frame.timestamp[:2])
    assert result.close.tolist()==[100.5,100.5]


@pytest.mark.parametrize('now',['2026-10-08T12:00:00Z','2026-10-11T23:59:59Z','2026-10-12T00:00:00Z'])
def test_weekly_close_uses_the_rows_open_instead_of_epoch_week(monkeypatch,now):
    pipeline=IngestionPipeline(object(),use_cache=False)
    monkeypatch.setattr(pipeline,'_fill_time_gaps',lambda frame,tf:frame)
    monkeypatch.setattr('backend.data.ingestion_pipeline.time.time',lambda:pd.Timestamp(now).timestamp())
    result=pipeline.normalize_and_validate(candles(['2026-09-28','2026-10-05']),'BTC/USDT','1w')
    expected=2 if now=='2026-10-12T00:00:00Z' else 1
    assert len(result)==expected


def test_all_unclosed_or_future_rows_are_excluded(monkeypatch):
    pipeline=IngestionPipeline(object(),use_cache=False)
    monkeypatch.setattr('backend.data.ingestion_pipeline.time.time',lambda:pd.Timestamp('2026-10-08T09:30:00Z').timestamp())
    result=pipeline.normalize_and_validate(candles(['2026-10-08T08:00:00Z','2026-10-08T09:00:00Z','2026-10-08T10:00:00Z']),'BTC/USDT','1h')
    assert list(result.timestamp)==[pd.Timestamp('2026-10-08T08:00:00Z')]


def test_duplicate_timestamps_are_resolved_before_reindex(monkeypatch):
    pipeline=IngestionPipeline(object(),use_cache=False)
    monkeypatch.setattr('backend.data.ingestion_pipeline.time.time',lambda:pd.Timestamp('2026-10-08T10:00:00Z').timestamp())
    result=pipeline.normalize_and_validate(candles(['2026-10-08T06:00:00Z','2026-10-08T07:00:00Z','2026-10-08T07:00:00Z','2026-10-08T08:00:00Z']),'BTC/USDT','1h')
    assert len(result)==3 and result.timestamp.is_unique


def test_off_grid_observations_are_rejected_instead_of_lost():
    pipeline=IngestionPipeline(object(),use_cache=False)
    with pytest.raises(ValueError,match='grid'):
        pipeline.normalize_and_validate(candles(['2026-10-08T06:00:00Z','2026-10-08T07:30:00Z','2026-10-08T08:00:00Z']),'BTC/USDT','1h')


def test_missing_week_is_filled_on_the_supplied_anchor(monkeypatch):
    pipeline=IngestionPipeline(object(),use_cache=False)
    monkeypatch.setattr('backend.data.ingestion_pipeline.time.time',lambda:pd.Timestamp('2026-10-20T00:00:00Z').timestamp())
    result=pipeline.normalize_and_validate(candles(['2026-09-28','2026-10-12']),'BTC/USDT','1w')
    assert list(result.timestamp)==list(pd.to_datetime(['2026-09-28','2026-10-05','2026-10-12'],utc=True))
    assert result.volume.tolist()==[10.,0.,10.]
    assert result.iloc[1].open==result.iloc[1].high==result.iloc[1].low==result.iloc[1].close==100.5


def test_sunday_feed_keeps_its_own_weekly_anchor(monkeypatch):
    pipeline=IngestionPipeline(object(),use_cache=False)
    monkeypatch.setattr('backend.data.ingestion_pipeline.time.time',lambda:pd.Timestamp('2026-10-18T00:00:00Z').timestamp())
    frame=candles(['2026-10-04','2026-10-11','2026-10-18'])
    original=frame.copy(deep=True)
    result=pipeline.normalize_and_validate(frame,'BTC/USDT','1w')
    assert list(result.timestamp)==list(frame.timestamp[:2])
    pd.testing.assert_frame_equal(frame,original)


def test_no_closed_candles_is_an_explicit_failure(monkeypatch):
    pipeline=IngestionPipeline(object(),use_cache=False)
    monkeypatch.setattr('backend.data.ingestion_pipeline.time.time',lambda:pd.Timestamp('2026-10-08T09:30:00Z').timestamp())
    with pytest.raises(ValueError,match='No valid data remaining'):
        pipeline.normalize_and_validate(candles(['2026-10-08T09:00:00Z','2026-10-08T10:00:00Z']),'BTC/USDT','1h')


def test_failed_close_time_validation_cannot_pass_a_partial_candle(monkeypatch):
    pipeline=IngestionPipeline(object(),use_cache=False)
    monkeypatch.setattr('backend.data.ingestion_pipeline.time.time',lambda:float('nan'))
    with pytest.raises(ValueError,match='Cannot establish candle closure'):
        pipeline.normalize_and_validate(candles(['2026-10-08T09:00:00Z']),'BTC/USDT','1h')
