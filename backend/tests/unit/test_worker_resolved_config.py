"""A process worker must execute the parent's resolved settings, not mode defaults."""
import copy
from datetime import datetime, timezone

import pytest

from backend.engine import orchestrator as module
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode


@pytest.mark.parametrize('mode_name', ['stealth', 'strike', 'surgical', 'overwatch'])
def test_worker_resolved_config_preserves_overrides(monkeypatch, mode_name):
    monkeypatch.setattr(module, '_WORKER_ORCHESTRATOR', None)
    monkeypatch.setattr(module, '_WORKER_CONFIG_ID', None)
    mode = get_mode(mode_name)
    parent = module.Orchestrator(ScanConfig(profile=mode.profile), exchange_adapter=object())
    # These are explicit caller-resolved settings, not proposed production defaults.
    parent.config.min_confluence_score = 81.
    parent.config.min_rr_ratio = 2.7
    parent.config.min_stop_atr = 1.1
    parent.config.max_stop_atr = 3.1
    parent.config.confluence_soft_floor = 73.
    expected = copy.deepcopy(vars(parent.config))
    def inspect(worker, *args, **kwargs):
        assert vars(worker.config) == expected
        assert worker.confluence_service._config is worker.config
        return 'inspected', None
    monkeypatch.setattr(module.Orchestrator, '_process_symbol', inspect)
    result = module._parallel_process_symbol_worker((
        'BTC/USDT', 'config-test', datetime.now(timezone.utc), None,
        parent.config, None, None, mode, .01, .001))
    assert result[:2] == ('inspected', None), result
    assert all(not rows for rows in result[2].values())
    assert vars(parent.config) == expected, 'worker startup mutated its input snapshot'


def test_worker_resolved_config_preserves_paper_balanced_preset(monkeypatch):
    monkeypatch.setattr(module, '_WORKER_ORCHESTRATOR', None)
    monkeypatch.setattr(module, '_WORKER_CONFIG_ID', None)
    from backend.bot.paper_trading_service import _SENSITIVITY_PRESETS
    mode = get_mode('stealth')
    parent = module.Orchestrator(ScanConfig(profile=mode.profile), exchange_adapter=object())
    parent.config.min_confluence_score = _SENSITIVITY_PRESETS['balanced']['gate']
    parent.config.confluence_soft_floor = _SENSITIVITY_PRESETS['balanced']['floor']
    expected = copy.deepcopy(vars(parent.config))
    def inspect(worker, *args, **kwargs):
        assert vars(worker.config) == expected
        return 'inspected', None
    monkeypatch.setattr(module.Orchestrator, '_process_symbol', inspect)
    result = module._parallel_process_symbol_worker((
        'BTC/USDT', 'config-test', datetime.now(timezone.utc), None,
        parent.config, None, None, mode, .01, .001))
    assert result[:2] == ('inspected', None), result
    assert all(not rows for rows in result[2].values())
    assert vars(parent.config) == expected


def test_worker_resolved_config_cached_override_refresh(monkeypatch):
    monkeypatch.setattr(module, '_WORKER_ORCHESTRATOR', None)
    monkeypatch.setattr(module, '_WORKER_CONFIG_ID', None)
    mode = get_mode('stealth')
    parent = module.Orchestrator(ScanConfig(profile=mode.profile), exchange_adapter=object())
    config = parent.config
    expected = copy.deepcopy(vars(config))
    def inspect(worker, *args, **kwargs):
        assert vars(worker.config) == expected
        assert worker.confluence_service._config is worker.config
        return 'inspected', None
    monkeypatch.setattr(module.Orchestrator, '_process_symbol', inspect)
    args = ('BTC/USDT', 'config-test', datetime.now(timezone.utc), None,
            config, None, None, mode, .01, .001)
    assert module._parallel_process_symbol_worker(args)[:2] == ('inspected', None)
    worker = module._WORKER_ORCHESTRATOR
    assert worker._worker_config_source is config
    config.min_rr_ratio = 2.8
    config.min_confluence_score = 82.
    expected = copy.deepcopy(vars(config))
    assert module._parallel_process_symbol_worker(args)[:2] == ('inspected', None)
    assert module._WORKER_ORCHESTRATOR is worker
    assert vars(config) == expected


def test_worker_resolved_config_mode_change_rebuilds(monkeypatch):
    monkeypatch.setattr(module, '_WORKER_ORCHESTRATOR', None)
    monkeypatch.setattr(module, '_WORKER_CONFIG_ID', None)
    parent = module.Orchestrator(ScanConfig(profile=get_mode('stealth').profile), exchange_adapter=object())
    config = parent.config
    monkeypatch.setattr(module.Orchestrator, '_process_symbol', lambda *a, **k: ('inspected', None))
    def run(mode):
        return module._parallel_process_symbol_worker((
            'BTC/USDT', 'config-test', datetime.now(timezone.utc), None,
            config, None, None, mode, .01, .001))
    assert run(get_mode('stealth'))[:2] == ('inspected', None)
    worker = module._WORKER_ORCHESTRATOR
    parent.apply_mode(get_mode('surgical'))
    config.min_rr_ratio = 2.4
    expected = copy.deepcopy(vars(config))
    assert run(get_mode('surgical'))[:2] == ('inspected', None)
    assert module._WORKER_ORCHESTRATOR is not worker
    assert vars(module._WORKER_ORCHESTRATOR.config) == expected
    assert module._WORKER_ORCHESTRATOR.smc_service._mode == 'surgical'
