"""Score-setting precedence, startup wiring and risk tightening regressions."""
import ast
import inspect
from types import SimpleNamespace as S

import pytest

from backend.bot import paper_trading_service as paper
from backend.bot import live_trading_service as live
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.sensitivity import resolve_sensitivity


@pytest.mark.parametrize('preset,gate,floor,expected', [
    ('balanced', None, None, (65.,55.)), ('aggressive', None, None, (60.,50.)),
    ('conservative', None, None, (75.,65.)), ('BALANCED', None, 60., (65.,60.)),
    ('balanced', 80., None, (80.,70.)), ('balanced', 80., 75., (80.,75.)),
    ('balanced', 0., None, (0.,0.)), ('custom', None, None, (65.,55.)),
    ('custom', 58., 48., (58.,48.)), ('aggressive', 58., None, (58.,48.)),
])
def test_sensitivity_resolution_and_actual_startup_blocks(preset, gate, floor, expected):
    config = paper.PaperTradingConfig(sensitivity_preset=preset, min_confluence=gate, confluence_soft_floor=floor)
    mode = get_mode('stealth')
    assert resolve_sensitivity(config, mode.min_confluence_score)[:2] == expected
    # Execute the production configuration block with the real Orchestrator.
    # Leave credentials, executors and background tasks outside this offline test.
    for module, cls in [(paper, paper.PaperTradingService), (live, live.LiveTradingService)]:
        tree = ast.parse(inspect.getsource(module))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == cls.__name__)
        method = next(n for n in method.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_start_session')
        blocks = [method.body] + [n.body for n in ast.walk(method) if isinstance(n, ast.Try)]
        block = next(body for body in blocks if any(isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Tuple) and any(isinstance(x, ast.Name) and x.id == '_min_conf'
            for x in n.targets[0].elts) for n in body))
        start = next(i for i,n in enumerate(block) if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Tuple)
                     and any(isinstance(x, ast.Name) and x.id == "_min_conf" for x in n.targets[0].elts))
        end = next(i for i,n in enumerate(block[start:], start) if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Attribute) and ast.unparse(n.targets[0]) == 'self.orchestrator.config.confluence_soft_floor')
        svc = S(mode=mode, adapter=object())
        ns = dict(module.__dict__, config=config, mode=mode, self=svc, adapter=svc.adapter,
                  planner_cfg=None, min_rr=1.)
        exec(compile(ast.fix_missing_locations(ast.Module(body=block[start:end+1], type_ignores=[])),
                     '<production-score-config>', 'exec'), ns)
        resolved = svc.orchestrator.config
        expected_gate, expected_floor = (max(mode.min_confluence_score, value) for value in expected)
        assert resolved.min_confluence_score == (expected_floor if module is paper else expected_gate)
        assert resolved.confluence_soft_floor == expected_floor
        assert svc.orchestrator.confluence_service._config is resolved


@pytest.mark.parametrize('gate,floor', [(float('nan'), None), (float('inf'), None), (True, None),
                                     (-1, None), (101, None), (70, float('nan')), (60, 65), (70, -1)])
def test_sensitivity_invalid_thresholds_rejected(gate, floor):
    with pytest.raises(ValueError):
        resolve_sensitivity(S(min_confluence=gate, confluence_soft_floor=floor, sensitivity_preset='custom'), 70.)


@pytest.mark.parametrize('dd', [5., 8., 12.])
@pytest.mark.parametrize('gate,floor,preset', [(80.,75.,'custom'), (60.,50.,'aggressive'), (75.,65.,'conservative')])
def test_sensitivity_drawdown_never_loosens_even_in_kill_zone(monkeypatch, dd, gate, floor, preset):
    service = paper.PaperTradingService()
    monkeypatch.setattr(service, '_get_current_drawdown_pct', lambda: dd)
    monkeypatch.setattr(paper, 'get_current_kill_zone', lambda now: 'fixture-zone')
    actual_gate, actual_floor, _ = service._get_effective_sensitivity_thresholds(gate, floor, preset)
    assert actual_gate >= gate and actual_floor >= floor
    if dd >= 8:
        assert actual_gate >= 75. and actual_floor >= 65.


def test_sensitivity_zero_floor_stays_zero_in_kill_zone(monkeypatch):
    service = paper.PaperTradingService()
    monkeypatch.setattr(service, '_get_current_drawdown_pct', lambda: 0.)
    monkeypatch.setattr(paper, 'get_current_kill_zone', lambda now: 'fixture-zone')
    assert service._get_effective_sensitivity_thresholds(0., 0., 'custom')[:2] == (0., 0.)
