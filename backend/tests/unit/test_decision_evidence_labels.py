"""Unavailable and uncalibrated evidence must be described honestly."""
import ast
import inspect
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from backend.engine import orchestrator as module


@pytest.mark.parametrize('primary', ['1h', '4h'])
def test_dormant_cycle_failure_is_inspectable_without_activating_strategy(primary):
    tree = ast.parse(inspect.getsource(module))
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.Try)
                and node.body and isinstance(node.body[0], ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'cycle_tf'
                        for target in node.body[0].targets))
    context = SimpleNamespace(metadata={}, multi_tf_data=SimpleNamespace(
        timeframes={'1h': pd.DataFrame({'close': [100.]})}))
    logger = Mock()
    ns = dict(module.__dict__, self=SimpleNamespace(config=SimpleNamespace(primary_planning_timeframe=primary)),
              context=context, symbol='BTC/USDT', cycle_context=None, current_price_val=100., logger=logger)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 'production-cycle-context', 'exec'), ns)
    assert ns['cycle_context'] is None
    assert context.metadata['cycle_context_status']['status'] == 'unavailable'
    assert context.metadata['cycle_context_status']['error_type'] in ('NameError', 'ValueError')
    assert 'CYCLE_CONTEXT_UNAVAILABLE' in logger.warning.call_args.args[0]


def test_early_confluence_failure_preserves_original_reason_and_profile():
    method = module.Orchestrator._process_symbol
    node = ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]
    index = next(i for i, n in enumerate(node.body) if isinstance(n, ast.Try) and n.finalbody
                 and any(isinstance(x, ast.Name) and x.id == '_fusion_active'
                         for x in ast.walk(n)))
    # Keep the preceding guard initialization when present, then run the actual
    # production try/except/finally through an early input failure.
    prefix = node.body[index-1:index]
    if not (prefix and isinstance(prefix[0], ast.Assign)):
        prefix = []
    node.body = prefix + [node.body[index]]
    node.args = ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[])
    svc = SimpleNamespace(config=SimpleNamespace(profile='precision'))
    context = SimpleNamespace(metadata={}, multi_tf_data=SimpleNamespace(
        get_current_price=Mock(side_effect=ValueError('fixture missing price'))))
    ns = dict(module.__dict__, self=svc, context=context, symbol='FIXTURE/USDT', trace_id='fixture')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<actual-confluence-failure>', 'exec'), ns)
    plan, rejection = ns['_process_symbol']()
    assert plan is None
    assert rejection['reason_type'] == 'errors'
    assert 'fixture missing price' in rejection['reason']
    assert svc.config.profile == 'precision'
