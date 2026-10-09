"""Provider data must close the advice workflow without stale/source substitution."""
import json
from dataclasses import asdict
from types import SimpleNamespace as S
from unittest.mock import Mock

import pytest

from backend.analysis import dominance_service as module


@pytest.fixture
def feed(tmp_path, monkeypatch):
    clock = S(now=100000.)
    monkeypatch.setattr(module.time, 'time', lambda: clock.now)
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock.now)
    payload = {'data': {'updated_at': clock.now-60, 'total_market_cap': {'usd': 1000000.},
                        'market_cap_percentage': {'btc': 59., 'usdt': 6., 'usdc': 3.}}}
    request = Mock(return_value=S(status_code=200, json=lambda: payload))
    monkeypatch.setattr(module.requests, 'get', request)
    service = module.DominanceService(cache_dir=tmp_path)
    return service, clock, payload, request


def test_dominance_workflow_fresh_source_cache_and_provenance(feed):
    service, clock, payload, request = feed
    first = service.get_dominance()
    assert first.timestamp == payload['data']['updated_at']
    assert module.dominance_values(first) == (59., 32., 9.)
    assert first.source == module.DOMINANCE_VERSION
    assert service.get_dominance() == first
    request.assert_called_once()
    assert service.get_dominance_context().history == []


@pytest.mark.parametrize('bad', ['missing', 'nan', 'negative', 'oversum', 'future', 'stale', 'zero_cap'])
def test_dominance_workflow_invalid_provider_never_becomes_advice(feed, bad):
    service, clock, payload, request = feed
    data = payload['data']
    if bad == 'missing': del data['market_cap_percentage']['usdc']
    if bad == 'nan': data['market_cap_percentage']['btc'] = float('nan')
    if bad == 'negative': data['market_cap_percentage']['usdt'] = -1
    if bad == 'oversum': data['market_cap_percentage']['btc'] = 99
    if bad == 'future': data['updated_at'] = clock.now + 1
    if bad == 'stale': data['updated_at'] = clock.now - module.CACHE_TTL_SECONDS
    if bad == 'zero_cap': data['total_market_cap']['usd'] = 0
    assert service.get_dominance() is None
    assert not service.cache_file.exists()


def test_dominance_workflow_outage_backoff_retries_without_stale_fallback(feed):
    service, clock, payload, request = feed
    first = service.get_dominance()
    clock.now += module.CACHE_TTL_SECONDS
    request.return_value.status_code = 429
    assert service.get_dominance() is None
    assert 'HTTP 429' in service.last_error
    assert service.get_dominance() is None
    assert request.call_count == 2
    clock.now += 61
    request.return_value.status_code = 200
    payload['data']['updated_at'] = clock.now-10
    assert service.get_dominance().timestamp > first.timestamp
    assert len(service.get_dominance_context().history) == 1


def test_dominance_workflow_legacy_and_wrong_source_not_reused_or_rewritten(feed):
    service, clock, payload, request = feed
    legacy = service.cache_dir / 'dominance_cache.json'
    legacy.write_text('{"timestamp":100000,"btc_dom":90}')
    original = legacy.read_bytes()
    first = service.get_dominance()
    wrong = {**asdict(first), 'source': 'different-denominator'}
    service.cache_file.write_text(json.dumps(wrong))
    request.return_value.status_code = 401
    assert service.get_dominance() is None
    assert legacy.read_bytes() == original


def test_dominance_workflow_feed_expiry_bounds_market_snapshot(reader):
    # Fixture belongs to the service test module; imported below for reuse.
    reader.dominance.side_effect = lambda: S(btc_dom=54., alt_dom=42.5, stable_dom=3.5,
        timestamp=module.time.time()-module.CACHE_TTL_SECONDS+20)
    result = reader.service._read_global()
    assert result['expires_at'] == result['dominance_expires_at']
    reader.dominance.assert_called_once()


from backend.tests.unit.test_market_regime_ownership import reader
