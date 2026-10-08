"""Final paper/testnet order risk, using fixtures only and no service startup."""
import ast
import asyncio
import inspect
import textwrap
from decimal import Decimal
from types import SimpleNamespace as S
from unittest.mock import Mock

import ccxt
import pytest

from backend.bot.paper_trading_service import PaperTradingService, PaperTradingConfig


@pytest.fixture(params=['LONG', 'SHORT'])
def state(request):
    svc = PaperTradingService()
    svc.config = PaperTradingConfig(risk_per_trade=1., leverage=10, rr_floor_at_entry=0)
    svc.executor = S(_accounting=None, get_balance=lambda: 1000.)
    svc.position_manager = None
    svc._get_regime_size_multiplier = lambda: 1.2
    svc._log_activity = Mock()
    svc._log_signal = Mock()
    direction = request.param
    plan = S(symbol='FIXTURE/USDT:USDT', direction=direction,
             entry_zone=S(near_entry=100.), stop_loss=S(level=99. if direction == 'LONG' else 101.),
             lot_size=.03, targets=[], confidence_score=75., trade_type='intraday')
    return S(svc=svc, plan=plan)


def test_regime_cannot_raise_configured_or_reduced_risk(state):
    svc, p = state.svc, state.plan
    for streak, modifier, budget in [(0, 1., 10.), (-3, 1., 5.), (0, .5, 5.)]:
        svc.stats.current_streak = streak
        qty = svc._calculate_position_size(p, modifier)
        assert 0 < qty * abs(p.entry_zone.near_entry-p.stop_loss.level) <= budget


@pytest.mark.parametrize('case', ['no_snap', 'wider_snap', 'narrower_snap'])
def test_actual_order_block_respects_final_budget_and_lot(state, case):
    # Execute the production entry block through place_order, excluding selection
    # and downstream adoption. This verifies the final guard is wired to the order.
    svc, p = state.svc, state.plan
    sign = 1 if p.direction == 'LONG' else -1
    p.entry_zone.near_entry += {'no_snap': 0, 'wider_snap': -1., 'narrower_snap': 1.}[case]*sign
    p.stop_loss.level = p.entry_zone.near_entry - (2. if case == 'narrower_snap' else 1.)*sign
    qty = svc._calculate_position_size(p)
    node = ast.parse(textwrap.dedent(inspect.getsource(svc._process_signal))).body[0]
    block = next(n for n in node.body if isinstance(n, ast.Try) and any(
        isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == 'place_order'
        for c in ast.walk(n)))
    index = next(i for i, n in enumerate(block.body) if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id == 'order' for t in n.targets))
    node.body = ast.parse('position_size = initial_quantity').body + block.body[:index+1]
    svc.executor.place_order = Mock(return_value=S())
    ns = dict(svc._process_signal.__globals__, executor=svc.executor, current_price=100.,
              initial_quantity=qty, size_modifier=1.)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<actual-entry-block>', 'exec'), ns)
    asyncio.run(ns['_process_signal'](svc, p))
    order = svc.executor.place_order.call_args.kwargs
    risk = Decimal(str(order['quantity']))*abs(Decimal(str(order['price']))-Decimal(str(p.stop_loss.level)))
    assert 0 < risk <= Decimal('10')
    assert Decimal(str(order['quantity'])) % Decimal(str(p.lot_size)) == 0


@pytest.mark.parametrize('field', ['equity', 'entry', 'stop', 'risk', 'modifier', 'regime'])
@pytest.mark.parametrize('bad', [float('nan'), float('inf'), True, -1.])
def test_invalid_sizing_inputs_do_not_generate_quantity(state, field, bad):
    svc, p = state.svc, state.plan
    modifier = 1.
    if field == 'equity': svc.executor.get_balance = lambda: bad
    elif field == 'entry': p.entry_zone.near_entry = bad
    elif field == 'stop': p.stop_loss.level = bad
    elif field == 'risk': svc.config.risk_per_trade = bad
    elif field == 'modifier': modifier = bad
    else: svc._get_regime_size_multiplier = lambda: bad
    assert svc._calculate_position_size(p, modifier) == 0


def test_final_quantity_uses_both_rounded_and_planned_stop(state):
    svc, p = state.svc, state.plan
    exchange = ccxt.phemex()
    exchange.fetch = Mock(side_effect=AssertionError('Network forbidden'))
    exchange.markets = {p.symbol: dict(id='FIXTUREUSDT', symbol=p.symbol, spot=False,
        swap=True, contract=True, linear=True, inverse=False, contractSize=1.,
        precision={'price': .1, 'amount': .01})}
    svc.adapter = S(exchange=exchange)
    svc.executor._accounting = True
    svc.executor.accounting_status = lambda: dict(entry_eligible=True, equity=1000., free=1000.)
    sign = 1 if p.direction == 'LONG' else -1
    p.stop_loss.level = 100.-1.04*sign
    qty, entry, native = svc._prepare_entry_order(p, 100.+.06*sign, 100., 1.)
    distance = max(abs(Decimal(str(entry))-Decimal(str(native))),
                   abs(Decimal(str(entry))-Decimal(str(p.stop_loss.level))))
    assert Decimal(str(qty))*distance <= Decimal('10')
    assert str(entry) == ('100.1' if sign == 1 else '99.9')
    assert Decimal(str(qty)) == Decimal(exchange.amount_to_precision(p.symbol, qty))
    exchange.fetch.assert_not_called()


def test_invalid_final_geometry_rejects(state):
    p = state.plan
    with pytest.raises(ValueError, match='ENTRY_RISK_INVALID'):
        state.svc._prepare_entry_order(p, p.stop_loss.level, 10., 1.)
